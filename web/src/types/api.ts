/** 分页元数据 (对齐 OpenAPI V2.0) */
export interface PaginationMeta {
  page: number;
  size: number;
  total: number;
  total_pages: number;
}

/** 通用分页响应 */
export interface PaginatedResponse<T> {
  data: T[];
  pagination: PaginationMeta;
}

/** ErrorResponse (对齐 OpenAPI V2.0) */
export interface ErrorResponse {
  code: string;
  message: string;
  details: Record<string, unknown> | null;
  severity: "info" | "warning" | "error" | "critical";
}
