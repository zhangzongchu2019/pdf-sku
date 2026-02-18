import { useCallback } from "react";
import { tasksApi } from "../api/tasks";
import { useNotificationStore } from "../stores/notificationStore";

/**
 * 自动领取下一个任务 [V1.1 POST /tasks/next]
 */
export function useAutoPickTask() {
  const pickNext = useCallback(async () => {
    try {
      const task = await tasksApi.acquireNext("current-user");
      if (!task) {
        useNotificationStore.getState().addNotification({
          type: "info",
          message: "暂无可领取的任务",
        });
        return null;
      }
      return task;
    } catch (e: any) {
      if (e.response?.status === 409) {
        // Concurrent conflict, retry once
        try {
          const task2 = await tasksApi.acquireNext("current-user");
          if (!task2) return null;
          return task2;
        } catch {
          return null;
        }
      }
      if (!e._handled) {
        useNotificationStore.getState().addNotification({
          type: "error",
          message: "领取任务失败",
        });
      }
      return null;
    }
  }, []);

  return { pickNext };
}
