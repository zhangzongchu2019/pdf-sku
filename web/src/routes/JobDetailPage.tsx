import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useJobStore } from "../stores/jobStore";
import { useSSEStore } from "../stores/sseStore";
import { jobsApi } from "../api/jobs";
import type { PageDetail } from "../api/jobs";
import StatusBadge from "../components/common/StatusBadge";
import Loading from "../components/common/Loading";
import { PageHeatmap } from "../components/dashboard/PageHeatmap";
import { EvaluationCard } from "../components/dashboard/EvaluationCard";
import { PrescanCard } from "../components/dashboard/PrescanCard";
import { SKUList } from "../components/dashboard/SKUList";
import { TimelineDrawer } from "../components/dashboard/TimelineDrawer";
import { formatDate, formatPercent } from "../utils/format";
import type { PageHeatmapCell } from "../components/dashboard/PageHeatmap";
import type { PageDetailSKU } from "../api/jobs";

function buildSkuImageUrls(
  sku: Pick<PageDetailSKU, "images" | "image_paths">,
  fallbackImageUrl: (imageId: string) => string,
) {
  const urls: string[] = [];

  for (const img of sku.images || []) {
    const url = img.image_url || fallbackImageUrl(img.image_id);
    if (url && !urls.includes(url)) {
      urls.push(url);
    }
  }

  for (const url of sku.image_paths || []) {
    if (url && !urls.includes(url)) {
      urls.push(url);
    }
  }

  return urls;
}

function skuPrimaryText(sku: Pick<PageDetailSKU, "sku_id" | "attributes">) {
  return (
    sku.attributes?.product_name
    || sku.attributes?.name
    || sku.attributes?.model_number
    || sku.attributes?.model
    || sku.sku_id
  );
}

function skuMetaRows(sku: Pick<PageDetailSKU, "attributes" | "import_confirmation">) {
  return [
    { label: "型号", value: sku.attributes?.model_number || sku.attributes?.model || "—" },
    { label: "名称", value: sku.attributes?.product_name || sku.attributes?.name || "—" },
    { label: "价格", value: sku.attributes?.price || "—" },
    { label: "导入", value: sku.import_confirmation || "—" },
  ];
}

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const { currentJob, pages, skus, fetchJob, fetchPages, fetchSkus, loading } = useJobStore();
  const { connect, disconnect, onEvent } = useSSEStore();
  const [selectedPage, setSelectedPage] = useState<number | null>(null);
  const [expandedPage, setExpandedPage] = useState<number | null>(null);
  const [pageDetail, setPageDetail] = useState<PageDetail | null>(null);
  const [lightboxImg, setLightboxImg] = useState<string | null>(null);
  const [tab, setTab] = useState<"pages" | "skus" | "heatmap" | "eval">("pages");
  const [showTimeline, setShowTimeline] = useState(false);

  useEffect(() => {
    if (!jobId) return;
    fetchJob(jobId);
    fetchPages(jobId);
    connect(jobId);

    const unsub = onEvent((e) => {
      // SSE is per-job, so all events belong to this job.
      // Some events (page_completed) don't have job_id field.
      if (!e.data.job_id || e.data.job_id === jobId) {
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

  const apiBase = import.meta.env.VITE_API_BASE || "/api/v1";
  const screenshotUrl = (pageNo: number) =>
    `${apiBase}/jobs/${jobId}/pages/${pageNo}/screenshot`;
  const imageUrl = (imageId: string) =>
    jobsApi.getImageUrl(jobId!, imageId);
  const resolveImageUrl = (img: { image_id: string; image_url?: string }) =>
    img.image_url || imageUrl(img.image_id);

  const toggleExpand = async (pageNo: number) => {
    if (expandedPage === pageNo) {
      setExpandedPage(null);
      setPageDetail(null);
      return;
    }
    setExpandedPage(pageNo);
    setPageDetail(null);
    try {
      const detail = await jobsApi.getPageDetail(jobId!, pageNo);
      setPageDetail(detail);
    } catch {
      setPageDetail(null);
    }
  };

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
              <th style={{ width: 70 }}>缩略图</th>
              <th>页码</th><th>状态</th><th>类型</th><th>SKU数</th>
              <th>置信度</th><th>提取方式</th><th>LLM模型</th>
            </tr>
          </thead>
          <tbody>
            {pages.map((p) => (
              <>
                <tr key={p.id} className={selectedPage === p.page_number ? "selected" : ""}
                    onClick={() => toggleExpand(p.page_number)}
                    style={{ cursor: "pointer" }}>
                  <td>
                    <img
                      src={screenshotUrl(p.page_number)}
                      loading="lazy"
                      alt={`p${p.page_number}`}
                      style={{ width: 60, height: 80, objectFit: "cover", borderRadius: 3, border: "1px solid #2D3548" }}
                    />
                  </td>
                  <td>{p.page_number}</td>
                  <td><StatusBadge status={p.status} /></td>
                  <td>{p.page_type || "-"}</td>
                  <td>{p.sku_count}</td>
                  <td>{p.page_confidence ? formatPercent(p.page_confidence) : "-"}</td>
                  <td>{p.extraction_method || "-"}</td>
                  <td>{p.llm_model_used || "-"}</td>
                </tr>
                {expandedPage === p.page_number && (
                  <tr key={`detail-${p.id}`}>
                    <td colSpan={8} style={{ padding: 0 }}>
                      <div style={{ display: "flex", gap: 16, padding: 16, backgroundColor: "#151C2C", borderBottom: "2px solid #22D3EE33" }}>
                        {/* Left: large screenshot */}
                        <div style={{ flexShrink: 0 }}>
                          <img
                            src={screenshotUrl(p.page_number)}
                            alt={`page-${p.page_number}`}
                            style={{ width: 300, borderRadius: 4, border: "1px solid #2D3548", cursor: "pointer" }}
                            onClick={() => setLightboxImg(screenshotUrl(p.page_number))}
                          />
                        </div>
                        {/* Right: SKUs with images */}
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <h4 style={{ margin: "0 0 8px", fontSize: 13, color: "#94A3B8" }}>
                            页面 SKU ({pageDetail?.skus.length ?? 0})
                          </h4>
                          {pageDetail?.skus.map((sku) => {
                            const skuImages = buildSkuImageUrls(sku, imageUrl);
                            return (
                              <div key={sku.sku_id} style={{ marginBottom: 10, padding: 10, backgroundColor: "#1B2233", borderRadius: 6, border: "1px solid #2D3548" }}>
                                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, fontSize: 12, marginBottom: 8 }}>
                                  <span style={{ color: "#E2E8F4", fontWeight: 600 }}>{skuPrimaryText(sku)}</span>
                                  <span style={{ color: "#64748B", flexShrink: 0 }}>{sku.validity}</span>
                                </div>
                                <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "4px 12px", marginBottom: 8, fontSize: 12 }}>
                                  {skuMetaRows(sku).map((item) => (
                                    <div key={`${sku.sku_id}-${item.label}`} style={{ display: "flex", gap: 6, minWidth: 0 }}>
                                      <span style={{ color: "#64748B", flexShrink: 0 }}>{item.label}</span>
                                      <span style={{ color: "#CBD5E1", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.value}</span>
                                    </div>
                                  ))}
                                </div>
                                {skuImages.length > 0 ? (
                                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                                    {skuImages.slice(0, 4).map((url) => (
                                      <img
                                        key={url}
                                        src={url}
                                        style={{ width: 56, height: 56, objectFit: "cover", borderRadius: 3, border: "1px solid #2D3548", cursor: "pointer" }}
                                        onClick={(e) => { e.stopPropagation(); setLightboxImg(url); }}
                                      />
                                    ))}
                                    {skuImages.length > 4 && (
                                      <span style={{ display: "flex", alignItems: "center", fontSize: 11, color: "#64748B" }}>
                                        +{skuImages.length - 4}
                                      </span>
                                    )}
                                  </div>
                                ) : (
                                  <span style={{ fontSize: 11, color: "#64748B" }}>无关联图片</span>
                                )}
                              </div>
                            );
                          })}
                          {pageDetail && pageDetail.skus.length === 0 && (
                            <span style={{ fontSize: 12, color: "#64748B" }}>该页暂无 SKU 数据</span>
                          )}
                          {pageDetail?.images && pageDetail.images.length > 0 && (
                            <>
                              <h4 style={{ margin: "12px 0 8px", fontSize: 13, color: "#94A3B8" }}>
                                页面图片 ({pageDetail.images.length})
                              </h4>
                              <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                                {pageDetail.images.map((img) => (
                                  <img
                                    key={img.image_id}
                                    src={resolveImageUrl(img)}
                                    style={{ width: 48, height: 48, objectFit: "cover", borderRadius: 3, border: "1px solid #2D3548", cursor: "pointer" }}
                                    onClick={() => setLightboxImg(resolveImageUrl(img))}
                                  />
                                ))}
                              </div>
                            </>
                          )}
                          {!pageDetail && <span style={{ fontSize: 12, color: "#64748B" }}>加载中...</span>}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      )}

      {tab === "skus" && (
        <SKUList skus={skus} jobId={jobId} />
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

      {/* Lightbox */}
      {lightboxImg && (
        <div
          onClick={() => setLightboxImg(null)}
          style={{
            position: "fixed", inset: 0, zIndex: 9999,
            backgroundColor: "rgba(0,0,0,0.85)",
            display: "flex", alignItems: "center", justifyContent: "center",
            cursor: "pointer",
          }}
        >
          <img src={lightboxImg} style={{ maxWidth: "90vw", maxHeight: "90vh", borderRadius: 6 }} />
        </div>
      )}
    </div>
  );
}
