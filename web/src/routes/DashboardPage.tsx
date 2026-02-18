import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useJobStore } from "../stores/jobStore";
import { useSSEStore } from "../stores/sseStore";
import MetricsCard from "../components/dashboard/MetricsCard";
import { TrendChart } from "../components/dashboard/TrendChart";
import { RouteChart } from "../components/dashboard/RouteChart";
import { JobTable } from "../components/dashboard/JobTable";
import { BatchActionBar } from "../components/dashboard/BatchActionBar";
import Loading from "../components/common/Loading";
import { formatPercent } from "../utils/format";
import { opsApi } from "../api/ops";
import type { Job } from "../types/models";

export default function DashboardPage() {
  const { dashboard, fetchDashboard, loading } = useJobStore();
  const { connect, disconnect } = useSSEStore();
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const fetchJobs = useCallback(async () => {
    try {
      const res = await import("../api/jobs").then((m) => m.jobsApi.list({ page: 1, size: 20 }));
      setJobs(res.items);
    } catch {
      // handle
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
    fetchJobs();
    connect("__dashboard__");
    const timer = setInterval(fetchDashboard, 30000);
    return () => { clearInterval(timer); disconnect(); };
  }, [fetchDashboard, fetchJobs, connect, disconnect]);

  if (loading && !dashboard) return <Loading />;

  const d = dashboard;

  /* Trend chart data (future API extension, currently empty) */
  const trendData: { date: string; auto: number; hybrid: number; human: number; failed: number }[] = [];
  const routeData: { name: string; value: number; color: string }[] = [];

  const handleBatchRetry = async () => {
    if (selectedIds.size === 0) return;
    await opsApi.batchRetry(Array.from(selectedIds));
    setSelectedIds(new Set());
    fetchJobs();
  };
  const handleBatchCancel = async () => {
    if (selectedIds.size === 0) return;
    await opsApi.batchCancel(Array.from(selectedIds));
    setSelectedIds(new Set());
    fetchJobs();
  };

  return (
    <div className="page dashboard-page" style={{ padding: 24 }}>
      <h2 style={{ margin: "0 0 20px", fontSize: 20, color: "#E2E8F4" }}>系统仪表盘</h2>

      {/* Metrics summary */}
      <div className="metrics-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, marginBottom: 24 }}>
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
        <MetricsCard title="活跃 Job" value={d?.job_stats.active ?? 0} color="#fa8c16" />
        <MetricsCard
          title="标注队列深度"
          value={d?.task_stats.queue_depth ?? 0}
          subtitle={`SLA 健康度: ${formatPercent(d?.task_stats.sla_health ?? 0)}`}
          color="#eb2f96"
        />
      </div>

      {/* Charts row */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16, marginBottom: 24 }}>
        <div style={{ backgroundColor: "#1B2233", border: "1px solid #2D3548", borderRadius: 8, padding: 16 }}>
          <h3 style={{ margin: "0 0 12px", fontSize: 14, color: "#94A3B8" }}>14天趋势</h3>
          <TrendChart data={trendData} />
        </div>
        <div style={{ backgroundColor: "#1B2233", border: "1px solid #2D3548", borderRadius: 8, padding: 16 }}>
          <h3 style={{ margin: "0 0 12px", fontSize: 14, color: "#94A3B8" }}>路由分布</h3>
          <RouteChart data={routeData} />
        </div>
      </div>

      {/* Batch action bar */}
      {selectedIds.size > 0 && (
        <BatchActionBar
          selectedCount={selectedIds.size}
          onBatchRetry={handleBatchRetry}
          onBatchCancel={handleBatchCancel}
          onBatchAssign={() => {}}
          onExportCSV={() => {}}
          onClear={() => setSelectedIds(new Set())}
        />
      )}

      {/* Job table */}
      <div style={{ backgroundColor: "#1B2233", border: "1px solid #2D3548", borderRadius: 8, padding: 16 }}>
        <h3 style={{ margin: "0 0 12px", fontSize: 14, color: "#94A3B8" }}>Job 列表</h3>
        <JobTable
          jobs={jobs}
          selectedIds={selectedIds}
          onSelect={(id, checked) => {
            setSelectedIds((prev) => {
              const next = new Set(prev);
              checked ? next.add(id) : next.delete(id);
              return next;
            });
          }}
          onSelectAll={(checked) => {
            setSelectedIds(checked ? new Set(jobs.map((j) => j.job_id)) : new Set());
          }}
          onJobClick={(id) => navigate(`/jobs/${id}`)}
        />
      </div>
    </div>
  );
}
