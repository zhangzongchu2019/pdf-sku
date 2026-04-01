import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import api from "../api/client";
import { useAuthStore } from "../stores/authStore";
import { statusLabel } from "../utils/format";
import Loading from "../components/common/Loading";

/* ── 类型定义 ── */
interface SKUAttributes {
  product_name?: string;
  model_number?: string;
  price?: string;
  specs?: string;
  color?: string;
  tag?: string;
  source?: string;
}

interface SKUData {
  sku_id: string;
  attributes: SKUAttributes;
  confidence: number;
  validity: string;
  extraction_method: string;
  image_paths: string[];
}

interface PageData {
  page_no: number;
  status: string;
  page_type: string | null;
  fitz_page_class: string | null;
  extraction_method: string | null;
  slice_count: number;
  sku_count: number;
  skus: SKUData[];
  error: string | null;
}

interface DatasetDetail {
  dataset: string;
  pdf: string;
  total_pages: number;
  total_skus: number;
  elapsed_seconds: number;
  pages: PageData[];
}

interface JobInfo {
  job_id: string;
  source_file: string;
  status: string;
  user_status: string;
  degrade_reason: string | null;
  total_pages: number;
  total_skus: number;
  created_at: string;
}

interface PageInfo {
  page_number: number;
  status: string;
  page_type: string | null;
  sku_count: number;
  extraction_method: string | null;
}

/* ── 辅助组件 ── */
const badgeStyles: Record<string, React.CSSProperties> = {
  green:  { background: "#f6ffed", color: "#389e0d", border: "1px solid #b7eb8f" },
  yellow: { background: "#fffbe6", color: "#d48806", border: "1px solid #ffe58f" },
  red:    { background: "#fff2f0", color: "#cf1322", border: "1px solid #ffccc7" },
  blue:   { background: "#e6f7ff", color: "#096dd9", border: "1px solid #91d5ff" },
  purple: { background: "#f9f0ff", color: "#722ed1", border: "1px solid #d3adf7" },
  gray:   { background: "#fafafa", color: "#8c8c8c", border: "1px solid #d9d9d9" },
};

function Badge({ text, color }: { text: string; color: string }) {
  const s = badgeStyles[color] || badgeStyles.gray;
  return (
    <span style={{
      display: "inline-block", padding: "1px 8px", borderRadius: 10,
      fontSize: 12, fontWeight: 500, whiteSpace: "nowrap", ...s,
    }}>
      {text}
    </span>
  );
}

function statusColor(s: string) {
  if (s === "AI_COMPLETED") return "green";
  if (s === "AI_FAILED") return "red";
  if (s === "HUMAN_QUEUED") return "yellow";
  return "gray";
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = value >= 0.7 ? "#52c41a" : value >= 0.5 ? "#faad14" : "#ff4d4f";
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span style={{ width: 50, height: 6, background: "#f0f0f0", borderRadius: 3, overflow: "hidden", display: "inline-block" }}>
        <span style={{ display: "block", height: "100%", width: `${pct}%`, background: color, borderRadius: 3 }} />
      </span>
      <span style={{ fontSize: 12, fontWeight: 600, color }}>{value.toFixed(2)}</span>
    </span>
  );
}

const TERMINAL_STATUSES = ["COMPLETED", "PARTIAL", "FAILED", "CANCELLED", "NEEDS_MANUAL", "ORPHANED", "REJECTED", "DEGRADED"];
function isTerminal(status: string) {
  return TERMINAL_STATUSES.some((s) => status?.toUpperCase().includes(s));
}

/** 判断 Job 是否可重试，返回提示标题和描述 */
function retryableInfo(job: JobInfo): { title: string; desc: string } | null {
  const s = job.status;
  const dr = job.degrade_reason || "";
  if (s === "DEGRADED_HUMAN" && dr.startsWith("eval_failed"))
    return { title: "AI 模型调用超时", desc: "评估阶段大模型请求失败，可能由于网络波动或服务繁忙，请尝试重新分析" };
  if (s === "DEGRADED_HUMAN")
    return { title: "已降级为人工处理", desc: "评估阶段判定需要人工处理，可尝试重新分析" };
  if (s === "EVAL_FAILED")
    return { title: "评估失败", desc: "文件评估阶段出现异常，请尝试重新分析" };
  if (s === "PARTIAL_FAILED")
    return { title: "部分页面处理失败", desc: "部分页面处理过程中出现异常，可尝试重新分析" };
  if (s === "ORPHANED")
    return { title: "处理中断", desc: "任务处理过程中意外中断，请尝试重新分析" };
  if (s === "CANCELLED")
    return { title: "任务已取消", desc: "该任务此前已被取消，可重新发起分析" };
  if (s === "REJECTED")
    return { title: "文件被拒绝", desc: "文件预检未通过，可尝试重新分析" };
  if (s === "EVALUATING" || s === "PROCESSING")
    return { title: "任务似乎已卡住", desc: "任务长时间未更新，可能后端已中断，可尝试重新分析" };
  return null;
}

/** 卡住检测阈值：连续 N 次轮询状态未变化则视为卡住 */
const STUCK_POLL_THRESHOLD = 20; // 20 * 3s = 60s

/* ── 进度面板 ── */
function ProgressPanel({ jobId }: { jobId: string }) {
  const [job, setJob] = useState<JobInfo | null>(null);
  const [pages, setPages] = useState<PageInfo[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval>>();
  const [done, setDone] = useState(false);
  const [stuck, setStuck] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const stuckCountRef = useRef(0);
  const lastStatusRef = useRef("");

  const poll = useCallback(async () => {
    try {
      const j = await api.get<JobInfo>(`/jobs/${jobId}`);
      setJob(j);
      const resp = await api.get<{ data: PageInfo[] }>(`/jobs/${jobId}/pages`);
      setPages(resp.data || []);
      if (isTerminal(j.user_status)) {
        setDone(true);
        setRetrying(false);
      } else {
        // 重试成功后状态变为活跃态，清除 retrying
        setRetrying(false);
        // 卡住检测：如果 status 持续不变且处于活跃态
        const key = `${j.status}:${(resp.data || []).map((p: PageInfo) => p.status).join(",")}`;
        if (key === lastStatusRef.current) {
          stuckCountRef.current++;
          if (stuckCountRef.current >= STUCK_POLL_THRESHOLD) setStuck(true);
        } else {
          stuckCountRef.current = 0;
          setStuck(false);
        }
        lastStatusRef.current = key;
      }
    } catch { /* ignore */ }
  }, [jobId]);

  useEffect(() => {
    poll();
    timerRef.current = setInterval(poll, 3000);
    return () => clearInterval(timerRef.current);
  }, [poll]);

  useEffect(() => {
    if (done && timerRef.current) clearInterval(timerRef.current);
  }, [done]);

  if (!job) return <Loading />;

  const completed = pages.filter((p) =>
    ["AI_COMPLETED", "HUMAN_COMPLETED", "IMPORTED_CONFIRMED", "IMPORTED_ASSUMED", "BLANK"].includes(p.status)
  ).length;
  const failed = pages.filter((p) => p.status === "AI_FAILED").length;
  const processing = pages.filter((p) => ["AI_PROCESSING", "HUMAN_QUEUED", "HUMAN_PROCESSING"].includes(p.status)).length;
  const total = job.total_pages || pages.length;
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0;

  const displayStatus = statusLabel(job.user_status);

  return (
    <div style={{ marginBottom: 24 }}>
      {/* 统计卡片 */}
      <div className="metrics-grid">
        <div className="metrics-card">
          <div className="metrics-title">文件</div>
          <div style={{ fontSize: 16, fontWeight: 600, marginTop: 4 }}>{job.source_file}</div>
        </div>
        <div className="metrics-card">
          <div className="metrics-title">状态</div>
          <div className="metrics-value" style={{ fontSize: 20 }}>{displayStatus}</div>
        </div>
        <div className="metrics-card">
          <div className="metrics-title">总页数</div>
          <div className="metrics-value">{total}</div>
        </div>
      </div>

      {/* 进度条 */}
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, fontSize: 13 }}>
          <span style={{ color: "#8c8c8c" }}>处理进度</span>
          <span style={{ fontWeight: 600, color: "#1f1f1f" }}>
            {pct}%
            <span style={{ color: "#8c8c8c", fontWeight: 400, marginLeft: 8 }}>
              {completed}/{total} 页完成
              {failed > 0 && <span style={{ color: "#ff4d4f" }}> / {failed} 失败</span>}
              {processing > 0 && <span style={{ color: "#faad14" }}> / {processing} 处理中</span>}
            </span>
          </span>
        </div>
        <div style={{ height: 8, background: "#f0f0f0", borderRadius: 4, overflow: "hidden" }}>
          <div style={{
            height: "100%", borderRadius: 4, transition: "width 0.5s ease",
            width: `${pct}%`,
            background: pct >= 100 ? "#52c41a" : "#1890ff",
          }} />
        </div>

        {/* 页面状态网格 */}
        {pages.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 3, marginTop: 12 }}>
            {pages.map((p) => {
              const c =
                p.status === "AI_COMPLETED" ? "#52c41a" :
                p.status === "AI_FAILED" ? "#ff4d4f" :
                p.status === "AI_PROCESSING" ? "#1890ff" :
                p.status === "BLANK" ? "#d9d9d9" : "#e8e8e8";
              return (
                <div
                  key={p.page_number}
                  title={`第 ${p.page_number} 页: ${p.status}`}
                  style={{ width: 14, height: 14, borderRadius: 2, background: c }}
                />
              );
            })}
          </div>
        )}
      </div>

      {stuck && !done && !retrying && (
        <div className="card" style={{
          display: "flex", alignItems: "center", gap: 12,
          padding: "14px 20px", marginTop: 12,
          background: "#fffbe6", border: "1px solid #ffe58f",
        }}>
          <span style={{ fontSize: 20 }}>&#9888;</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: "#d48806" }}>
              任务似乎已卡住
            </div>
            <div style={{ fontSize: 12, color: "#8c8c8c", marginTop: 2 }}>
              任务长时间未更新，可能后端已中断，可尝试强制重新分析
            </div>
          </div>
          <button
            onClick={async () => {
              setRetrying(true);
              try {
                await api.post(`/jobs/${jobId}/requeue`);
                setStuck(false);
                stuckCountRef.current = 0;
                lastStatusRef.current = "";
                poll();
              } catch {
                setRetrying(false);
              }
            }}
            style={{
              padding: "6px 16px", backgroundColor: "#d48806", color: "#fff",
              border: "none", borderRadius: 6, cursor: "pointer",
              fontSize: 13, fontWeight: 500, whiteSpace: "nowrap",
            }}
          >
            强制重新分析
          </button>
        </div>
      )}

      {done && retryableInfo(job) && !retrying && (
        <div className="card" style={{
          display: "flex", alignItems: "center", gap: 12,
          padding: "14px 20px", marginTop: 12,
          background: "#fff2f0", border: "1px solid #ffccc7",
        }}>
          <span style={{ fontSize: 20 }}>&#9888;</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: "#cf1322" }}>
              {retryableInfo(job)!.title}
            </div>
            <div style={{ fontSize: 12, color: "#8c8c8c", marginTop: 2 }}>
              {retryableInfo(job)!.desc}
            </div>
          </div>
          <button
            onClick={async () => {
              setRetrying(true);
              try {
                await api.post(`/jobs/${jobId}/requeue`);
                setDone(false);
                poll();
              } catch {
                setRetrying(false);
              }
            }}
            style={{
              padding: "6px 16px", backgroundColor: "#1890ff", color: "#fff",
              border: "none", borderRadius: 6, cursor: "pointer",
              fontSize: 13, fontWeight: 500, whiteSpace: "nowrap",
            }}
          >
            重新分析
          </button>
        </div>
      )}

      {retrying && (
        <div style={{
          fontSize: 13, color: "#1890ff", marginTop: 12,
          display: "flex", alignItems: "center", gap: 8,
        }}>
          <span style={{
            display: "inline-block", width: 14, height: 14,
            border: "2px solid #1890ff", borderTopColor: "transparent",
            borderRadius: "50%", animation: "spin 0.8s linear infinite",
          }} />
          已提交重新分析，正在重新处理...
        </div>
      )}

      {done && !retryableInfo(job) && (
        <div style={{ fontSize: 13, color: "#8c8c8c", marginTop: 8 }}>
          处理已完成，正在加载结果...
        </div>
      )}
    </div>
  );
}

/* ── 结果视图 ── */
/** 带 Authorization header 加载图片，返回 blob URL */
function useAuthImage(url: string) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let revoke = "";
    const token = useAuthStore.getState().token;
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    fetch(url, { headers })
      .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.blob(); })
      .then((blob) => { revoke = URL.createObjectURL(blob); setBlobUrl(revoke); })
      .catch(() => setFailed(true));

    return () => { if (revoke) URL.revokeObjectURL(revoke); };
  }, [url]);

  return { blobUrl, failed };
}

function PageScreenshot({ jobId, pageNo, onClick }: { jobId: string; pageNo: number; onClick: (src: string) => void }) {
  const API_BASE = import.meta.env.VITE_API_BASE || "/api/v1";
  const url = `${API_BASE}/jobs/${jobId}/pages/${pageNo}/screenshot`;
  const { blobUrl, failed } = useAuthImage(url);

  if (failed) return null;
  if (!blobUrl) return <div style={{ width: 300, height: 200, display: "flex", alignItems: "center", justifyContent: "center", color: "#bfbfbf", fontSize: 13 }}>加载中...</div>;

  return (
    <div style={{ flexShrink: 0, marginBottom: 8 }}>
      <div style={{ fontSize: 12, color: "#8c8c8c", marginBottom: 4, fontWeight: 500 }}>原始页面</div>
      <img
        src={blobUrl}
        alt={`第 ${pageNo} 页原始内容`}
        onClick={() => onClick(blobUrl)}
        style={{
          maxWidth: 300, maxHeight: 400, borderRadius: 6,
          border: "1px solid #e8e8e8", cursor: "pointer",
          objectFit: "contain", background: "#fafafa",
        }}
      />
    </div>
  );
}

function ResultView({ data }: { data: DatasetDetail }) {
  const { jobId } = useParams<{ jobId: string }>();
  const [expandedPages, setExpandedPages] = useState<Set<number>>(
    new Set(data.pages?.length ? [data.pages[0].page_no] : [])
  );
  const [lightboxImg, setLightboxImg] = useState<string | null>(null);

  const togglePage = (pageNo: number) => {
    setExpandedPages((prev) => {
      const next = new Set(prev);
      if (next.has(pageNo)) next.delete(pageNo);
      else next.add(pageNo);
      return next;
    });
  };

  const withImages = data.pages.reduce((n, p) =>
    n + p.skus.filter((s) => s.image_paths?.length).length, 0);

  return (
    <>
      {/* 摘要统计 */}
      <div className="metrics-grid">
        {[
          { title: "总页数", value: data.total_pages },
          { title: "总 SKU", value: data.total_skus },
          { title: "有图 SKU", value: withImages },
          { title: "处理耗时", value: `${data.elapsed_seconds.toFixed(1)}s` },
        ].map((s) => (
          <div key={s.title} className="metrics-card">
            <div className="metrics-title">{s.title}</div>
            <div className="metrics-value">{s.value}</div>
          </div>
        ))}
      </div>

      {/* 按页展示 */}
      {data.pages.map((page) => {
        const isOpen = expandedPages.has(page.page_no);
        return (
          <div key={page.page_no} className="card" style={{ padding: 0, overflow: "hidden" }}>
            {/* 页头 */}
            <div
              onClick={() => togglePage(page.page_no)}
              style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "12px 16px", cursor: "pointer", userSelect: "none",
                background: isOpen ? "#fafafa" : "#fff",
                borderBottom: isOpen ? "1px solid #e8e8e8" : "none",
              }}
            >
              <span style={{
                fontSize: 12, color: "#bfbfbf", transition: "transform .2s",
                transform: isOpen ? "rotate(90deg)" : "none",
              }}>&#9654;</span>
              <strong style={{ fontSize: 14 }}>第 {page.page_no} 页</strong>
              <Badge text={statusLabel(page.status)} color={statusColor(page.status)} />
              {page.page_type && <Badge text={`类型 ${page.page_type}`} color="blue" />}
              {page.extraction_method && <Badge text={statusLabel(page.extraction_method)} color="purple" />}
              {page.fitz_page_class && <Badge text={statusLabel(page.fitz_page_class)} color="gray" />}
              <span style={{ marginLeft: "auto", fontSize: 13, color: "#8c8c8c", fontWeight: 600 }}>
                {page.sku_count} SKUs
              </span>
            </div>

            {/* 页内容 */}
            {isOpen && (
              <div style={{ display: "flex", gap: 16, padding: "0 16px" }}>
                {/* 左侧: 原始页面截图 */}
                {jobId && (
                  <PageScreenshot jobId={jobId} pageNo={page.page_no} onClick={setLightboxImg} />
                )}

                {/* 右侧: SKU 列表 */}
                <div style={{ flex: 1, minWidth: 0 }}>
                {page.error && (
                  <div style={{
                    color: "#cf1322", background: "#fff2f0", padding: "10px 16px",
                    margin: "12px 16px", borderRadius: 6, fontSize: 13,
                    border: "1px solid #ffccc7",
                  }}>
                    {page.error}
                  </div>
                )}

                {page.skus.length === 0 ? (
                  <div style={{ padding: 40, textAlign: "center", color: "#bfbfbf" }}>
                    该页无 SKU 数据
                  </div>
                ) : (
                  page.skus.map((sku, i) => {
                    const a = sku.attributes || {};
                    const imgs = sku.image_paths || [];
                    return (
                      <div key={sku.sku_id} style={{
                        display: "flex", gap: 16, padding: "14px 20px",
                        borderBottom: "1px solid #f5f5f5", alignItems: "flex-start",
                      }}>
                        {/* 序号 */}
                        <div style={{
                          width: 28, height: 28, borderRadius: "50%",
                          background: "#e6f7ff", color: "#096dd9",
                          display: "flex", alignItems: "center", justifyContent: "center",
                          fontSize: 12, fontWeight: 700, flexShrink: 0, marginTop: 2,
                        }}>
                          {i + 1}
                        </div>

                        {/* SKU 信息 */}
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: 15, fontWeight: 600, color: "#1f1f1f", marginBottom: 6, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                            {a.product_name || "未知商品"}
                            <Badge text={statusLabel(sku.validity)} color={sku.validity === "valid" ? "green" : "red"} />
                          </div>

                          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", fontSize: 13, marginBottom: 6 }}>
                            {a.model_number && (
                              <span style={{ background: "#f5f5f5", borderRadius: 4, padding: "2px 8px", display: "inline-flex", gap: 4 }}>
                                <span style={{ color: "#8c8c8c", fontWeight: 500 }}>型号</span>
                                <span style={{ color: "#1f1f1f", fontWeight: 600 }}>{a.model_number}</span>
                              </span>
                            )}
                            {a.price && (
                              <span style={{ background: "#fff7e6", borderRadius: 4, padding: "2px 8px", display: "inline-flex", gap: 4 }}>
                                <span style={{ color: "#8c8c8c", fontWeight: 500 }}>价格</span>
                                <span style={{ color: "#d46b08", fontWeight: 600 }}>{a.price}</span>
                              </span>
                            )}
                            {a.specs && (
                              <span style={{ background: "#f5f5f5", borderRadius: 4, padding: "2px 8px", display: "inline-flex", gap: 4 }}>
                                <span style={{ color: "#8c8c8c", fontWeight: 500 }}>规格</span>
                                <span style={{ color: "#1f1f1f", fontWeight: 600 }}>{a.specs}</span>
                              </span>
                            )}
                            {a.color && (
                              <span style={{ background: "#f5f5f5", borderRadius: 4, padding: "2px 8px", display: "inline-flex", gap: 4 }}>
                                <span style={{ color: "#8c8c8c", fontWeight: 500 }}>颜色</span>
                                <span style={{ color: "#1f1f1f", fontWeight: 600 }}>{a.color}</span>
                              </span>
                            )}
                            {a.tag && (
                              <span style={{ background: "#f5f5f5", borderRadius: 4, padding: "2px 8px", display: "inline-flex", gap: 4 }}>
                                <span style={{ color: "#8c8c8c", fontWeight: 500 }}>标签</span>
                                <span style={{ color: "#1f1f1f", fontWeight: 600 }}>{a.tag}</span>
                              </span>
                            )}
                            {a.source && (
                              <span style={{ background: "#f5f5f5", borderRadius: 4, padding: "2px 8px", display: "inline-flex", gap: 4 }}>
                                <span style={{ color: "#8c8c8c", fontWeight: 500 }}>来源</span>
                                <span style={{ color: "#1f1f1f", fontWeight: 600 }}>{a.source}</span>
                              </span>
                            )}
                          </div>

                          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                            {sku.extraction_method && <Badge text={statusLabel(sku.extraction_method)} color="gray" />}
                            <ConfidenceBar value={sku.confidence || 0} />
                            <span style={{ fontSize: 11, color: "#bfbfbf" }}>{sku.sku_id}</span>
                          </div>
                        </div>

                        {/* 绑定图片 */}
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", flexShrink: 0, alignItems: "flex-start" }}>
                          {imgs.length > 0 ? imgs.map((p, j) => (
                            <img
                              key={j}
                              src={p}
                              alt="商品图"
                              loading="lazy"
                              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                              onClick={() => setLightboxImg(p)}
                              style={{
                                width: 72, height: 72, objectFit: "cover", borderRadius: 6,
                                border: "1px solid #e8e8e8", cursor: "pointer",
                              }}
                            />
                          )) : (
                            <div style={{
                              width: 72, height: 72, borderRadius: 6,
                              border: "2px dashed #e8e8e8", display: "flex",
                              alignItems: "center", justifyContent: "center",
                              color: "#bfbfbf", fontSize: 11,
                            }}>
                              无图
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
                </div>
              </div>
            )}
          </div>
        );
      })}

      {/* Lightbox */}
      {lightboxImg && (
        <div
          onClick={() => setLightboxImg(null)}
          style={{
            position: "fixed", inset: 0, zIndex: 9999,
            backgroundColor: "rgba(0,0,0,0.7)",
            display: "flex", alignItems: "center", justifyContent: "center",
            cursor: "pointer",
          }}
        >
          <img src={lightboxImg} style={{ maxWidth: "90vw", maxHeight: "90vh", borderRadius: 8, boxShadow: "0 8px 40px rgba(0,0,0,0.3)" }} alt="preview" />
        </div>
      )}
    </>
  );
}

/* ── 主页面 ── */
export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [result, setResult] = useState<DatasetDetail | null>(null);
  const [resultError, setResultError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [jobTitle, setJobTitle] = useState<string>("任务详情");
  const retryRef = useRef<ReturnType<typeof setInterval>>();

  // 加载 job 信息获取真实文件名
  useEffect(() => {
    if (!jobId) return;
    api.get<JobInfo>(`/jobs/${jobId}`).then((j) => {
      if (j.source_file) setJobTitle(j.source_file);
    }).catch(() => {});
  }, [jobId]);

  const loadResult = useCallback(async () => {
    if (!jobId) return;
    try {
      const d = await api.get<DatasetDetail>(`/jobs/${jobId}/result`);
      setResult(d);
      setResultError(false);
      setLoading(false);
      if (retryRef.current) clearInterval(retryRef.current);
    } catch {
      setResultError(true);
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    loadResult();
    retryRef.current = setInterval(loadResult, 5000);
    return () => { if (retryRef.current) clearInterval(retryRef.current); };
  }, [loadResult]);

  useEffect(() => {
    if (result && retryRef.current) clearInterval(retryRef.current);
  }, [result]);

  if (loading) return <Loading />;

  const [exporting, setExporting] = useState(false);

  const handleExportExcel = useCallback(async () => {
    if (!jobId || exporting) return;
    setExporting(true);
    try {
      const API_BASE = import.meta.env.VITE_API_BASE || "/api/v1";
      const token = useAuthStore.getState().token;
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch(`${API_BASE}/jobs/${jobId}/export/excel`, { headers });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ message: "导出失败" }));
        throw new Error(err.message || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const disposition = res.headers.get("content-disposition") || "";
      const match = disposition.match(/filename\*?=(?:UTF-8''|"?)([^";]+)/i);
      const filename = match ? decodeURIComponent(match[1]) : "export.xlsx";
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      alert(e.message || "Excel 导出失败");
    } finally {
      setExporting(false);
    }
  }, [jobId, exporting]);

  return (
    <div className="page">
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <Link to="/jobs" className="back-link">← 返回列表</Link>
          <h2>{jobTitle}</h2>
        </div>
        {result && (
          <button
            onClick={handleExportExcel}
            disabled={exporting}
            style={{
              padding: "8px 20px", fontSize: 14, fontWeight: 600,
              background: exporting ? "#d9d9d9" : "#52c41a", color: "#fff",
              border: "none", borderRadius: 6, cursor: exporting ? "not-allowed" : "pointer",
              display: "flex", alignItems: "center", gap: 8, whiteSpace: "nowrap",
            }}
          >
            {exporting && (
              <span style={{
                display: "inline-block", width: 14, height: 14,
                border: "2px solid #fff", borderTopColor: "transparent",
                borderRadius: "50%", animation: "spin 0.8s linear infinite",
              }} />
            )}
            {exporting ? "导出中..." : "导出 Excel"}
          </button>
        )}
      </div>

      {!result && resultError && jobId && <ProgressPanel jobId={jobId} />}
      {result && <ResultView data={result} />}
    </div>
  );
}
