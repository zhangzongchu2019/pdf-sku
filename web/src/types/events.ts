/** SSE 9 事件类型定义 (对齐 OpenAPI V2.0) */

export type SSEEventType =
  | "heartbeat"
  | "page_completed"
  | "pages_batch_update"
  | "job_completed"
  | "job_failed"
  | "human_needed"
  | "sla_escalated"
  | "sla_auto_resolve"
  | "sla_auto_accepted";

export interface SSEPageCompleted {
  page_no: number;
  status: string;
  confidence: number | null;
  sku_count: number;
}

export interface SSEPagesBatchUpdate {
  pages: { page_no: number; status: string }[];
}

export interface SSEJobCompleted {
  job_id: string;
  status: string;
  total_skus: number;
  total_images: number;
  duration_sec: number;
}

export interface SSEJobFailed {
  job_id: string;
  error_code: string;
  error_message: string;
}

export interface SSEHumanNeeded {
  job_id: string;
  task_count: number;
  priority: string;
}

export interface SSESlaEscalated {
  task_id: string;
  sla_level: "HIGH" | "CRITICAL" | "AUTO_RESOLVE";
  deadline: string;
}

export interface SSEHeartbeat {
  timestamp: string;
}
