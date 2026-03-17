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

const STATUS_LABELS: Record<string, string> = {
  processing: "处理中",
  partial_success: "部分完成",
  completed: "已完成",
  needs_manual: "需人工处理",
  failed: "失败",
  pending: "待处理",
  approved: "已批准",
  rejected: "已拒绝",
  applied: "已应用",
  valid: "有效",
  invalid: "无效",
  needs_review: "待复核",
  online: "在线",
  busy: "忙碌",
  offline: "离线",
  UPLOADED: "已上传",
  EVALUATING: "评估中",
  EVAL_FAILED: "评估失败",
  EVALUATED: "已评估",
  PROCESSING: "处理中",
  PARTIAL_FAILED: "部分失败",
  PARTIAL_IMPORTED: "部分导入",
  DEGRADED_HUMAN: "转人工处理",
  FULL_IMPORTED: "导入完成",
  REJECTED: "已拒绝",
  ORPHANED: "处理中断",
  CANCELLED: "已取消",
  PENDING: "待处理",
  CREATED: "待领取",
  COMPLETED: "已完成",
  ESCALATED: "已升级",
  SKIPPED: "已跳过",
  EXPIRED: "已过期",
  BLANK: "空白页",
  AI_QUEUED: "AI排队中",
  AI_PROCESSING: "AI处理中",
  AI_COMPLETED: "AI完成",
  AI_FAILED: "AI失败",
  HUMAN_QUEUED: "待人工处理",
  HUMAN_PROCESSING: "人工处理中",
  HUMAN_COMPLETED: "人工完成",
  IMPORTED_CONFIRMED: "已确认导入",
  IMPORTED_ASSUMED: "已默认导入",
  IMPORT_FAILED: "导入失败",
  DEAD_LETTER: "死信",
  NEEDS_REVIEW: "待复核",
  RUNNING: "运行中",
  APPROVED: "已批准",
  APPLIED: "已应用",
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] || status;
}

export function statusColor(status: string): string {
  const map: Record<string, string> = {
    COMPLETED: "#52c41a", PROCESSING: "#1890ff", FAILED: "#ff4d4f",
    CANCELLED: "#d9d9d9", PARTIAL: "#faad14", PENDING: "#8c8c8c",
    completed: "#52c41a", processing: "#1890ff", failed: "#ff4d4f",
    partial_success: "#faad14", needs_manual: "#faad14",
    AI_COMPLETED: "#52c41a", NEEDS_REVIEW: "#faad14", LOCKED: "#1890ff",
    IMPORTED_CONFIRMED: "#389e0d", IMPORTED_ASSUMED: "#7cb305",
  };
  return map[status] || "#8c8c8c";
}
