/**
 * SKU 列表 — 展示提取结果表格
 */
import type { SKU } from "../../types/models";

interface SKUListProps {
  skus: SKU[];
  onReconcile?: (skuId: string) => void;
}

export function SKUList({ skus, onReconcile }: SKUListProps) {
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
              <tr
                key={sku.sku_id}
                style={{ borderBottom: "1px solid #2D354866" }}
              >
                <td style={{ padding: "6px", color: "#E2E8F4" }}>
                  {sku.attributes?.model ?? "—"}
                </td>
                <td style={{ padding: "6px", color: "#E2E8F4" }}>
                  {sku.attributes?.name ?? "—"}
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
                <td style={{ padding: "6px", color: "#94A3B8" }}>
                  {sku.images?.length ?? 0}
                </td>
                <td style={{ padding: "6px", color: "#94A3B8" }}>
                  {sku.page_number}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
