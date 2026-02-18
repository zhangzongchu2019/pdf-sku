import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import { jobsApi } from "../api/jobs";
import { useJobStore } from "./jobStore";
import { useNotificationStore } from "./notificationStore";
import type {
  SSEPageCompleted,
  SSEJobCompleted,
  SSEJobFailed,
  SSEHumanNeeded,
  SSESlaEscalated,
} from "../types/events";

const API_BASE = import.meta.env.VITE_API_BASE || "/api/v1";

type SSEStatus = "connected" | "reconnecting" | "disconnected" | "polling";

interface SSEState {
  status: SSEStatus;
  retryCount: number;
  lastHeartbeat: number | null;
  eventSource: EventSource | null;
  pollTimer: ReturnType<typeof setTimeout> | null;

  connect: (jobId: string) => void;
  disconnect: () => void;
  setStatus: (s: SSEStatus) => void;
  onEvent: (handler: (e: { event: string; data: any }) => void) => () => void;
}

const handlers = new Set<(e: { event: string; data: any }) => void>();
const MAX_RETRY = 3;

export const useSSEStore = create<SSEState>()(
  immer((set, get) => ({
    status: "disconnected" as SSEStatus,
    retryCount: 0,
    lastHeartbeat: null,
    eventSource: null,
    pollTimer: null,

    connect: (jobId: string) => {
      const prev = get().eventSource;
      if (prev) prev.close();
      const prevPoll = get().pollTimer;
      if (prevPoll) clearTimeout(prevPoll);

      const url = `${API_BASE}/jobs/${jobId}/events`;
      const es = new EventSource(url);

      es.onopen = () => {
        set((s) => {
          s.status = "connected";
          s.retryCount = 0;
        });
      };

      const dispatch = (event: string, data: any) => {
        handlers.forEach((h) => h({ event, data }));
      };

      // [V1.1 B1] 9 event types
      es.addEventListener("heartbeat", () => {
        set((s) => { s.lastHeartbeat = Date.now(); });
      });

      es.addEventListener("page_completed", (e: MessageEvent) => {
        try {
          const data: SSEPageCompleted = JSON.parse(e.data);
          useJobStore.getState().updatePageStatus(data.page_no, data.status ?? "AI_COMPLETED");
          dispatch("page_completed", data);
        } catch { /* ignore */ }
      });

      es.addEventListener("pages_batch_update", (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data);
          dispatch("pages_batch_update", data);
        } catch { /* ignore */ }
      });

      es.addEventListener("job_completed", (e: MessageEvent) => {
        try {
          const data: SSEJobCompleted = JSON.parse(e.data);
          useJobStore.getState().updateJobFromSSE(data.job_id, { status: data.status as any });
          useNotificationStore.getState().add({
            level: "info",
            message: `Job 处理完成，共 ${data.total_skus} 个 SKU`,
            jobId: data.job_id,
          });
          dispatch("job_completed", data);
        } catch { /* ignore */ }
      });

      es.addEventListener("job_failed", (e: MessageEvent) => {
        try {
          const data: SSEJobFailed = JSON.parse(e.data);
          useJobStore.getState().updateJobFromSSE(data.job_id, { status: "EVAL_FAILED" as any });
          useNotificationStore.getState().add({
            level: "urgent",
            message: `Job 处理失败：${data.error_message}`,
            jobId: data.job_id,
          });
          dispatch("job_failed", data);
        } catch { /* ignore */ }
      });

      es.addEventListener("human_needed", (e: MessageEvent) => {
        try {
          const data: SSEHumanNeeded = JSON.parse(e.data);
          useNotificationStore.getState().add({
            level: "warning",
            message: `${data.task_count} 个任务需要人工标注`,
            jobId: data.job_id,
          });
          dispatch("human_needed", data);
        } catch { /* ignore */ }
      });

      es.addEventListener("sla_escalated", (e: MessageEvent) => {
        try {
          const data: SSESlaEscalated = JSON.parse(e.data);
          if (data.sla_level === "CRITICAL") {
            useNotificationStore.getState().add({
              level: "urgent",
              message: "任务 SLA 已升级至紧急",
              taskId: data.task_id,
            });
          }
          dispatch("sla_escalated", data);
        } catch { /* ignore */ }
      });

      es.addEventListener("sla_auto_resolve", (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data);
          useNotificationStore.getState().add({
            level: "warning",
            message: "任务已进入 AI 质检处置流程",
          });
          dispatch("sla_auto_resolve", data);
        } catch { /* ignore */ }
      });

      es.addEventListener("sla_auto_accepted", (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data);
          useNotificationStore.getState().add({
            level: "info",
            message: "任务 SLA 超时，已自动接受 AI 结果",
          });
          dispatch("sla_auto_accepted", data);
        } catch { /* ignore */ }
      });

      // Reconnect / degrade to polling
      es.onerror = () => {
        set((s) => {
          s.status = "reconnecting";
          s.retryCount++;
        });
        if (get().retryCount > MAX_RETRY) {
          degradeToPoll(jobId, set, get);
        }
      };

      set((s) => {
        s.eventSource = es as any;
        s.status = "reconnecting";
      });
    },

    disconnect: () => {
      const es = get().eventSource;
      if (es) (es as any).close?.();
      const poll = get().pollTimer;
      if (poll) clearTimeout(poll);
      set((s) => {
        s.eventSource = null;
        s.pollTimer = null;
        s.status = "disconnected";
      });
    },

    setStatus: (status) => set((s) => { s.status = status; }),

    onEvent: (handler) => {
      handlers.add(handler);
      return () => { handlers.delete(handler); };
    },
  })),
);

/** [V1.1 F2] Degrade to polling with dynamic interval */
function degradeToPoll(
  jobId: string,
  set: any,
  get: () => SSEState,
) {
  const es = get().eventSource;
  if (es) (es as any).close?.();

  set((s: any) => {
    s.eventSource = null;
    s.status = "polling";
  });

  const poll = async () => {
    try {
      const job = await jobsApi.get(jobId);
      useJobStore.getState().updateJobFromSSE(job.job_id, job);

      const isProcessing = ["UPLOADED", "EVALUATING", "EVALUATED", "PROCESSING"].includes(
        job.status,
      );
      const interval = isProcessing ? 5000 : 30000;
      const timer = setTimeout(poll, interval);
      set((s: any) => { s.pollTimer = timer; });
    } catch {
      const timer = setTimeout(poll, 30000);
      set((s: any) => { s.pollTimer = timer; });
    }
  };
  poll();
}
