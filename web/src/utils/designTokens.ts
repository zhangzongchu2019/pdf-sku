/** Design Tokens — 共享常量 (对齐 UI/UX §2.1) */

export const GROUP_COLORS = [
  "#22D3EE", "#A78BFA", "#34D399", "#F472B6", "#FBBF24",
  "#FB923C", "#818CF8", "#2DD4BF", "#F87171", "#A3E635",
];

export const STATUS_COLORS: Record<string, string> = {
  COMPLETED: "#52c41a",
  PROCESSING: "#1890ff",
  FAILED: "#ff4d4f",
  CANCELLED: "#d9d9d9",
  PARTIAL: "#faad14",
  PENDING: "#8c8c8c",
  AI_COMPLETED: "#52c41a",
  NEEDS_REVIEW: "#faad14",
  LOCKED: "#1890ff",
  IMPORTED_CONFIRMED: "#389e0d",
  IMPORTED_ASSUMED: "#7cb305",
  HUMAN_COMPLETED: "#52c41a",
  HUMAN_QUEUED: "#faad14",
  HUMAN_PROCESSING: "#1890ff",
  AI_FAILED: "#ff4d4f",
  IMPORT_FAILED: "#ff4d4f",
  DEAD_LETTER: "#ff4d4f",
  BLANK: "#434343",
  SKIPPED: "#8c8c8c",
  ESCALATED: "#ff4d4f",
  CREATED: "#8c8c8c",
  TIMEOUT: "#faad14",
  // validity
  valid: "#52c41a",
  invalid: "#ff4d4f",
  needs_review: "#faad14",
  // calibration (lowercase aliases)
  pending: "#faad14",
  approved: "#52c41a",
  rejected: "#ff4d4f",
};

export const PAGE_HEATMAP_COLORS: Record<string, string> = {
  AI_COMPLETED: "#52C41A",
  HUMAN_COMPLETED: "#52C41A",
  IMPORTED_CONFIRMED: "#1890FF",
  HUMAN_QUEUED: "#FAAD14",
  HUMAN_PROCESSING: "#FAAD14",
  AI_FAILED: "#FF4D4F",
  IMPORT_FAILED: "#FF4D4F",
  DEAD_LETTER: "#FF4D4F",
  BLANK: "#434343",
  PENDING: "#262626",
};
