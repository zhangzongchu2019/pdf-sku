/**
 * 路由决策追溯卡片
 * 展示: 五维雷达图 + 阈值对比 + 评估详情 + 解析引擎
 */
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from "recharts";

export interface RouteDimension {
  dimension: string;
  score: number;
  threshold: number;
}

interface RouteTraceCardProps {
  dimensions: RouteDimension[];
  route: string;
  routeReason?: string;
  configVersion?: string;
  evalScore?: number;
  collapsed?: boolean;
  onToggle?: () => void;
}

export function RouteTraceCard({
  dimensions,
  route,
  routeReason,
  configVersion,
  evalScore,
  collapsed = true,
  onToggle,
}: RouteTraceCardProps) {
  const radarData = dimensions.map((d) => ({
    ...d,
    fullMark: 1,
  }));

  return (
    <div
      style={{
        backgroundColor: "#1B2233",
        border: "1px solid #2D3548",
        borderRadius: 8,
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <button
        onClick={onToggle}
        style={{
          width: "100%",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "12px 16px",
          backgroundColor: "transparent",
          border: "none",
          cursor: "pointer",
          color: "#E2E8F4",
        }}
      >
        <span style={{ fontSize: 13, fontWeight: 500 }}>
          路由决策追溯 — {route}
        </span>
        <span style={{ fontSize: 12, color: "#64748B" }}>
          {collapsed ? "▼ 展开" : "▲ 收起"}
        </span>
      </button>

      {!collapsed && (
        <div style={{ padding: "0 16px 16px" }}>
          {/* Radar */}
          <div style={{ width: "100%", height: 240, marginBottom: 12 }}>
            <ResponsiveContainer>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#2D3548" />
                <PolarAngleAxis
                  dataKey="dimension"
                  tick={{ fill: "#94A3B8", fontSize: 11 }}
                />
                <PolarRadiusAxis
                  domain={[0, 1]}
                  tick={{ fill: "#64748B", fontSize: 10 }}
                />
                <Radar
                  name="得分"
                  dataKey="score"
                  stroke="#22D3EE"
                  fill="#22D3EE"
                  fillOpacity={0.2}
                />
                <Radar
                  name="阈值"
                  dataKey="threshold"
                  stroke="#F59E0B"
                  fill="none"
                  strokeDasharray="4 4"
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          {/* Dimension table */}
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: 12,
              marginBottom: 12,
            }}
          >
            <thead>
              <tr style={{ borderBottom: "1px solid #2D3548" }}>
                <th style={{ padding: 6, textAlign: "left", color: "#64748B" }}>维度</th>
                <th style={{ padding: 6, textAlign: "right", color: "#64748B" }}>得分</th>
                <th style={{ padding: 6, textAlign: "right", color: "#64748B" }}>阈值</th>
                <th style={{ padding: 6, textAlign: "center", color: "#64748B" }}>结果</th>
              </tr>
            </thead>
            <tbody>
              {dimensions.map((d) => {
                const pass = d.score >= d.threshold;
                return (
                  <tr key={d.dimension} style={{ borderBottom: "1px solid #2D354866" }}>
                    <td style={{ padding: 6, color: "#E2E8F4" }}>{d.dimension}</td>
                    <td style={{ padding: 6, textAlign: "right", color: "#E2E8F4" }}>
                      {d.score.toFixed(3)}
                    </td>
                    <td style={{ padding: 6, textAlign: "right", color: "#94A3B8" }}>
                      {d.threshold.toFixed(3)}
                    </td>
                    <td style={{ padding: 6, textAlign: "center" }}>
                      <span style={{ color: pass ? "#22C55E" : "#EF4444" }}>
                        {pass ? "✓" : "✗"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {/* Meta info */}
          <div style={{ display: "flex", gap: 16, fontSize: 11, color: "#64748B" }}>
            {routeReason && <span>原因: {routeReason}</span>}
            {configVersion && <span>配置: v{configVersion}</span>}
            {evalScore !== undefined && (
              <span>评分: {(evalScore * 100).toFixed(1)}%</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default RouteTraceCard;
