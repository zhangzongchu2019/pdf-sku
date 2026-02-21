import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import { tasksApi } from "../api/tasks";
import { annotationsApi } from "../api/annotations";
import { useUndoStore } from "./undoStore";
import type {
  AnnotationElement,
  AnnotationGroup,
  AmbiguousBinding,
  CrossPageSKU,
  TaskCompletePayload,
  AnnotationType,
  LayoutType,
  PrefetchData,
  TaskDetail,
} from "../types/models";
import { PageType } from "../types/enums";

/**
 * 标注页面状态 Store [V1.1 C1/C3]
 * 最复杂的 Store：元素-分组模型 + undo 原子性 + immer
 */
interface AnnotationState {
  // Current context
  currentTaskId: string | null;
  currentJobId: string | null;
  currentPageNo: number | null;

  // Elements & groups
  elements: AnnotationElement[];
  groups: AnnotationGroup[];
  selectedElementIds: string[];
  selectedGroupId: string | null;
  activeToolMode: "select" | "lasso";

  // Page attributes
  pageType: PageType | null;
  layoutType: LayoutType | null;
  pageTypeModified: boolean;
  layoutTypeModified: boolean;

  // Cross-page SKU
  crossPageSKUs: CrossPageSKU[];

  // Ambiguous bindings
  ambiguousBindings: AmbiguousBinding[];

  // Prefetch cache
  prefetchCache: Map<string, PrefetchData>;

  // Rest reminder
  sessionStartAt: number;

  // Legacy compat
  currentTask: any;
  skus: any[];
  annotations: any[];
  selectedSkuId: string | null;
  loading: boolean;

  // Operations
  loadTask: (taskId: string) => Promise<void>;
  acquireTask: (annotatorId: string) => Promise<any>;
  setCurrentTask: (task: any) => void;
  setSkus: (skus: any[]) => void;
  addAnnotation: (annotation: any) => void;
  removeAnnotation: (index: number) => void;
  updateAnnotation: (index: number, data: any) => void;
  selectSku: (skuId: string | null) => void;
  createGroup: (elementIds: string[]) => void;
  deleteGroup: (groupId: string) => void;
  moveElementToGroup: (elementId: string, groupId: string) => void;
  removeElementFromGroup: (elementId: string) => void;
  updateSKUAttribute: (groupId: string, field: string, value: string) => void;
  setPageType: (type: PageType) => void;
  setLayoutType: (type: LayoutType) => void;
  resolveBinding: (elementId: string, selectedUri: string | null) => void;
  buildSubmitPayload: () => TaskCompletePayload;
  submitAnnotation: (type: AnnotationType, payload: Record<string, unknown>) => Promise<void>;
  submitTask: () => Promise<void>;
  skipTask: (reason?: string) => Promise<void>;
  selectAllUngrouped: () => void;
  setTool: (mode: "select" | "lasso") => void;
  cancelCurrentAction: () => void;
  heartbeat: () => Promise<void>;
  updateThumbnail: (pageNo: number, status: string) => void;
  updateSLA: (taskId: string, slaLevel: string) => void;
  refreshFileList: () => void;
  reset: () => void;
}

let heartbeatTimer: ReturnType<typeof setInterval> | null = null;

export const useAnnotationStore = create<AnnotationState>()(
  immer((set, get) => ({
    currentTaskId: null,
    currentJobId: null,
    currentPageNo: null,
    elements: [],
    groups: [],
    selectedElementIds: [],
    selectedGroupId: null,
    activeToolMode: "select" as const,
    pageType: null,
    layoutType: null,
    pageTypeModified: false,
    layoutTypeModified: false,
    crossPageSKUs: [],
    ambiguousBindings: [],
    prefetchCache: new Map(),
    sessionStartAt: Date.now(),

    // Legacy
    currentTask: null,
    skus: [],
    annotations: [],
    selectedSkuId: null,
    loading: false,

    loadTask: async (taskId) => {
      try {
        const { default: { get: apiGet } } = await import("../api/client");
        const task = await apiGet<TaskDetail>(`/tasks/${taskId}`);
        set((s) => {
          s.currentTaskId = task.task_id;
          s.currentJobId = task.job_id;
          s.currentPageNo = task.page_number;
          s.elements = task.elements ?? [];
          s.ambiguousBindings = task.ambiguous_bindings ?? [];
          s.pageType = (task.context?.page_type as PageType) ?? null;
          s.layoutType = (task.context?.layout_type as LayoutType) ?? null;
          s.groups = [];
          s.selectedElementIds = [];
          s.selectedGroupId = null;
          s.pageTypeModified = false;
          s.layoutTypeModified = false;
          s.currentTask = task;
        });
        useUndoStore.getState().clear();
      } catch {
        // Error handled by interceptor
      }
    },

    acquireTask: async (annotatorId) => {
      set((s) => { s.loading = true; });
      try {
        let attempt = 0;
        let task = await tasksApi.acquireNext(annotatorId);
        while (task && task.status === "SKIPPED" && attempt < 3) {
          // 过滤掉已作废任务，再拉取下一个
          task = await tasksApi.acquireNext(annotatorId);
          attempt += 1;
        }

        set((s) => {
          s.currentTask = task;
          s.loading = false;
          s.annotations = [];
          if (task) {
            s.currentTaskId = task.task_id;
            s.currentJobId = task.job_id;
            s.currentPageNo = task.page_number;
            s.elements = (task as any).elements ?? [];
          }
        });
        if (heartbeatTimer) clearInterval(heartbeatTimer);
        if (task) {
          heartbeatTimer = setInterval(() => get().heartbeat(), 25000);
        }
        return task;
      } catch {
        set((s) => { s.loading = false; });
        return null;
      }
    },

    setCurrentTask: (task) => set((s) => { s.currentTask = task; }),
    setSkus: (skus) => set((s) => { s.skus = skus; }),

    addAnnotation: (ann) => set((s) => { s.annotations.push(ann); }),
    removeAnnotation: (index) => set((s) => { s.annotations.splice(index, 1); }),
    updateAnnotation: (index, data) => set((s) => {
      Object.assign(s.annotations[index], data);
    }),

    selectSku: (skuId) => set((s) => { s.selectedSkuId = skuId; }),

    // [V1.1 C3] Atomic: state change + undo push
    createGroup: (elementIds) => {
      if (elementIds.length === 0) return;
      const prevGroups = JSON.parse(JSON.stringify(get().groups));
      const prevSelected = [...get().selectedElementIds];

      set((s) => {
        const groupId = `g-${Date.now()}`;
        s.groups.push({
          id: groupId,
          label: `分组 ${s.groups.length + 1}`,
          skuType: "complete",
          elementIds: [...elementIds],
          skuAttributes: {},
          customAttributes: [],
          crossPageSkuId: null,
        });
        s.selectedElementIds = [];
        s.selectedGroupId = groupId;
      });

      useUndoStore.getState().push({
        type: "CREATE_GROUP",
        description: `创建分组（${elementIds.length} 个元素）`,
        forward: () => {
          // Re-apply: restore to post-create state
          set((s) => {
            const groupId = `g-${Date.now()}`;
            s.groups.push({
              id: groupId,
              label: `分组 ${s.groups.length + 1}`,
              skuType: "complete",
              elementIds: [...elementIds],
              skuAttributes: {},
              customAttributes: [],
              crossPageSkuId: null,
            });
            s.selectedElementIds = [];
            s.selectedGroupId = groupId;
          });
        },
        backward: () => set((s) => {
          s.groups = prevGroups;
          s.selectedElementIds = prevSelected;
        }),
      });
    },

    deleteGroup: (groupId) => {
      const prevGroups = JSON.parse(JSON.stringify(get().groups));
      set((s) => {
        s.groups = s.groups.filter((g) => g.id !== groupId);
        if (s.selectedGroupId === groupId) s.selectedGroupId = null;
      });
      useUndoStore.getState().push({
        type: "DELETE_GROUP",
        description: "删除分组",
        forward: () => set((s) => {
          s.groups = s.groups.filter((g) => g.id !== groupId);
          if (s.selectedGroupId === groupId) s.selectedGroupId = null;
        }),
        backward: () => set((s) => { s.groups = prevGroups; }),
      });
    },

    moveElementToGroup: (elementId, groupId) => {
      const prevGroups = JSON.parse(JSON.stringify(get().groups));
      set((s) => {
        for (const g of s.groups) {
          g.elementIds = g.elementIds.filter((id) => id !== elementId);
        }
        const target = s.groups.find((g) => g.id === groupId);
        if (target) target.elementIds.push(elementId);
      });
      useUndoStore.getState().push({
        type: "MOVE_ELEMENT",
        description: "移动元素到分组",
        forward: () => set((s) => {
          for (const g of s.groups) {
            g.elementIds = g.elementIds.filter((id) => id !== elementId);
          }
          const target = s.groups.find((g) => g.id === groupId);
          if (target) target.elementIds.push(elementId);
        }),
        backward: () => set((s) => { s.groups = prevGroups; }),
      });
    },

    removeElementFromGroup: (elementId) => {
      const prevGroups = JSON.parse(JSON.stringify(get().groups));
      set((s) => {
        for (const g of s.groups) {
          g.elementIds = g.elementIds.filter((id) => id !== elementId);
        }
      });
      useUndoStore.getState().push({
        type: "MOVE_ELEMENT",
        description: "从分组移除元素",
        forward: () => set((s) => {
          for (const g of s.groups) {
            g.elementIds = g.elementIds.filter((id) => id !== elementId);
          }
        }),
        backward: () => set((s) => { s.groups = prevGroups; }),
      });
    },

    updateSKUAttribute: (groupId, field, value) => {
      const group = get().groups.find((g) => g.id === groupId);
      const prevValue = group?.skuAttributes[field] ?? "";
      set((s) => {
        const g = s.groups.find((g) => g.id === groupId);
        if (g) g.skuAttributes[field] = value;
      });
      useUndoStore.getState().push({
        type: "MODIFY_ATTRIBUTE",
        description: `修改 ${field}`,
        forward: () => set((s) => {
          const g = s.groups.find((g) => g.id === groupId);
          if (g) g.skuAttributes[field] = value;
        }),
        backward: () => set((s) => {
          const g = s.groups.find((g) => g.id === groupId);
          if (g) g.skuAttributes[field] = prevValue;
        }),
      });
    },

    setPageType: (type) => {
      const prev = get().pageType;
      set((s) => { s.pageType = type; s.pageTypeModified = true; });
      useUndoStore.getState().push({
        type: "CHANGE_PAGE_TYPE",
        description: `页面类型 ${prev} → ${type}`,
        forward: () => set((s) => { s.pageType = type; s.pageTypeModified = true; }),
        backward: () => set((s) => { s.pageType = prev; }),
      });
    },

    setLayoutType: (type) => {
      const prev = get().layoutType;
      set((s) => { s.layoutType = type; s.layoutTypeModified = true; });
      useUndoStore.getState().push({
        type: "CHANGE_LAYOUT_TYPE",
        description: `布局类型 ${prev} → ${type}`,
        forward: () => set((s) => { s.layoutType = type; s.layoutTypeModified = true; }),
        backward: () => set((s) => { s.layoutType = prev; }),
      });
    },

    resolveBinding: (elementId, selectedUri) => set((s) => {
      const binding = s.ambiguousBindings.find((b) => b.elementId === elementId);
      if (binding) {
        binding.resolved = true;
        binding.selectedUri = selectedUri;
      }
    }),

    buildSubmitPayload: () => {
      const s = get();
      return {
        task_id: s.currentTaskId!,
        page_type: s.pageType!,
        layout_type: s.layoutType!,
        groups: s.groups.map((g) => ({
          group_id: g.id,
          label: g.label,
          sku_type: g.skuType,
          elements: s.elements.filter((el) => g.elementIds.includes(el.id)),
          sku_attributes: g.skuAttributes,
          custom_attributes: g.customAttributes,
          partial_contains: g.partialContains ?? [],
          cross_page_sku_id: g.crossPageSkuId,
          invalid_reason: g.invalidReason ?? null,
        })),
        ungrouped_elements: s.elements
          .filter((el) => !s.groups.some((g) => g.elementIds.includes(el.id)))
          .map((el) => el.id),
        binding_confirmations: s.ambiguousBindings
          .filter((b) => b.resolved)
          .map((b) => ({
            element_id: b.elementId,
            selected_rank: b.candidates.find((c) => c.imageUri === b.selectedUri)?.rank ?? 0,
          })),
        feedback: {
          page_type_modified: s.pageTypeModified,
          layout_type_modified: s.layoutTypeModified,
          new_image_role_observed: false,
          new_text_role_observed: false,
          notes: "",
        },
      };
    },

    submitAnnotation: async (type, payload) => {
      const { currentJobId, currentPageNo, currentTaskId } = get();
      if (!currentJobId || currentPageNo == null) return;
      await annotationsApi.create({
        job_id: currentJobId,
        page_number: currentPageNo,
        task_id: currentTaskId,
        type,
        payload,
      });
    },

    submitTask: async () => {
      const { currentTask, currentTaskId, annotations } = get();
      const taskId = currentTaskId ?? currentTask?.task_id;
      if (!taskId) return;

      await tasksApi.complete(taskId, annotations as any);
      if (heartbeatTimer) clearInterval(heartbeatTimer);
      useUndoStore.getState().clear();
      set((s) => {
        s.currentTask = null;
        s.currentTaskId = null;
        s.currentJobId = null;
        s.currentPageNo = null;
        s.annotations = [];
        s.skus = [];
        s.selectedSkuId = null;
        s.elements = [];
        s.groups = [];
        s.selectedElementIds = [];
        s.selectedGroupId = null;
        s.ambiguousBindings = [];
        s.pageType = null;
        s.layoutType = null;
        s.pageTypeModified = false;
        s.layoutTypeModified = false;
      });
    },

    skipTask: async (reason) => {
      const { currentTask, currentTaskId } = get();
      const taskId = currentTaskId ?? currentTask?.task_id;
      if (!taskId) return;

      await tasksApi.skip(taskId, reason ?? "");
      if (heartbeatTimer) clearInterval(heartbeatTimer);
      useUndoStore.getState().clear();
      set((s) => {
        s.currentTask = null;
        s.currentTaskId = null;
        s.annotations = [];
        s.skus = [];
        s.selectedSkuId = null;
        s.elements = [];
        s.groups = [];
      });
    },

    selectAllUngrouped: () => set((s) => {
      const grouped = new Set(s.groups.flatMap((g) => g.elementIds));
      s.selectedElementIds = s.elements
        .filter((el) => !grouped.has(el.id))
        .map((el) => el.id);
    }),

    setTool: (mode) => set((s) => { s.activeToolMode = mode; }),

    cancelCurrentAction: () => set((s) => {
      s.selectedElementIds = [];
      s.activeToolMode = "select";
    }),

    heartbeat: async () => {
      const taskId = get().currentTaskId ?? get().currentTask?.task_id;
      if (taskId) {
        try {
          await tasksApi.heartbeat(taskId);
        } catch { /* handled by useHeartbeat hook */ }
      }
    },

    updateThumbnail: (_pageNo, _status) => {
      // Triggered by SSE page_completed to update thumbnail state
    },

    updateSLA: (_taskId, _slaLevel) => {
      // Triggered by SSE sla_escalated
    },

    refreshFileList: () => {
      // Re-fetch task list (triggered by SSE human_needed)
    },

    reset: () => {
      if (heartbeatTimer) clearInterval(heartbeatTimer);
      useUndoStore.getState().clear();
      set((s) => {
        s.currentTaskId = null;
        s.currentJobId = null;
        s.currentPageNo = null;
        s.elements = [];
        s.groups = [];
        s.selectedElementIds = [];
        s.selectedGroupId = null;
        s.ambiguousBindings = [];
        s.pageType = null;
        s.layoutType = null;
        s.pageTypeModified = false;
        s.layoutTypeModified = false;
        s.currentTask = null;
        s.skus = [];
        s.annotations = [];
        s.selectedSkuId = null;
        s.sessionStartAt = Date.now();
      });
    },
  })),
);
