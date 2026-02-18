/**
 * 趋势图 — 堆叠柱状图 14天处理趋势
 * 使用 recharts 渲染
 */
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

export interface TrendDataPoint {
  date: string;
  auto: number;
  hybrid: number;
  human: number;
  failed: number;
}

interface TrendChartProps {
  data: TrendDataPoint[];
  loading?: boolean;
}

export function TrendChart({ data, loading }: TrendChartProps) {
  if (loading) {
    return (
      <div style={{ height: 260, display: "flex", alignItems: "center", justifyContent: "center", color: "#64748B" }}>
        加载中…
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div style={{ height: 260, display: "flex", alignItems: "center", justifyContent: "center", color: "#64748B" }}>
        暂无数据
      </div>
    );
  }

  return (
    <div style={{ width: "100%", height: 260 }}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2D3548" />
          <XAxis
            dataKey="date"
            tick={{ fill: "#64748B", fontSize: 11 }}
            axisLine={{ stroke: "#2D3548" }}
          />
          <YAxis
            tick={{ fill: "#64748B", fontSize: 11 }}
            axisLine={{ stroke: "#2D3548" }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1E2536",
              border: "1px solid #2D3548",
              borderRadius: 6,
              fontSize: 12,
            }}
          />
          <Legend
            wrapperStyle={{ fontSize: 11, color: "#94A3B8" }}
          />
          <Bar dataKey="auto" name="全自动" stackId="a" fill="#22C55E" radius={[0, 0, 0, 0]} />
          <Bar dataKey="hybrid" name="混合" stackId="a" fill="#3B82F6" />
          <Bar dataKey="human" name="全人工" stackId="a" fill="#F59E0B" />
          <Bar dataKey="failed" name="失败" stackId="a" fill="#EF4444" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default TrendChart;
