import api from "./client";
import type { Job, Page, SKU, DashboardMetrics } from "../types/models";

/** 后端分页响应格式适配 */
interface BackendPaginated<T> {
  data: T[];
  pagination: { page: number; page_size: number; total_count: number; total_pages: number };
}

function adaptPaginated<T>(resp: BackendPaginated<T>): { items: T[]; total: number } {
  return { items: resp.data, total: resp.pagination.total_count };
}

export const jobsApi = {
  list: async (params?: { status?: string; page?: number; size?: number; merchantId?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.merchantId) q.set("merchant_id", params.merchantId);
    q.set("page", String(params?.page ?? 1));
    q.set("page_size", String(params?.size ?? 20));
    const resp = await api.get<BackendPaginated<Job>>(`/jobs?${q}`);
    return adaptPaginated(resp);
  },

  get: (jobId: string) => api.get<Job>(`/jobs/${jobId}`),

  create: (fileId: string, merchantId: string, category?: string) =>
    api.post<Job>("/jobs", { file_id: fileId, merchant_id: merchantId, category }),

  cancel: (jobId: string) => api.post<void>(`/jobs/${jobId}/cancel`),
  retry: (jobId: string) => api.post<void>(`/jobs/${jobId}/requeue`),

  getPages: async (jobId: string) => {
    const resp = await api.get<BackendPaginated<Page>>(`/jobs/${jobId}/pages?page_size=200`);
    return adaptPaginated(resp);
  },

  getPage: (jobId: string, pageNo: number) =>
    api.get<Page>(`/jobs/${jobId}/pages/${pageNo}`),

  getSkus: async (jobId: string, pageNo?: number) => {
    const q = new URLSearchParams();
    q.set("page_size", "200");
    if (pageNo) q.set("page_number", String(pageNo));
    const resp = await api.get<BackendPaginated<SKU>>(`/jobs/${jobId}/skus?${q}`);
    return adaptPaginated(resp);
  },

  getImages: (jobId: string, pageNo: number) =>
    api.get<{ items: Array<{ image_id: string; bbox: number[]; url?: string }> }>(
      `/jobs/${jobId}/pages/${pageNo}/images`
    ),

  dashboard: () => api.get<DashboardMetrics>("/dashboard/metrics"),
};
