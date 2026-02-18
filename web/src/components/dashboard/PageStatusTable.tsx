/**
 * 页面状态表格 — Job 详情中按页面展示状态列表
 */

export interface PageStatusRow {
  page_no: number;
  status: string;
  page_type?: string;
  confidence?: number;
  duration_ms?: number;
  assigned_to?: string;
  sku_count?: number;
}

interface PageStatusTableProps {
  pages: PageStatusRow[];
  onPageClick?: (pageNo: number) => void;
}

export function PageStatusTable({ pages, onPageClick }: PageStatusTableProps) {
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
            {["页码", "状态", "页面类型", "置信度", "耗时", "分配", "SKU数"].map(
              (h) => (
                <th
                  key={h}
                  style={{
                    padding: "8px 6px",
                    textAlign: "left",
                    color: "#64748B",
                    fontWeight: 500,
                    fontSize: 11,
                  }}
                >
                  {h}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {pages.map((p) => (
            <tr
              key={p.page_no}
              style={{
                borderBottom: "1px solid #2D354866",
                cursor: onPageClick ? "pointer" : "default",
              }}
              onClick={() => onPageClick?.(p.page_no)}
            >
              <td style={{ padding: "6px" }}>{p.page_no}</td>
              <td style={{ padding: "6px" }}>
                <StatusDot status={p.status} />
              </td>
              <td style={{ padding: "6px", color: "#94A3B8" }}>
                {p.page_type ?? "—"}
              </td>
              <td style={{ padding: "6px", color: "#94A3B8" }}>
                {p.confidence !== undefined
                  ? `${(p.confidence * 100).toFixed(0)}%`
                  : "—"}
              </td>
              <td style={{ padding: "6px", color: "#94A3B8" }}>
                {p.duration_ms !== undefined
                  ? `${(p.duration_ms / 1000).toFixed(1)}s`
                  : "—"}
              </td>
              <td style={{ padding: "6px", color: "#94A3B8" }}>
                {p.assigned_to ?? "—"}
              </td>
              <td style={{ padding: "6px", color: "#94A3B8" }}>
                {p.sku_count ?? 0}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StatusDot({ status }: { status: string }) {
  const colorMap: Record<string, string> = {
    AI_COMPLETED: "#52C41A",
    HUMAN_COMPLETED: "#1890FF",
    HUMAN_QUEUED: "#FAAD14",
    HUMAN_PROCESSING: "#FAAD14",
    AI_FAILED: "#FF4D4F",
    BLANK: "#434343",
    PENDING: "#262626",
  };
  const color = colorMap[status] ?? "#64748B";

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          backgroundColor: color,
          display: "inline-block",
        }}
      />
      <span style={{ color, fontSize: 11 }}>{status}</span>
    </span>
  );
}

export default PageStatusTable;
