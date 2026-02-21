import api from "./client";
import type { Job, Page, SKU, DashboardMetrics } from "../types/models";

export interface SKUBindingImage {
  image_id: string;
  method: string;
  confidence: number;
  rank: number;
}

export interface PageDetailSKU {
  sku_id: string;
  page_number: number;
  attributes: Record<string, string>;
  status: string;
  validity: string;
  attribute_source: string;
  import_confirmation: string;
  source_bbox: number[] | null;
  images: SKUBindingImage[];
}

export interface PageDetailImage {
  image_id: string;
  role: string;
  bbox: number[] | null;
  extracted_path: string;
  resolution: number[] | null;
  short_edge: number;
  search_eligible: boolean;
}

export interface PageDetail {
  page: Page;
  skus: PageDetailSKU[];
  images: PageDetailImage[];
}

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

  create: (uploadId: string, merchantId: string, category?: string) =>
    api.post<Job>("/jobs", { upload_id: uploadId, merchant_id: merchantId, category }),

  cancel: (jobId: string) => api.post<void>(`/jobs/${jobId}/cancel`),
  retry: (jobId: string) => api.post<void>(`/jobs/${jobId}/requeue`),
  delete: (jobId: string) => api.delete<void>(`/ops/jobs/${jobId}`),

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

  getPageDetail: (jobId: string, pageNo: number) =>
    api.get<PageDetail>(`/jobs/${jobId}/pages/${pageNo}/detail`),

  getImageUrl: (jobId: string, imageId: string) => {
    const base = import.meta.env.VITE_API_BASE || "/api/v1";
    return `${base}/jobs/${jobId}/images/${imageId}`;
  },

  dashboard: () => api.get<DashboardMetrics>("/dashboard/metrics"),
};
