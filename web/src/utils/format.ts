export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024, sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("zh-CN", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

export function formatPercent(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

export function statusColor(status: string): string {
  const map: Record<string, string> = {
    COMPLETED: "#52c41a", PROCESSING: "#1890ff", FAILED: "#ff4d4f",
    CANCELLED: "#d9d9d9", PARTIAL: "#faad14", PENDING: "#8c8c8c",
    AI_COMPLETED: "#52c41a", NEEDS_REVIEW: "#faad14", LOCKED: "#1890ff",
    IMPORTED_CONFIRMED: "#389e0d", IMPORTED_ASSUMED: "#7cb305",
  };
  return map[status] || "#8c8c8c";
}
