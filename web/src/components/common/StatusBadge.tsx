import { formatStatusLabel, statusColor } from "../../utils/format";

export default function StatusBadge({ status, label }: { status: string; label?: string }) {
  return (
    <span className="status-badge" style={{
      backgroundColor: statusColor(status) + "20",
      color: statusColor(status),
      border: `1px solid ${statusColor(status)}40`,
    }}>
      {label ?? formatStatusLabel(status)}
    </span>
  );
}
