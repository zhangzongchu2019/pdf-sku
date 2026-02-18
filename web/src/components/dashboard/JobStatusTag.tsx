/**
 * Job 状态标签 — 双状态模型 (internal_status + user_status)
 * 按 action_hint 渲染不同颜色
 */
import { STATUS_COLORS } from "../../utils/designTokens";

interface JobStatusTagProps {
  internalStatus: string;
  userStatus?: string;
  actionHint?: string;
}

export function JobStatusTag({ internalStatus, userStatus, actionHint }: JobStatusTagProps) {
  const color = STATUS_COLORS[internalStatus as keyof typeof STATUS_COLORS] ?? "#64748B";

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "2px 8px",
        backgroundColor: `${color}18`,
        border: `1px solid ${color}33`,
        borderRadius: 4,
        fontSize: 11,
        fontWeight: 500,
        color,
        whiteSpace: "nowrap",
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          backgroundColor: color,
        }}
      />
      {userStatus || internalStatus}
      {actionHint && (
        <ActionHintBadge hint={actionHint} />
      )}
    </span>
  );
}

interface ActionHintBadgeProps {
  hint: string;
}

const HINT_LABELS: Record<string, { label: string; color: string }> = {
  WAIT: { label: "等待", color: "#64748B" },
  ASSIGN_TASKS: { label: "需分配", color: "#F59E0B" },
  RETRY_AVAILABLE: { label: "可重试", color: "#3B82F6" },
  VIEW_RESULTS: { label: "查看结果", color: "#22C55E" },
  IMPORT_CONFIRM: { label: "待确认", color: "#A855F7" },
  CONTACT_SUPPORT: { label: "联系支持", color: "#EF4444" },
};

export function ActionHintBadge({ hint }: ActionHintBadgeProps) {
  const info = HINT_LABELS[hint] ?? { label: hint, color: "#64748B" };

  return (
    <span
      style={{
        marginLeft: 4,
        padding: "1px 5px",
        backgroundColor: `${info.color}22`,
        borderRadius: 3,
        fontSize: 10,
        color: info.color,
        fontWeight: 400,
      }}
    >
      {info.label}
    </span>
  );
}

export default JobStatusTag;
