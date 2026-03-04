import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useJobStore } from "../stores/jobStore";
import { jobsApi } from "../api/jobs";
import StatusBadge from "../components/common/StatusBadge";
import Pagination from "../components/common/Pagination";
import Loading from "../components/common/Loading";
import EmptyState from "../components/common/EmptyState";
import { formatDate } from "../utils/format";

const STATUSES = ["", "PROCESSING", "COMPLETED", "PARTIAL", "FAILED", "CANCELLED"];

export default function JobListPage() {
  const { jobs, total, loading, fetchJobs, cancelJob, deleteJob } = useJobStore();
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const [reprocessingId, setReprocessingId] = useState<string | null>(null);

  const handleReprocess = async (jobId: string) => {
    if (reprocessingId) return;
    if (!window.confirm("确认重新分析该 PDF？将清空现有 SKU 和图片数据后重新提取。")) return;
    setReprocessingId(jobId);
    try {
      await jobsApi.reprocessAI(jobId);
      await fetchJobs({ status: filter || undefined, page });
    } catch (e) {
      console.error("重新分析失败:", e);
      alert("重新分析失败，请稍后重试");
    } finally {
      setReprocessingId(null);
    }
  };

  useEffect(() => {
    fetchJobs({ status: filter || undefined, page });
  }, [filter, page]);

  return (
    <div className="page">
      <div className="page-header">
        <h2>任务列表</h2>
        <Link to="/upload" className="btn btn-primary">+ 新建任务</Link>
      </div>

      <div className="filter-bar">
        {STATUSES.map((s) => (
          <button key={s} className={`btn btn-filter ${filter === s ? "active" : ""}`}
                  onClick={() => { setFilter(s); setPage(1); }}>
            {s || "全部"}
          </button>
        ))}
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
                <th>商户</th>
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
                  <td><Link to={`/jobs/${job.job_id}`} className="link">{job.job_id.slice(0, 8)}...</Link></td>
                  <td className="td-ellipsis">{job.source_file}</td>
                  <td>{job.merchant_id}</td>
                  <td><StatusBadge status={job.user_status} /></td>
                  <td>{job.total_pages}</td>
                  <td>{job.total_skus}</td>
                  <td>{formatDate(job.created_at)}</td>
                  <td>
                    {job.user_status === "PROCESSING" && (
                      <button className="btn btn-text btn-sm" onClick={() => cancelJob(job.job_id)}>取消</button>
                    )}
                    {job.user_status === "FAILED" && (
                      <button className="btn btn-text btn-sm" onClick={() => useJobStore.getState().retryJob(job.job_id)}>重试</button>
                    )}
                    <button
                      className="btn btn-text btn-sm"
                      style={{ marginLeft: 4, color: "#60A5FA" }}
                      disabled={reprocessingId === job.job_id}
                      onClick={() => handleReprocess(job.job_id)}
                    >
                      {reprocessingId === job.job_id ? "⏳" : "🔄 重新分析"}
                    </button>
                    <button
                      className="btn btn-danger btn-sm"
                      style={{ marginLeft: 4 }}
                      onClick={async () => {
                        if (!window.confirm("确认删除该任务？将同时删除关联页面/SKU/标注数据，且不可恢复")) return;
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
