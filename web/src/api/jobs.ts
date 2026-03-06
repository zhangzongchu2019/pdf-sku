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

  cancel: (jobId: string) => api.post<Job>(`/jobs/${jobId}/cancel`),
  retry: (jobId: string) => api.post<Job>(`/jobs/${jobId}/requeue`),
  reprocessAI: (jobId: string) =>
    api.post<{ job_id: string; queued: boolean; route: string }>(`/ops/jobs/${jobId}/reprocess-ai`),
  reprocessPage: (jobId: string, pageNo: number) =>
    api.post<{ page_number: number; status: string }>(`/ops/jobs/${jobId}/reprocess-page/${pageNo}`),
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

  updateSku: (jobId: string, skuId: string, data: { attributes?: Record<string, string | null>; validity?: string }) =>
    api.patch<{ sku_id: string; attributes: Record<string, string>; validity: string; status: string }>(
      `/jobs/${jobId}/skus/${skuId}`, data
    ),

  updateSkuBinding: (jobId: string, skuId: string, imageId: string) =>
    api.patch<{ sku_id: string; new_image_id: string; old_image_ids: string[] }>(
      `/jobs/${jobId}/skus/${skuId}/binding`, { image_id: imageId }
    ),

  addSkuBinding: (jobId: string, skuId: string, imageId: string) =>
    api.post<{ sku_id: string; image_id: string }>(`/jobs/${jobId}/skus/${skuId}/bindings`, { image_id: imageId }),

  removeSkuBinding: (jobId: string, skuId: string, imageId: string) =>
    api.delete<void>(`/jobs/${jobId}/skus/${skuId}/bindings/${imageId}`),

  deleteImage: (jobId: string, pageNo: number, imageId: string) =>
    api.delete<void>(`/jobs/${jobId}/pages/${pageNo}/images/${imageId}`),

  createSku: (jobId: string, pageNo: number, attributes?: Record<string, string>) =>
    api.post<{ sku_id: string; page_number: number; attributes: Record<string, string>; validity: string }>(
      `/jobs/${jobId}/pages/${pageNo}/skus`, { attributes: attributes ?? {} }
    ),

  deleteSku: (jobId: string, skuId: string) =>
    api.delete<void>(`/jobs/${jobId}/skus/${skuId}`),

  markReviewComplete: (jobId: string, pageNo: number, reviewTimeSec?: number) =>
    api.post<{ page_number: number; needs_review: boolean }>(
      `/jobs/${jobId}/pages/${pageNo}/review-complete`,
      { reviewer: "", review_time_sec: reviewTimeSec ?? null }
    ),

  ocrRegion: (jobId: string, pageNo: number, bbox: number[]) =>
    api.post<{ attributes: Record<string, string>; source_text: string }>(
      `/jobs/${jobId}/pages/${pageNo}/ocr-region`, { bbox }
    ),

  skuFromRegion: (jobId: string, pageNo: number, bbox: number[]) =>
    api.post<{ sku_id: string; page_number: number; attributes: Record<string, string>; source_text: string; validity: string }>(
      `/jobs/${jobId}/pages/${pageNo}/sku-from-region`, { bbox }
    ),

  /** 从页面截图裁剪商品子图 (添加新图片 或 调整已有图片) */
  cropImage: (
    jobId: string,
    pageNo: number,
    bbox: number[],
    options?: { image_id?: string; sku_id?: string },
  ) =>
    api.post<{ image_id: string; bbox: number[]; resolution: number[]; short_edge: number; mode: string }>(
      `/jobs/${jobId}/pages/${pageNo}/crop-image`,
      { bbox, ...options },
    ),

  startExportTask: async (jobId: string, includeRaw: boolean): Promise<string> => {
    const res = await api.post<{ task_id: string }>(
      `/jobs/${jobId}/export/excel/start${includeRaw ? "?include_raw=true" : ""}`
    );
    return res.task_id;
  },

  downloadExportTask: async (jobId: string, taskId: string, filename: string): Promise<void> => {
    const blob = await api.getBlob(`/jobs/${jobId}/export/excel/${taskId}/download`);
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(objectUrl);
  },

  dashboard: () => api.get<DashboardMetrics>("/dashboard/metrics"),
};
