export enum JobStatus {
  PROCESSING = "processing",
  PARTIAL_SUCCESS = "partial_success",
  COMPLETED = "completed",
  NEEDS_MANUAL = "needs_manual",
  FAILED = "failed",
}

export enum PageStatus {
  PENDING = "PENDING",
  PROCESSING = "PROCESSING",
  AI_COMPLETED = "AI_COMPLETED",
  NEEDS_REVIEW = "NEEDS_REVIEW",
  HUMAN_COMPLETED = "HUMAN_COMPLETED",
  IMPORTED_CONFIRMED = "IMPORTED_CONFIRMED",
  IMPORTED_ASSUMED = "IMPORTED_ASSUMED",
  BLANK = "BLANK",
  FAILED = "FAILED",
}

export enum TaskStatus {
  CREATED = "CREATED",
  ASSIGNED = "ASSIGNED",
  PROCESSING = "PROCESSING",
  COMPLETED = "COMPLETED",
  SKIPPED = "SKIPPED",
  ESCALATED = "ESCALATED",
  EXPIRED = "EXPIRED",
  LOCKED = "LOCKED",
  TIMEOUT = "TIMEOUT",
}

export enum PageType { A = "A", B = "B", C = "C", D = "D", PV = "PV" }
export enum Route { AUTO = "AUTO", HYBRID = "HYBRID", HUMAN_ALL = "HUMAN_ALL" }
export type Priority = "URGENT" | "HIGH" | "NORMAL" | "LOW";
