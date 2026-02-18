/**
 * 阈值配置文件列表 — 卡片网格
 */
import type { ThresholdProfile } from "../../types/models";

interface ProfileListProps {
  profiles: ThresholdProfile[];
  activeId?: string;
  onEdit: (profileId: string) => void;
  onCreate: () => void;
}

export function ProfileList({
  profiles,
  activeId,
  onEdit,
  onCreate,
}: ProfileListProps) {
  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <h3 style={{ margin: 0, fontSize: 15, color: "#E2E8F4" }}>
          阈值配置 ({profiles.length})
        </h3>
        <button
          onClick={onCreate}
          style={{
            padding: "6px 14px",
            backgroundColor: "#22D3EE",
            border: "none",
            borderRadius: 6,
            color: "#0F172A",
            fontWeight: 600,
            cursor: "pointer",
            fontSize: 12,
          }}
        >
          + 新建配置
        </button>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: 12,
        }}
      >
        {profiles.map((p) => {
          const isActive = p.profile_id === activeId;
          return (
            <div
              key={p.profile_id}
              style={{
                padding: 16,
                backgroundColor: "#1B2233",
                border: `1px solid ${isActive ? "#22D3EE44" : "#2D3548"}`,
                borderRadius: 8,
                cursor: "pointer",
                position: "relative",
              }}
              onClick={() => onEdit(p.profile_id)}
            >
              {isActive && (
                <span
                  style={{
                    position: "absolute",
                    top: 8,
                    right: 8,
                    padding: "2px 8px",
                    backgroundColor: "#22D3EE22",
                    borderRadius: 4,
                    fontSize: 10,
                    color: "#22D3EE",
                  }}
                >
                  当前激活
                </span>
              )}

              <h4 style={{ margin: "0 0 8px", fontSize: 14, color: "#E2E8F4" }}>
                {p.profile_id}
              </h4>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr 1fr",
                  gap: 8,
                  marginBottom: 8,
                }}
              >
                {Object.entries(p.thresholds).slice(0, 3).map(([key, val]) => (
                  <ThresholdBadge key={key} label={key} value={val} />
                ))}
              </div>

              <div style={{ fontSize: 11, color: "#64748B" }}>
                {p.category ?? "默认"} · v{p.version}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ThresholdBadge({ label, value }: { label: string; value: number }) {
  return (
    <div
      style={{
        textAlign: "center",
        padding: "4px 0",
        backgroundColor: "#161D2F",
        borderRadius: 4,
      }}
    >
      <div style={{ fontSize: 10, color: "#64748B" }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 600, color: "#E2E8F4" }}>
        {value.toFixed(2)}
      </div>
    </div>
  );
}

export default ProfileList;
