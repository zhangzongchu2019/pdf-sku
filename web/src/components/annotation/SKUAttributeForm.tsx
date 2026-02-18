import type { AnnotationGroup } from "../../types/models";

/**
 * SKU 属性表单 [§6.5]
 * 编辑分组内的 SKU 属性 + 自定义属性
 */
interface SKUAttributeFormProps {
  group: AnnotationGroup;
  onUpdateAttribute: (field: string, value: string) => void;
  onAddCustomAttribute: (key: string, value: string) => void;
  onRemoveCustomAttribute: (index: number) => void;
  suggestions?: Record<string, string[]>;
}

export function SKUAttributeForm({
  group,
  onUpdateAttribute,
  onAddCustomAttribute,
  onRemoveCustomAttribute,
}: SKUAttributeFormProps) {
  const standardFields = [
    { key: "model", label: "型号" },
    { key: "name", label: "名称" },
    { key: "color", label: "颜色" },
    { key: "size", label: "尺码" },
    { key: "material", label: "材质" },
    { key: "price", label: "价格" },
    { key: "unit", label: "单位" },
    { key: "specification", label: "规格" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, padding: 8 }}>
      <h4 style={{ color: "#E2E8F4", fontSize: 13, margin: 0 }}>
        SKU 属性 — {group.label}
      </h4>

      {/* Standard fields */}
      {standardFields.map((field) => (
        <div key={field.key} style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <label
            style={{ width: 60, fontSize: 12, color: "#94A3B8", textAlign: "right" }}
          >
            {field.label}
          </label>
          <input
            value={group.skuAttributes[field.key] ?? ""}
            onChange={(e) => onUpdateAttribute(field.key, e.target.value)}
            placeholder={`输入${field.label}`}
            style={{
              flex: 1,
              padding: "4px 8px",
              fontSize: 12,
              backgroundColor: "#0F1117",
              border: "1px solid #2D3548",
              borderRadius: 4,
              color: "#E2E8F4",
              outline: "none",
            }}
          />
        </div>
      ))}

      {/* Custom attributes */}
      <div style={{ marginTop: 8 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 4,
          }}
        >
          <span style={{ fontSize: 12, color: "#94A3B8" }}>自定义属性</span>
          <button
            onClick={() => onAddCustomAttribute("", "")}
            style={{
              background: "none",
              border: "1px solid #2D3548",
              color: "#22D3EE",
              borderRadius: 4,
              padding: "2px 8px",
              cursor: "pointer",
              fontSize: 11,
            }}
          >
            + 添加
          </button>
        </div>
        {group.customAttributes.map((attr, idx) => (
          <div key={idx} style={{ display: "flex", gap: 4, marginBottom: 4 }}>
            <input
              value={attr.key}
              onChange={(e) =>
                onUpdateAttribute(`_custom_key_${idx}`, e.target.value)
              }
              placeholder="属性名"
              style={{
                width: 80,
                padding: "3px 6px",
                fontSize: 11,
                backgroundColor: "#0F1117",
                border: "1px solid #2D3548",
                borderRadius: 4,
                color: "#E2E8F4",
                outline: "none",
              }}
            />
            <input
              value={attr.value}
              onChange={(e) =>
                onUpdateAttribute(`_custom_val_${idx}`, e.target.value)
              }
              placeholder="属性值"
              style={{
                flex: 1,
                padding: "3px 6px",
                fontSize: 11,
                backgroundColor: "#0F1117",
                border: "1px solid #2D3548",
                borderRadius: 4,
                color: "#E2E8F4",
                outline: "none",
              }}
            />
            <button
              onClick={() => onRemoveCustomAttribute(idx)}
              style={{
                background: "none",
                border: "none",
                color: "#F87171",
                cursor: "pointer",
                fontSize: 12,
                padding: "0 4px",
              }}
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default SKUAttributeForm;
