/**
 * SKU 列表 — 展示提取结果表格
 */
import { useState } from "react";
import type { SKU } from "../../types/models";

interface SKUListProps {
  skus: SKU[];
  jobId?: string;
  onReconcile?: (skuId: string) => void;
}

const ATTR_LABELS: Record<string, string> = {
  product_name: "名称", model_number: "型号", model: "型号",
  name: "名称", brand: "品牌", category: "分类",
  price: "价格", unit: "单位", spec: "规格",
  material: "材质", color: "颜色", size: "尺寸",
  weight: "重量", origin: "产地", barcode: "条码",
  description: "描述",
};

export function SKUList({ skus, jobId, onReconcile }: SKUListProps) {
  const [lightboxImg, setLightboxImg] = useState<string | null>(null);
  const [expandedSku, setExpandedSku] = useState<string | null>(null);
  const apiBase = import.meta.env.VITE_API_BASE || "/api/v1";
  const imgUrl = (imageId: string) =>
    jobId ? `${apiBase}/jobs/${jobId}/images/${imageId}` : "";
  const validCount = skus.filter((s) => s.validity === "valid").length;
  const needsReviewCount = skus.filter((s) => s.validity === "needs_review").length;
  const invalidCount = skus.filter((s) => s.validity === "invalid").length;
  const assumedCount = skus.filter((s) => s.import_confirmation === "assumed").length;
  const confirmedCount = skus.filter((s) => s.import_confirmation === "confirmed").length;

  return (
    <div>
      {/* Summary bar */}
      <div
        style={{
          display: "flex",
          gap: 12,
          marginBottom: 12,
          padding: "8px 12px",
          backgroundColor: "#1B2233",
          borderRadius: 6,
          fontSize: 12,
          color: "#94A3B8",
        }}
      >
        <span>共 {skus.length} 个SKU</span>
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
            color: "#E2E8F4",
          }}
        >
          <thead>
            <tr style={{ borderBottom: "1px solid #2D3548" }}>
              {["型号", "名称", "有效性", "状态", "导入确认", "图片数", "页码"].map(
                (h) => (
                  <th
                    key={h}
                    style={{
                      padding: "8px 6px",
                      textAlign: "left",
                      color: "#64748B",
                      fontWeight: 500,
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
            {skus.map((sku) => (
              <>
                <tr
                  key={sku.sku_id}
                  style={{ borderBottom: "1px solid #2D354866", cursor: "pointer" }}
                  onClick={() => setExpandedSku(expandedSku === sku.sku_id ? null : sku.sku_id)}
                >
                  <td style={{ padding: "6px", color: "#E2E8F4" }}>
                    {sku.attributes?.model_number ?? sku.attributes?.model ?? "—"}
                  </td>
                  <td style={{ padding: "6px", color: "#E2E8F4" }}>
                    {sku.attributes?.product_name ?? sku.attributes?.name ?? "—"}
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
                            style={{ width: 32, height: 32, objectFit: "cover", borderRadius: 2, border: "1px solid #2D3548", cursor: "pointer" }}
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
                </tr>
                {expandedSku === sku.sku_id && (
                  <tr key={`detail-${sku.sku_id}`}>
                    <td colSpan={7} style={{ padding: 0 }}>
                      <div style={{
                        padding: "10px 16px",
                        backgroundColor: "#151C2C",
                        borderBottom: "2px solid #22D3EE33",
                        display: "flex",
                        gap: 24,
                      }}>
                        {/* Attributes */}
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 12, color: "#CBD5E1", marginBottom: 6, fontWeight: 600 }}>全部属性</div>
                          <div style={{ display: "grid", gridTemplateColumns: "100px 1fr", gap: "4px 8px", fontSize: 13 }}>
                            {Object.entries(sku.attributes || {}).map(([key, val]) => (
                              val != null && String(val).trim() !== "" ? (
                                <>
                                  <span key={`k-${key}`} style={{ color: "#94A3B8", fontWeight: 500 }}>{ATTR_LABELS[key] || key}</span>
                                  <span key={`v-${key}`} style={{ color: "#F1F5F9" }}>{String(val)}</span>
                                </>
                              ) : null
                            ))}
                            {Object.values(sku.attributes || {}).every((v) => v == null || String(v).trim() === "") && (
                              <span style={{ color: "#94A3B8", gridColumn: "1 / -1" }}>无有效属性</span>
                            )}
                          </div>
                          <div style={{ marginTop: 8, fontSize: 11, color: "#94A3B8" }}>
                            SKU ID: {sku.sku_id} | 来源: {sku.attribute_source}
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
                                  style={{ width: 64, height: 64, objectFit: "cover", borderRadius: 3, border: "1px solid #2D3548", cursor: "pointer" }}
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
            ))}
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
