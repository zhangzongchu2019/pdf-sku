/**
 * 影响预览面板 — debounce 500ms 调用 impact-preview API
 * 展示 current vs projected 自动化率/人工率
 */
import type { ImpactPreviewResult } from "../../types/models";

interface ImpactPreviewPanelProps {
  result: ImpactPreviewResult | null;
  loading?: boolean;
}

export function ImpactPreviewPanel({
  result,
  loading,
}: ImpactPreviewPanelProps) {
  if (loading) {
    return (
      <div
        style={{
          padding: 16,
          backgroundColor: "#1B2233",
          border: "1px solid #2D3548",
          borderRadius: 8,
          color: "#64748B",
          fontSize: 13,
        }}
      >
        正在预估影响…
      </div>
    );
  }

  if (!result) {
    return (
      <div
        style={{
          padding: 16,
          backgroundColor: "#1B2233",
          border: "1px solid #2D3548",
          borderRadius: 8,
          color: "#64748B",
          fontSize: 13,
        }}
      >
        调整阈值后将自动预览影响
      </div>
    );
  }

  return (
    <div
      style={{
        padding: 16,
        backgroundColor: "#1B2233",
        border: "1px solid #2D3548",
        borderRadius: 8,
      }}
    >
      <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "#E2E8F4" }}>
        影响预览
      </h4>

      <div style={{ fontSize: 11, color: "#64748B", marginBottom: 12 }}>
        基于 {result.sample_period_days} 天 · {result.sample_job_count} 个Job
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 12,
          marginBottom: 12,
        }}
      >
        <RateCard
          label="全自动率"
          current={result.current_auto_rate}
          projected={result.projected_auto_rate}
          delta={result.delta_auto}
        />
        <RateCard
          label="人工率"
          current={result.current_human_rate}
          projected={result.projected_human_rate}
          delta={result.delta_human}
          inverse
        />
      </div>

      {result.capacity_warning && (
        <div
          style={{
            padding: "8px 12px",
            backgroundColor: "#EF444411",
            border: "1px solid #EF444433",
            borderRadius: 6,
            fontSize: 12,
            color: "#EF4444",
          }}
        >
          ⚠ 预计变更将导致人工标注量显著增加，请确认团队处理能力
        </div>
      )}
    </div>
  );
}

function RateCard({
  label,
  current,
  projected,
  delta,
  inverse,
}: {
  label: string;
  current: number;
  projected: number;
  delta: number;
  inverse?: boolean;
}) {
  const isGood = inverse ? delta < 0 : delta > 0;
  const deltaColor = isGood ? "#22C55E" : delta === 0 ? "#64748B" : "#EF4444";

  return (
    <div
      style={{
        padding: 12,
        backgroundColor: "#161D2F",
        borderRadius: 6,
      }}
    >
      <div style={{ fontSize: 11, color: "#64748B", marginBottom: 4 }}>
        {label}
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <span style={{ fontSize: 11, color: "#94A3B8" }}>
          {(current * 100).toFixed(1)}%
        </span>
        <span style={{ color: "#64748B" }}>→</span>
        <span
          style={{
            fontSize: 16,
            fontWeight: 600,
            color: "#E2E8F4",
          }}
        >
          {(projected * 100).toFixed(1)}%
        </span>
      </div>
      <div
        style={{
          fontSize: 11,
          color: deltaColor,
          marginTop: 4,
        }}
      >
        {delta > 0 ? "+" : ""}
        {(delta * 100).toFixed(1)}%
      </div>
    </div>
  );
}

export default ImpactPreviewPanel;
