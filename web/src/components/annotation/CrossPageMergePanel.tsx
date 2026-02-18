/**
 * 跨页 SKU 合并面板
 * 管理跨页 SKU 片段，允许合并/拆分
 */
import { useState } from "react";
import type { CrossPageSKU } from "../../types/models";
import { GROUP_COLORS } from "../../utils/designTokens";

interface CrossPageMergePanelProps {
  crossPageSKUs: CrossPageSKU[];
  onMerge: (skuIds: string[]) => void;
  onSplit: (skuId: string) => void;
  onSelect: (skuId: string) => void;
}

export function CrossPageMergePanel({
  crossPageSKUs,
  onMerge,
  onSplit,
  onSelect,
}: CrossPageMergePanelProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleMerge = () => {
    if (selected.size < 2) return;
    onMerge(Array.from(selected));
    setSelected(new Set());
  };

  if (crossPageSKUs.length === 0) {
    return (
      <div style={{ padding: 16, color: "#64748B", fontSize: 13 }}>
        暂无跨页 SKU
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
        padding: 12,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 4,
        }}
      >
        <h4 style={{ margin: 0, fontSize: 13, color: "#E2E8F4" }}>
          跨页 SKU 片段 ({crossPageSKUs.length})
        </h4>
        {selected.size >= 2 && (
          <button
            onClick={handleMerge}
            style={{
              padding: "4px 10px",
              backgroundColor: "#22D3EE22",
              border: "1px solid #22D3EE44",
              borderRadius: 4,
              color: "#22D3EE",
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            合并选中 ({selected.size})
          </button>
        )}
      </div>

      {crossPageSKUs.map((sku, idx) => {
        const isChecked = selected.has(sku.xsku_id);
        const color = GROUP_COLORS[idx % GROUP_COLORS.length];
        const pageNos = sku.fragments.map((f) => f.page_number);

        return (
          <div
            key={sku.xsku_id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: 8,
              backgroundColor: isChecked ? "#22D3EE08" : "#1B2233",
              border: `1px solid ${isChecked ? "#22D3EE33" : "#2D3548"}`,
              borderRadius: 6,
              cursor: "pointer",
            }}
            onClick={() => onSelect(sku.xsku_id)}
          >
            <input
              type="checkbox"
              checked={isChecked}
              onChange={(e) => {
                e.stopPropagation();
                toggleSelect(sku.xsku_id);
              }}
              style={{ accentColor: "#22D3EE" }}
            />
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: 2,
                backgroundColor: color,
                flexShrink: 0,
              }}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: 12,
                  color: "#E2E8F4",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {sku.xsku_id}
              </div>
              <div style={{ fontSize: 11, color: "#64748B" }}>
                页面: {pageNos.join(", ")} · 片段:{" "}
                {sku.fragments.length} · {sku.status}
              </div>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onSplit(sku.xsku_id);
              }}
              title="拆分"
              style={{
                background: "none",
                border: "none",
                color: "#64748B",
                cursor: "pointer",
                fontSize: 14,
                padding: 4,
              }}
            >
              ✂
            </button>
          </div>
        );
      })}
    </div>
  );
}

export default CrossPageMergePanel;
