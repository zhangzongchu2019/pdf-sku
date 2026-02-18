import api from "./client";
import type {
  DashboardMetrics, AnnotatorSummary, AnnotatorDetail,
  MerchantStats, CustomAttrUpgrade,
} from "../types/models";

/** 运维 API (对齐 OpenAPI V2.0) */
export const opsApi = {
  /* Dashboard */
  getDashboard: () => api.get<DashboardMetrics>("/ops/dashboard"),

  /* 批量操作 */
  batchRetry: (jobIds: string[]) =>
    api.post<{ success_count: number; failed_items: { job_id: string; reason: string }[] }>(
      "/ops/jobs/batch-retry", { job_ids: jobIds }),

  batchCancel: (jobIds: string[]) =>
    api.post<{ success_count: number }>("/ops/jobs/batch-cancel", { job_ids: jobIds }),

  batchReassign: (taskIds: string[], targetAnnotatorId: string) =>
    api.post("/ops/tasks/batch-reassign", { task_ids: taskIds, target_annotator_id: targetAnnotatorId }),

  batchSkip: (taskIds: string[], reason?: string) =>
    api.post<{ success_count: number; failed_count: number }>(
      "/ops/tasks/batch-skip", { task_ids: taskIds, reason }),

  /* 标注员 */
  listAnnotators: () => api.get<{ data: AnnotatorSummary[] }>("/ops/annotators"),

  getAnnotatorStats: (annotatorId: string) =>
    api.get<AnnotatorDetail>(`/ops/annotators/${annotatorId}/stats`),

  getMyOutcomeStats: () =>
    api.get<{ today_completed: number; today_skus: number; today_accuracy: number }>(
      "/annotators/me/outcome-stats"),

  /* 商家 */
  getMerchantStats: (merchantId: string) =>
    api.get<MerchantStats>(`/merchants/${merchantId}/stats`),

  /* 自定义属性升级 */
  listCustomAttrUpgrades: (params?: { status?: string; merchant_id?: string; page?: number; size?: number }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.merchant_id) q.set("merchant_id", params.merchant_id);
    q.set("page", String(params?.page ?? 1));
    q.set("size", String(params?.size ?? 20));
    return api.get<{ data: CustomAttrUpgrade[]; pagination: { total: number } }>(
      `/ops/custom-attr-upgrades?${q}`);
  },

  reviewCustomAttrUpgrade: (body: { upgrade_id: string; action: "approve" | "reject"; comment?: string }) =>
    api.post("/ops/custom-attr-upgrades", body),

  /* SKU 对账 */
  reconcileSKU: (skuId: string) => api.post(`/skus/${skuId}/reconcile`),

  /* 审计日志 */
  getAuditLog: (params?: { page?: number; size?: number }) => {
    const q = new URLSearchParams();
    q.set("page", String(params?.page ?? 1));
    q.set("size", String(params?.size ?? 20));
    return api.get<{ data: import("../types/models").AuditLogEntry[]; pagination: { total: number } }>(
      `/ops/config/audit-log?${q}`);
  },

  rollbackConfig: (profileId: string) =>
    api.post(`/ops/config/rollback/${profileId}`),
};
