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
   const [selected, setSelected] = useState<string[]>([]);
  const pageSize = 20;

  const fetchHistory = useCallback(async () => {
    try {
      setLoading(true);
      const res = await tasksApi.list({ page, status: "COMPLETED" });
      setTasks(res.items);
      setTotal(res.total);
      setSelected([]);
    } catch {
      // handle
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => { fetchHistory(); }, [fetchHistory]);

  const handleDelete = async (taskId: string) => {
    if (!window.confirm("确认删除该任务？此操作不可恢复")) return;
    await tasksApi.delete(taskId);
    fetchHistory();
  };

  const handleBatchDelete = async () => {
    if (selected.length === 0) return;
    if (!window.confirm(`确认删除 ${selected.length} 个任务？此操作不可恢复`)) return;
    await tasksApi.batchDelete(selected);
    fetchHistory();
  };

  const toggleSelect = (taskId: string) => {
    setSelected((prev) =>
      prev.includes(taskId)
        ? prev.filter((id) => id !== taskId)
        : [...prev, taskId]
    );
  };

  const toggleSelectAll = (checked: boolean) => {
    if (checked) setSelected(tasks.map((t) => t.task_id));
    else setSelected([]);
  };

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: "0 auto" }}>
      <h2 style={{ margin: "0 0 20px", fontSize: 18, color: "#E2E8F4" }}>
        历史任务
      </h2>

      <div style={{ marginBottom: 12, display: "flex", gap: 8 }}>
        <button
          className="btn"
          onClick={handleBatchDelete}
          disabled={selected.length === 0}
        >
          批量删除
        </button>
        <span style={{ color: "#94A3B8", fontSize: 12 }}>
          已选 {selected.length} 个
        </span>
      </div>

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
                <th
                  style={{
                    padding: "8px",
                    textAlign: "left",
                    color: "#64748B",
                    fontWeight: 500,
                    fontSize: 11,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={selected.length > 0 && selected.length === tasks.length}
                    onChange={(e) => toggleSelectAll(e.target.checked)}
                  />
                </th>
                {["任务ID", "Job", "页码", "类型", "完成时间", "操作"].map((h) => (
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
                  <td style={{ padding: "8px" }}>
                    <input
                      type="checkbox"
                      checked={selected.includes(t.task_id)}
                      onChange={() => toggleSelect(t.task_id)}
                    />
                  </td>
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
                  <td style={{ padding: "8px" }}>
                    <button className="btn btn-danger btn-sm" onClick={() => handleDelete(t.task_id)}>
                      删除
                    </button>
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
