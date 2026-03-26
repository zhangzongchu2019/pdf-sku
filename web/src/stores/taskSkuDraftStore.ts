import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export interface TaskSkuDraftRow {
  id: string;
  skuId: string;
  attributes: Record<string, string>;
}

interface TaskSkuDraftState {
  drafts: Record<string, TaskSkuDraftRow[]>;
  ensureDraft: (taskId: string, rows: TaskSkuDraftRow[]) => void;
  replaceDraft: (taskId: string, rows: TaskSkuDraftRow[]) => void;
  updateCell: (taskId: string, rowId: string, key: string, value: string) => void;
  removeDraft: (taskId: string) => void;
}

export const useTaskSkuDraftStore = create<TaskSkuDraftState>()(
  persist(
    (set) => ({
      drafts: {},
      ensureDraft: (taskId, rows) =>
        set((state) => {
          if (state.drafts[taskId]) return state;
          return { drafts: { ...state.drafts, [taskId]: rows } };
        }),
      replaceDraft: (taskId, rows) =>
        set((state) => ({
          drafts: { ...state.drafts, [taskId]: rows },
        })),
      updateCell: (taskId, rowId, key, value) =>
        set((state) => ({
          drafts: {
            ...state.drafts,
            [taskId]: (state.drafts[taskId] || []).map((row) =>
              row.id === rowId
                ? {
                    ...row,
                    skuId: key === "sku_id" ? value : row.skuId,
                    attributes: {
                      ...row.attributes,
                      [key]: value,
                    },
                  }
                : row,
            ),
          },
        })),
      removeDraft: (taskId) =>
        set((state) => {
          if (!(taskId in state.drafts)) return state;
          const next = { ...state.drafts };
          delete next[taskId];
          return { drafts: next };
        }),
    }),
    {
      name: "pdf-sku-task-sku-drafts",
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
