/**
 * 标注员详情页 /annotators/:annotatorId
 */
import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { opsApi } from "../api/ops";
import { AnnotatorDailyChart } from "../components/annotator/AnnotatorDailyChart";
import type { AnnotatorDetail } from "../types/models";

export default function AnnotatorDetailPage() {
  const { annotatorId } = useParams<{ annotatorId: string }>();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<AnnotatorDetail | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchDetail = useCallback(async () => {
    if (!annotatorId) return;
    try {
      setLoading(true);
      const data = await opsApi.getAnnotatorStats(annotatorId);
      setDetail(data);
    } catch {
      // handle
    } finally {
      setLoading(false);
    }
  }, [annotatorId]);

  useEffect(() => { fetchDetail(); }, [fetchDetail]);

  if (loading) return <div style={{ padding: 24, color: "#64748B" }}>加载中…</div>;
  if (!detail) return <div style={{ padding: 24, color: "#64748B" }}>未找到标注员</div>;

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: "0 auto" }}>
      <button
        onClick={() => navigate("/annotators")}
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
        ← 返回标注员列表
      </button>

      <h2 style={{ margin: "0 0 8px", fontSize: 18, color: "#E2E8F4" }}>
        {detail.name}
      </h2>
      <div style={{ fontSize: 12, color: "#64748B", marginBottom: 20 }}>
        ID: {detail.annotator_id}
      </div>

      {/* Summary cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 12,
          marginBottom: 24,
        }}
      >
        <SCard label="活跃任务" value={detail.active_tasks} />
        <SCard label="今日完成" value={detail.daily_completed} />
        <SCard label="准确率" value={`${(detail.accuracy * 100).toFixed(1)}%`}
               color={detail.accuracy >= 0.9 ? "#22C55E" : "#F59E0B"} />
        <SCard label="平均耗时" value={`${(detail.avg_time_per_task / 1000).toFixed(1)}s`} />
      </div>

      {/* Daily chart (placeholder data) */}
      <div
        style={{
          backgroundColor: "#1B2233",
          border: "1px solid #2D3548",
          borderRadius: 8,
          padding: 16,
          marginBottom: 24,
        }}
      >
        <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "#E2E8F4" }}>
          30日趋势
        </h4>
        <AnnotatorDailyChart
          data={(detail as unknown as { daily_trend?: { date: string; completed: number; accuracy: number }[] }).daily_trend ?? []}
        />
      </div>
    </div>
  );
}

function SCard({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{
      padding: 16, backgroundColor: "#1B2233", border: "1px solid #2D3548",
      borderRadius: 8, textAlign: "center",
    }}>
      <div style={{ fontSize: 11, color: "#64748B", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: color ?? "#E2E8F4" }}>{value}</div>
    </div>
  );
}
