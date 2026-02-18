import { useEffect, useRef } from "react";
import { tasksApi } from "../api/tasks";

/**
 * 心跳 Hook — 30s 间隔发送心跳，Tab 切回时补发
 * [V1.1 E3] 连续失败降级提示
 */
export function useHeartbeat(taskId: string | null) {
  const intervalRef = useRef<ReturnType<typeof setInterval>>();
  const failCountRef = useRef(0);

  useEffect(() => {
    if (!taskId) return;

    const sendHeartbeat = async () => {
      try {
        await tasksApi.heartbeat(taskId);
        failCountRef.current = 0;
      } catch {
        failCountRef.current++;
        // Degradation warnings handled by caller via notification store
      }
    };

    sendHeartbeat();
    intervalRef.current = setInterval(sendHeartbeat, 30000);

    const handleVisibility = () => {
      if (document.visibilityState === "visible") sendHeartbeat();
    };
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      clearInterval(intervalRef.current);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [taskId]);

  return { failCount: failCountRef.current };
}
