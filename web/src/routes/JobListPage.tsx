import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useJobStore } from "../stores/jobStore";
import StatusBadge from "../components/common/StatusBadge";
import Pagination from "../components/common/Pagination";
import Loading from "../components/common/Loading";
import EmptyState from "../components/common/EmptyState";
import { formatDate } from "../utils/format";

/** 可重试状态：仅限明确的失败/降级态 */
const RETRYABLE = new Set([
  "DEGRADED_HUMAN", "EVAL_FAILED", "ORPHANED",
  "PARTIAL_FAILED", "CANCELLED", "REJECTED",
]);

export default function JobListPage() {
  const { jobs, total, loading, fetchJobs, deleteJob, retryJob } = useJobStore();
  const [page, setPage] = useState(1);
  const [retryingId, setRetryingId] = useState<string | null>(null);

  useEffect(() => {
    fetchJobs({ page });
  }, [page]);

  return (
    <div className="page">
      <div className="page-header">
        <h2>任务列表</h2>
        <Link to="/upload" className="btn btn-primary">+ 新建任务</Link>
      </div>

      {loading ? <Loading /> : jobs.length === 0 ? (
        <EmptyState icon="📋" title="暂无任务" description="上传 PDF 开始处理" />
      ) : (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>Job ID</th>
                <th>文件</th>
                <th>状态</th>
                <th>页数</th>
                <th>SKU</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.job_id}>
                  <td>
                    <Link to={`/jobs/${job.job_id}`} className="link">
                      {job.job_id.slice(0, 8)}...
                    </Link>
                  </td>
                  <td className="td-ellipsis">{job.source_file}</td>
                  <td><StatusBadge status={job.user_status} /></td>
                  <td>{job.total_pages}</td>
                  <td>{job.total_skus}</td>
                  <td>{formatDate(job.created_at)}</td>
                  <td style={{ display: "flex", gap: 4, alignItems: "center" }}>
                    {RETRYABLE.has(job.status) && retryingId !== job.job_id && (
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={async (e) => {
                          e.preventDefault();
                          setRetryingId(job.job_id);
                          try {
                            await retryJob(job.job_id);
                            await fetchJobs({ page });
                          } catch { /* ignore */ }
                          setRetryingId(null);
                        }}
                      >
                        重试
                      </button>
                    )}
                    {retryingId === job.job_id && (
                      <span style={{ fontSize: 12, color: "#1890ff" }}>重试中...</span>
                    )}
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={async () => {
                        if (!window.confirm("确认删除该任务？")) return;
                        await deleteJob(job.job_id);
                      }}
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
