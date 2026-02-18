/**
 * 评估卡片 — 展示 route_reason / sampling / prompt_version
 */
import type { Evaluation } from "../../types/models";

interface EvaluationCardProps {
  evaluation?: Evaluation | null;
}

export function EvaluationCard({ evaluation }: EvaluationCardProps) {
  if (!evaluation) {
    return (
      <div
        style={{
          padding: 16,
          color: "#64748B",
          fontSize: 13,
          backgroundColor: "#1B2233",
          borderRadius: 8,
          border: "1px solid #2D3548",
        }}
      >
        暂无评估数据
      </div>
    );
  }

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
        评估详情
      </h4>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: 12,
          marginBottom: 12,
        }}
      >
        <InfoCell label="路由" value={evaluation.route} />
        <InfoCell label="路由原因" value={evaluation.route_reason ?? "—"} />
        <InfoCell label="文档置信度" value={`${(evaluation.doc_confidence * 100).toFixed(1)}%`} />
        <InfoCell label="模型" value={evaluation.model_used} />
        <InfoCell label="Prompt版本" value={evaluation.prompt_version ?? "—"} />
        <InfoCell label="配置版本" value={evaluation.config_version} />
      </div>

      {/* Dimension scores */}
      {Object.keys(evaluation.dimension_scores).length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, color: "#64748B", marginBottom: 6 }}>
            维度评分
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {Object.entries(evaluation.dimension_scores).map(([dim, score]) => {
              const threshold = evaluation.thresholds_used?.[dim];
              const pass = threshold !== undefined ? score >= threshold : true;
              return (
                <span
                  key={dim}
                  style={{
                    padding: "2px 8px",
                    backgroundColor: pass ? "#22C55E11" : "#EF444411",
                    border: `1px solid ${pass ? "#22C55E33" : "#EF444433"}`,
                    borderRadius: 4,
                    fontSize: 11,
                    color: pass ? "#22C55E" : "#EF4444",
                  }}
                >
                  {dim}: {score.toFixed(3)}
                  {threshold !== undefined && ` / ${threshold.toFixed(3)}`}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* Prescan */}
      {evaluation.prescan_result && (
        <div
          style={{
            padding: 8,
            backgroundColor: evaluation.prescan_result.passed ? "#22C55E08" : "#EF444408",
            border: `1px solid ${evaluation.prescan_result.passed ? "#22C55E22" : "#EF444422"}`,
            borderRadius: 6,
            fontSize: 11,
          }}
        >
          <span style={{ color: evaluation.prescan_result.passed ? "#22C55E" : "#EF4444" }}>
            预扫描 {evaluation.prescan_result.passed ? "✓ 通过" : "✗ 未通过"}
          </span>
          <span style={{ color: "#64748B", marginLeft: 12 }}>
            扣分: {evaluation.prescan_result.total_deduction.toFixed(2)}
          </span>
          {evaluation.prescan_result.penalties.length > 0 && (
            <div style={{ marginTop: 4, color: "#94A3B8" }}>
              {evaluation.prescan_result.penalties.map((p, i) => (
                <div key={i}>
                  {p.rule}: -{p.deduction.toFixed(2)} ({p.reason})
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function InfoCell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: "#64748B" }}>{label}</div>
      <div style={{ fontSize: 12, color: "#E2E8F4" }}>{value}</div>
    </div>
  );
}

export default EvaluationCard;
