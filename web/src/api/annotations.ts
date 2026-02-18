import api from "./client";
import type { CreateAnnotationRequest } from "../types/models";

/** 独立标注端点 (对齐 OpenAPI V2.0) */
export const annotationsApi = {
  create: (body: CreateAnnotationRequest) =>
    api.post<{ annotation_id: string }>("/annotations", body),

  suggest: (merchantId: string, field: string, prefix: string) =>
    api.get<string[]>(
      `/annotations/suggest?merchant_id=${merchantId}&field=${field}&prefix=${encodeURIComponent(prefix)}`,
    ),
};
