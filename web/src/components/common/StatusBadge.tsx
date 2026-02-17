import { statusColor } from "../../utils/format";

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span className="status-badge" style={{
      backgroundColor: statusColor(status) + "20",
      color: statusColor(status),
      border: `1px solid ${statusColor(status)}40`,
    }}>
      {status}
    </span>
  );
}
