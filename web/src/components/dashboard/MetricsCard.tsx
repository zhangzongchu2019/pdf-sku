interface Props {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: "up" | "down" | "neutral";
  color?: string;
}

export default function MetricsCard({ title, value, subtitle, trend, color }: Props) {
  return (
    <div className="metrics-card" style={color ? { borderLeftColor: color } : {}}>
      <div className="metrics-header">
        <span className="metrics-title">{title}</span>
        {trend && (
          <span className={`metrics-trend trend-${trend}`}>
            {trend === "up" ? "↑" : trend === "down" ? "↓" : "→"}
          </span>
        )}
      </div>
      <div className="metrics-value">{value}</div>
      {subtitle && <div className="metrics-subtitle">{subtitle}</div>}
    </div>
  );
}
