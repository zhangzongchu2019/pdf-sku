import {
  JobStatus, PageStatus, TaskStatus, PageType, Route, Priority,
} from "./enums";

export { PageType };
export type { JobStatus, PageStatus, TaskStatus, Route, Priority };

/* ======== Job ======== */
export type JobInternalStatus =
  | "UPLOADED" | "EVALUATING" | "EVAL_FAILED" | "EVALUATED"
  | "PROCESSING" | "PARTIAL_FAILED" | "PARTIAL_IMPORTED"
  | "DEGRADED_HUMAN" | "FULL_IMPORTED" | "REJECTED"
  | "ORPHANED" | "CANCELLED";

export type JobUserStatus =
  | "processing" | "partial_success" | "completed" | "needs_manual" | "failed";

export interface Job {
  job_id: string;
  merchant_id: string;
  source_file: string;
  file_hash: string;
  category: string | null;
  status: JobInternalStatus;
  user_status: JobStatus;
  action_hint: string | null;
  route?: Route;
  degrade_reason: string | null;
  total_pages: number;
  total_skus: number;
  total_images: number;
  blank_pages: number[];
  ai_pages: number[];
  human_pages: number[];
  failed_pages: number[];
  created_at: string;
  updated_at: string;
  eval_completed_at?: string;
  process_completed_at?: string;
}

export interface JobDetail extends Job {
  frozen_config_version: string;
  worker_id: string;
  completion_source: "AI_ONLY" | "HUMAN_ONLY" | "HYBRID" | "DEGRADED_HUMAN" | null;
  uploaded_at: string;
  eval_started_at: string | null;
  process_started_at: string | null;
  token_consumption: {
    eval_tokens: number;
    process_tokens: number;
    total_api_calls: number;
  };
  error_message: string | null;
}

/* ======== Page ======== */
export type LayoutType = "L1" | "L2" | "L3" | "L4";
export type SLALevel = "NORMAL" | "HIGH" | "CRITICAL" | "AUTO_RESOLVE";

export interface Page {
  id: number;
  job_id: string;
  page_number: number;
  status: PageStatus;
  page_type?: PageType;
  layout_type?: LayoutType;
  needs_review: boolean;
  sku_count: number;
  page_confidence?: number;
  extraction_method?: string;
  llm_model_used?: string;
  parse_time_ms?: number;
  llm_time_ms?: number;
  task_id?: string | null;
}

export interface PageInfo {
  page_no: number;
  status: PageStatus;
  page_type: PageType | null;
  layout_type: LayoutType | null;
  confidence: number | null;
  task_id: string | null;
  parser_backend: string;
  jobId?: string;
}

/* ======== SKU ======== */
export type SKUStatus =
  | "EXTRACTED" | "VALIDATED" | "CONFIRMED" | "BOUND"
  | "EXPORTED" | "SUPERSEDED" | "PARTIAL" | "INVALID";

export interface SKUImage {
  image_uri: string;
  image_id: string;
  role: "PRODUCT_MAIN" | "DETAIL" | "SCENE" | "LOGO" | "DECORATION" | "SIZE_CHART" | null;
  binding_method: "spatial_proximity" | "grid_alignment" | "id_matching" | "page_inheritance";
  bound_confidence: number;
  is_ambiguous: boolean;
  is_duplicate: boolean;
  image_hash: string | null;
  rank: number;
  extracted_path: string;
  resolution: [number, number];
  search_eligible: boolean;
  quality_grade: "HIGH" | "LOW_QUALITY" | "UNASSESSED";
  short_edge_px: number;
}

export interface SKU {
  id: number;
  sku_id: string;
  job_id: string;
  page_number: number;
  validity: "valid" | "invalid" | "needs_review";
  attributes: Record<string, string>;
  custom_attributes: { key: string; value: string }[];
  confidence?: number;
  source_bbox?: number[];
  import_status: string;
  import_confirmation: "confirmed" | "assumed" | "failed" | "pending";
  attribute_source: "AI_EXTRACTED" | "HUMAN_CORRECTED" | "CROSS_PAGE_MERGED" | "PROMOTED";
  status: SKUStatus;
  images: SKUImage[];
}

/* ======== Task ======== */
export interface HumanTask {
  task_id: string;
  job_id: string;
  page_number: number;
  task_type: string;
  status: TaskStatus;
  priority: Priority;
  sla_deadline: string | null;
  sla_level: SLALevel;
  assigned_to?: string;
  assigned_at?: string;
  locked_by?: string | null;
  locked_at?: string;
  timeout_at: string;
  rework_count: number;
  created_at: string;
  completed_at?: string | null;
}

export interface TaskDetail extends HumanTask {
  context: {
    page_type: string;
    layout_type: string;
    screenshot_url: string;
    ai_result: Record<string, unknown>;
    cross_page_table: Record<string, unknown> | null;
  };
  elements: AnnotationElement[];
  ambiguous_bindings: AmbiguousBinding[];
}

export interface TaskFileGroup {
  job_id: string;
  source_file: string;
  tasks: HumanTask[];
  total_pending: number;
}

/* ======== Annotation ======== */
export interface AnnotationElement {
  id: string;
  type: "image" | "text";
  bbox: { x: number; y: number; w: number; h: number };
  aiRole: string;
  confidence: number;
}

export interface AnnotationGroup {
  id: string;
  label: string;
  skuType: "complete" | "partial" | "invalid";
  elementIds: string[];
  skuAttributes: Record<string, string>;
  customAttributes: { key: string; value: string }[];
  crossPageSkuId: string | null;
  partialContains?: string[];
  invalidReason?: string;
}

export interface AmbiguousBinding {
  elementId: string;
  candidates: { imageUri: string; confidence: number; rank: number }[];
  resolved: boolean;
  selectedUri: string | null;
}

export interface Annotation {
  annotation_id: string;
  task_id: string;
  type: string;
  annotator: string;
  payload: Record<string, unknown>;
  annotated_at: string;
}

export type AnnotationType =
  | "PAGE_TYPE_CORRECTION" | "TEXT_ROLE_CORRECTION" | "IMAGE_ROLE_CORRECTION"
  | "SKU_ATTRIBUTE_CORRECTION" | "BINDING_CORRECTION" | "CUSTOM_ATTR_CONFIRM"
  | "NEW_TYPE_REPORT" | "LAYOUT_CORRECTION";

export interface CreateAnnotationRequest {
  task_id: string | null;
  job_id: string;
  page_number: number;
  type: AnnotationType;
  payload: Record<string, unknown>;
}

/* ======== Cross-Page SKU ======== */
export interface CrossPageSKU {
  xsku_id: string;
  fragments: {
    page_number: number;
    task_id: string;
    group_id: string;
    partial_contains: string[];
  }[];
  status: "pending" | "merged";
}

/* ======== Image ======== */
export interface ImageInfo {
  image_id: string;
  page_number: number;
  bbox: number[];
  url?: string;
  quality_score?: number;
}

/* ======== Dashboard ======== */
export interface DashboardMetrics {
  job_stats: {
    total: number;
    active: number;
    completed: number;
    by_status: Record<string, number>;
  };
  page_stats: { total: number; completed: number; completion_rate: number };
  task_stats: { queue_depth: number; sla_health: number };
  import_stats: { success_rate: number };
  calibration_stats: { pending_approvals: number };
  today_jobs: number;
  today_skus: number;
}

/* ======== SSE ======== */
export interface SSEEvent {
  event: string;
  data: Record<string, unknown>;
  timestamp: string;
}

/* ======== Config ======== */
export interface ThresholdProfile {
  profile_id: string;
  version: number;
  previous_version: string | null;
  category: string | null;
  industry: string | null;
  thresholds: Record<string, number>;
  confidence_weights: Record<string, number>;
  sku_validity_mode: "strict" | "lenient";
  is_active: boolean;
  effective_from: string;
  change_reason: string | null;
}

export interface ImpactPreviewResult {
  sample_period_days: number;
  sample_job_count: number;
  current_auto_rate: number;
  projected_auto_rate: number;
  current_human_rate: number;
  projected_human_rate: number;
  delta_auto: number;
  delta_human: number;
  sample_count: number;
  capacity_warning: boolean;
}

export interface CalibrationRecord {
  calibration_id: string;
  profile_id: string;
  status: "PENDING" | "APPROVED" | "REJECTED";
  sample_count: number;
  suggested_adjustments: Record<string, unknown>;
  created_at: string;
}

export interface AuditLogEntry {
  id: string;
  profile_id: string;
  action: string;
  operator: string;
  previous_value: Record<string, unknown>;
  new_value: Record<string, unknown>;
  reason: string;
  created_at: string;
}

/* ======== Evaluation ======== */
export interface Evaluation {
  file_hash: string;
  config_version: string;
  doc_confidence: number;
  route: "AUTO" | "HYBRID" | "HUMAN_ALL";
  route_reason: string | null;
  degrade_reason: string | null;
  dimension_scores: Record<string, number>;
  weights_snapshot: Record<string, number>;
  thresholds_used: Record<string, number> | null;
  page_evaluations: Record<string, number>;
  model_used: string;
  prompt_version: string | null;
  sampling: { sampled_pages: number[]; sample_ratio: number } | null;
  evaluated_at: string | null;
  prescan_result: {
    passed: boolean;
    penalties: { rule: string; deduction: number; reason: string }[];
    total_deduction: number;
    raw_metrics: {
      total_pages: number;
      blank_page_count: number;
      blank_rate: number;
      ocr_rate: number;
      image_count: number;
    };
  };
}

export interface EvalReportSummary {
  report_id: number;
  golden_set_id: string;
  config_version: string;
  status: string;
  accuracy: number;
  created_at: string;
}

export interface EvalReport extends EvalReportSummary {
  details: Record<string, unknown>;
  metrics: Record<string, number>;
}

/* ======== Annotator ======== */
export interface AnnotatorSummary {
  annotator_id: string;
  name: string;
  active_tasks: number;
  daily_completed: number;
  accuracy: number;
  avg_time_per_task: number;
}

export interface AnnotatorDetail extends AnnotatorSummary {
  daily_stats: { date: string; completed: number; accuracy: number; avg_time: number }[];
  skill_scores: Record<string, number>;
}

/* ======== Task Submit (元素-分组模型) ======== */
export interface TaskCompletePayload {
  task_id: string;
  page_type: PageType;
  layout_type: LayoutType;
  groups: {
    group_id: string;
    label: string;
    sku_type: "complete" | "partial" | "invalid";
    elements: AnnotationElement[];
    sku_attributes: Record<string, string>;
    custom_attributes: { key: string; value: string }[];
    partial_contains: string[];
    cross_page_sku_id: string | null;
    invalid_reason: string | null;
  }[];
  ungrouped_elements: string[];
  binding_confirmations: { element_id: string; selected_rank: number }[];
  feedback: {
    page_type_modified: boolean;
    layout_type_modified: boolean;
    new_image_role_observed: boolean;
    new_text_role_observed: boolean;
    notes: string;
  };
}

/* ======== Custom Attr Upgrade ======== */
export interface CustomAttrUpgrade {
  upgrade_id: string;
  merchant_id: string;
  attribute_key: string;
  proposed_value: string;
  status: "pending" | "approved" | "rejected";
  comment: string | null;
  created_at: string;
}

/* ======== Merchant ======== */
export interface MerchantStats {
  merchant_id: string;
  total_jobs: number;
  total_skus: number;
  success_rate: number;
  avg_process_time: number;
}

/* ======== Prefetch ======== */
export interface PrefetchData {
  screenshot: Blob;
  elements: AnnotationElement[];
  lockStatus: string | null;
  fetchedAt: number;
}
