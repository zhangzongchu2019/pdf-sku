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

/** 状态中文标签映射 */
const STATUS_LABELS: Record<string, string> = {
  // Job user status
  processing: "处理中", partial_success: "部分完成", completed: "已完成",
  needs_manual: "需人工处理", failed: "失败",
  // Job internal status
  UPLOADED: "已上传", EVALUATING: "评估中", EVAL_FAILED: "评估失败",
  EVALUATED: "已评估", PROCESSING: "处理中", PARTIAL_FAILED: "部分失败",
  PARTIAL_IMPORTED: "部分导入", DEGRADED_HUMAN: "已降级(人工)",
  FULL_IMPORTED: "已导入", REJECTED: "已拒绝", ORPHANED: "已孤立",
  CANCELLED: "已取消",
  // Page status
  PENDING: "待处理", BLANK: "空白页", AI_QUEUED: "AI排队中",
  AI_PROCESSING: "AI处理中", AI_COMPLETED: "AI完成", AI_FAILED: "AI失败",
  HUMAN_QUEUED: "人工排队", HUMAN_PROCESSING: "人工处理中",
  HUMAN_COMPLETED: "人工完成", IMPORTED_CONFIRMED: "已确认导入",
  IMPORTED_ASSUMED: "默认导入", IMPORT_FAILED: "导入失败",
  SKIPPED: "已跳过", DEAD_LETTER: "死信",
  // Task status
  CREATED: "待处理", ASSIGNED: "已分配", LOCKED: "处理中",
  COMPLETED: "已完成", EXPIRED: "已过期", ESCALATED: "已升级",
  TIMEOUT: "已超时",
  // SKU status
  EXTRACTED: "已提取", VALIDATED: "已验证", CONFIRMED: "已确认",
  BOUND: "已绑定", EXPORTED: "已导出", SUPERSEDED: "已替代",
  PARTIAL: "部分完成", INVALID: "无效",
  // Route
  AUTO: "自动处理", HYBRID: "混合处理", HUMAN_ALL: "全量人工",
  // Priority
  NORMAL: "普通", HIGH: "高", URGENT: "紧急", CRITICAL: "严重",
  AUTO_RESOLVE: "自动处理",
  // Attribute source
  AI_EXTRACTED: "AI提取", HUMAN_CORRECTED: "人工修正",
  CROSS_PAGE_MERGED: "跨页合并", PROMOTED: "已提升",
  // Task type
  PAGE_PROCESS: "页面处理", SKU_CONFIRM: "SKU确认",
  ATTRIBUTE_CONFIRM: "属性确认", BINDING_CONFIRM: "绑定确认",
  CLASSIFICATION_REVIEW: "分类审核", FULL_MANUAL: "全量人工",
  // Validity
  valid: "有效", invalid: "无效", needs_review: "待审核",
  // Import confirmation
  confirmed: "已确认", assumed: "默认确认", pending: "待确认",
  // Calibration
  approved: "已批准", rejected: "已拒绝",
};

/** 将英文状态码翻译为中文，无匹配则原样返回 */
export function statusLabel(status: string | undefined | null): string {
  if (!status) return "—";
  return STATUS_LABELS[status] ?? status;
}
