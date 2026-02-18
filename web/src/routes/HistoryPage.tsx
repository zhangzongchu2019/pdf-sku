/**
 * 历史任务页 /annotate/history
 */
import { useState, useEffect, useCallback } from "react";
import { tasksApi } from "../api/tasks";
import Pagination from "../components/common/Pagination";
import type { HumanTask } from "../types/models";

export default function HistoryPage() {
  const [tasks, setTasks] = useState<HumanTask[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const pageSize = 20;

  const fetchHistory = useCallback(async () => {
    try {
      setLoading(true);
      const res = await tasksApi.list({ page, status: "COMPLETED" });
      setTasks(res.items);
      setTotal(res.total);
    } catch {
      // handle
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => { fetchHistory(); }, [fetchHistory]);

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: "0 auto" }}>
      <h2 style={{ margin: "0 0 20px", fontSize: 18, color: "#E2E8F4" }}>
        历史任务
      </h2>

      {loading ? (
        <div style={{ color: "#64748B" }}>加载中…</div>
      ) : tasks.length === 0 ? (
        <div style={{ color: "#64748B" }}>暂无历史任务</div>
      ) : (
        <>
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
                {["任务ID", "Job", "页码", "类型", "完成时间"].map((h) => (
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
              {tasks.map((t) => (
                <tr key={t.task_id} style={{ borderBottom: "1px solid #2D354866" }}>
                  <td style={{ padding: "8px" }}>{t.task_id.slice(0, 8)}</td>
                  <td style={{ padding: "8px", color: "#94A3B8" }}>
                    {t.job_id.slice(0, 8)}
                  </td>
                  <td style={{ padding: "8px", color: "#94A3B8" }}>
                    {t.page_number}
                  </td>
                  <td style={{ padding: "8px", color: "#94A3B8" }}>
                    {t.task_type}
                  </td>
                  <td style={{ padding: "8px", color: "#94A3B8" }}>
                    {t.completed_at ? new Date(t.completed_at).toLocaleString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: 16 }}>
            <Pagination
              current={page}
              total={total}
              pageSize={pageSize}
              onChange={setPage}
            />
          </div>
        </>
      )}
    </div>
  );
}
