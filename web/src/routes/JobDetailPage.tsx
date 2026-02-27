import { useEffect, useState, useRef, useCallback } from "react";
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
import ImageCropOverlay from "../components/annotation/ImageCropOverlay";

// ── 实时活动面板 ──
interface ActivityEntry {
  id: number;
  time: string;
  event: string;
  message: string;
  level: "info" | "success" | "warning" | "error";
}

const EVENT_CONFIG: Record<string, { label: string; level: ActivityEntry["level"]; format: (d: any) => string }> = {
  page_completed:     { label: "页面完成", level: "success", format: (d) => `第 ${d.page_no} 页处理完成${d.sku_count ? `，${d.sku_count} 个 SKU` : ""}` },
  pages_batch_update: { label: "批量更新", level: "info",    format: (d) => `${d.completed ?? "?"} 页已完成` },
  job_completed:      { label: "Job 完成", level: "success", format: (d) => `处理完成，共 ${d.total_skus} 个 SKU` },
  job_failed:         { label: "Job 失败", level: "error",   format: (d) => d.error_message || "处理失败" },
  human_needed:       { label: "需人工",   level: "warning", format: (d) => `${d.task_count} 个任务需要人工标注` },
  sla_escalated:      { label: "SLA 升级", level: "warning", format: (d) => `任务 SLA 升级至 ${d.sla_level}` },
  heartbeat:          { label: "心跳",     level: "info",    format: () => "连接正常" },
};

const LEVEL_COLORS: Record<string, string> = {
  info: "#64748B", success: "#22C55E", warning: "#F59E0B", error: "#EF4444",
};

function LiveActivityPanel({ activities, sseStatus }: { activities: ActivityEntry[]; sseStatus: string }) {
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [activities.length]);

  const statusDot = sseStatus === "connected" ? "#22C55E"
    : sseStatus === "reconnecting" ? "#F59E0B"
    : sseStatus === "polling" ? "#3B82F6" : "#EF4444";
  const statusLabel = sseStatus === "connected" ? "已连接"
    : sseStatus === "reconnecting" ? "重连中"
    : sseStatus === "polling" ? "轮询中" : "未连接";

  return (
    <div style={{
      backgroundColor: "#151C2C", border: "1px solid #2D3548", borderRadius: 8,
      padding: 12, marginBottom: 16,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: "#E2E8F0" }}>实时动态</span>
          <span style={{
            display: "inline-flex", alignItems: "center", gap: 4,
            fontSize: 11, color: statusDot, padding: "1px 6px",
            backgroundColor: `${statusDot}18`, border: `1px solid ${statusDot}33`,
            borderRadius: 3,
          }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", backgroundColor: statusDot,
              animation: sseStatus === "connected" ? "pulse 2s infinite" : undefined }} />
            {statusLabel}
          </span>
        </div>
        <span style={{ fontSize: 11, color: "#475569" }}>{activities.length} 条</span>
      </div>
      <div ref={listRef} style={{
        maxHeight: 160, overflowY: "auto", fontSize: 12,
        display: "flex", flexDirection: "column", gap: 2,
      }}>
        {activities.length === 0 && (
          <div style={{ color: "#475569", textAlign: "center", padding: 16 }}>等待事件...</div>
        )}
        {activities.map((a) => (
          <div key={a.id} style={{ display: "flex", gap: 8, padding: "3px 0", borderBottom: "1px solid #1E293B" }}>
            <span style={{ color: "#475569", flexShrink: 0, fontFamily: "monospace" }}>{a.time}</span>
            <span style={{ color: LEVEL_COLORS[a.level], flexShrink: 0, fontWeight: 500, minWidth: 60 }}>{EVENT_CONFIG[a.event]?.label ?? a.event}</span>
            <span style={{ color: "#94A3B8" }}>{a.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const { currentJob, pages, skus, fetchJob, fetchPages, fetchSkus, loading } = useJobStore();
  const { connect, disconnect, onEvent, status: sseStatus } = useSSEStore();
  const [selectedPage, setSelectedPage] = useState<number | null>(null);
  const [expandedPage, setExpandedPage] = useState<number | null>(null);
  const [pageDetail, setPageDetail] = useState<PageDetail | null>(null);
  const [lightboxImg, setLightboxImg] = useState<string | null>(null);
  const [reviewCompleting, setReviewCompleting] = useState(false);
  const [bindingSku, setBindingSku] = useState<string | null>(null);
  const [reviewStartTime] = useState<Record<number, number>>({});
  const [tab, setTab] = useState<"pages" | "skus" | "heatmap" | "eval">("pages");
  const [showTimeline, setShowTimeline] = useState(false);
  const [activities, setActivities] = useState<ActivityEntry[]>([]);
  const actIdRef = useRef(0);

  // 裁剪模式状态
  const [cropState, setCropState] = useState<{
    pageNo: number;
    mode: "add" | "adjust";
    imageId?: string;
    skuId?: string;
    initialBbox?: number[];
  } | null>(null);

  const addActivity = useCallback((event: string, data: any) => {
    // 心跳事件不记录，避免刷屏
    if (event === "heartbeat") return;
    const cfg = EVENT_CONFIG[event];
    const entry: ActivityEntry = {
      id: ++actIdRef.current,
      time: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
      event,
      message: cfg ? cfg.format(data) : JSON.stringify(data).slice(0, 80),
      level: cfg?.level ?? "info",
    };
    setActivities((prev) => [...prev.slice(-99), entry]); // 最多保留 100 条
  }, []);

  useEffect(() => {
    if (!jobId) return;
    fetchJob(jobId);
    fetchPages(jobId);
    connect(jobId);

    const unsub = onEvent((e) => {
      addActivity(e.event, e.data);
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

  const toggleExpand = async (pageNo: number) => {
    if (expandedPage === pageNo) {
      setExpandedPage(null);
      setPageDetail(null);
      return;
    }
    setExpandedPage(pageNo);
    // Track review start time for time calculation
    const pg = pages.find((pp) => pp.page_number === pageNo);
    if (pg?.needs_review && !reviewStartTime[pageNo]) {
      reviewStartTime[pageNo] = Date.now();
    }
    try {
      const detail = await jobsApi.getPageDetail(jobId!, pageNo);
      setPageDetail(detail);
    } catch {
      setPageDetail(null);
    }
  };

  const handleReviewComplete = async (pageNo: number) => {
    if (!jobId || reviewCompleting) return;
    setReviewCompleting(true);
    try {
      const startTime = reviewStartTime[pageNo];
      const timeSec = startTime ? Math.round((Date.now() - startTime) / 1000) : undefined;
      await jobsApi.markReviewComplete(jobId, pageNo, timeSec);
      await fetchPages(jobId);
      await fetchJob(jobId);
    } catch (e) {
      console.error("审核完成失败:", e);
    } finally {
      setReviewCompleting(false);
    }
  };

  const handleBindImage = async (skuId: string, imageId: string) => {
    if (!jobId) return;
    try {
      await jobsApi.updateSkuBinding(jobId, skuId, imageId);
      if (expandedPage !== null) {
        const detail = await jobsApi.getPageDetail(jobId, expandedPage);
        setPageDetail(detail);
      }
    } catch (e) {
      console.error("绑定修正失败:", e);
    } finally {
      setBindingSku(null);
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

      {/* 实时活动面板 */}
      <LiveActivityPanel activities={activities} sseStatus={sseStatus} />

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
              <th>置信度</th><th style={{ width: 70 }}>需介入</th><th>提取方式</th><th>LLM模型</th>
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
                  <td style={{ textAlign: "center" }}>
                    {p.needs_review ? (
                      <span title="需要人工介入" style={{ color: "#EF4444", fontSize: 16 }}>&#9873;</span>
                    ) : (p.page_confidence != null && p.page_confidence < 0.6) ? (
                      <span title="已审核完成" style={{ color: "#22C55E", fontSize: 14 }}>&#10003;</span>
                    ) : (
                      <span style={{ color: "#64748B" }}>—</span>
                    )}
                  </td>
                  <td>{p.extraction_method || "-"}</td>
                  <td>{p.llm_model_used || "-"}</td>
                </tr>
                {expandedPage === p.page_number && (
                  <tr key={`detail-${p.id}`}>
                    <td colSpan={9} style={{ padding: 0 }}>
                      {/* Review toolbar for needs_review pages */}
                      {p.needs_review && (
                        <div style={{
                          display: "flex", alignItems: "center", gap: 12,
                          padding: "8px 16px",
                          backgroundColor: "#1A1520",
                          borderBottom: "1px solid #EF444433",
                        }}>
                          <span style={{ fontSize: 12, color: "#F59E0B", fontWeight: 600 }}>
                            &#9873; 审核修正
                          </span>
                          <span style={{ fontSize: 11, color: "#64748B" }}>
                            修改 SKU 属性请使用 SKU Tab 编辑功能
                          </span>
                          <div style={{ flex: 1 }} />
                          <button
                            onClick={() => handleReviewComplete(p.page_number)}
                            disabled={reviewCompleting}
                            style={{
                              padding: "4px 14px", fontSize: 12, cursor: "pointer",
                              backgroundColor: "#22C55E22", border: "1px solid #22C55E44",
                              borderRadius: 4, color: "#22C55E", fontWeight: 500,
                            }}
                          >
                            {reviewCompleting ? "提交中..." : "审核完成"}
                          </button>
                        </div>
                      )}
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
                          {pageDetail?.skus.map((sku) => (
                            <div key={sku.sku_id} style={{ marginBottom: 10, padding: 8, backgroundColor: "#1B2233", borderRadius: 6, border: "1px solid #2D3548" }}>
                              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
                                <span style={{ color: "#E2E8F4" }}>
                                  {sku.attributes?.model_number || sku.attributes?.model || sku.sku_id}
                                  {sku.attributes?.product_name || sku.attributes?.name ? ` ${sku.attributes.product_name || sku.attributes.name}` : ""}
                                  {sku.attributes?.size ? ` | ${sku.attributes.size}` : ""}
                                </span>
                                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                                  <span style={{ color: "#64748B", fontSize: 11 }}>{sku.attribute_source === "HUMAN_CORRECTED" ? "已修正" : ""}</span>
                                  <span style={{ color: "#64748B" }}>{sku.validity}</span>
                                </div>
                              </div>
                              {/* SKU images with binding correction */}
                              <div style={{ display: "flex", gap: 4, flexWrap: "wrap", alignItems: "center" }}>
                                {sku.images.slice(0, 3).map((img) => (
                                  <img
                                    key={img.image_id}
                                    src={imageUrl(img.image_id)}
                                    style={{
                                      width: 48, height: 48, objectFit: "cover", borderRadius: 3,
                                      border: bindingSku === sku.sku_id ? "2px solid #F59E0B" : "1px solid #2D3548",
                                      cursor: "pointer",
                                    }}
                                    onClick={(e) => { e.stopPropagation(); setLightboxImg(imageUrl(img.image_id)); }}
                                  />
                                ))}
                                {sku.images.length > 3 && (
                                  <span style={{ display: "flex", alignItems: "center", fontSize: 11, color: "#64748B" }}>
                                    +{sku.images.length - 3}
                                  </span>
                                )}
                                {p.needs_review && (
                                  <button
                                    onClick={(e) => { e.stopPropagation(); setBindingSku(bindingSku === sku.sku_id ? null : sku.sku_id); }}
                                    style={{
                                      padding: "2px 6px", fontSize: 10, cursor: "pointer",
                                      backgroundColor: bindingSku === sku.sku_id ? "#F59E0B22" : "transparent",
                                      border: `1px solid ${bindingSku === sku.sku_id ? "#F59E0B44" : "#2D3548"}`,
                                      borderRadius: 3,
                                      color: bindingSku === sku.sku_id ? "#F59E0B" : "#64748B",
                                    }}
                                  >
                                    {bindingSku === sku.sku_id ? "取消" : "换图"}
                                  </button>
                                )}
                              </div>
                              {/* Binding selection: show all page images to pick from */}
                              {bindingSku === sku.sku_id && pageDetail?.images && (
                                <div style={{ marginTop: 6, padding: 6, backgroundColor: "#151C2C", borderRadius: 4, border: "1px dashed #F59E0B44" }}>
                                  <div style={{ fontSize: 11, color: "#F59E0B", marginBottom: 4 }}>选择正确的图片:</div>
                                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                                    {pageDetail.images.map((img) => (
                                      <img
                                        key={img.image_id}
                                        src={imageUrl(img.image_id)}
                                        style={{
                                          width: 56, height: 56, objectFit: "cover", borderRadius: 3,
                                          border: "2px solid #2D3548", cursor: "pointer",
                                        }}
                                        onClick={(e) => { e.stopPropagation(); handleBindImage(sku.sku_id, img.image_id); }}
                                        onMouseEnter={(e) => { (e.target as HTMLImageElement).style.borderColor = "#22D3EE"; }}
                                        onMouseLeave={(e) => { (e.target as HTMLImageElement).style.borderColor = "#2D3548"; }}
                                      />
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          ))}
                          {pageDetail?.images && pageDetail.images.length > 0 && (
                            <>
                              <h4 style={{ margin: "12px 0 8px", fontSize: 13, color: "#94A3B8" }}>
                                页面图片 ({pageDetail.images.length})
                              </h4>
                              <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                                {pageDetail.images.map((img) => (
                                  <img
                                    key={img.image_id}
                                    src={imageUrl(img.image_id)}
                                    style={{ width: 48, height: 48, objectFit: "cover", borderRadius: 3, border: "1px solid #2D3548", cursor: "pointer" }}
                                    onClick={() => setLightboxImg(imageUrl(img.image_id))}
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
        <SKUList skus={skus} jobId={jobId} onSkuUpdated={() => { if (jobId) fetchSkus(jobId); }} />
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
