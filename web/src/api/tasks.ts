import api from "./client";
import type { HumanTask, Annotation } from "../types/models";

/** 后端分页适配 */
interface TaskPaginated {
  data: HumanTask[];
  pagination: { page: number; size: number; total: number };
}

export const tasksApi = {
  list: async (params?: { status?: string; page?: number }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    q.set("page", String(params?.page ?? 1));
    const resp = await api.get<TaskPaginated>(`/tasks?${q}`);
    return { items: resp.data, total: resp.pagination.total };
  },

  acquireNext: async (annotatorId: string, _taskType?: string) => {
    const resp = await api.post<HumanTask | { data: null; message: string }>(
      "/tasks/next",
      { operator: annotatorId },
    );
    // Backend returns {data: null} when no tasks available
    if (resp && "data" in resp && resp.data === null) return null;
    return resp as HumanTask;
  },

  heartbeat: (taskId: string) =>
    api.post<void>(`/tasks/${taskId}/heartbeat`),

  complete: (taskId: string, annotations: Omit<Annotation, "annotation_id" | "annotated_at">[], operator?: string) =>
    api.post<void>(`/tasks/${taskId}/complete`, {
      operator: operator || "web_user",
      result: { annotations },
    }),

  skip: (taskId: string, reason: string) =>
    api.post<void>(`/tasks/${taskId}/revert`, {
      operator: "web_user",
      reason,
    }),

  revert: (taskId: string) =>
    api.post<void>(`/tasks/${taskId}/revert`, {
      operator: "web_user",
    }),

  /** 运维作废（单个或批量）。*/
  batchSkip: (taskIds: string[], reason: string, operator = "web_user") =>
    api.post(`/ops/tasks/batch-skip`, {
      task_ids: taskIds,
      reason,
      operator,
    }),

  /** 物理删除（单个或批量）。*/
  batchDelete: (taskIds: string[], operator = "web_user") =>
    api.post(`/ops/tasks/batch-delete`, {
      task_ids: taskIds,
      operator,
    }),
  delete: (taskId: string, operator = "web_user") =>
    api.delete(`/ops/tasks/${taskId}?operator=${encodeURIComponent(operator)}`),
};
