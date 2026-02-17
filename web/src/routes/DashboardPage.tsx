import { useEffect } from "react";
import { useJobStore } from "../stores/jobStore";
import { useSSEStore } from "../stores/sseStore";
import MetricsCard from "../components/dashboard/MetricsCard";
import Loading from "../components/common/Loading";
import { formatPercent } from "../utils/format";

export default function DashboardPage() {
  const { dashboard, fetchDashboard, loading } = useJobStore();
  const { connect, disconnect } = useSSEStore();

  useEffect(() => {
    fetchDashboard();
    connect();
    const timer = setInterval(fetchDashboard, 30000);
    return () => { clearInterval(timer); disconnect(); };
  }, []);

  if (loading && !dashboard) return <Loading />;

  const d = dashboard;

  return (
    <div className="page dashboard-page">
      <h2>系统仪表盘</h2>

      <div className="metrics-grid">
        <MetricsCard title="今日 Job" value={d?.today_jobs ?? 0} color="#1890ff" />
        <MetricsCard title="今日 SKU" value={d?.today_skus ?? 0} color="#52c41a" />
        <MetricsCard
          title="页面完成率"
          value={formatPercent(d?.page_stats.completion_rate ?? 0)}
          color="#722ed1"
        />
        <MetricsCard
          title="导入成功率"
          value={formatPercent(d?.import_stats.success_rate ?? 0)}
          color="#13c2c2"
        />
      </div>

      <div className="metrics-grid">
        <MetricsCard title="活跃 Job" value={d?.job_stats.active ?? 0} color="#fa8c16" />
        <MetricsCard title="已完成 Job" value={d?.job_stats.completed ?? 0} color="#52c41a" />
        <MetricsCard
          title="标注队列深度"
          value={d?.task_stats.queue_depth ?? 0}
          subtitle={`SLA 健康度: ${formatPercent(d?.task_stats.sla_health ?? 0)}`}
          color="#eb2f96"
        />
        <MetricsCard
          title="待审批校准"
          value={d?.calibration_stats.pending_approvals ?? 0}
          color="#faad14"
        />
      </div>

      {d?.job_stats.by_status && (
        <div className="card">
          <h3>Job 状态分布</h3>
          <div className="status-distribution">
            {Object.entries(d.job_stats.by_status).map(([status, count]) => (
              <div key={status} className="status-bar-item">
                <span className="status-label">{status}</span>
                <div className="status-bar">
                  <div
                    className="status-bar-fill"
                    style={{
                      width: `${Math.max(2, (count / Math.max(1, d.job_stats.total)) * 100)}%`,
                    }}
                  />
                </div>
                <span className="status-count">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
