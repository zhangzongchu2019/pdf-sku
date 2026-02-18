/**
 * 触发评测按钮 (Admin only)
 */
import { useState, useCallback } from "react";
import { evalApi } from "../../api/eval";

interface EvalRunButtonProps {
  goldenSetId?: string;
  configVersion?: string;
  onSuccess?: () => void;
  disabled?: boolean;
}

export function EvalRunButton({ goldenSetId, configVersion, onSuccess, disabled }: EvalRunButtonProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRun = useCallback(async () => {
    if (!goldenSetId || !configVersion) {
      setError("请指定黄金集ID和配置版本");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await evalApi.run({ golden_set_id: goldenSetId, config_version: configVersion });
      onSuccess?.();
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "触发评测失败",
      );
    } finally {
      setLoading(false);
    }
  }, [onSuccess]);

  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
      <button
        onClick={handleRun}
        disabled={loading || disabled}
        style={{
          padding: "8px 18px",
          backgroundColor: loading || disabled ? "#2D3548" : "#22D3EE",
          border: "none",
          borderRadius: 6,
          color: loading || disabled ? "#64748B" : "#0F172A",
          fontWeight: 600,
          cursor: loading || disabled ? "not-allowed" : "pointer",
          fontSize: 13,
        }}
      >
        {loading ? "评测中…" : "触发评测"}
      </button>
      {error && (
        <span style={{ fontSize: 12, color: "#EF4444" }}>{error}</span>
      )}
    </div>
  );
}

export default EvalRunButton;
