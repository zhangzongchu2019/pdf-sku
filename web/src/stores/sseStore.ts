import { create } from "zustand";
import type { SSEEvent } from "../types/models";

const API_BASE = import.meta.env.VITE_API_BASE || "/api/v1";

interface SSEState {
  connected: boolean;
  events: SSEEvent[];
  eventSource: EventSource | null;
  connect: (jobId?: string) => void;
  disconnect: () => void;
  onEvent: (handler: (e: SSEEvent) => void) => () => void;
}

const handlers = new Set<(e: SSEEvent) => void>();

export const useSSEStore = create<SSEState>((set, get) => ({
  connected: false,
  events: [],
  eventSource: null,

  connect: (jobId) => {
    const prev = get().eventSource;
    if (prev) prev.close();

    // Backend route: /api/v1/jobs/{jobId}/events
    const url = jobId
      ? `${API_BASE}/jobs/${jobId}/events`
      : `${API_BASE}/jobs/_global/events`;  // fallback

    const es = new EventSource(url);

    es.onopen = () => set({ connected: true });

    // Listen to named events from backend SSE
    const eventTypes = [
      "page.completed", "job.completed", "job.failed",
      "human.needed", "sla.escalated", "heartbeat",
    ];

    for (const evtType of eventTypes) {
      es.addEventListener(evtType, (msg: MessageEvent) => {
        try {
          const data = JSON.parse(msg.data);
          const event: SSEEvent = {
            event: evtType,
            data,
            timestamp: new Date().toISOString(),
          };
          set((s) => ({ events: [...s.events.slice(-99), event] }));
          handlers.forEach((h) => h(event));
        } catch { /* ignore */ }
      });
    }

    es.onerror = () => {
      set({ connected: false });
      setTimeout(() => {
        if (!get().connected) get().connect(jobId);
      }, 5000);
    };

    set({ eventSource: es, connected: false });
  },

  disconnect: () => {
    get().eventSource?.close();
    set({ eventSource: null, connected: false });
  },

  onEvent: (handler) => {
    handlers.add(handler);
    return () => handlers.delete(handler);
  },
}));
