/**
 * 商家Jobs页
 */
import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { opsApi } from "../api/ops";
import { jobsApi } from "../api/jobs";
import Pagination from "../components/common/Pagination";
import type { MerchantStats, Job } from "../types/models";

const STATUS_COLORS: Record<string, string> = {
  processing: "#3B82F6",
  completed: "#10B981",
  failed: "#EF4444",
  cancelled: "#6B7280",
  queued: "#F59E0B",
};

export default function MerchantJobsPage() {
  const { merchantId } = useParams<{ merchantId: string }>();
  const navigate = useNavigate();
  const [stats, setStats] = useState<MerchantStats | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobTotal, setJobTotal] = useState(0);
  const [jobPage, setJobPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [jobsLoading, setJobsLoading] = useState(true);
  const pageSize = 20;

  const fetchStats = useCallback(async () => {
    if (!merchantId) return;
    try {
      setLoading(true);
      const data = await opsApi.getMerchantStats(merchantId);
      setStats(data);
    } catch {
      // handle
    } finally {
      setLoading(false);
    }
  }, [merchantId]);

  const fetchJobs = useCallback(async () => {
    if (!merchantId) return;
    try {
      setJobsLoading(true);
      const res = await jobsApi.list({ merchantId, page: jobPage, size: pageSize });
      setJobs(res.items);
      setJobTotal(res.total);
    } catch {
      // handle
    } finally {
      setJobsLoading(false);
    }
  }, [merchantId, jobPage]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  if (loading) {
    return <div style={{ padding: 24, color: "#64748B" }}>加载中…</div>;
  }

  if (!stats) {
    return <div style={{ padding: 24, color: "#64748B" }}>未找到商家信息</div>;
  }

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <h2 style={{ margin: "0 0 20px", fontSize: 18, color: "#E2E8F4" }}>
        商家 {merchantId}
      </h2>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 12,
          marginBottom: 24,
        }}
      >
        <StatCard label="总Job数" value={stats.total_jobs} />
        <StatCard label="总SKU数" value={stats.total_skus} />
        <StatCard label="成功率" value={`${(stats.success_rate * 100).toFixed(1)}%`} />
        <StatCard label="平均处理时间" value={`${(stats.avg_process_time / 1000).toFixed(1)}s`} />
      </div>

      {/* Job 列表 */}
      <h3 style={{ margin: "0 0 12px", fontSize: 14, color: "#94A3B8" }}>
        Job 列表
      </h3>

      {jobsLoading ? (
        <div style={{ color: "#64748B" }}>加载中…</div>
      ) : jobs.length === 0 ? (
        <div style={{ color: "#64748B", fontSize: 13 }}>暂无 Job</div>
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
                {["Job ID", "文件", "状态", "总页数", "SKU数", "创建时间"].map((h) => (
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
              {jobs.map((j) => (
                <tr
                  key={j.job_id}
                  style={{ borderBottom: "1px solid #2D354866", cursor: "pointer" }}
                  onClick={() => navigate(`/jobs/${j.job_id}`)}
                >
                  <td style={{ padding: "8px", fontFamily: "monospace" }}>
                    {j.job_id.slice(0, 8)}
                  </td>
                  <td style={{ padding: "8px", color: "#94A3B8", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {j.source_file}
                  </td>
                  <td style={{ padding: "8px" }}>
                    <span
                      style={{
                        display: "inline-block",
                        padding: "2px 8px",
                        borderRadius: 4,
                        fontSize: 11,
                        color: STATUS_COLORS[j.user_status] ?? "#94A3B8",
                        backgroundColor: (STATUS_COLORS[j.user_status] ?? "#94A3B8") + "18",
                      }}
                    >
                      {j.user_status}
                    </span>
                  </td>
                  <td style={{ padding: "8px", color: "#94A3B8" }}>{j.total_pages}</td>
                  <td style={{ padding: "8px", color: "#94A3B8" }}>{j.total_skus}</td>
                  <td style={{ padding: "8px", color: "#94A3B8" }}>
                    {new Date(j.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: 16 }}>
            <Pagination
              current={jobPage}
              total={jobTotal}
              pageSize={pageSize}
              onChange={setJobPage}
            />
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div
      style={{
        padding: 16,
        backgroundColor: "#1B2233",
        border: "1px solid #2D3548",
        borderRadius: 8,
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: 11, color: "#64748B", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: "#E2E8F4" }}>{value}</div>
    </div>
  );
}
