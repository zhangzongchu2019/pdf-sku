import { create } from "zustand";
import { persist } from "zustand/middleware";
import { immer } from "zustand/middleware/immer";

export interface FieldMapping {
  id: string;
  sourceField: string;
  targetField: string;
}

export interface CosConfig {
  secretId: string;
  secretKey: string;
  bucket: string;
  region: string;
}

interface ImportConfigState {
  apiEndpoint: string;
  authToken: string;
  fieldMappings: FieldMapping[];
  cosConfig: CosConfig;

  setApiEndpoint: (v: string) => void;
  setAuthToken: (v: string) => void;
  addMapping: () => void;
  updateMapping: (id: string, patch: Partial<Omit<FieldMapping, "id">>) => void;
  removeMapping: (id: string) => void;
  setCosConfig: (patch: Partial<CosConfig>) => void;
}

let _nextId = 1;
function genId() {
  return `fm-${Date.now()}-${_nextId++}`;
}

export const useImportConfigStore = create<ImportConfigState>()(
  persist(
    immer((set) => ({
      apiEndpoint: "",
      authToken: "",
      fieldMappings: [],
      cosConfig: { secretId: "", secretKey: "", bucket: "", region: "" },

      setApiEndpoint: (v) => set((s) => { s.apiEndpoint = v; }),
      setAuthToken: (v) => set((s) => { s.authToken = v; }),

      addMapping: () =>
        set((s) => {
          s.fieldMappings.push({ id: genId(), sourceField: "", targetField: "" });
        }),

      updateMapping: (id, patch) =>
        set((s) => {
          const m = s.fieldMappings.find((f) => f.id === id);
          if (m) Object.assign(m, patch);
        }),

      removeMapping: (id) =>
        set((s) => {
          s.fieldMappings = s.fieldMappings.filter((f) => f.id !== id);
        }),

      setCosConfig: (patch) =>
        set((s) => { Object.assign(s.cosConfig, patch); }),
    })),
    { name: "pdf-sku-import-config" },
  ),
);
