/**
 * 路由分布环形图 — 显示 AUTO / HYBRID / HUMAN_ALL 分布
 */
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

export interface RouteDistribution {
  name: string;
  value: number;
  color: string;
}

interface RouteChartProps {
  data: RouteDistribution[];
  loading?: boolean;
}

const DEFAULT_COLORS: Record<string, string> = {
  AUTO: "#22C55E",
  HYBRID: "#3B82F6",
  HUMAN_ALL: "#F59E0B",
  FAILED: "#EF4444",
};

export function RouteChart({ data, loading }: RouteChartProps) {
  if (loading) {
    return (
      <div style={{ height: 260, display: "flex", alignItems: "center", justifyContent: "center", color: "#64748B" }}>
        加载中…
      </div>
    );
  }

  const total = data.reduce((s, d) => s + d.value, 0);

  if (total === 0) {
    return (
      <div style={{ height: 260, display: "flex", alignItems: "center", justifyContent: "center", color: "#64748B" }}>
        暂无数据
      </div>
    );
  }

  const chartData = data.map((d) => ({
    ...d,
    color: d.color || DEFAULT_COLORS[d.name] || "#64748B",
  }));

  return (
    <div style={{ width: "100%", height: 260 }}>
      <ResponsiveContainer>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={90}
            dataKey="value"
            nameKey="name"
            paddingAngle={2}
          >
            {chartData.map((entry, idx) => (
              <Cell key={idx} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: "#1E2536",
              border: "1px solid #2D3548",
              borderRadius: 6,
              fontSize: 12,
            }}
            formatter={(value, name) => [
              `${value ?? 0} (${(((Number(value) || 0) / total) * 100).toFixed(1)}%)`,
              String(name),
            ]}
          />
          <Legend
            wrapperStyle={{ fontSize: 11 }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

export default RouteChart;
