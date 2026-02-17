import { useState } from "react";
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
}

export default function GroupPanel({
  skus, annotations, selectedSkuId,
  onSelectSku, onEditSku, onToggleValidity, onRemoveAnnotation,
}: Props) {
  const [expandedSku, setExpandedSku] = useState<string | null>(null);

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

          return (
            <div key={sku.sku_id}
                 className={`sku-card ${isSelected ? "selected" : ""}`}
                 onClick={() => onSelectSku(sku.sku_id)}>
              <div className="sku-card-header">
                <span className="sku-id">{sku.sku_id.slice(0, 12)}</span>
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
                    {Object.entries(sku.attributes).map(([key, val]) => (
                      <div key={key} className="attr-row">
                        <label>{key}</label>
                        <input
                          className="input input-sm"
                          defaultValue={val}
                          onBlur={(e) => {
                            if (e.target.value !== val) {
                              onEditSku(sku.sku_id, key, e.target.value);
                            }
                          }}
                        />
                      </div>
                    ))}
                  </div>

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
