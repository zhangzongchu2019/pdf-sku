import { create } from "zustand";
import { tasksApi } from "../api/tasks";
import type { HumanTask, SKU, Annotation } from "../types/models";

interface AnnotationState {
  currentTask: HumanTask | null;
  skus: SKU[];
  annotations: Partial<Annotation>[];
  selectedSkuId: string | null;
  loading: boolean;

  acquireTask: (annotatorId: string) => Promise<HumanTask | null>;
  setCurrentTask: (task: HumanTask | null) => void;
  setSkus: (skus: SKU[]) => void;
  addAnnotation: (annotation: Partial<Annotation>) => void;
  removeAnnotation: (index: number) => void;
  updateAnnotation: (index: number, data: Partial<Annotation>) => void;
  selectSku: (skuId: string | null) => void;
  submitTask: () => Promise<void>;
  skipTask: (reason: string) => Promise<void>;
  heartbeat: () => Promise<void>;
  reset: () => void;
}

let heartbeatTimer: ReturnType<typeof setInterval> | null = null;

export const useAnnotationStore = create<AnnotationState>((set, get) => ({
  currentTask: null, skus: [], annotations: [],
  selectedSkuId: null, loading: false,

  acquireTask: async (annotatorId) => {
    set({ loading: true });
    const task = await tasksApi.acquireNext(annotatorId);
    set({ currentTask: task, loading: false, annotations: [] });
    if (task && heartbeatTimer) clearInterval(heartbeatTimer);
    if (task) {
      heartbeatTimer = setInterval(() => get().heartbeat(), 25000);
    }
    return task;
  },

  setCurrentTask: (task) => set({ currentTask: task }),
  setSkus: (skus) => set({ skus }),

  addAnnotation: (ann) => set((s) => ({
    annotations: [...s.annotations, ann],
  })),

  removeAnnotation: (index) => set((s) => ({
    annotations: s.annotations.filter((_, i) => i !== index),
  })),

  updateAnnotation: (index, data) => set((s) => ({
    annotations: s.annotations.map((a, i) => i === index ? { ...a, ...data } : a),
  })),

  selectSku: (skuId) => set({ selectedSkuId: skuId }),

  submitTask: async () => {
    const { currentTask, annotations } = get();
    if (!currentTask) return;
    await tasksApi.complete(currentTask.task_id, annotations as any);
    if (heartbeatTimer) clearInterval(heartbeatTimer);
    set({ currentTask: null, annotations: [], skus: [], selectedSkuId: null });
  },

  skipTask: async (reason) => {
    const { currentTask } = get();
    if (!currentTask) return;
    await tasksApi.skip(currentTask.task_id, reason);
    if (heartbeatTimer) clearInterval(heartbeatTimer);
    set({ currentTask: null, annotations: [], skus: [], selectedSkuId: null });
  },

  heartbeat: async () => {
    const { currentTask } = get();
    if (currentTask) {
      try { await tasksApi.heartbeat(currentTask.task_id); } catch { /* ignore */ }
    }
  },

  reset: () => {
    if (heartbeatTimer) clearInterval(heartbeatTimer);
    set({ currentTask: null, skus: [], annotations: [], selectedSkuId: null });
  },
}));
