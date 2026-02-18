import { create } from "zustand";
import { persist } from "zustand/middleware";
import { immer } from "zustand/middleware/immer";
import { tusUpload, UploadProgress } from "../api/upload";

export type UploadStatus = "pending" | "hashing" | "uploading" | "completed" | "error";

export interface UploadItem {
  id: string;
  file: File;
  progress: UploadProgress;
  status: UploadStatus;
  profileId?: string;
  fileId?: string;
  error?: string;
}

interface UploadState {
  uploads: UploadItem[];
  addFile: (file: File, profileId?: string) => void;
  startUpload: (id: string) => Promise<string>;
  updateProgress: (uploadId: string, progress: number) => void;
  setStatus: (uploadId: string, status: UploadStatus) => void;
  removeUpload: (id: string) => void;
  clearCompleted: () => void;
}

let counter = 0;

export const useUploadStore = create<UploadState>()(
  persist(
    immer((set, get) => ({
      uploads: [],

      addFile: (file, profileId) => {
        const id = `upload_${++counter}_${Date.now()}`;
        set((s) => {
          s.uploads.push({
            id,
            file,
            profileId,
            progress: { loaded: 0, total: file.size, percentage: 0 },
            status: "pending",
          });
        });
      },

      updateProgress: (uploadId, percentage) => set((s) => {
        const item = s.uploads.find((u) => u.id === uploadId);
        if (item) {
          item.progress.percentage = percentage;
          item.progress.loaded = Math.round(item.progress.total * percentage);
        }
      }),

      setStatus: (uploadId, status) => set((s) => {
        const item = s.uploads.find((u) => u.id === uploadId);
        if (item) item.status = status;
      }),

      startUpload: async (id) => {
        const item = get().uploads.find((u) => u.id === id);
        if (!item) throw new Error("Upload not found");

        set((s) => {
          const u = s.uploads.find((u) => u.id === id);
          if (u) u.status = "uploading";
        });

        try {
          const fileId = await tusUpload(
            item.file,
            (progress) => set((s) => {
              const u = s.uploads.find((u) => u.id === id);
              if (u) u.progress = progress;
            }),
          );
          set((s) => {
            const u = s.uploads.find((u) => u.id === id);
            if (u) {
              u.status = "completed";
              u.fileId = fileId;
            }
          });
          return fileId;
        } catch (e: any) {
          set((s) => {
            const u = s.uploads.find((u) => u.id === id);
            if (u) {
              u.status = "error";
              u.error = e.message;
            }
          });
          throw e;
        }
      },

      removeUpload: (id) => set((s) => {
        s.uploads = s.uploads.filter((u) => u.id !== id);
      }),

      clearCompleted: () => set((s) => {
        s.uploads = s.uploads.filter((u) => u.status !== "completed");
      }),
    })),
    {
      name: "pdf-sku-uploads",
      partialize: (_s) => ({ uploads: [] } as any), // Don't persist File objects
    },
  ),
);
