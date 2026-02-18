/**
 * 歧义绑定卡片
 * 用于解决图片与 SKU 之间的歧义绑定关系
 */
import type { AmbiguousBinding } from "../../types/models";

interface AmbiguousBindingCardProps {
  binding: AmbiguousBinding;
  onResolve: (elementId: string, selectedUri: string | null) => void;
}

export function AmbiguousBindingCard({ binding, onResolve }: AmbiguousBindingCardProps) {
  return (
    <div
      style={{
        padding: 12,
        backgroundColor: binding.resolved ? "#22C55E08" : "#F59E0B08",
        border: `1px solid ${binding.resolved ? "#22C55E22" : "#F59E0B22"}`,
        borderRadius: 8,
        marginBottom: 8,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 8,
        }}
      >
        <span
          style={{
            fontSize: 12,
            color: binding.resolved ? "#22C55E" : "#F59E0B",
            fontWeight: 500,
          }}
        >
          {binding.resolved ? "✓ 已解决" : "⚠ 歧义绑定"}
        </span>
        <span style={{ fontSize: 11, color: "#64748B" }}>
          元素: {binding.elementId}
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 8 }}>
        {binding.candidates.map((c) => (
          <div
            key={c.imageUri}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "4px 8px",
              backgroundColor:
                binding.selectedUri === c.imageUri ? "#22D3EE11" : "transparent",
              border: `1px solid ${binding.selectedUri === c.imageUri ? "#22D3EE33" : "#2D354800"}`,
              borderRadius: 4,
              cursor: "pointer",
            }}
            onClick={() => onResolve(binding.elementId, c.imageUri)}
          >
            <span style={{ fontSize: 11, color: "#64748B", width: 16 }}>#{c.rank}</span>
            <span
              style={{
                flex: 1,
                fontSize: 12,
                color: "#E2E8F4",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {c.imageUri}
            </span>
            <span style={{ fontSize: 11, color: "#94A3B8" }}>
              {(c.confidence * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>

      {!binding.resolved && (
        <button
          onClick={() => onResolve(binding.elementId, null)}
          style={{
            padding: "4px 10px",
            backgroundColor: "#EF444422",
            border: "1px solid #EF444444",
            borderRadius: 4,
            color: "#EF4444",
            cursor: "pointer",
            fontSize: 11,
          }}
        >
          全部拒绝
        </button>
      )}
    </div>
  );
}

export default AmbiguousBindingCard;
