import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import { jobsApi } from "../api/jobs";
import type { PageDetail } from "../api/jobs";
import type { Job, Page, SKU, DashboardMetrics } from "../types/models";

interface PaginationMeta { page: number; size: number; total: number; total_pages: number; }

interface JobFilters {
  status?: string;
  merchant_id?: string;
  created_after?: string;
  created_before?: string;
  sort?: string;
  page?: number;
  size?: number;
}

interface JobState {
  jobs: Job[];
  total: number;
  filters: JobFilters;
  selectedIds: string[];
  pagination: PaginationMeta;
  currentJob: Job | null;
  pages: Page[];
  skus: SKU[];
  pageDetail: PageDetail | null;
  dashboard: DashboardMetrics | null;
  loading: boolean;
  error: string | null;

  // Filter & selection
  setFilter: (f: Partial<JobFilters>) => void;
  toggleSelect: (id: string) => void;
  selectAll: () => void;
  clearSelection: () => void;

  // Data fetching
  fetchJobs: (params?: { status?: string; page?: number }) => Promise<void>;
  fetchJob: (jobId: string) => Promise<void>;
  fetchPages: (jobId: string) => Promise<void>;
  fetchSkus: (jobId: string, pageNo?: number) => Promise<void>;
  fetchPageDetail: (jobId: string, pageNo: number) => Promise<void>;
  fetchDashboard: () => Promise<void>;
  createJob: (fileId: string, merchantId: string, category?: string) => Promise<Job>;
  cancelJob: (jobId: string) => Promise<void>;
  retryJob: (jobId: string) => Promise<void>;
  deleteJob: (jobId: string) => Promise<void>;

  // SSE callbacks
  updateJobFromSSE: (jobId: string, updates: Partial<Job>) => void;
  updatePageStatus: (pageNo: number, status: string) => void;
}

export const useJobStore = create<JobState>()(
  immer((set, _get) => ({
    jobs: [],
    total: 0,
    filters: {},
    selectedIds: [],
    pagination: { page: 1, size: 20, total: 0, total_pages: 0 },
    currentJob: null,
    pages: [],
    skus: [],
    pageDetail: null,
    dashboard: null,
    loading: false,
    error: null,

    setFilter: (f) => set((s) => { Object.assign(s.filters, f); }),

    toggleSelect: (id) => set((s) => {
      const idx = s.selectedIds.indexOf(id);
      if (idx >= 0) s.selectedIds.splice(idx, 1);
      else s.selectedIds.push(id);
    }),

    selectAll: () => set((s) => {
      s.selectedIds = s.jobs.map((j) => j.job_id);
    }),

    clearSelection: () => set((s) => { s.selectedIds = []; }),

    fetchJobs: async (params) => {
      set((s) => { s.loading = true; s.error = null; });
      try {
        const { items, total } = await jobsApi.list(params);
        set((s) => {
          s.jobs = items;
          s.total = total;
          s.loading = false;
          // [V1.1 C4] Only keep selectedIds in current list
          const currentIds = new Set(items.map((j: Job) => j.job_id));
          s.selectedIds = s.selectedIds.filter((id) => currentIds.has(id));
        });
      } catch (e: any) {
        set((s) => { s.error = e.message; s.loading = false; });
      }
    },

    fetchJob: async (jobId) => {
      set((s) => { s.loading = true; });
      try {
        const job = await jobsApi.get(jobId);
        set((s) => { s.currentJob = job; s.loading = false; });
      } catch (e: any) {
        set((s) => { s.error = e.message; s.loading = false; });
      }
    },

    fetchPages: async (jobId) => {
      const { items } = await jobsApi.getPages(jobId);
      set((s) => { s.pages = items; });
    },

    fetchSkus: async (jobId, pageNo) => {
      const { items } = await jobsApi.getSkus(jobId, pageNo);
      set((s) => { s.skus = items; });
    },

    fetchPageDetail: async (jobId, pageNo) => {
      try {
        const detail = await jobsApi.getPageDetail(jobId, pageNo);
        set((s) => { s.pageDetail = detail; });
      } catch (e: any) {
        set((s) => { s.pageDetail = null; s.error = e.message; });
      }
    },

    fetchDashboard: async () => {
      try {
        const data = await jobsApi.dashboard();
        set((s) => { s.dashboard = data; });
      } catch (e: any) {
        set((s) => { s.error = e.message; });
      }
    },

    createJob: async (fileId, merchantId, category) => {
      const job = await jobsApi.create(fileId, merchantId, category);
      set((s) => { s.jobs.unshift(job); s.total++; });
      return job;
    },

    cancelJob: async (jobId) => {
      await jobsApi.cancel(jobId);
      set((s) => {
        const job = s.jobs.find((j) => j.job_id === jobId);
        if (job) job.user_status = "failed" as any;
      });
    },

    retryJob: async (jobId) => {
      await jobsApi.retry(jobId);
      set((s) => {
        const job = s.jobs.find((j) => j.job_id === jobId);
        if (job) job.user_status = "processing" as any;
      });
    },

    deleteJob: async (jobId) => {
      await jobsApi.delete(jobId);
      set((s) => {
        s.jobs = s.jobs.filter((j) => j.job_id !== jobId);
        s.total = Math.max(0, s.total - 1);
        s.selectedIds = s.selectedIds.filter((id) => id !== jobId);
      });
    },

    updateJobFromSSE: (jobId, updates) => set((s) => {
      const job = s.jobs.find((j) => j.job_id === jobId);
      if (job) Object.assign(job, updates);
      if (s.currentJob?.job_id === jobId) Object.assign(s.currentJob, updates);
    }),

    updatePageStatus: (pageNo, status) => set((s) => {
      const page = s.pages.find((p) => p.page_number === pageNo);
      if (page) page.status = status as any;
    }),
  })),
);
