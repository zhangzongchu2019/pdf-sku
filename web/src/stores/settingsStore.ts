import { create } from "zustand";
import { persist } from "zustand/middleware";

interface SettingsState {
  locale: "zh" | "en";
  theme: "light" | "dark";
  annotatorId: string;
  setLocale: (l: "zh" | "en") => void;
  setTheme: (t: "light" | "dark") => void;
  setAnnotatorId: (id: string) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      locale: "zh", theme: "light", annotatorId: "",
      setLocale: (locale) => set({ locale }),
      setTheme: (theme) => set({ theme }),
      setAnnotatorId: (annotatorId) => set({ annotatorId }),
    }),
    { name: "pdf-sku-settings" },
  ),
);
