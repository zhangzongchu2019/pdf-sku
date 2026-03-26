import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { tasksApi } from "../api/tasks";
import { useAnnotationStore } from "../stores/annotationStore";
import { useSettingsStore } from "../stores/settingsStore";
import { useNotificationStore } from "../stores/notificationStore";
import StatusBadge from "../components/common/StatusBadge";
import Pagination from "../components/common/Pagination";
import Loading from "../components/common/Loading";
import EmptyState from "../components/common/EmptyState";
import EditableSkuGrid from "../components/tasks/EditableSkuGrid";
import { formatDate } from "../utils/format";
import { TaskStatus } from "../types/enums";
import type { HumanTask } from "../types/models";

const STATUS_FILTERS = [
  { value: "", label: "全部" },
  { value: TaskStatus.CREATED, label: "待处理" },
  { value: TaskStatus.PROCESSING, label: "处理中" },
  { value: TaskStatus.COMPLETED, label: "已完成" },
  { value: TaskStatus.SKIPPED, label: "已作废" },
  { value: TaskStatus.ESCALATED, label: "已升级" },
] as const;

export default function TaskListPage() {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<HumanTask[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string[]>([]);
  const [hideSkipped, setHideSkipped] = useState(true);

  const annotatorId = useSettingsStore((s) => s.annotatorId);
  const setAnnotatorId = useSettingsStore((s) => s.setAnnotatorId);
  const acquireTask = useAnnotationStore((s) => s.acquireTask);
  const notify = useNotificationStore((s) => s.add);

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const res = await tasksApi.list({ status: filter || undefined, page });
      const filtered = hideSkipped && !filter
        ? res.items.filter((t) => t.status !== TaskStatus.SKIPPED)
        : res.items;
      setTasks(filtered);
      setTotal(res.total); // 保持后端分页总数，避免分页跳页失真
      setSelected([]);
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
    setLoading(false);
  };

  useEffect(() => { fetchTasks(); }, [filter, page, hideSkipped]);

  const handleAcquire = async () => {
    if (!annotatorId) {
      notify({ type: "error", message: "请先设置标注员 ID" });
      return;
    }
    try {
      const task = await acquireTask(annotatorId);
      if (task) {
        navigate(`/annotate/${task.task_id}`);
      } else {
        notify({ type: "info", message: "当前无可领取任务" });
      }
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
  };

  const handleDelete = async (taskId: string) => {
    if (!window.confirm("确认删除该任务？此操作不可恢复")) return;
    try {
      await tasksApi.delete(taskId);
      notify({ type: "success", message: "已删除该任务" });
      fetchTasks();
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
  };

  const handleBatchSkip = async () => {
    if (selected.length === 0) return;
    if (!window.confirm(`确认删除 ${selected.length} 个任务？此操作不可恢复`)) return;
    try {
      await tasksApi.batchDelete(selected);
      notify({ type: "success", message: `已删除 ${selected.length} 个任务` });
      fetchTasks();
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
  };

  const toggleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelected(tasks.map((t) => t.task_id));
    } else {
      setSelected([]);
    }
  };

  const toggleSelect = (taskId: string) => {
    setSelected((prev) =>
      prev.includes(taskId)
        ? prev.filter((id) => id !== taskId)
        : [...prev, taskId]
    );
  };

  return (
    <div className="page">
      <div className="page-header">
        <h2>标注任务队列</h2>
        <div className="header-actions">
          <input className="input input-sm" placeholder="标注员 ID"
                 value={annotatorId} onChange={(e) => setAnnotatorId(e.target.value)} />
          <button className="btn btn-primary" onClick={handleAcquire}>
            领取下一个任务
          </button>
          <button className="btn" onClick={handleBatchSkip} disabled={selected.length === 0}>
            批量删除
          </button>
        </div>
      </div>

      <div className="filter-bar">
        <label className="checkbox">
          <input
            type="checkbox"
            checked={hideSkipped && !filter}
            onChange={(e) => {
              setHideSkipped(e.target.checked);
              setPage(1);
            }}
          />
          隐藏作废（默认）
        </label>
        <span className="text-muted">当前显示 {tasks.length} 条</span>
        {STATUS_FILTERS.map(({ value, label }) => (
          <button key={value || "all"} className={`btn btn-filter ${filter === value ? "active" : ""}`}
                  onClick={() => { setFilter(value); setPage(1); }}>
            {label}
          </button>
        ))}
      </div>

      {loading ? <Loading /> : tasks.length === 0 ? (
        <EmptyState icon="✏️" title="暂无任务" />
      ) : (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
                    checked={selected.length > 0 && selected.length === tasks.length}
                    onChange={(e) => toggleSelectAll(e.target.checked)}
                  />
                </th>
                <th>Task ID</th><th>Job ID</th><th>页码</th><th>类型</th>
                <th>SKU 信息</th><th>状态</th><th>优先级</th><th>分配</th><th>超时</th><th>创建</th><th>操作</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((t) => (
                <tr key={t.task_id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selected.includes(t.task_id)}
                      onChange={() => toggleSelect(t.task_id)}
                    />
                  </td>
                  <td className="td-mono">{t.task_id.slice(0, 8)}...</td>
                  <td className="td-mono">{t.job_id.slice(0, 8)}...</td>
                  <td>{t.page_number}</td>
                  <td>{t.task_type}</td>
                  <td className="task-sku-cell">
                    <EditableSkuGrid task={t} />
                  </td>
                  <td><StatusBadge status={t.status} /></td>
                  <td><span className={`priority priority-${t.priority.toLowerCase()}`}>{t.priority}</span></td>
                  <td>{t.assigned_to || "-"}</td>
                  <td>{formatDate(t.timeout_at)}</td>
                  <td>{formatDate(t.created_at)}</td>
                  <td>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => handleDelete(t.task_id)}
                    >
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination current={page} total={total} pageSize={20} onChange={setPage} />
        </>
      )}
    </div>
  );
}
