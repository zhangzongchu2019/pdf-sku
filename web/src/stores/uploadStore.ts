import { create } from "zustand";
import { tusUpload, UploadProgress } from "../api/upload";

interface UploadItem {
  id: string;
  file: File;
  progress: UploadProgress;
  status: "pending" | "uploading" | "completed" | "error";
  fileId?: string;
  error?: string;
}

interface UploadState {
  uploads: UploadItem[];
  addFile: (file: File) => void;
  startUpload: (id: string) => Promise<string>;
  removeUpload: (id: string) => void;
  clearCompleted: () => void;
}

let counter = 0;

export const useUploadStore = create<UploadState>((set, get) => ({
  uploads: [],

  addFile: (file) => {
    const id = `upload_${++counter}_${Date.now()}`;
    set((s) => ({
      uploads: [...s.uploads, {
        id, file, progress: { loaded: 0, total: file.size, percentage: 0 },
        status: "pending",
      }],
    }));
  },

  startUpload: async (id) => {
    const item = get().uploads.find((u) => u.id === id);
    if (!item) throw new Error("Upload not found");

    set((s) => ({
      uploads: s.uploads.map((u) => u.id === id ? { ...u, status: "uploading" as const } : u),
    }));

    try {
      const fileId = await tusUpload(
        item.file,
        (progress) => set((s) => ({
          uploads: s.uploads.map((u) => u.id === id ? { ...u, progress } : u),
        })),
      );
      set((s) => ({
        uploads: s.uploads.map((u) =>
          u.id === id ? { ...u, status: "completed" as const, fileId } : u),
      }));
      return fileId;
    } catch (e: any) {
      set((s) => ({
        uploads: s.uploads.map((u) =>
          u.id === id ? { ...u, status: "error" as const, error: e.message } : u),
      }));
      throw e;
    }
  },

  removeUpload: (id) => set((s) => ({ uploads: s.uploads.filter((u) => u.id !== id) })),
  clearCompleted: () => set((s) => ({ uploads: s.uploads.filter((u) => u.status !== "completed") })),
}));
