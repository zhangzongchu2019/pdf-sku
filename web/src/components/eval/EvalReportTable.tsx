/**
 * 评测报告列表
 */
import type { EvalReportSummary } from "../../types/models";

interface EvalReportTableProps {
  reports: EvalReportSummary[];
  onDetail: (reportId: number) => void;
  loading?: boolean;
}

export function EvalReportTable({
  reports,
  onDetail,
  loading,
}: EvalReportTableProps) {
  if (loading) {
    return (
      <div style={{ padding: 16, color: "#64748B", fontSize: 13 }}>
        加载评测报告…
      </div>
    );
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: 12,
          color: "#E2E8F4",
        }}
      >
        <thead>
          <tr style={{ borderBottom: "1px solid #2D3548" }}>
            {[
              "报告ID",
              "黄金集",
              "配置版本",
              "状态",
              "准确率",
              "创建时间",
              "操作",
            ].map((h) => (
              <th
                key={h}
                style={{
                  padding: "8px",
                  textAlign: "left",
                  color: "#64748B",
                  fontWeight: 500,
                  fontSize: 11,
                }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {reports.length === 0 ? (
            <tr>
              <td
                colSpan={7}
                style={{
                  padding: 24,
                  textAlign: "center",
                  color: "#64748B",
                }}
              >
                暂无评测报告
              </td>
            </tr>
          ) : (
            reports.map((r) => (
              <tr
                key={r.report_id}
                style={{
                  borderBottom: "1px solid #2D354866",
                  cursor: "pointer",
                }}
                onClick={() => onDetail(r.report_id)}
              >
                <td style={{ padding: "8px" }}>{r.report_id}</td>
                <td style={{ padding: "8px", color: "#94A3B8" }}>
                  {r.golden_set_id}
                </td>
                <td style={{ padding: "8px", color: "#94A3B8" }}>
                  {r.config_version}
                </td>
                <td style={{ padding: "8px" }}>
                  <StatusBadge status={r.status} />
                </td>
                <td style={{ padding: "8px" }}>
                  {r.accuracy !== undefined
                    ? `${(r.accuracy * 100).toFixed(1)}%`
                    : "—"}
                </td>
                <td style={{ padding: "8px", color: "#94A3B8" }}>
                  {new Date(r.created_at).toLocaleString()}
                </td>
                <td style={{ padding: "8px" }}>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDetail(r.report_id);
                    }}
                    style={{
                      padding: "3px 8px",
                      background: "none",
                      border: "1px solid #2D3548",
                      borderRadius: 3,
                      color: "#94A3B8",
                      cursor: "pointer",
                      fontSize: 11,
                    }}
                  >
                    详情
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colorMap: Record<string, string> = {
    COMPLETED: "#22C55E",
    RUNNING: "#22D3EE",
    FAILED: "#EF4444",
    PENDING: "#F59E0B",
  };
  const color = colorMap[status] ?? "#64748B";

  return (
    <span
      style={{
        padding: "1px 6px",
        backgroundColor: `${color}18`,
        border: `1px solid ${color}33`,
        borderRadius: 3,
        fontSize: 11,
        color,
      }}
    >
      {status}
    </span>
  );
}

export default EvalReportTable;
