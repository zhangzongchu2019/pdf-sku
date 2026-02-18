import api from "./client";
import type { EvalReportSummary, EvalReport } from "../types/models";

/** 评测报告 API */
export const evalApi = {
  listReports: () =>
    api.get<{ data: EvalReportSummary[] }>("/ops/eval/reports"),

  getReport: (reportId: number) =>
    api.get<EvalReport>(`/ops/eval/reports/${reportId}`),

  run: (body: { golden_set_id: string; config_version: string }) =>
    api.post<{ report_id: number }>("/ops/eval/run", body),
};
