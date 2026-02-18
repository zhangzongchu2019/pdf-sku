/**
 * 标注员表格
 */

export interface AnnotatorRow {
  annotator_id: string;
  name: string;
  current_task?: string | null;
  today_completed: number;
  avg_time_ms: number;
  accuracy: number;
  status: "online" | "offline" | "busy";
}

interface AnnotatorTableProps {
  annotators: AnnotatorRow[];
  onDetail: (id: string) => void;
  onAssign?: (id: string) => void;
}

export function AnnotatorTable({
  annotators,
  onDetail,
  onAssign,
}: AnnotatorTableProps) {
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
            {["姓名", "当前任务", "今日完成", "平均耗时", "准确率", "状态", "操作"].map(
              (h) => (
                <th
                  key={h}
                  style={{
                    padding: "8px 8px",
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
          {annotators.map((a) => (
            <tr
              key={a.annotator_id}
              style={{ borderBottom: "1px solid #2D354866", cursor: "pointer" }}
              onClick={() => onDetail(a.annotator_id)}
            >
              <td style={{ padding: "8px" }}>{a.name}</td>
              <td style={{ padding: "8px", color: "#94A3B8" }}>
                {a.current_task ?? "空闲"}
              </td>
              <td style={{ padding: "8px" }}>{a.today_completed}</td>
              <td style={{ padding: "8px", color: "#94A3B8" }}>
                {(a.avg_time_ms / 1000).toFixed(1)}s
              </td>
              <td style={{ padding: "8px" }}>
                <span
                  style={{
                    color: a.accuracy >= 0.9 ? "#22C55E" : a.accuracy >= 0.7 ? "#F59E0B" : "#EF4444",
                  }}
                >
                  {(a.accuracy * 100).toFixed(1)}%
                </span>
              </td>
              <td style={{ padding: "8px" }}>
                <StatusDot status={a.status} />
              </td>
              <td style={{ padding: "8px" }}>
                <div style={{ display: "flex", gap: 4 }}>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDetail(a.annotator_id);
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
                  {onAssign && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onAssign(a.annotator_id);
                      }}
                      style={{
                        padding: "3px 8px",
                        background: "none",
                        border: "1px solid #22D3EE44",
                        borderRadius: 3,
                        color: "#22D3EE",
                        cursor: "pointer",
                        fontSize: 11,
                      }}
                    >
                      分配
                    </button>
                  )}
                </div>
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
    online: "#22C55E",
    busy: "#F59E0B",
    offline: "#64748B",
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
        }}
      />
      <span style={{ color, fontSize: 11 }}>{status}</span>
    </span>
  );
}

export default AnnotatorTable;
