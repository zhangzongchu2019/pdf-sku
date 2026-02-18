import { useState, useEffect } from "react";

/**
 * 休息提醒 Hook — 连续标注 N 分钟后柔性提醒 [V1.1 A4]
 */
export function useRestReminder(
  enableRestReminder: boolean,
  restReminderMinutes: number,
  sessionStartAt: number,
) {
  const [showReminder, setShowReminder] = useState(false);

  useEffect(() => {
    if (!enableRestReminder) return;

    const checkInterval = setInterval(() => {
      const elapsed = (Date.now() - sessionStartAt) / 60000;
      if (elapsed >= restReminderMinutes) {
        setShowReminder(true);
      }
    }, 60000);

    return () => clearInterval(checkInterval);
  }, [enableRestReminder, restReminderMinutes, sessionStartAt]);

  const dismiss = () => {
    setShowReminder(false);
  };

  return { showReminder, dismiss };
}
