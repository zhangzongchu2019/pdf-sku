import { useState, useEffect } from "react";
import StatusBadge from "../common/StatusBadge";
import type { SKU, Annotation } from "../../types/models";

interface Props {
  skus: SKU[];
  annotations: Partial<Annotation>[];
  selectedSkuId: string | null;
  onSelectSku: (id: string | null) => void;
  onEditSku: (skuId: string, field: string, value: string) => void;
  onToggleValidity: (skuId: string, validity: string) => void;
  onRemoveAnnotation: (index: number) => void;
  ocrLoadingSkuIds?: Set<string>;
  skuSourceTexts?: Record<string, string>;
  extraBboxes?: Record<string, number[][]>;
}

/** Controlled editable attribute row — syncs with upstream value (e.g. OCR fill) while allowing local edits. */
function EditableAttrRow({ label, value, disabled, placeholder, onCommit }: {
  label: string;
  value: string;
  disabled?: boolean;
  placeholder?: string;
  onCommit: (v: string) => void;
}) {
  const [local, setLocal] = useState(value);
  // Sync from upstream when value changes (e.g. OCR fill)
  useEffect(() => { setLocal(value); }, [value]);
  return (
    <div className="attr-row">
      <label>{label}</label>
      <input
        className="input input-sm"
        value={local}
        placeholder={placeholder}
        disabled={disabled}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (local !== value) onCommit(local);
        }}
      />
    </div>
  );
}

const ATTRIBUTE_KEYS = [
  "product_name", "model_number", "price", "description",
  "material", "color", "size", "weight",
];

export default function GroupPanel({
  skus, annotations, selectedSkuId,
  onSelectSku, onEditSku, onToggleValidity, onRemoveAnnotation,
  ocrLoadingSkuIds = new Set(),
  skuSourceTexts = {},
  extraBboxes = {},
}: Props) {
  const [expandedSku, setExpandedSku] = useState<string | null>(null);

  // Auto-expand selected SKU (e.g. after drawing a box)
  useEffect(() => {
    if (selectedSkuId) setExpandedSku(selectedSkuId);
  }, [selectedSkuId]);

  return (
    <div className="group-panel">
      <h3>SKU 列表 ({skus.length})</h3>

      <div className="sku-list">
        {skus.map((sku) => {
          const isSelected = selectedSkuId === sku.sku_id;
          const isExpanded = expandedSku === sku.sku_id;
          const skuAnnotations = annotations.filter(
            (a) => a.payload?.sku_id === sku.sku_id
          );
          const isOcrLoading = ocrLoadingSkuIds.has(sku.sku_id);
          const sourceText = skuSourceTexts[sku.sku_id];
          const extras = extraBboxes[sku.sku_id];

          // For manual SKUs, always show all standard attribute keys (+ any extras from OCR)
          const isManual = sku.sku_id.startsWith("manual_");
          const attrKeys = Object.keys(sku.attributes);
          const displayKeys = isManual
            ? [...new Set([...ATTRIBUTE_KEYS, ...attrKeys])]
            : attrKeys;

          return (
            <div key={sku.sku_id}
                 className={`sku-card ${isSelected ? "selected" : ""}`}
                 onClick={() => onSelectSku(sku.sku_id)}>
              <div className="sku-card-header">
                <span className="sku-id">{sku.sku_id.slice(0, 12)}</span>
                {isManual && (
                  <span className="manual-badge">手动添加</span>
                )}
                {isOcrLoading && (
                  <span className="ocr-badge" style={{
                    fontSize: 11, padding: "1px 6px",
                    backgroundColor: "#1890ff18", border: "1px solid #1890ff33",
                    borderRadius: 3, color: "#1890ff", animation: "pulse 1.5s infinite",
                  }}>OCR 识别中...</span>
                )}
                {extras && extras.length > 0 && (
                  <span style={{
                    fontSize: 11, padding: "1px 6px",
                    backgroundColor: "#52c41a18", border: "1px solid #52c41a33",
                    borderRadius: 3, color: "#52c41a",
                  }}>{extras.length + 1} 区域</span>
                )}
                <StatusBadge status={sku.validity} />
                {skuAnnotations.length > 0 && (
                  <span className="annotation-badge">{skuAnnotations.length} 修改</span>
                )}
                <button className="btn-expand"
                        onClick={(e) => { e.stopPropagation(); setExpandedSku(isExpanded ? null : sku.sku_id); }}>
                  {isExpanded ? "▲" : "▼"}
                </button>
              </div>

              {isExpanded && (
                <div className="sku-card-body">
                  <div className="sku-attributes">
                    {displayKeys.map((key) => (
                      <EditableAttrRow
                        key={key}
                        label={key}
                        value={sku.attributes[key] || ""}
                        placeholder={isOcrLoading ? "识别中..." : ""}
                        disabled={isOcrLoading}
                        onCommit={(v) => onEditSku(sku.sku_id, key, v)}
                      />
                    ))}
                  </div>

                  {sourceText && (
                    <div className="ocr-source-text" style={{
                      marginTop: 8, padding: 8,
                      backgroundColor: "#f5f5f5", borderRadius: 4,
                      fontSize: 12, color: "#666",
                      whiteSpace: "pre-wrap", maxHeight: 120, overflowY: "auto",
                    }}>
                      <div style={{ fontWeight: 600, marginBottom: 4, color: "#333" }}>OCR 原文</div>
                      {sourceText}
                    </div>
                  )}

                  <div className="sku-actions">
                    <button className={`btn btn-sm ${sku.validity === "valid" ? "btn-danger" : "btn-success"}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              onToggleValidity(sku.sku_id, sku.validity === "valid" ? "invalid" : "valid");
                            }}>
                      {sku.validity === "valid" ? "标记无效" : "标记有效"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {annotations.length > 0 && (
        <div className="annotation-summary">
          <h4>本次修改 ({annotations.length})</h4>
          {annotations.map((a, i) => (
            <div key={i} className="annotation-item">
              <span className="annotation-type">{a.type}</span>
              <span className="annotation-detail">
                {a.payload?.field ? `${a.payload.field}: ${a.payload.value}` : a.type}
              </span>
              <button className="btn-remove" onClick={() => onRemoveAnnotation(i)}>✕</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
