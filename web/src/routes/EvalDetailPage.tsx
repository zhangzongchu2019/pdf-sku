/**
 * 评测详情页 /eval/:reportId
 */
import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { evalApi } from "../api/eval";
import { EvalDetailView } from "../components/eval/EvalDetailView";
import type { EvalReport } from "../types/models";

export default function EvalDetailPage() {
  const { reportId } = useParams<{ reportId: string }>();
  const navigate = useNavigate();
  const [report, setReport] = useState<EvalReport | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchReport = useCallback(async () => {
    if (!reportId) return;
    try {
      setLoading(true);
      const data = await evalApi.getReport(Number(reportId));
      setReport(data as unknown as EvalReport);
    } catch {
      // handle
    } finally {
      setLoading(false);
    }
  }, [reportId]);

  useEffect(() => { fetchReport(); }, [fetchReport]);

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: "0 auto" }}>
      <button
        onClick={() => navigate("/eval")}
        style={{
          background: "none",
          border: "none",
          color: "#22D3EE",
          cursor: "pointer",
          fontSize: 12,
          marginBottom: 12,
          padding: 0,
        }}
      >
        ← 返回评测列表
      </button>

      <EvalDetailView report={report} loading={loading} />
    </div>
  );
}
