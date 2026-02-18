/**
 * 指标行 — 5 个 MetricCard 一行展示
 */

interface MetricItem {
  label: string;
  value: string | number;
  delta?: number; // 百分比变化, >0 up, <0 down
  color?: string;
}

interface MetricsRowProps {
  metrics: MetricItem[];
}

export function MetricsRow({ metrics }: MetricsRowProps) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${Math.min(metrics.length, 5)}, 1fr)`,
        gap: 12,
        marginBottom: 16,
      }}
    >
      {metrics.map((m, i) => (
        <div
          key={i}
          style={{
            padding: "16px 20px",
            backgroundColor: "#1B2233",
            border: "1px solid #2D3548",
            borderRadius: 8,
          }}
        >
          <div style={{ fontSize: 12, color: "#64748B", marginBottom: 4 }}>
            {m.label}
          </div>
          <div
            style={{
              fontSize: 24,
              fontWeight: 700,
              color: m.color ?? "#E2E8F4",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {m.value}
          </div>
          {m.delta !== undefined && (
            <div
              style={{
                fontSize: 11,
                color: m.delta >= 0 ? "#22C55E" : "#EF4444",
                marginTop: 4,
              }}
            >
              {m.delta >= 0 ? "↑" : "↓"} {Math.abs(m.delta).toFixed(1)}%
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default MetricsRow;
