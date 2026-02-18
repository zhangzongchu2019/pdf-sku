/**
 * 我的产出统计 — 大数字 + 7日趋势
 */
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

interface MyOutcomeStatsProps {
  todayPages: number;
  avgTimeMs: number;
  accuracy: number;
  weeklyRank?: number;
  trendData: { date: string; avgTime: number }[];
  outcomeMetrics: {
    extracted: number;
    imported: number;
    pending: number;
    rejected: number;
  };
}

export function MyOutcomeStats({
  todayPages,
  avgTimeMs,
  accuracy,
  weeklyRank,
  trendData,
  outcomeMetrics,
}: MyOutcomeStatsProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Big numbers */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 12,
        }}
      >
        <BigNumber label="今日页面" value={todayPages} />
        <BigNumber
          label="平均耗时"
          value={`${(avgTimeMs / 1000).toFixed(1)}s`}
        />
        <BigNumber
          label="准确率"
          value={`${(accuracy * 100).toFixed(1)}%`}
          color={accuracy >= 0.9 ? "#22C55E" : "#F59E0B"}
        />
        {weeklyRank !== undefined && (
          <BigNumber label="周排名" value={`#${weeklyRank}`} />
        )}
      </div>

      {/* 7-day trend */}
      {trendData.length > 0 && (
        <div
          style={{
            backgroundColor: "#1B2233",
            border: "1px solid #2D3548",
            borderRadius: 8,
            padding: 16,
          }}
        >
          <h4 style={{ margin: "0 0 8px", fontSize: 13, color: "#E2E8F4" }}>
            7日平均耗时趋势
          </h4>
          <div style={{ width: "100%", height: 160 }}>
            <ResponsiveContainer>
              <LineChart data={trendData}>
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#64748B", fontSize: 10 }}
                  axisLine={{ stroke: "#2D3548" }}
                />
                <YAxis
                  tick={{ fill: "#64748B", fontSize: 10 }}
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
                <Line
                  type="monotone"
                  dataKey="avgTime"
                  stroke="#22D3EE"
                  strokeWidth={2}
                  dot={{ r: 3, fill: "#22D3EE" }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Outcome metrics */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 12,
        }}
      >
        <OutcomeCard label="提取SKU" value={outcomeMetrics.extracted} color="#22D3EE" />
        <OutcomeCard label="已导入" value={outcomeMetrics.imported} color="#22C55E" />
        <OutcomeCard label="待确认" value={outcomeMetrics.pending} color="#F59E0B" />
        <OutcomeCard label="被拒绝" value={outcomeMetrics.rejected} color="#EF4444" />
      </div>
    </div>
  );
}

function BigNumber({
  label,
  value,
  color,
}: {
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <div
      style={{
        padding: "16px 20px",
        backgroundColor: "#1B2233",
        border: "1px solid #2D3548",
        borderRadius: 8,
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: 11, color: "#64748B", marginBottom: 4 }}>
        {label}
      </div>
      <div
        style={{
          fontSize: 28,
          fontWeight: 700,
          color: color ?? "#E2E8F4",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {value}
      </div>
    </div>
  );
}

function OutcomeCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div
      style={{
        padding: 12,
        backgroundColor: `${color}08`,
        border: `1px solid ${color}22`,
        borderRadius: 8,
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: 20, fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: 11, color: "#94A3B8" }}>{label}</div>
    </div>
  );
}

export default MyOutcomeStats;
