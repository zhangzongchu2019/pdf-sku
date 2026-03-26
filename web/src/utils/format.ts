import { STATUS_COLORS } from "./designTokens";

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
  cancelled: "已取消",
  queued: "排队中",
  pending: "待处理",
  uploading: "上传中",
  hashing: "处理中",
  creating: "创建任务中",
  approved: "已通过",
  rejected: "已拒绝",
  applied: "已应用",
  merged: "已合并",
  valid: "有效",
  invalid: "无效",
  needs_review: "待复核",
  PROCESSING: "处理中",
  PARTIAL_SUCCESS: "部分完成",
  COMPLETED: "已完成",
  FAILED: "失败",
  CANCELLED: "已取消",
  PENDING: "待处理",
  CREATED: "待处理",
  ASSIGNED: "已分配",
  LOCKED: "处理中",
  SKIPPED: "已作废",
  ESCALATED: "已升级",
  EXPIRED: "已超时",
  TIMEOUT: "已超时",
  APPROVED: "已通过",
  REJECTED: "已拒绝",
  APPLIED: "已应用",
  AI_QUEUED: "AI排队中",
  AI_PROCESSING: "AI处理中",
  AI_COMPLETED: "AI已完成",
  AI_FAILED: "AI失败",
  HUMAN_QUEUED: "待人工处理",
  HUMAN_PROCESSING: "人工处理中",
  HUMAN_COMPLETED: "人工已完成",
  IMPORTED_CONFIRMED: "已确认导入",
  IMPORTED_ASSUMED: "已推定导入",
  IMPORT_FAILED: "导入失败",
  BLANK: "空白页",
  DEAD_LETTER: "死信",
};

export function formatStatusLabel(status?: string | null): string {
  if (!status) return "-";
  return STATUS_LABELS[status] ?? status;
}

export function statusColor(status: string): string {
  return STATUS_COLORS[status] ?? "#8c8c8c";
}
