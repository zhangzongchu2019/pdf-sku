import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useJobStore } from "../stores/jobStore";
import StatusBadge from "../components/common/StatusBadge";
import Pagination from "../components/common/Pagination";
import Loading from "../components/common/Loading";
import EmptyState from "../components/common/EmptyState";
import { formatDate } from "../utils/format";
import { JobStatus } from "../types/enums";

const STATUS_FILTERS = [
  { value: "", label: "全部" },
  { value: JobStatus.PROCESSING, label: "处理中" },
  { value: JobStatus.PARTIAL_SUCCESS, label: "部分完成" },
  { value: JobStatus.COMPLETED, label: "已完成" },
  { value: JobStatus.NEEDS_MANUAL, label: "需人工处理" },
  { value: JobStatus.FAILED, label: "失败" },
] as const;

export default function JobListPage() {
  const { jobs, total, loading, fetchJobs, cancelJob, deleteJob } = useJobStore();
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);

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
        {STATUS_FILTERS.map(({ value, label }) => (
          <button key={value || "all"} className={`btn btn-filter ${filter === value ? "active" : ""}`}
                  onClick={() => { setFilter(value); setPage(1); }}>
            {label}
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
                    {job.user_status === JobStatus.PROCESSING && (
                      <button className="btn btn-text btn-sm" onClick={() => cancelJob(job.job_id)}>取消</button>
                    )}
                    {job.user_status === JobStatus.FAILED && (
                      <button className="btn btn-text btn-sm" onClick={() => useJobStore.getState().retryJob(job.job_id)}>重试</button>
                    )}
                    <button
                      className="btn btn-danger btn-sm"
                      style={{ marginLeft: 8 }}
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
