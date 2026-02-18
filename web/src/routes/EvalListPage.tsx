/**
 * 评测列表页 /eval
 */
import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { evalApi } from "../api/eval";
import { EvalReportTable } from "../components/eval/EvalReportTable";
import { EvalRunButton } from "../components/eval/EvalRunButton";
import type { EvalReportSummary } from "../types/models";

export default function EvalListPage() {
  const navigate = useNavigate();
  const [reports, setReports] = useState<EvalReportSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchReports = useCallback(async () => {
    try {
      setLoading(true);
      const res = await evalApi.listReports();
      setReports(
        Array.isArray(res) ? res : (res as unknown as { data: EvalReportSummary[] }).data ?? [],
      );
    } catch {
      // handle
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchReports(); }, [fetchReports]);

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 18, color: "#E2E8F4" }}>
          评测报告
        </h2>
        <EvalRunButton onSuccess={fetchReports} />
      </div>

      <EvalReportTable
        reports={reports}
        onDetail={(id) => navigate(`/eval/${id}`)}
        loading={loading}
      />
    </div>
  );
}
