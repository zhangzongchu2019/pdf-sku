import { create } from "zustand";
import { jobsApi } from "../api/jobs";
import type { Job, Page, SKU, DashboardMetrics } from "../types/models";

interface JobState {
  jobs: Job[];
  total: number;
  currentJob: Job | null;
  pages: Page[];
  skus: SKU[];
  dashboard: DashboardMetrics | null;
  loading: boolean;
  error: string | null;

  fetchJobs: (params?: { status?: string; page?: number }) => Promise<void>;
  fetchJob: (jobId: string) => Promise<void>;
  fetchPages: (jobId: string) => Promise<void>;
  fetchSkus: (jobId: string, pageNo?: number) => Promise<void>;
  fetchDashboard: () => Promise<void>;
  createJob: (fileId: string, merchantId: string, category?: string) => Promise<Job>;
  cancelJob: (jobId: string) => Promise<void>;
  retryJob: (jobId: string) => Promise<void>;
  updateJobFromSSE: (jobId: string, updates: Partial<Job>) => void;
}

export const useJobStore = create<JobState>((set, get) => ({
  jobs: [], total: 0, currentJob: null, pages: [], skus: [],
  dashboard: null, loading: false, error: null,

  fetchJobs: async (params) => {
    set({ loading: true, error: null });
    try {
      const { items, total } = await jobsApi.list(params);
      set({ jobs: items, total, loading: false });
    } catch (e: any) {
      set({ error: e.message, loading: false });
    }
  },

  fetchJob: async (jobId) => {
    set({ loading: true });
    try {
      const job = await jobsApi.get(jobId);
      set({ currentJob: job, loading: false });
    } catch (e: any) {
      set({ error: e.message, loading: false });
    }
  },

  fetchPages: async (jobId) => {
    const { items } = await jobsApi.getPages(jobId);
    set({ pages: items });
  },

  fetchSkus: async (jobId, pageNo) => {
    const { items } = await jobsApi.getSkus(jobId, pageNo);
    set({ skus: items });
  },

  fetchDashboard: async () => {
    try {
      const data = await jobsApi.dashboard();
      set({ dashboard: data });
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  createJob: async (fileId, merchantId, category) => {
    const job = await jobsApi.create(fileId, merchantId, category);
    set((s) => ({ jobs: [job, ...s.jobs], total: s.total + 1 }));
    return job;
  },

  cancelJob: async (jobId) => {
    await jobsApi.cancel(jobId);
    set((s) => ({
      jobs: s.jobs.map((j) => j.job_id === jobId ? { ...j, user_status: "CANCELLED" as any } : j),
    }));
  },

  retryJob: async (jobId) => {
    await jobsApi.retry(jobId);
    set((s) => ({
      jobs: s.jobs.map((j) => j.job_id === jobId ? { ...j, user_status: "PROCESSING" as any } : j),
    }));
  },

  updateJobFromSSE: (jobId, updates) => {
    set((s) => ({
      jobs: s.jobs.map((j) => j.job_id === jobId ? { ...j, ...updates } : j),
      currentJob: s.currentJob?.job_id === jobId ? { ...s.currentJob, ...updates } : s.currentJob,
    }));
  },
}));
