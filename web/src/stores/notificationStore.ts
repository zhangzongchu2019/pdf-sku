import { create } from "zustand";

interface Notification {
  id: string;
  type: "success" | "error" | "warning" | "info";
  message: string;
  duration?: number;
}

interface NotificationState {
  notifications: Notification[];
  add: (n: Omit<Notification, "id">) => void;
  remove: (id: string) => void;
}

let seq = 0;

export const useNotificationStore = create<NotificationState>((set) => ({
  notifications: [],
  add: (n) => {
    const id = `n_${++seq}`;
    set((s) => ({ notifications: [...s.notifications, { ...n, id }] }));
    setTimeout(() => {
      set((s) => ({ notifications: s.notifications.filter((x) => x.id !== id) }));
    }, n.duration ?? 4000);
  },
  remove: (id) => set((s) => ({
    notifications: s.notifications.filter((x) => x.id !== id),
  })),
}));
