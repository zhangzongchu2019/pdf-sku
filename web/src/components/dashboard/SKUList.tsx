/**
 * SKU 列表 — 展示提取结果表格，支持行内编辑属性
 * 按 product_id 分组显示：产品行（名称+图片+SKU数）→ 子行（变体）
 * 无 product_id 的保持原样（向后兼容）
 */
import { useState, useEffect, useMemo } from "react";
import { jobsApi } from "../../api/jobs";
import type { SKU } from "../../types/models";

interface SKUListProps {
  skus: SKU[];
  jobId?: string;
  onReconcile?: (skuId: string) => void;
  onSkuUpdated?: () => void;
}

const ATTR_LABELS: Record<string, string> = {
  product_name: "名称", model_number: "型号", model: "型号",
  name: "名称", brand: "品牌", category: "分类",
  price: "价格", unit: "单位", spec: "规格",
  material: "材质", color: "颜色", size: "尺寸",
  weight: "重量", origin: "产地", barcode: "条码",
  description: "描述",
};

/** Controlled input that syncs with upstream value. */
function EditableField({ value, onCommit, disabled }: {
  value: string;
  onCommit: (v: string) => void;
  disabled?: boolean;
}) {
  const [local, setLocal] = useState(value);
  useEffect(() => { setLocal(value); }, [value]);
  return (
    <input
      value={local}
      onChange={(e) => setLocal(e.target.value)}
      onBlur={() => { if (local !== value) onCommit(local); }}
      onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
      disabled={disabled}
      style={{
        backgroundColor: "transparent", border: "1px solid #2D3548",
        borderRadius: 3, padding: "2px 6px", color: "#E2E8F0",
        fontSize: 13, width: "100%",
      }}
    />
  );
}

interface ProductGroup {
  product_id: string;
  product_name: string;
  model_number: string;
  skus: SKU[];
}

function groupByProduct(skus: SKU[]): { groups: ProductGroup[]; ungrouped: SKU[] } {
  const map = new Map<string, SKU[]>();
  const ungrouped: SKU[] = [];

  for (const sku of skus) {
    if (sku.product_id) {
      const list = map.get(sku.product_id) || [];
      list.push(sku);
      map.set(sku.product_id, list);
    } else {
      ungrouped.push(sku);
    }
  }

  const groups: ProductGroup[] = [];
  for (const [pid, items] of map) {
    const first = items[0];
    groups.push({
      product_id: pid,
      product_name: first.attributes?.product_name ?? first.attributes?.name ?? "",
      model_number: first.attributes?.model_number ?? first.attributes?.model ?? "",
      skus: items,
    });
  }

  return { groups, ungrouped };
}

export function SKUList({ skus, jobId, onReconcile, onSkuUpdated }: SKUListProps) {
  const [lightboxImg, setLightboxImg] = useState<string | null>(null);
  const [expandedSku, setExpandedSku] = useState<string | null>(null);
  const [expandedProduct, setExpandedProduct] = useState<string | null>(null);
  const [editingSku, setEditingSku] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const apiBase = import.meta.env.VITE_API_BASE || "/api/v1";
  const imgUrl = (imageId: string) =>
    jobId ? `${apiBase}/jobs/${jobId}/images/${imageId}` : "";
  const validCount = skus.filter((s) => s.validity === "valid").length;
  const needsReviewCount = skus.filter((s) => s.validity === "needs_review").length;
  const invalidCount = skus.filter((s) => s.validity === "invalid").length;
  const assumedCount = skus.filter((s) => s.import_confirmation === "assumed").length;
  const confirmedCount = skus.filter((s) => s.import_confirmation === "confirmed").length;

  const { groups, ungrouped } = useMemo(() => groupByProduct(skus), [skus]);
  const hasGroups = groups.length > 0;

  const handleSaveAttr = async (skuId: string, field: string, value: string) => {
    if (!jobId) return;
    setSaving(true);
    try {
      await jobsApi.updateSku(jobId, skuId, { attributes: { [field]: value } });
      onSkuUpdated?.();
    } catch (e) {
      console.error("SKU 更新失败:", e);
    } finally {
      setSaving(false);
    }
  };

  const handleToggleValidity = async (sku: SKU) => {
    if (!jobId) return;
    const newValidity = sku.validity === "valid" ? "invalid" : "valid";
    setSaving(true);
    try {
      await jobsApi.updateSku(jobId, sku.sku_id, { validity: newValidity });
      onSkuUpdated?.();
    } catch (e) {
      console.error("SKU 更新失败:", e);
    } finally {
      setSaving(false);
    }
  };

  const renderSkuRow = (sku: SKU, indent: boolean = false) => (
    <>
      <tr
        key={sku.sku_id}
        style={{ borderBottom: "1px solid #E5E7EB66", cursor: "pointer" }}
        onClick={() => setExpandedSku(expandedSku === sku.sku_id ? null : sku.sku_id)}
      >
        <td style={{ padding: "6px", paddingLeft: indent ? 28 : 6, color: "#1F2937", fontWeight: 500 }}>
          {indent && <span style={{ color: "#CBD5E1", marginRight: 4 }}>└</span>}
          {sku.variant_label || (sku.attributes?.model_number ?? sku.attributes?.model ?? "—")}
        </td>
        <td style={{ padding: "6px", color: "#1F2937", fontWeight: 500 }}>
          {indent && sku.variant_label
            ? (sku.attributes?.size ?? sku.attributes?.color ?? "—")
            : (sku.attributes?.product_name ?? sku.attributes?.name ?? "—")}
        </td>
        <td style={{ padding: "6px" }}>
          <ValidityTag validity={sku.validity} />
        </td>
        <td style={{ padding: "6px", color: "#94A3B8" }}>
          {sku.status ?? "—"}
        </td>
        <td style={{ padding: "6px" }}>
          <ImportTag status={sku.import_status} />
        </td>
        <td style={{ padding: "6px" }}>
          {jobId && sku.images && sku.images.length > 0 ? (
            <div style={{ display: "flex", gap: 2, alignItems: "center" }}>
              {sku.images.slice(0, 3).map((img: any) => (
                <img
                  key={img.image_id}
                  src={imgUrl(img.image_id)}
                  style={{ width: 32, height: 32, objectFit: "cover", borderRadius: 2, border: "1px solid #E5E7EB", cursor: "pointer" }}
                  onClick={(e) => { e.stopPropagation(); setLightboxImg(imgUrl(img.image_id)); }}
                />
              ))}
              {sku.images.length > 3 && (
                <span style={{ fontSize: 10, color: "#64748B" }}>+{sku.images.length - 3}</span>
              )}
            </div>
          ) : (
            <span style={{ color: "#64748B", fontSize: 11 }}>{sku.images?.length ?? 0}</span>
          )}
        </td>
        <td style={{ padding: "6px", color: "#94A3B8" }}>
          {sku.page_number}
        </td>
        <td style={{ padding: "6px" }}>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setExpandedSku(sku.sku_id);
              setEditingSku(editingSku === sku.sku_id ? null : sku.sku_id);
            }}
            style={{
              padding: "2px 8px", fontSize: 11, cursor: "pointer",
              backgroundColor: editingSku === sku.sku_id ? "#22D3EE22" : "transparent",
              border: "1px solid #2D3548", borderRadius: 3,
              color: editingSku === sku.sku_id ? "#22D3EE" : "#94A3B8",
            }}
          >
            {editingSku === sku.sku_id ? "完成" : "编辑"}
          </button>
        </td>
      </tr>
      {expandedSku === sku.sku_id && (
        <tr key={`detail-${sku.sku_id}`}>
          <td colSpan={8} style={{ padding: 0 }}>
            <div style={{
              padding: "10px 16px",
              backgroundColor: "#F8FAFC",
              borderBottom: "2px solid #E2E8F0",
              display: "flex",
              gap: 24,
            }}>
              {/* Attributes */}
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12, color: "#374151", marginBottom: 6, fontWeight: 600 }}>
                  全部属性
                  {saving && <span style={{ marginLeft: 8, color: "#94A3B8", fontWeight: 400 }}>保存中...</span>}
                </div>
                {editingSku === sku.sku_id ? (
                  <div style={{ display: "grid", gridTemplateColumns: "100px 1fr", gap: "4px 8px", fontSize: 13 }}>
                    {Object.entries(sku.attributes || {}).map(([key, val]) => (
                      <>
                        <span key={`k-${key}`} style={{ color: "#6B7280", fontWeight: 500, lineHeight: "28px" }}>
                          {ATTR_LABELS[key] || key}
                        </span>
                        <EditableField
                          key={`v-${key}`}
                          value={String(val ?? "")}
                          disabled={saving}
                          onCommit={(v) => handleSaveAttr(sku.sku_id, key, v)}
                        />
                      </>
                    ))}
                  </div>
                ) : (
                  <div style={{ display: "grid", gridTemplateColumns: "100px 1fr", gap: "4px 8px", fontSize: 13 }}>
                    {Object.entries(sku.attributes || {}).map(([key, val]) => (
                      val != null && String(val).trim() !== "" ? (
                        <>
                          <span key={`k-${key}`} style={{ color: "#6B7280", fontWeight: 500 }}>{ATTR_LABELS[key] || key}</span>
                          <span key={`v-${key}`} style={{ color: "#1F2937" }}>{String(val)}</span>
                        </>
                      ) : null
                    ))}
                    {Object.values(sku.attributes || {}).every((v) => v == null || String(v).trim() === "") && (
                      <span style={{ color: "#9CA3AF", gridColumn: "1 / -1" }}>无有效属性</span>
                    )}
                  </div>
                )}
                <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center" }}>
                  <span style={{ fontSize: 11, color: "#9CA3AF" }}>
                    SKU ID: {sku.sku_id}
                    {sku.product_id && <> | 产品组: {sku.product_id}</>}
                    {sku.variant_label && <> | 变体: {sku.variant_label}</>}
                    {" "}| 来源: {sku.attribute_source}
                  </span>
                  {jobId && (
                    <button
                      onClick={(e) => { e.stopPropagation(); handleToggleValidity(sku); }}
                      disabled={saving}
                      style={{
                        padding: "2px 8px", fontSize: 11, cursor: "pointer",
                        backgroundColor: sku.validity === "valid" ? "#EF444418" : "#22C55E18",
                        border: `1px solid ${sku.validity === "valid" ? "#EF444433" : "#22C55E33"}`,
                        borderRadius: 3,
                        color: sku.validity === "valid" ? "#EF4444" : "#22C55E",
                      }}
                    >
                      {sku.validity === "valid" ? "标记无效" : "标记有效"}
                    </button>
                  )}
                </div>
              </div>
              {/* Images */}
              {jobId && sku.images && sku.images.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, color: "#64748B", marginBottom: 6 }}>关联图片 ({sku.images.length})</div>
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    {sku.images.map((img: any) => (
                      <img
                        key={img.image_id}
                        src={imgUrl(img.image_id)}
                        style={{ width: 64, height: 64, objectFit: "cover", borderRadius: 3, border: "1px solid #E5E7EB", cursor: "pointer" }}
                        onClick={(e) => { e.stopPropagation(); setLightboxImg(imgUrl(img.image_id)); }}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );

  const renderProductGroup = (group: ProductGroup) => {
    const isExpanded = expandedProduct === group.product_id;
    const firstImg = group.skus.find(s => s.images && s.images.length > 0)?.images?.[0];
    return (
      <>
        <tr
          key={`pg-${group.product_id}`}
          style={{
            borderBottom: "1px solid #E5E7EB",
            backgroundColor: "#F8FAFC",
            cursor: "pointer",
          }}
          onClick={() => setExpandedProduct(isExpanded ? null : group.product_id)}
        >
          <td style={{ padding: "8px 6px", fontWeight: 600, color: "#1E293B" }}>
            <span style={{ marginRight: 6, fontSize: 10, color: "#94A3B8" }}>
              {isExpanded ? "▼" : "▶"}
            </span>
            {group.model_number || "—"}
          </td>
          <td style={{ padding: "8px 6px", fontWeight: 600, color: "#1E293B" }}>
            {group.product_name || "—"}
          </td>
          <td colSpan={2} style={{ padding: "8px 6px", fontSize: 11, color: "#64748B" }}>
            {group.skus.length} 个变体
          </td>
          <td style={{ padding: "8px 6px" }} />
          <td style={{ padding: "8px 6px" }}>
            {firstImg && jobId && (
              <img
                src={imgUrl(firstImg.image_id)}
                style={{ width: 32, height: 32, objectFit: "cover", borderRadius: 2, border: "1px solid #E5E7EB", cursor: "pointer" }}
                onClick={(e) => { e.stopPropagation(); setLightboxImg(imgUrl(firstImg.image_id)); }}
              />
            )}
          </td>
          <td style={{ padding: "8px 6px", color: "#94A3B8", fontSize: 11 }}>
            P{group.skus[0]?.page_number}
          </td>
          <td style={{ padding: "8px 6px" }} />
        </tr>
        {isExpanded && group.skus.map((sku) => renderSkuRow(sku, true))}
      </>
    );
  };

  return (
    <div>
      {/* Summary bar */}
      <div
        style={{
          display: "flex",
          gap: 12,
          marginBottom: 12,
          padding: "8px 12px",
          backgroundColor: "#F1F5F9",
          borderRadius: 6,
          fontSize: 12,
          color: "#475569",
        }}
      >
        <span>共 {skus.length} 个SKU</span>
        {hasGroups && <span style={{ color: "#6366F1" }}>{groups.length} 个产品组</span>}
        <span style={{ color: "#22C55E" }}>有效 {validCount}</span>
        <span style={{ color: "#F59E0B" }}>待审 {needsReviewCount}</span>
        <span style={{ color: "#EF4444" }}>无效 {invalidCount}</span>
        <span>导入确认 {confirmedCount}</span>
        {assumedCount > 0 && (
          <>
            <span style={{ color: "#A855F7" }}>假设 {assumedCount}</span>
            {onReconcile && (
              <button
                onClick={() => onReconcile("")}
                style={{
                  padding: "2px 8px",
                  backgroundColor: "#A855F722",
                  border: "1px solid #A855F744",
                  borderRadius: 3,
                  color: "#A855F7",
                  cursor: "pointer",
                  fontSize: 11,
                }}
              >
                触发对账
              </button>
            )}
          </>
        )}
      </div>

      {/* Table */}
      <div style={{ overflowX: "auto" }}>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontSize: 12,
            color: "#374151",
          }}
        >
          <thead>
            <tr style={{ borderBottom: "1px solid #E5E7EB" }}>
              {["型号", "名称", "有效性", "状态", "导入确认", "图片数", "页码", "操作"].map(
                (h) => (
                  <th
                    key={h}
                    style={{
                      padding: "8px 6px",
                      textAlign: "left",
                      color: "#6B7280",
                      fontWeight: 600,
                      fontSize: 11,
                    }}
                  >
                    {h}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {groups.map((group) => renderProductGroup(group))}
            {ungrouped.map((sku) => renderSkuRow(sku))}
          </tbody>
        </table>
      </div>

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

function ValidityTag({ validity }: { validity?: string }) {
  const map: Record<string, { label: string; color: string }> = {
    valid: { label: "有效", color: "#22C55E" },
    needs_review: { label: "待审", color: "#F59E0B" },
    invalid: { label: "无效", color: "#EF4444" },
  };
  const info = map[validity ?? ""] ?? { label: validity ?? "—", color: "#64748B" };
  return (
    <span
      style={{
        padding: "1px 6px",
        backgroundColor: `${info.color}18`,
        border: `1px solid ${info.color}33`,
        borderRadius: 3,
        fontSize: 11,
        color: info.color,
      }}
    >
      {info.label}
    </span>
  );
}

function ImportTag({ status }: { status?: string }) {
  if (status === "confirmed")
    return <span style={{ color: "#22C55E", fontSize: 11 }}>✓ 确认</span>;
  if (status === "assumed")
    return <span style={{ color: "#A855F7", fontSize: 11 }}>~ 假设</span>;
  return <span style={{ color: "#64748B", fontSize: 11 }}>—</span>;
}

export default SKUList;
