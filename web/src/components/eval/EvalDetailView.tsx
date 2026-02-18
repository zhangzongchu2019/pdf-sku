/**
 * 评测详情视图
 */
import type { EvalReport } from "../../types/models";

interface EvalDetailViewProps {
  report: EvalReport | null;
  loading?: boolean;
}

export function EvalDetailView({ report, loading }: EvalDetailViewProps) {
  if (loading) {
    return (
      <div style={{ padding: 16, color: "#64748B", fontSize: 13 }}>
        加载评测详情…
      </div>
    );
  }

  if (!report) {
    return (
      <div style={{ padding: 16, color: "#64748B", fontSize: 13 }}>
        未找到评测报告
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <h3 style={{ margin: "0 0 4px", fontSize: 16, color: "#E2E8F4" }}>
            评测报告 #{report.report_id}
          </h3>
          <span style={{ fontSize: 12, color: "#64748B" }}>
            {new Date(report.created_at).toLocaleString()}
          </span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <InfoChip label="配置" value={report.config_version} />
          <InfoChip label="黄金集" value={report.golden_set_id} />
          <InfoChip
            label="准确率"
            value={`${(report.accuracy * 100).toFixed(1)}%`}
            color={report.accuracy >= 0.9 ? "#22C55E" : "#F59E0B"}
          />
        </div>
      </div>

      {/* Metrics grid */}
      {Object.keys(report.metrics).length > 0 && (
        <div
          style={{
            backgroundColor: "#1B2233",
            border: "1px solid #2D3548",
            borderRadius: 8,
            padding: 16,
          }}
        >
          <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "#E2E8F4" }}>
            评测指标
          </h4>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
              gap: 12,
            }}
          >
            {Object.entries(report.metrics).map(([key, val]) => (
              <div
                key={key}
                style={{
                  padding: 12,
                  backgroundColor: "#161D2F",
                  borderRadius: 6,
                }}
              >
                <div style={{ fontSize: 10, color: "#64748B" }}>{key}</div>
                <div
                  style={{
                    fontSize: 16,
                    fontWeight: 600,
                    color: "#E2E8F4",
                  }}
                >
                  {typeof val === "number"
                    ? val < 1 ? (val * 100).toFixed(1) + "%" : val.toFixed(2)
                    : String(val)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Details (raw JSON) */}
      {Object.keys(report.details).length > 0 && (
        <div
          style={{
            backgroundColor: "#1B2233",
            border: "1px solid #2D3548",
            borderRadius: 8,
            padding: 16,
          }}
        >
          <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "#E2E8F4" }}>
            详细信息
          </h4>
          <pre
            style={{
              margin: 0,
              padding: 12,
              backgroundColor: "#161D2F",
              borderRadius: 6,
              fontSize: 11,
              color: "#94A3B8",
              overflow: "auto",
              maxHeight: 400,
            }}
          >
            {JSON.stringify(report.details, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

function InfoChip({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <span
      style={{
        padding: "4px 10px",
        backgroundColor: "#1B2233",
        border: "1px solid #2D3548",
        borderRadius: 6,
        fontSize: 11,
      }}
    >
      <span style={{ color: "#64748B" }}>{label}: </span>
      <span style={{ color: color ?? "#E2E8F4", fontWeight: 500 }}>
        {value}
      </span>
    </span>
  );
}

export default EvalDetailView;
