/**
 * 批量操作栏 — 选中 Job 后出现
 * 支持: 批量重试 / 批量取消 / 批量分配 / 导出CSV
 */

interface BatchActionBarProps {
  selectedCount: number;
  onBatchRetry: () => void;
  onBatchCancel: () => void;
  onBatchAssign: () => void;
  onExportCSV: () => void;
  onClear: () => void;
}

export function BatchActionBar({
  selectedCount,
  onBatchRetry,
  onBatchCancel,
  onBatchAssign,
  onExportCSV,
  onClear,
}: BatchActionBarProps) {
  if (selectedCount === 0) return null;

  return (
    <div
      role="toolbar"
      aria-label="批量操作"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "8px 12px",
        backgroundColor: "#22D3EE08",
        border: "1px solid #22D3EE22",
        borderRadius: 8,
        marginBottom: 12,
      }}
    >
      <span style={{ fontSize: 13, color: "#22D3EE", fontWeight: 500, marginRight: 8 }}>
        已选 {selectedCount} 个任务
      </span>

      <BarButton onClick={onBatchRetry} color="#3B82F6">
        批量重试
      </BarButton>
      <BarButton onClick={onBatchCancel} color="#EF4444">
        批量取消
      </BarButton>
      <BarButton onClick={onBatchAssign} color="#F59E0B">
        批量分配
      </BarButton>
      <BarButton onClick={onExportCSV} color="#22C55E">
        导出 CSV
      </BarButton>

      <div style={{ flex: 1 }} />
      <button
        onClick={onClear}
        style={{
          background: "none",
          border: "none",
          color: "#64748B",
          cursor: "pointer",
          fontSize: 12,
        }}
      >
        清除选择
      </button>
    </div>
  );
}

function BarButton({
  onClick,
  color,
  children,
}: {
  onClick: () => void;
  color: string;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: "4px 12px",
        backgroundColor: `${color}18`,
        border: `1px solid ${color}33`,
        borderRadius: 4,
        color,
        cursor: "pointer",
        fontSize: 12,
        fontWeight: 500,
      }}
    >
      {children}
    </button>
  );
}

export default BatchActionBar;
