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

// ── 属性标签映射 ──────────────────────────────────────────────────────────────
const PAGE_ATTR_LABELS: Record<string, string> = {
  product_name: "名称", model_number: "型号", model: "型号",
  name: "名称", brand: "品牌", color: "颜色", size: "尺寸",
  price: "价格", material: "材质",
};

// ── SKU 验证卡片 ──────────────────────────────────────────────────────────────
function SkuVerifyCard({
  sku, jobId, pageImages, imageUrlFn, onLightbox, onUpdated, onHover, onLeave, onDeleteSku, onDeleteImage,
}: {
  sku: PageDetail["skus"][number];
  jobId: string;
  pageImages: PageDetail["images"];
  imageUrlFn: (imageId: string) => string;
  onLightbox: (url: string) => void;
  onUpdated: () => Promise<void>;
  onHover?: () => void;
  onLeave?: () => void;
  onDeleteSku: () => void;
  onDeleteImage: (imageId: string) => void;
}) {
  const [binding, setBinding] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editingVal, setEditingVal] = useState("");
  const [addingAttr, setAddingAttr] = useState(false);
  const [newAttrKey, setNewAttrKey] = useState("");
  const [newAttrVal, setNewAttrVal] = useState("");
  const [attrSaving, setAttrSaving] = useState(false);
  const boundImageIds = new Set(sku.images.map((i) => i.image_id));

  const handleSaveAttr = async (key: string, value: string) => {
    if (attrSaving) return;
    setAttrSaving(true);
    try {
      await jobsApi.updateSku(jobId, sku.sku_id, { attributes: { [key]: value } });
      await onUpdated();
      setEditingKey(null);
    } catch (err) { console.error("保存属性失败:", err); }
    finally { setAttrSaving(false); }
  };

  const handleDeleteAttr = async (key: string) => {
    if (attrSaving) return;
    setAttrSaving(true);
    try {
      await jobsApi.updateSku(jobId, sku.sku_id, { attributes: { [key]: null } });
      await onUpdated();
    } catch (err) { console.error("删除属性失败:", err); }
    finally { setAttrSaving(false); }
  };

  const handleAddAttr = async () => {
    const k = newAttrKey.trim();
    if (!k || attrSaving) return;
    setAttrSaving(true);
    try {
      await jobsApi.updateSku(jobId, sku.sku_id, { attributes: { [k]: newAttrVal.trim() } });
      await onUpdated();
      setAddingAttr(false); setNewAttrKey(""); setNewAttrVal("");
    } catch (err) { console.error("添加属性失败:", err); }
    finally { setAttrSaving(false); }
  };

  const handleAddBinding = async (imageId: string) => {
    try {
      await jobsApi.addSkuBinding(jobId, sku.sku_id, imageId);
      await onUpdated();
    } catch (err) { console.error("添加绑定失败:", err); }
  };

  const handleUnbindImage = async (imageId: string) => {
    try {
      await jobsApi.removeSkuBinding(jobId, sku.sku_id, imageId);
      await onUpdated();
    } catch (err) { console.error("解绑失败:", err); }
  };

  const handleToggleValidity = async () => {
    if (saving) return;
    const next = sku.validity === "valid" ? "invalid" : "valid";
    setSaving(true);
    try {
      await jobsApi.updateSku(jobId, sku.sku_id, { validity: next });
      await onUpdated();
    } catch (err) {
      console.error("SKU 更新失败:", err);
    } finally {
      setSaving(false);
    }
  };

  const vc = sku.validity === "valid" ? "#22C55E" : sku.validity === "invalid" ? "#EF4444" : "#F59E0B";
  const vl = sku.validity === "valid" ? "有效" : sku.validity === "invalid" ? "无效" : "待审";
  const attr = sku.attributes as Record<string, any> | undefined;
  // All attribute entries (deduplicated by label for display, keep raw key for editing)
  const allAttrEntries: [string, string][] = Object.entries(attr ?? {}).filter(
    ([, v]) => v != null && String(v).trim() !== ""
  ).map(([k, v]) => [k, String(v)]);

  return (
    <div
      onMouseEnter={() => { setHovered(true); onHover?.(); }}
      onMouseLeave={() => { setHovered(false); onLeave?.(); }}
      style={{ marginBottom: 10, padding: 12, backgroundColor: hovered ? "#1F2E45" : "#1B2233", borderRadius: 6, border: `1px solid ${hovered ? "#22D3EE55" : "#2D3548"}`, transition: "background-color 0.15s, border-color 0.15s" }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", minWidth: 0 }}>
          <span style={{ padding: "1px 6px", fontSize: 11, borderRadius: 3, flexShrink: 0, backgroundColor: `${vc}18`, border: `1px solid ${vc}33`, color: vc }}>
            {vl}
          </span>
          <span style={{ fontSize: 13, fontWeight: 600, color: "#E2E8F0" }}>
            {attr?.model_number || attr?.model || sku.sku_id}
            {(attr?.product_name || attr?.name) ? ` ${attr.product_name || attr.name}` : ""}
            {attr?.size ? ` | ${attr.size}` : ""}
          </span>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center", flexShrink: 0 }}>
          <button
            onClick={(e) => { e.stopPropagation(); handleToggleValidity(); }}
            disabled={saving}
            style={{
              padding: "2px 8px", fontSize: 11, cursor: saving ? "not-allowed" : "pointer",
              backgroundColor: sku.validity === "valid" ? "#EF444418" : "#22C55E18",
              border: `1px solid ${sku.validity === "valid" ? "#EF444433" : "#22C55E33"}`,
              borderRadius: 3, color: sku.validity === "valid" ? "#EF4444" : "#22C55E",
            }}
          >
            {sku.validity === "valid" ? "标记无效" : "标记有效"}
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onDeleteSku(); }}
            style={{ padding: "2px 6px", fontSize: 11, cursor: "pointer", backgroundColor: "#EF444418", border: "1px solid #EF444433", borderRadius: 3, color: "#EF4444" }}
            title="删除SKU"
          >🗑</button>
        </div>
      </div>
      {/* ── 属性编辑区 ── */}
      <div style={{ marginBottom: 10 }}>
        {allAttrEntries.map(([key, val]) => (
          <div key={key} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3, fontSize: 12 }}>
            <span style={{ width: 80, flexShrink: 0, color: "#64748B", fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={key}>
              {PAGE_ATTR_LABELS[key] || key}
            </span>
            {editingKey === key ? (
              <>
                <input
                  autoFocus
                  value={editingVal}
                  onChange={(e) => setEditingVal(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleSaveAttr(key, editingVal); if (e.key === "Escape") setEditingKey(null); }}
                  style={{ flex: 1, padding: "1px 6px", fontSize: 12, backgroundColor: "#0F172A", border: "1px solid #22D3EE44", borderRadius: 3, color: "#E2E8F0", outline: "none" }}
                />
                <button onClick={() => handleSaveAttr(key, editingVal)} disabled={attrSaving}
                  style={{ padding: "1px 6px", fontSize: 11, cursor: "pointer", backgroundColor: "#22C55E18", border: "1px solid #22C55E44", borderRadius: 3, color: "#22C55E", flexShrink: 0 }}>✓</button>
                <button onClick={() => setEditingKey(null)}
                  style={{ padding: "1px 6px", fontSize: 11, cursor: "pointer", backgroundColor: "transparent", border: "1px solid #2D3548", borderRadius: 3, color: "#64748B", flexShrink: 0 }}>✕</button>
              </>
            ) : (
              <>
                <span
                  onClick={() => { setEditingKey(key); setEditingVal(val); }}
                  style={{ flex: 1, color: "#CBD5E1", cursor: "text", padding: "1px 4px", borderRadius: 3, border: "1px solid transparent" }}
                  onMouseEnter={(e) => { (e.target as HTMLElement).style.borderColor = "#2D3548"; }}
                  onMouseLeave={(e) => { (e.target as HTMLElement).style.borderColor = "transparent"; }}
                  title="点击编辑"
                >{val}</span>
                <button onClick={() => { setEditingKey(key); setEditingVal(val); }}
                  style={{ padding: "1px 5px", fontSize: 10, cursor: "pointer", backgroundColor: "transparent", border: "1px solid #2D3548", borderRadius: 3, color: "#475569", flexShrink: 0 }}>✏</button>
                <button onClick={() => handleDeleteAttr(key)} disabled={attrSaving}
                  style={{ padding: "1px 5px", fontSize: 10, cursor: "pointer", backgroundColor: "#EF444418", border: "1px solid #EF444433", borderRadius: 3, color: "#EF4444", flexShrink: 0 }}>✕</button>
              </>
            )}
          </div>
        ))}
        {/* ── 添加新属性 ── */}
        {addingAttr ? (
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4, fontSize: 12 }}>
            <input
              autoFocus
              placeholder="属性名"
              value={newAttrKey}
              onChange={(e) => setNewAttrKey(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleAddAttr(); if (e.key === "Escape") { setAddingAttr(false); setNewAttrKey(""); setNewAttrVal(""); } }}
              style={{ width: 80, flexShrink: 0, padding: "1px 6px", fontSize: 12, backgroundColor: "#0F172A", border: "1px solid #22D3EE44", borderRadius: 3, color: "#E2E8F0", outline: "none" }}
            />
            <input
              placeholder="属性值"
              value={newAttrVal}
              onChange={(e) => setNewAttrVal(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleAddAttr(); if (e.key === "Escape") { setAddingAttr(false); setNewAttrKey(""); setNewAttrVal(""); } }}
              style={{ flex: 1, padding: "1px 6px", fontSize: 12, backgroundColor: "#0F172A", border: "1px solid #22D3EE44", borderRadius: 3, color: "#E2E8F0", outline: "none" }}
            />
            <button onClick={handleAddAttr} disabled={attrSaving || !newAttrKey.trim()}
              style={{ padding: "1px 6px", fontSize: 11, cursor: "pointer", backgroundColor: "#22C55E18", border: "1px solid #22C55E44", borderRadius: 3, color: "#22C55E", flexShrink: 0 }}>✓</button>
            <button onClick={() => { setAddingAttr(false); setNewAttrKey(""); setNewAttrVal(""); }}
              style={{ padding: "1px 6px", fontSize: 11, cursor: "pointer", backgroundColor: "transparent", border: "1px solid #2D3548", borderRadius: 3, color: "#64748B", flexShrink: 0 }}>✕</button>
          </div>
        ) : (
          <button
            onClick={(e) => { e.stopPropagation(); setAddingAttr(true); }}
            style={{ marginTop: 4, padding: "1px 8px", fontSize: 11, cursor: "pointer", backgroundColor: "transparent", border: "1px dashed #2D3548", borderRadius: 3, color: "#475569" }}
          >+ 添加属性</button>
        )}
      </div>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 8, flexWrap: "wrap" }}>
        {sku.images.map((img) => (
          <div key={img.image_id} style={{ position: "relative", display: "inline-block" }}>
            <img
              src={imageUrlFn(img.image_id)}
              style={{ width: 130, height: 130, objectFit: "cover", borderRadius: 4, border: "1px solid #2D3548", cursor: "pointer", display: "block" }}
              onClick={(e) => { e.stopPropagation(); onLightbox(imageUrlFn(img.image_id)); }}
            />
            <button
              onClick={(e) => { e.stopPropagation(); handleUnbindImage(img.image_id); }}
              style={{ position: "absolute", top: 4, right: 4, width: 20, height: 20, backgroundColor: "#EF4444CC", border: "none", borderRadius: "50%", color: "#fff", fontSize: 11, cursor: "pointer", padding: 0, lineHeight: "20px", textAlign: "center" }}
              title="解除绑定"
            >✕</button>
          </div>
        ))}
        <button
          onClick={(e) => { e.stopPropagation(); setBinding(!binding); }}
          style={{
            padding: "4px 10px", fontSize: 11, cursor: "pointer", alignSelf: "flex-end",
            backgroundColor: binding ? "#F59E0B22" : "transparent",
            border: `1px solid ${binding ? "#F59E0B44" : "#2D3548"}`,
            borderRadius: 3, color: binding ? "#F59E0B" : "#64748B",
          }}
        >
          {binding ? "取消" : "+ 添加图片"}
        </button>
      </div>
      {binding && pageImages && pageImages.length > 0 && (
        <div style={{ marginTop: 8, padding: 8, backgroundColor: "#151C2C", borderRadius: 4, border: "1px dashed #F59E0B44" }}>
          <div style={{ fontSize: 11, color: "#F59E0B", marginBottom: 6 }}>
            点击图片添加绑定（绿色=已绑定，再次点击可解绑）
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {pageImages.map((img) => {
              const isBound = boundImageIds.has(img.image_id);
              return (
                <div key={img.image_id} style={{ position: "relative", display: "inline-block" }}>
                  <img
                    src={imageUrlFn(img.image_id)}
                    style={{ width: 80, height: 80, objectFit: "cover", borderRadius: 3, border: `2px solid ${isBound ? "#22C55E" : "#2D3548"}`, cursor: "pointer", display: "block" }}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (isBound) { handleUnbindImage(img.image_id); } else { handleAddBinding(img.image_id); }
                    }}
                    onMouseEnter={(e) => { (e.target as HTMLImageElement).style.borderColor = "#22D3EE"; }}
                    onMouseLeave={(e) => { (e.target as HTMLImageElement).style.borderColor = isBound ? "#22C55E" : "#2D3548"; }}
                  />
                  <button
                    onClick={(e) => { e.stopPropagation(); onDeleteImage(img.image_id); }}
                    style={{ position: "absolute", top: 2, right: 2, width: 16, height: 16, backgroundColor: "#EF4444CC", border: "none", borderRadius: "50%", color: "#fff", fontSize: 9, cursor: "pointer", padding: 0, lineHeight: "16px", textAlign: "center" }}
                    title="删除图片"
                  >✕</button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── 页面验证面板 ──────────────────────────────────────────────────────────────
function PageVerifyPanel({
  page, pageDetail, pages, reviewCompleting, jobId,
  screenshotUrl, imageUrl, onReviewComplete, onNavigate, onLightbox, onUpdated,
}: {
  page: { page_number: number; sku_count: number; needs_review: boolean; [key: string]: any };
  pageDetail: PageDetail | null;
  pages: Array<{ page_number: number; [key: string]: any }>;
  reviewCompleting: boolean;
  jobId: string;
  screenshotUrl: (pageNo: number) => string;
  imageUrl: (imageId: string) => string;
  onReviewComplete: (pageNo: number) => void;
  onNavigate: (pageNo: number) => void;
  onLightbox: (url: string) => void;
  onUpdated: () => Promise<void>;
}) {
  const idx = pages.findIndex((pp) => pp.page_number === page.page_number);
  const prevPage = idx > 0 ? pages[idx - 1] : null;
  const nextPage = idx < pages.length - 1 ? pages[idx + 1] : null;

  const [hoveredSkuId, setHoveredSkuId] = useState<string | null>(null);
  const [naturalSize, setNaturalSize] = useState<[number, number] | null>(null);
  const [cropMode, setCropMode] = useState(false);
  const [skuExtractMode, setSkuExtractMode] = useState(false);
  const [drawing, setDrawing] = useState<{ sx: number; sy: number; ex: number; ey: number } | null>(null);
  const [cropping, setCropping] = useState(false);
  const [skuExtracting, setSkuExtracting] = useState(false);
  const screenshotImgRef = useRef<HTMLImageElement>(null);

  let hoveredBboxes: number[][] = [];
  if (hoveredSkuId && pageDetail) {
    const hovSku = pageDetail.skus.find((s) => s.sku_id === hoveredSkuId);
    if (hovSku) {
      const boundIds = new Set(hovSku.images.map((i) => i.image_id));
      hoveredBboxes = pageDetail.images
        .filter((img) => boundIds.has(img.image_id) && img.bbox)
        .map((img) => img.bbox as number[]);
    }
  }

  const toImgCoords = (clientX: number, clientY: number) => {
    const img = screenshotImgRef.current;
    if (!img) return null;
    const rect = img.getBoundingClientRect();
    const dispX = Math.max(0, Math.min(clientX - rect.left, rect.width));
    const dispY = Math.max(0, Math.min(clientY - rect.top, rect.height));
    return { dispX, dispY, imgX: Math.round(dispX * img.naturalWidth / rect.width), imgY: Math.round(dispY * img.naturalHeight / rect.height) };
  };

  const handleCropMouseDown = (e: React.MouseEvent) => {
    e.preventDefault(); e.stopPropagation();
    const c = toImgCoords(e.clientX, e.clientY);
    if (c) setDrawing({ sx: c.dispX, sy: c.dispY, ex: c.dispX, ey: c.dispY });
  };

  const handleCropMouseMove = (e: React.MouseEvent) => {
    if (!drawing) return;
    const c = toImgCoords(e.clientX, e.clientY);
    if (c) setDrawing((d) => d ? { ...d, ex: c.dispX, ey: c.dispY } : d);
  };

  const handleCropMouseUp = async (e: React.MouseEvent) => {
    if (!drawing) return;
    e.stopPropagation();
    const img = screenshotImgRef.current;
    if (!img) { setDrawing(null); return; }
    const rect = img.getBoundingClientRect();
    const x1 = Math.round(Math.min(drawing.sx, drawing.ex) * img.naturalWidth / rect.width);
    const y1 = Math.round(Math.min(drawing.sy, drawing.ey) * img.naturalHeight / rect.height);
    const x2 = Math.round(Math.max(drawing.sx, drawing.ex) * img.naturalWidth / rect.width);
    const y2 = Math.round(Math.max(drawing.sy, drawing.ey) * img.naturalHeight / rect.height);
    setDrawing(null);
    if (x2 - x1 < 20 || y2 - y1 < 20) return;
    setCropping(true);
    try {
      await jobsApi.cropImage(jobId, page.page_number, [x1, y1, x2, y2]);
      await onUpdated(); setCropMode(false);
    } catch (err) { console.error("框选失败:", err); }
    finally { setCropping(false); }
  };

  const handleSkuExtractMouseUp = async (e: React.MouseEvent) => {
    if (!drawing) return;
    e.stopPropagation();
    const img = screenshotImgRef.current;
    if (!img) { setDrawing(null); return; }
    const rect = img.getBoundingClientRect();
    const x1 = Math.round(Math.min(drawing.sx, drawing.ex) * img.naturalWidth / rect.width);
    const y1 = Math.round(Math.min(drawing.sy, drawing.ey) * img.naturalHeight / rect.height);
    const x2 = Math.round(Math.max(drawing.sx, drawing.ex) * img.naturalWidth / rect.width);
    const y2 = Math.round(Math.max(drawing.sy, drawing.ey) * img.naturalHeight / rect.height);
    setDrawing(null);
    if (x2 - x1 < 20 || y2 - y1 < 20) return;
    setSkuExtracting(true);
    try {
      await jobsApi.skuFromRegion(jobId, page.page_number, [x1, y1, x2, y2]);
      await onUpdated();
      setSkuExtractMode(false);
    } catch (err) { console.error("框选识别SKU失败:", err); alert("识别失败，请重试"); }
    finally { setSkuExtracting(false); }
  };

  const handleDeleteImage = async (imageId: string) => {
    try { await jobsApi.deleteImage(jobId, page.page_number, imageId); await onUpdated(); }
    catch (err) { console.error("删除图片失败:", err); }
  };

  const handleCreateSku = async () => {
    try { await jobsApi.createSku(jobId, page.page_number); await onUpdated(); }
    catch (err) { console.error("新增SKU失败:", err); }
  };

  const handleDeleteSku = async (skuId: string) => {
    if (!window.confirm("确认删除该 SKU？")) return;
    try { await jobsApi.deleteSku(jobId, skuId); await onUpdated(); }
    catch (err) { console.error("删除SKU失败:", err); }
  };

  return (
    <div style={{ backgroundColor: "#151C2C", borderBottom: "2px solid #22D3EE33" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "8px 16px", borderBottom: "1px solid #1E293B", backgroundColor: "#0F172A" }}>
        <span style={{ fontSize: 12, color: "#94A3B8", fontWeight: 600 }}>
          ⚒ 第 {page.page_number} 页 · {pageDetail?.skus.length ?? page.sku_count} 个 SKU
        </span>
        <div style={{ flex: 1 }} />
        <button
          onClick={() => { setCropMode(!cropMode); setSkuExtractMode(false); setDrawing(null); }}
          style={{
            padding: "3px 10px", fontSize: 11, cursor: "pointer",
            backgroundColor: cropMode ? "#22D3EE22" : "transparent",
            border: `1px solid ${cropMode ? "#22D3EE44" : "#2D3548"}`,
            borderRadius: 3, color: cropMode ? "#22D3EE" : "#94A3B8",
          }}
        >
          {cropping ? "裁剪中..." : cropMode ? "取消框选" : "✏ 框选子图"}
        </button>
        <button
          onClick={() => { setSkuExtractMode(!skuExtractMode); setCropMode(false); setDrawing(null); }}
          style={{
            padding: "3px 10px", fontSize: 11, cursor: "pointer",
            backgroundColor: skuExtractMode ? "#A78BFA22" : "transparent",
            border: `1px solid ${skuExtractMode ? "#A78BFA44" : "#2D3548"}`,
            borderRadius: 3, color: skuExtractMode ? "#A78BFA" : "#94A3B8",
          }}
        >
          {skuExtracting ? "识别中..." : skuExtractMode ? "取消识别" : "🔍 框选识别SKU"}
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); prevPage && onNavigate(prevPage.page_number); }}
          disabled={!prevPage}
          style={{ padding: "3px 10px", fontSize: 11, cursor: prevPage ? "pointer" : "not-allowed", backgroundColor: "transparent", border: "1px solid #2D3548", borderRadius: 3, color: prevPage ? "#94A3B8" : "#374151" }}
        >
          ← 上一页
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); nextPage && onNavigate(nextPage.page_number); }}
          disabled={!nextPage}
          style={{ padding: "3px 10px", fontSize: 11, cursor: nextPage ? "pointer" : "not-allowed", backgroundColor: "transparent", border: "1px solid #2D3548", borderRadius: 3, color: nextPage ? "#94A3B8" : "#374151" }}
        >
          下一页 →
        </button>
        {page.needs_review && (
          <button
            onClick={(e) => { e.stopPropagation(); onReviewComplete(page.page_number); }}
            disabled={reviewCompleting}
            style={{ padding: "4px 14px", fontSize: 12, cursor: "pointer", backgroundColor: "#22C55E22", border: "1px solid #22C55E44", borderRadius: 4, color: "#22C55E", fontWeight: 500 }}
          >
            {reviewCompleting ? "提交中..." : "审核完成"}
          </button>
        )}
      </div>
      <div style={{ display: "flex" }}>
        <div style={{ width: 380, flexShrink: 0, padding: 16, borderRight: "1px solid #1E293B" }}>
          <div
            style={{ position: "relative", cursor: (cropMode || skuExtractMode) ? "crosshair" : "default", userSelect: "none" }}
            onMouseDown={(cropMode || skuExtractMode) ? handleCropMouseDown : undefined}
            onMouseMove={(cropMode || skuExtractMode) ? handleCropMouseMove : undefined}
            onMouseUp={cropMode ? handleCropMouseUp : skuExtractMode ? handleSkuExtractMouseUp : undefined}
            onMouseLeave={(cropMode || skuExtractMode) ? () => setDrawing(null) : undefined}
          >
            <img
              ref={screenshotImgRef}
              src={screenshotUrl(page.page_number)}
              alt={`page-${page.page_number}`}
              style={{ width: "100%", borderRadius: 4, border: "1px solid #2D3548", cursor: cropMode ? "crosshair" : "pointer", display: "block" }}
              onClick={(e) => { e.stopPropagation(); if (!cropMode) onLightbox(screenshotUrl(page.page_number)); }}
              onLoad={(e) => { const img = e.target as HTMLImageElement; setNaturalSize([img.naturalWidth, img.naturalHeight]); }}
              draggable={false}
            />
            {naturalSize && hoveredBboxes.map((bbox, i) => (
              <div key={i} style={{
                position: "absolute",
                left: `${(bbox[0] / naturalSize[0]) * 100}%`,
                top: `${(bbox[1] / naturalSize[1]) * 100}%`,
                width: `${((bbox[2] - bbox[0]) / naturalSize[0]) * 100}%`,
                height: `${((bbox[3] - bbox[1]) / naturalSize[1]) * 100}%`,
                border: "2px solid #22D3EE", borderRadius: 2,
                pointerEvents: "none", boxShadow: "0 0 0 2px #22D3EE33",
              }} />
            ))}
            {(cropMode || skuExtractMode) && drawing && (
              <div style={{
                position: "absolute",
                left: Math.min(drawing.sx, drawing.ex),
                top: Math.min(drawing.sy, drawing.ey),
                width: Math.abs(drawing.ex - drawing.sx),
                height: Math.abs(drawing.ey - drawing.sy),
                border: `2px dashed ${skuExtractMode ? "#A78BFA" : "#22D3EE"}`,
                backgroundColor: skuExtractMode ? "#A78BFA18" : "#22D3EE18",
                borderRadius: 2, pointerEvents: "none",
              }} />
            )}
            {cropping && (
              <div style={{ position: "absolute", inset: 0, backgroundColor: "#00000055", display: "flex", alignItems: "center", justifyContent: "center", borderRadius: 4 }}>
                <span style={{ color: "#fff", fontSize: 12, fontWeight: 500 }}>裁剪中...</span>
              </div>
            )}
          </div>
          <div style={{ textAlign: "center", fontSize: 11, color: "#475569", marginTop: 6 }}>第 {page.page_number} 页（点击放大）</div>
        </div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 560, maxHeight: 700 }}>
          {/* ── 页面子图展示区 ── */}
          <div style={{ padding: "10px 16px 10px", borderBottom: "1px solid #1E293B", flexShrink: 0 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
              <span style={{ fontSize: 12, color: "#94A3B8", fontWeight: 600 }}>
                页面子图 ({pageDetail?.images.length ?? 0})
              </span>
              <span style={{ fontSize: 11, color: "#475569" }}>
                {cropMode ? "在左侧截图上拖拽框选新图" : "点击放大 · ✕ 删除"}
              </span>
            </div>
            {!pageDetail && <span style={{ fontSize: 11, color: "#475569" }}>加载中...</span>}
            {pageDetail && pageDetail.images.length === 0 && (
              <span style={{ fontSize: 11, color: "#475569" }}>暂无子图，使用工具栏「✏ 框选子图」添加</span>
            )}
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {pageDetail?.images.map((img) => (
                <div key={img.image_id} style={{ position: "relative", display: "inline-block" }}>
                  <img
                    src={imageUrl(img.image_id)}
                    style={{ width: 80, height: 80, objectFit: "cover", borderRadius: 3, border: "1px solid #2D3548", cursor: "pointer", display: "block" }}
                    onClick={(e) => { e.stopPropagation(); onLightbox(imageUrl(img.image_id)); }}
                  />
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDeleteImage(img.image_id); }}
                    style={{ position: "absolute", top: 2, right: 2, width: 16, height: 16, backgroundColor: "#EF4444CC", border: "none", borderRadius: "50%", color: "#fff", fontSize: 9, cursor: "pointer", padding: 0, lineHeight: "16px", textAlign: "center" }}
                    title="删除子图"
                  >✕</button>
                </div>
              ))}
            </div>
          </div>

          {/* ── SKU 列表 ── */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 16px 0", flexShrink: 0 }}>
            <span style={{ fontSize: 12, color: "#64748B" }}>
              {pageDetail ? `${pageDetail.skus.length} 个 SKU` : ""}
            </span>
            <button
              onClick={handleCreateSku}
              style={{ padding: "3px 10px", fontSize: 11, cursor: "pointer", backgroundColor: "#22C55E18", border: "1px solid #22C55E44", borderRadius: 3, color: "#22C55E" }}
            >
              + 新增 SKU
            </button>
          </div>
          <div style={{ flex: 1, padding: 16, overflowY: "auto" }}>
            {!pageDetail && <span style={{ fontSize: 12, color: "#64748B" }}>加载中...</span>}
            {pageDetail && pageDetail.skus.length === 0 && <span style={{ fontSize: 12, color: "#64748B" }}>该页无 SKU</span>}
            {pageDetail?.skus.map((sku) => (
              <SkuVerifyCard
                key={sku.sku_id}
                sku={sku}
                jobId={jobId}
                pageImages={pageDetail.images}
                imageUrlFn={imageUrl}
                onLightbox={onLightbox}
                onUpdated={onUpdated}
                onHover={() => setHoveredSkuId(sku.sku_id)}
                onLeave={() => setHoveredSkuId(null)}
                onDeleteSku={() => handleDeleteSku(sku.sku_id)}
                onDeleteImage={handleDeleteImage}
              />
            ))}
          </div>
        </div>
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
  const [reviewStartTime] = useState<Record<number, number>>({});
  const [tab, setTab] = useState<"pages" | "skus" | "heatmap" | "eval">("pages");
  const [showTimeline, setShowTimeline] = useState(false);
  const [activities, setActivities] = useState<ActivityEntry[]>([]);
  const [exporting, setExporting] = useState(false);
  const [includeRaw, setIncludeRaw] = useState(false);
  const [exportProgress, setExportProgress] = useState<{
    progress: number;
    message: string;
    step: string;
  } | null>(null);
  const [reprocessing, setReprocessing] = useState(false);
  const [reprocessingPage, setReprocessingPage] = useState<number | null>(null);
  const actIdRef = useRef(0);

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

  const handleReprocessPage = async (pageNo: number) => {
    if (!jobId || reprocessingPage !== null) return;
    setReprocessingPage(pageNo);
    try {
      await jobsApi.reprocessPage(jobId, pageNo);
      await fetchPages(jobId);
      await fetchJob(jobId);
      // 如果当前展开的就是这一页，刷新详情
      if (expandedPage === pageNo) {
        try {
          const detail = await jobsApi.getPageDetail(jobId, pageNo);
          setPageDetail(detail);
        } catch { /* ignore */ }
      }
    } catch (e) {
      console.error("单页重新分析失败:", e);
      alert("重新分析失败，请稍后重试");
    } finally {
      setReprocessingPage(null);
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


  if (loading && !currentJob) return <Loading />;
  if (!currentJob) return <div className="page"><h2>Job 不存在</h2></div>;

  const job = currentJob;
  const completedPages = pages.filter((p) =>
    ["AI_COMPLETED", "HUMAN_COMPLETED", "IMPORTED_CONFIRMED", "IMPORTED_ASSUMED", "BLANK",
     "AI_FAILED", "IMPORT_FAILED", "DEAD_LETTER", "SKIPPED"].includes(p.status)
  ).length;
  const progress = job.total_pages > 0 ? completedPages / job.total_pages : 0;

  return (
    <div className="page job-detail-page">
      {/* 导出进度浮层 */}
      {exportProgress && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 9999,
          background: "rgba(0,0,0,0.55)", display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <div style={{
            background: "#1E293B", border: "1px solid #2D3548", borderRadius: 12,
            padding: "28px 36px", width: 340, boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
          }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: "#E2E8F0", marginBottom: 16 }}>
              {exportProgress.step === "error" ? "导出失败" : "正在导出 Excel…"}
            </div>
            {exportProgress.step !== "error" && (
              <div style={{ background: "#0F172A", borderRadius: 6, height: 8, marginBottom: 12, overflow: "hidden" }}>
                <div style={{
                  height: "100%", borderRadius: 6,
                  width: `${Math.max(0, exportProgress.progress)}%`,
                  background: exportProgress.step === "done" ? "#22C55E" : "#38BDF8",
                  transition: "width 0.4s ease",
                }} />
              </div>
            )}
            <div style={{ fontSize: 13, color: exportProgress.step === "error" ? "#F87171" : "#94A3B8" }}>
              {exportProgress.message}
            </div>
            {(exportProgress.step === "error") && (
              <button
                onClick={() => { setExportProgress(null); setExporting(false); }}
                style={{
                  marginTop: 16, padding: "6px 18px", borderRadius: 6, border: "none",
                  background: "#334155", color: "#E2E8F0", cursor: "pointer", fontSize: 13,
                }}
              >
                关闭
              </button>
            )}
          </div>
        </div>
      )}
      <div className="page-header">
        <div>
          <Link to="/jobs" className="back-link">← 返回列表</Link>
          <h2>{job.source_file}</h2>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <StatusBadge status={job.user_status} />
          <button
            onClick={async () => {
              if (reprocessing || !jobId) return;
              if (!window.confirm("确认重新分析该 PDF？将清空现有 SKU 和图片数据后重新提取。")) return;
              setReprocessing(true);
              try {
                await jobsApi.reprocessAI(jobId);
                await fetchJob(jobId);
                await fetchPages(jobId);
              } catch (e) {
                console.error("重新分析失败:", e);
                alert("重新分析失败，请稍后重试");
              } finally {
                setReprocessing(false);
              }
            }}
            disabled={reprocessing}
            style={{
              padding: "5px 14px",
              backgroundColor: reprocessing ? "#1E293B" : "#1D4ED8",
              border: "none",
              borderRadius: 4,
              color: reprocessing ? "#475569" : "#fff",
              cursor: reprocessing ? "not-allowed" : "pointer",
              fontSize: 13,
              fontWeight: 500,
            }}
          >
            {reprocessing ? "⏳ 提交中..." : "🔄 重新分析"}
          </button>
        </div>
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
        <label
          style={{
            display: "flex", alignItems: "center", gap: 4,
            fontSize: 12, color: "#94A3B8", cursor: "pointer", marginRight: 4,
            userSelect: "none",
          }}
          title="打开后同时导出原始全量 Excel"
        >
          <input
            type="checkbox"
            checked={includeRaw}
            onChange={(e) => setIncludeRaw(e.target.checked)}
            style={{ cursor: "pointer" }}
          />
          含原始数据
        </label>
        <button
          onClick={async () => {
            if (exporting || !jobId) return;
            setExporting(true);
            setExportProgress({ progress: 0, message: "准备中...", step: "starting" });
            try {
              const taskId = await jobsApi.startExportTask(jobId, includeRaw);
              const apiBase = (import.meta.env.VITE_API_BASE as string) || "/api/v1";
              await new Promise<void>((resolve, reject) => {
                const es = new EventSource(`${apiBase}/jobs/${jobId}/export/excel/${taskId}/events`);
                es.onmessage = (e) => {
                  try {
                    const data = JSON.parse(e.data);
                    setExportProgress({ progress: data.progress, message: data.message, step: data.step });
                    if (data.step === "done") {
                      es.close();
                      resolve();
                    } else if (data.step === "error") {
                      es.close();
                      reject(new Error(data.message || "导出失败"));
                    }
                  } catch { /* ignore parse errors */ }
                };
                es.onerror = () => { es.close(); reject(new Error("SSE 连接断开")); };
              });
              const baseName = job.source_file.replace(/\.pdf$/i, "");
              const filename = includeRaw ? `${baseName}_export.zip` : `${baseName}_export.xlsx`;
              await jobsApi.downloadExportTask(jobId, taskId, filename);
            } catch (e: any) {
              console.error("导出失败:", e);
              setExportProgress({ progress: -1, message: e.message || "导出失败，请稍后重试", step: "error" });
              return;
            } finally {
              setExporting(false);
            }
            setTimeout(() => setExportProgress(null), 1500);
          }}
          disabled={exporting}
          style={{
            padding: "4px 12px",
            backgroundColor: exporting ? "#1E293B" : "transparent",
            border: "1px solid #2D3548",
            borderRadius: 4,
            color: exporting ? "#475569" : "#94A3B8",
            cursor: exporting ? "not-allowed" : "pointer",
            fontSize: 12,
            marginRight: 4,
          }}
        >
          {exporting ? "⏳ 导出中..." : "📥 导出 Excel"}
        </button>
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
              <th style={{ width: 90 }}>操作</th>
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
                  <td onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => handleReprocessPage(p.page_number)}
                      disabled={reprocessingPage !== null}
                      title="重新分析该页"
                      style={{
                        padding: "2px 8px", fontSize: 11, cursor: reprocessingPage !== null ? "not-allowed" : "pointer",
                        backgroundColor: "transparent", border: "1px solid #2D3548", borderRadius: 3,
                        color: reprocessingPage === p.page_number ? "#F59E0B" : "#94A3B8",
                      }}
                    >
                      {reprocessingPage === p.page_number ? "⏳" : "🔄"}
                    </button>
                  </td>
                </tr>
                {expandedPage === p.page_number && (
                  <tr key={`detail-${p.id}`}>
                    <td colSpan={10} style={{ padding: 0 }}>
                      <PageVerifyPanel
                        page={p}
                        pageDetail={pageDetail}
                        pages={pages}
                        reviewCompleting={reviewCompleting}
                        jobId={jobId!}
                        screenshotUrl={screenshotUrl}
                        imageUrl={imageUrl}
                        onReviewComplete={handleReviewComplete}
                        onNavigate={toggleExpand}
                        onLightbox={setLightboxImg}
                        onUpdated={async () => {
                          if (!jobId || expandedPage === null) return;
                          try {
                            const detail = await jobsApi.getPageDetail(jobId, expandedPage);
                            setPageDetail(detail);
                          } catch { /* ignore */ }
                        }}
                      />
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
