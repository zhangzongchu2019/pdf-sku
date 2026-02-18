import type { AnnotationGroup } from "../../types/models";
import { GROUP_COLORS } from "../../utils/designTokens";

/**
 * 分组编辑器 — 右面板 [§6.5]
 */
interface GroupEditorProps {
  groups: AnnotationGroup[];
  selectedGroupId: string | null;
  onSelectGroup: (groupId: string) => void;
  onDeleteGroup: (groupId: string) => void;
  onUpdateAttribute: (groupId: string, field: string, value: string) => void;
  onRenameGroup: (groupId: string, label: string) => void;
}

export function GroupEditor({
  groups,
  selectedGroupId,
  onSelectGroup,
  onDeleteGroup,
  onUpdateAttribute,
  onRenameGroup,
}: GroupEditorProps) {
  if (groups.length === 0) {
    return (
      <div
        data-tour="group-editor"
        style={{
          padding: 16,
          color: "#64748B",
          textAlign: "center",
          fontSize: 13,
        }}
      >
        <p>暂无分组</p>
        <p style={{ fontSize: 12, marginTop: 8 }}>
          使用套索工具 (L) 选中元素，按 G 创建分组
        </p>
      </div>
    );
  }

  return (
    <div
      data-tour="group-editor"
      aria-label="分组编辑区"
      role="region"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
        padding: 8,
        overflowY: "auto",
      }}
    >
      {groups.map((group, idx) => {
        const isSelected = group.id === selectedGroupId;
        const color = GROUP_COLORS[idx % GROUP_COLORS.length];

        return (
          <div
            key={group.id}
            onClick={() => onSelectGroup(group.id)}
            aria-label={`分组 ${group.label} 编辑区`}
            style={{
              border: isSelected ? `2px solid ${color}` : "1px solid #2D3548",
              borderRadius: 8,
              padding: 12,
              backgroundColor: isSelected ? `${color}11` : "#1A1F2C",
              cursor: "pointer",
            }}
          >
            {/* Group header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 8,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span
                  style={{
                    width: 12,
                    height: 12,
                    borderRadius: 3,
                    backgroundColor: color,
                  }}
                />
                <input
                  value={group.label}
                  onChange={(e) => onRenameGroup(group.id, e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                  style={{
                    background: "none",
                    border: "none",
                    color: "#E2E8F4",
                    fontSize: 14,
                    fontWeight: 500,
                    outline: "none",
                    padding: 0,
                    width: 120,
                  }}
                />
                <span style={{ color: "#64748B", fontSize: 11 }}>
                  ({group.elementIds.length} 元素)
                </span>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteGroup(group.id);
                }}
                style={{
                  background: "none",
                  border: "none",
                  color: "#F87171",
                  cursor: "pointer",
                  fontSize: 12,
                  padding: "2px 6px",
                }}
              >
                删除
              </button>
            </div>

            {/* SKU type selector */}
            <div style={{ display: "flex", gap: 4, marginBottom: 8 }}>
              {(["complete", "partial", "invalid"] as const).map((t) => (
                <button
                  key={t}
                  onClick={(e) => {
                    e.stopPropagation();
                    onUpdateAttribute(group.id, "_skuType", t);
                  }}
                  style={{
                    padding: "2px 8px",
                    fontSize: 11,
                    border: `1px solid ${group.skuType === t ? color : "#2D3548"}`,
                    borderRadius: 4,
                    backgroundColor: group.skuType === t ? `${color}22` : "transparent",
                    color: group.skuType === t ? color : "#94A3B8",
                    cursor: "pointer",
                  }}
                >
                  {t === "complete" ? "完整" : t === "partial" ? "部分" : "无效"}
                </button>
              ))}
            </div>

            {/* Attributes (when selected) */}
            {isSelected && (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {["model", "name", "color", "size", "material", "price"].map((field) => (
                  <div key={field} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <label
                      style={{
                        width: 50,
                        fontSize: 11,
                        color: "#94A3B8",
                        textAlign: "right",
                      }}
                    >
                      {field}
                    </label>
                    <input
                      value={group.skuAttributes[field] ?? ""}
                      onChange={(e) => onUpdateAttribute(group.id, field, e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      placeholder={`输入${field}`}
                      style={{
                        flex: 1,
                        padding: "3px 8px",
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
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default GroupEditor;
