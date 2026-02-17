import { JobStatus, PageStatus, TaskStatus, PageType, Route, Priority } from "./enums";

export interface Job {
  job_id: string;
  merchant_id: string;
  source_file: string;
  file_hash: string;
  user_status: JobStatus;
  route?: Route;
  total_pages: number;
  total_skus: number;
  total_images: number;
  blank_pages: number[];
  ai_pages: number[];
  human_pages: number[];
  created_at: string;
  updated_at: string;
  eval_completed_at?: string;
  process_completed_at?: string;
}

export interface Page {
  id: number;
  job_id: string;
  page_number: number;
  status: PageStatus;
  page_type?: PageType;
  needs_review: boolean;
  sku_count: number;
  page_confidence?: number;
  extraction_method?: string;
  llm_model_used?: string;
  parse_time_ms?: number;
  llm_time_ms?: number;
}

export interface SKU {
  id: number;
  sku_id: string;
  job_id: string;
  page_number: number;
  validity: "valid" | "invalid" | "needs_review";
  attributes: Record<string, string>;
  custom_attributes?: Record<string, string>;
  confidence?: number;
  source_bbox?: number[];
  import_status: string;
}

export interface HumanTask {
  task_id: string;
  job_id: string;
  page_number: number;
  task_type: string;
  status: TaskStatus;
  priority: Priority;
  assigned_to?: string;
  locked_at?: string;
  timeout_at: string;
  created_at: string;
}

export interface Annotation {
  annotation_id: string;
  task_id: string;
  type: string;
  annotator: string;
  payload: Record<string, unknown>;
  annotated_at: string;
}

export interface ImageInfo {
  image_id: string;
  page_number: number;
  bbox: number[];
  url?: string;
  quality_score?: number;
}

export interface DashboardMetrics {
  job_stats: { total: number; active: number; completed: number; by_status: Record<string, number> };
  page_stats: { total: number; completed: number; completion_rate: number };
  task_stats: { queue_depth: number; sla_health: number };
  import_stats: { success_rate: number };
  calibration_stats: { pending_approvals: number };
  today_jobs: number;
  today_skus: number;
}

export interface SSEEvent {
  event: string;
  data: Record<string, unknown>;
  timestamp: string;
}

export interface ThresholdProfile {
  profile_id: string;
  thresholds: Record<string, number>;
  version: number;
  effective_from: string;
}

export interface CalibrationRecord {
  calibration_id: string;
  profile_id: string;
  status: "PENDING" | "APPROVED" | "REJECTED";
  sample_count: number;
  suggested_adjustments: Record<string, unknown>;
  created_at: string;
}
