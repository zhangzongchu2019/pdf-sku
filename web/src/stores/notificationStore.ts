import { create } from "zustand";
import { persist } from "zustand/middleware";
import { immer } from "zustand/middleware/immer";

/**
 * 通知 Store [V1.1 A2] 三级优先级
 *
 * urgent (🔴): 持久 banner + 声音 + 不自动消失
 * warning (🟡): toast 5s 自动消失
 * info (🔵): toast 3s 自动消失
 */
export interface NotificationItem {
  id: string;
  level: "urgent" | "warning" | "info";
  type?: "success" | "error" | "warning" | "info"; // backward compat
  message: string;
  timestamp: number;
  read: boolean;
  duration?: number;
  jobId?: string;
  taskId?: string;
}

interface NotificationState {
  items: NotificationItem[];
  unreadCount: number;
  urgentCount: number;

  // Legacy toast list (for toast overlay)
  notifications: NotificationItem[];

  addNotification: (n: Partial<NotificationItem> & { message: string }) => void;
  add: (n: Omit<NotificationItem, "id" | "timestamp" | "read"> | { message: string; type?: string; level?: string }) => void;
  remove: (id: string) => void;
  markRead: (id: string) => void;
  markAllRead: () => void;
  clearAll: () => void;
}

let seq = 0;

export const useNotificationStore = create<NotificationState>()(
  persist(
    immer((set) => ({
      items: [],
      unreadCount: 0,
      urgentCount: 0,
      notifications: [],

      addNotification: (n) => {
        const level = n.level ?? (n.type === "error" ? "urgent" : n.type === "warning" ? "warning" : "info");
        const id = `n_${++seq}`;
        const item: NotificationItem = {
          id,
          level,
          message: n.message,
          timestamp: Date.now(),
          read: false,
          jobId: n.jobId,
          taskId: n.taskId,
          type: n.type,
        };
        set((s) => {
          s.items.unshift(item);
          if (s.items.length > 100) s.items.pop();
          s.unreadCount++;
          if (level === "urgent") s.urgentCount++;
          s.notifications.push(item);
        });
        // Auto-dismiss from toast overlay
        const duration = level === "urgent" ? 0 : level === "warning" ? 5000 : 3000;
        if (duration > 0) {
          setTimeout(() => {
            set((s) => {
              s.notifications = s.notifications.filter((x) => x.id !== id);
            });
          }, n.duration ?? duration);
        }
      },

      add: (n) => {
        const id = `n_${++seq}`;
        const level = (n as any).level ?? ((n as any).type === "error" ? "urgent" : (n as any).type === "warning" ? "warning" : "info") as NotificationItem["level"];
        const item: NotificationItem = {
          id,
          level,
          message: n.message,
          timestamp: Date.now(),
          read: false,
          type: (n as any).type,
        };
        set((s) => {
          s.items.unshift(item);
          if (s.items.length > 100) s.items.pop();
          s.unreadCount++;
          if (level === "urgent") s.urgentCount++;
          s.notifications.push(item);
        });
        const duration = level === "urgent" ? 0 : level === "warning" ? 5000 : 3000;
        if (duration > 0) {
          setTimeout(() => {
            set((s) => {
              s.notifications = s.notifications.filter((x) => x.id !== id);
            });
          }, (n as any).duration ?? duration);
        }
      },

      remove: (id) => set((s) => {
        s.notifications = s.notifications.filter((x) => x.id !== id);
      }),

      markRead: (id) => set((s) => {
        const item = s.items.find((i) => i.id === id);
        if (item && !item.read) {
          item.read = true;
          s.unreadCount--;
          if (item.level === "urgent") s.urgentCount--;
        }
      }),

      markAllRead: () => set((s) => {
        s.items.forEach((i) => { i.read = true; });
        s.unreadCount = 0;
        s.urgentCount = 0;
      }),

      clearAll: () => set((s) => {
        s.items = [];
        s.notifications = [];
        s.unreadCount = 0;
        s.urgentCount = 0;
      }),
    })),
    {
      name: "pdf-sku-notifications",
      partialize: (s) => ({ items: s.items, unreadCount: s.unreadCount, urgentCount: s.urgentCount } as any),
    },
  ),
);
