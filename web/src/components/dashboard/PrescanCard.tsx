/**
 * 预扫描卡片 — 显示 raw_metrics
 */
import type { Evaluation } from "../../types/models";

interface PrescanCardProps {
  evaluation?: Evaluation | null;
}

export function PrescanCard({ evaluation }: PrescanCardProps) {
  if (!evaluation) {
    return (
      <div style={{ padding: 16, color: "#64748B", fontSize: 13 }}>
        暂无预扫描数据
      </div>
    );
  }

  const rawMetrics = evaluation.prescan_result?.raw_metrics ?? {};
  const entries = Object.entries(rawMetrics);

  return (
    <div
      style={{
        backgroundColor: "#1B2233",
        border: "1px solid #2D3548",
        borderRadius: 8,
        padding: 16,
      }}
    >
      <h4 style={{ margin: "0 0 12px", fontSize: 13, color: "#E2E8F4" }}>
        预扫描评估
      </h4>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 8,
          marginBottom: 12,
        }}
      >
        <InfoItem label="路由原因" value={evaluation.route_reason ?? "—"} />
        <InfoItem
          label="采样策略"
          value={
            evaluation.sampling
              ? `${evaluation.sampling.sample_ratio * 100}% (${evaluation.sampling.sampled_pages.length}页)`
              : "—"
          }
        />
        <InfoItem label="Prompt版本" value={evaluation.prompt_version ?? "—"} />
        <InfoItem
          label="文档置信度"
          value={`${(evaluation.doc_confidence * 100).toFixed(1)}%`}
        />
      </div>

      {entries.length > 0 && (
        <>
          <div
            style={{
              fontSize: 12,
              color: "#64748B",
              marginBottom: 8,
              borderTop: "1px solid #2D3548",
              paddingTop: 8,
            }}
          >
            原始指标
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1fr",
              gap: 6,
            }}
          >
            {entries.map(([key, val]) => (
              <InfoItem
                key={key}
                label={key}
                value={typeof val === "number" ? val.toFixed(4) : String(val)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: "#64748B" }}>{label}</div>
      <div style={{ fontSize: 12, color: "#E2E8F4" }}>{value}</div>
    </div>
  );
}

export default PrescanCard;
