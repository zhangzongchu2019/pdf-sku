import { create } from "zustand";
import { persist } from "zustand/middleware";
import { immer } from "zustand/middleware/immer";

/**
 * 用户偏好 Store [V1.1 A6]
 */
interface SettingsState {
  // 基础偏好
  locale: "zh" | "en";
  theme: "light" | "dark";
  annotatorId: string;

  // [V1.1] 新增偏好
  skipSubmitConfirm: boolean;
  enableRestReminder: boolean;
  restReminderMinutes: number;
  enableSound: boolean;
  annotationOnboarded: boolean;
  preferredPageSize: number;

  // Actions
  setLocale: (l: "zh" | "en") => void;
  setTheme: (t: "light" | "dark") => void;
  setAnnotatorId: (id: string) => void;
  setSkipSubmitConfirm: (v: boolean) => void;
  setEnableRestReminder: (v: boolean) => void;
  setRestReminderMinutes: (v: number) => void;
  setEnableSound: (v: boolean) => void;
  setAnnotationOnboarded: (v: boolean) => void;
  setPreferredPageSize: (v: number) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    immer((set) => ({
      locale: "zh",
      theme: "dark",
      annotatorId: "",
      skipSubmitConfirm: false,
      enableRestReminder: true,
      restReminderMinutes: 60,
      enableSound: true,
      annotationOnboarded: false,
      preferredPageSize: 20,

      setLocale: (locale) => set((s) => { s.locale = locale; }),
      setTheme: (theme) => set((s) => { s.theme = theme; }),
      setAnnotatorId: (annotatorId) => set((s) => { s.annotatorId = annotatorId; }),
      setSkipSubmitConfirm: (v) => set((s) => { s.skipSubmitConfirm = v; }),
      setEnableRestReminder: (v) => set((s) => { s.enableRestReminder = v; }),
      setRestReminderMinutes: (v) => set((s) => { s.restReminderMinutes = v; }),
      setEnableSound: (v) => set((s) => { s.enableSound = v; }),
      setAnnotationOnboarded: (v) => set((s) => { s.annotationOnboarded = v; }),
      setPreferredPageSize: (v) => set((s) => { s.preferredPageSize = v; }),
    })),
    { name: "pdf-sku-settings" },
  ),
);
