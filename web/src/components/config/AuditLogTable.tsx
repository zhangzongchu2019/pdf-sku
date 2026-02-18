/**
 * 审计日志表 — 配置变更历史 + 回滚
 */
import type { AuditLogEntry } from "../../types/models";

interface AuditLogTableProps {
  entries: AuditLogEntry[];
  onRollback?: (entryId: string) => void;
  loading?: boolean;
}

export function AuditLogTable({
  entries,
  onRollback,
  loading,
}: AuditLogTableProps) {
  if (loading) {
    return (
      <div style={{ padding: 16, color: "#64748B", fontSize: 13 }}>
        加载审计日志…
      </div>
    );
  }

  return (
    <div
      style={{
        backgroundColor: "#1B2233",
        border: "1px solid #2D3548",
        borderRadius: 8,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "12px 16px",
          borderBottom: "1px solid #2D3548",
        }}
      >
        <h4 style={{ margin: 0, fontSize: 13, color: "#E2E8F4" }}>
          审计日志
        </h4>
      </div>

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
              {["时间", "操作人", "操作", "原因", "操作"].map((h) => (
                <th
                  key={h}
                  style={{
                    padding: "8px 12px",
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
            {entries.length === 0 ? (
              <tr>
                <td
                  colSpan={5}
                  style={{ padding: 24, textAlign: "center", color: "#64748B" }}
                >
                  暂无审计记录
                </td>
              </tr>
            ) : (
              entries.map((entry) => (
                <tr
                  key={entry.id}
                  style={{ borderBottom: "1px solid #2D354866" }}
                >
                  <td style={{ padding: "8px 12px", color: "#94A3B8", whiteSpace: "nowrap" }}>
                    {new Date(entry.created_at).toLocaleString()}
                  </td>
                  <td style={{ padding: "8px 12px" }}>{entry.operator}</td>
                  <td style={{ padding: "8px 12px" }}>
                    <ActionBadge action={entry.action} />
                  </td>
                  <td
                    style={{
                      padding: "8px 12px",
                      color: "#94A3B8",
                      maxWidth: 200,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    title={entry.reason}
                  >
                    {entry.reason || "—"}
                  </td>
                  <td style={{ padding: "8px 12px" }}>
                    {onRollback && (
                      <button
                        onClick={() => onRollback(entry.id)}
                        style={{
                          padding: "3px 8px",
                          backgroundColor: "#F59E0B18",
                          border: "1px solid #F59E0B33",
                          borderRadius: 4,
                          color: "#F59E0B",
                          cursor: "pointer",
                          fontSize: 11,
                        }}
                      >
                        回滚
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ActionBadge({ action }: { action: string }) {
  const colorMap: Record<string, string> = {
    CREATE: "#22C55E",
    UPDATE: "#3B82F6",
    ACTIVATE: "#22D3EE",
    DEACTIVATE: "#F59E0B",
    ROLLBACK: "#EF4444",
  };
  const color = colorMap[action] ?? "#64748B";

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
      {action}
    </span>
  );
}

export default AuditLogTable;
