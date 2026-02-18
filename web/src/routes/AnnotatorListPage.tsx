/**
 * 标注员列表页 /annotators
 */
import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { opsApi } from "../api/ops";
import { AnnotatorTable, type AnnotatorRow } from "../components/annotator/AnnotatorTable";

export default function AnnotatorListPage() {
  const navigate = useNavigate();
  const [annotators, setAnnotators] = useState<AnnotatorRow[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      const res = await opsApi.listAnnotators();
      setAnnotators(
        res.data.map((a) => ({
          annotator_id: a.annotator_id,
          name: a.name,
          current_task: null,
          today_completed: a.daily_completed,
          avg_time_ms: a.avg_time_per_task,
          accuracy: a.accuracy,
          status: a.active_tasks > 0 ? "busy" as const : "online" as const,
        })),
      );
    } catch {
      // handle
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 18, color: "#E2E8F4" }}>
          标注员管理
        </h2>
        <button
          style={{
            padding: "6px 14px",
            backgroundColor: "#F59E0B22",
            border: "1px solid #F59E0B44",
            borderRadius: 6,
            color: "#F59E0B",
            cursor: "pointer",
            fontSize: 12,
          }}
        >
          批量重分配
        </button>
      </div>

      {loading ? (
        <div style={{ color: "#64748B" }}>加载中…</div>
      ) : (
        <AnnotatorTable
          annotators={annotators}
          onDetail={(id) => navigate(`/annotators/${id}`)}
          onAssign={(id) => navigate(`/annotators/${id}`)}
        />
      )}
    </div>
  );
}
