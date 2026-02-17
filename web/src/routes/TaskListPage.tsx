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
import { formatDate } from "../utils/format";
import type { HumanTask } from "../types/models";

const STATUSES = ["", "CREATED", "LOCKED", "COMPLETED", "SKIPPED", "ESCALATED"];

export default function TaskListPage() {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<HumanTask[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);

  const annotatorId = useSettingsStore((s) => s.annotatorId);
  const setAnnotatorId = useSettingsStore((s) => s.setAnnotatorId);
  const acquireTask = useAnnotationStore((s) => s.acquireTask);
  const notify = useNotificationStore((s) => s.add);

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const res = await tasksApi.list({ status: filter || undefined, page });
      setTasks(res.items);
      setTotal(res.total);
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
    setLoading(false);
  };

  useEffect(() => { fetchTasks(); }, [filter, page]);

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
        </div>
      </div>

      <div className="filter-bar">
        {STATUSES.map((s) => (
          <button key={s} className={`btn btn-filter ${filter === s ? "active" : ""}`}
                  onClick={() => { setFilter(s); setPage(1); }}>
            {s || "全部"}
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
                <th>Task ID</th><th>Job ID</th><th>页码</th><th>类型</th>
                <th>状态</th><th>优先级</th><th>分配</th><th>超时</th><th>创建</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((t) => (
                <tr key={t.task_id}>
                  <td className="td-mono">{t.task_id.slice(0, 8)}...</td>
                  <td className="td-mono">{t.job_id.slice(0, 8)}...</td>
                  <td>{t.page_number}</td>
                  <td>{t.task_type}</td>
                  <td><StatusBadge status={t.status} /></td>
                  <td><span className={`priority priority-${t.priority.toLowerCase()}`}>{t.priority}</span></td>
                  <td>{t.assigned_to || "-"}</td>
                  <td>{formatDate(t.timeout_at)}</td>
                  <td>{formatDate(t.created_at)}</td>
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
