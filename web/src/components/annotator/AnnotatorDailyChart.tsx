/**
 * 标注员每日趋势图 — 30天每日量 + 准确率
 */
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

export interface DailyDataPoint {
  date: string;
  completed: number;
  accuracy: number;
}

interface AnnotatorDailyChartProps {
  data: DailyDataPoint[];
  loading?: boolean;
}

export function AnnotatorDailyChart({
  data,
  loading,
}: AnnotatorDailyChartProps) {
  if (loading) {
    return (
      <div
        style={{
          height: 260,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#64748B",
        }}
      >
        加载中…
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div
        style={{
          height: 260,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#64748B",
        }}
      >
        暂无数据
      </div>
    );
  }

  return (
    <div style={{ width: "100%", height: 260 }}>
      <ResponsiveContainer>
        <LineChart
          data={data}
          margin={{ top: 8, right: 16, left: 0, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#2D3548" />
          <XAxis
            dataKey="date"
            tick={{ fill: "#64748B", fontSize: 11 }}
            axisLine={{ stroke: "#2D3548" }}
          />
          <YAxis
            yAxisId="left"
            tick={{ fill: "#64748B", fontSize: 11 }}
            axisLine={{ stroke: "#2D3548" }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={[0, 1]}
            tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
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
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="completed"
            name="完成量"
            stroke="#22D3EE"
            strokeWidth={2}
            dot={false}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="accuracy"
            name="准确率"
            stroke="#22C55E"
            strokeWidth={2}
            dot={false}
            strokeDasharray="4 4"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default AnnotatorDailyChart;
