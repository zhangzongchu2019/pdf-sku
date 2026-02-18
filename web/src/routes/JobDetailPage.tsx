import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useJobStore } from "../stores/jobStore";
import { useSSEStore } from "../stores/sseStore";
import StatusBadge from "../components/common/StatusBadge";
import Loading from "../components/common/Loading";
import { PageHeatmap } from "../components/dashboard/PageHeatmap";
import { EvaluationCard } from "../components/dashboard/EvaluationCard";
import { PrescanCard } from "../components/dashboard/PrescanCard";
import { SKUList } from "../components/dashboard/SKUList";
import { TimelineDrawer } from "../components/dashboard/TimelineDrawer";
import { formatDate, formatPercent } from "../utils/format";
import type { PageHeatmapCell } from "../components/dashboard/PageHeatmap";

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const { currentJob, pages, skus, fetchJob, fetchPages, fetchSkus, loading } = useJobStore();
  const { connect, disconnect, onEvent } = useSSEStore();
  const [selectedPage, setSelectedPage] = useState<number | null>(null);
  const [tab, setTab] = useState<"pages" | "skus" | "heatmap" | "eval">("pages");
  const [showTimeline, setShowTimeline] = useState(false);

  useEffect(() => {
    if (!jobId) return;
    fetchJob(jobId);
    fetchPages(jobId);
    connect(jobId);

    const unsub = onEvent((e) => {
      if (e.data.job_id === jobId) {
        fetchJob(jobId);
        fetchPages(jobId);
      }
    });

    return () => { disconnect(); unsub(); };
  }, [jobId]);

  useEffect(() => {
    if (jobId && selectedPage !== null) {
      fetchSkus(jobId, selectedPage);
    } else if (jobId && tab === "skus") {
      fetchSkus(jobId);
    }
  }, [jobId, selectedPage, tab]);

  if (loading && !currentJob) return <Loading />;
  if (!currentJob) return <div className="page"><h2>Job 不存在</h2></div>;

  const job = currentJob;
  const completedPages = pages.filter((p) =>
    ["AI_COMPLETED", "HUMAN_COMPLETED", "IMPORTED_CONFIRMED", "IMPORTED_ASSUMED", "BLANK"].includes(p.status)
  ).length;
  const progress = job.total_pages > 0 ? completedPages / job.total_pages : 0;

  return (
    <div className="page job-detail-page">
      <div className="page-header">
        <div>
          <Link to="/jobs" className="back-link">← 返回列表</Link>
          <h2>{job.source_file}</h2>
        </div>
        <StatusBadge status={job.user_status} />
      </div>

      <div className="job-meta">
        <div className="meta-item"><label>Job ID</label><span>{job.job_id}</span></div>
        <div className="meta-item"><label>商户</label><span>{job.merchant_id}</span></div>
        <div className="meta-item"><label>路由</label><span>{job.route || "-"}</span></div>
        <div className="meta-item"><label>页数</label><span>{job.total_pages}</span></div>
        <div className="meta-item"><label>SKU</label><span>{job.total_skus}</span></div>
        <div className="meta-item"><label>创建</label><span>{formatDate(job.created_at)}</span></div>
      </div>

      <div className="progress-section">
        <div className="progress-header">
          <span>处理进度</span>
          <span>{formatPercent(progress)} ({completedPages}/{job.total_pages})</span>
        </div>
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${progress * 100}%` }} />
        </div>
      </div>

      <div className="tab-bar" style={{ display: "flex", gap: 4, marginBottom: 16 }}>
        <button className={`tab ${tab === "pages" ? "active" : ""}`} onClick={() => setTab("pages")}>
          页面 ({pages.length})
        </button>
        <button className={`tab ${tab === "skus" ? "active" : ""}`} onClick={() => { setTab("skus"); setSelectedPage(null); }}>
          SKU ({skus.length})
        </button>
        <button className={`tab ${tab === "heatmap" ? "active" : ""}`} onClick={() => setTab("heatmap")}>
          热力图
        </button>
        <button className={`tab ${tab === "eval" ? "active" : ""}`} onClick={() => setTab("eval")}>
          评估
        </button>
        <div style={{ flex: 1 }} />
        <button
          onClick={() => setShowTimeline(true)}
          style={{ padding: "4px 12px", backgroundColor: "transparent", border: "1px solid #2D3548", borderRadius: 4, color: "#94A3B8", cursor: "pointer", fontSize: 12 }}
        >
          📅 时间线
        </button>
      </div>

      {tab === "pages" && (
        <table className="data-table">
          <thead>
            <tr>
              <th>页码</th><th>状态</th><th>类型</th><th>SKU数</th>
              <th>置信度</th><th>提取方式</th><th>LLM模型</th>
            </tr>
          </thead>
          <tbody>
            {pages.map((p) => (
              <tr key={p.id} className={selectedPage === p.page_number ? "selected" : ""}
                  onClick={() => setSelectedPage(p.page_number)}>
                <td>{p.page_number}</td>
                <td><StatusBadge status={p.status} /></td>
                <td>{p.page_type || "-"}</td>
                <td>{p.sku_count}</td>
                <td>{p.page_confidence ? formatPercent(p.page_confidence) : "-"}</td>
                <td>{p.extraction_method || "-"}</td>
                <td>{p.llm_model_used || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === "skus" && (
        <SKUList skus={skus} />
      )}

      {tab === "heatmap" && (
        <div style={{ backgroundColor: "#1B2233", border: "1px solid #2D3548", borderRadius: 8, padding: 16 }}>
          <PageHeatmap
            pages={pages.map((p): PageHeatmapCell => ({
              page_no: p.page_number,
              status: p.status,
              confidence: p.page_confidence ?? undefined,
              page_type: p.page_type ?? undefined,
            }))}
            onPageClick={(pageNum) => {
              setSelectedPage(pageNum);
              setTab("pages");
            }}
          />
        </div>
      )}

      {tab === "eval" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <EvaluationCard />
          <PrescanCard />
        </div>
      )}

      {/* Timeline drawer */}
      {showTimeline && (
        <TimelineDrawer
          visible={true}
          title={`Job ${job.job_id} 时间线`}
          events={[]}
          onClose={() => setShowTimeline(false)}
        />
      )}
    </div>
  );
}
