import { describe, it, expect, beforeEach } from "vitest";
import { useNotificationStore } from "../../src/stores/notificationStore";

describe("notificationStore", () => {
  beforeEach(() => {
    // Reset store
    const state = useNotificationStore.getState();
    state.clearAll();
  });

  it("starts with empty notifications", () => {
    const { notifications } = useNotificationStore.getState();
    expect(notifications).toHaveLength(0);
  });

  it("adds a notification via addNotification", () => {
    const { addNotification } = useNotificationStore.getState();
    addNotification({ message: "Test notification" });
    const { notifications } = useNotificationStore.getState();
    expect(notifications.length).toBeGreaterThanOrEqual(1);
    expect(notifications[0].message).toBe("Test notification");
  });

  it("marks notification as read", () => {
    const { addNotification } = useNotificationStore.getState();
    addNotification({ message: "Read me" });

    const { items, markRead } = useNotificationStore.getState();
    const id = items[0].id;
    markRead(id);

    const updated = useNotificationStore.getState().items;
    const n = updated.find((x) => x.id === id);
    expect(n?.read).toBe(true);
  });

  it("removes a notification", () => {
    const { addNotification } = useNotificationStore.getState();
    addNotification({ message: "Remove me" });

    const { notifications, remove } = useNotificationStore.getState();
    const id = notifications[0].id;
    remove(id);

    const updated = useNotificationStore.getState().notifications;
    expect(updated.find((x) => x.id === id)).toBeUndefined();
  });

  it("clearAll empties the list", () => {
    const { addNotification } = useNotificationStore.getState();
    addNotification({ message: "A" });
    addNotification({ message: "B" });

    useNotificationStore.getState().clearAll();
    const { notifications } = useNotificationStore.getState();
    expect(notifications).toHaveLength(0);
  });

  it("respects max 100 items", () => {
    const { add } = useNotificationStore.getState();
    for (let i = 0; i < 110; i++) {
      add({ message: `Notification ${i}`, level: "info" });
    }
    const { items } = useNotificationStore.getState();
    expect(items.length).toBeLessThanOrEqual(100);
  });
});
