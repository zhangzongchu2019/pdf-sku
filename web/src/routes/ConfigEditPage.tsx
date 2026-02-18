/**
 * 配置编辑页 /config/:profileId
 * 阈值编辑 + 影响预览 + 关键词管理 + 安全护栏 + 乐观锁
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { configApi } from "../api/config";
import { ThresholdSlider } from "../components/config/ThresholdSlider";
import { ImpactPreviewPanel } from "../components/config/ImpactPreviewPanel";
import { KeywordManager } from "../components/config/KeywordManager";
import { useDebouncedCallback } from "../hooks/useDebouncedCallback";
import { useNotificationStore } from "../stores/notificationStore";
import type { ThresholdProfile, ImpactPreviewResult } from "../types/models";

/** 安全护栏检查 */
function getWarnings(key: string, value: number, thresholds: Record<string, number>): string | null {
  const b = thresholds["threshold_b"] ?? 0;
  const a = thresholds["threshold_a"] ?? 0;

  if (key === "threshold_b" && value === 0) {
    return "⚠️ B=0 将使所有页面进入人工流";
  }
  if (key === "threshold_a" && value >= 1.0) {
    return "⚠️ A=1.0 将使所有页面自动通过";
  }
  if (key === "threshold_b" && value >= a && a > 0) {
    return "⚠️ B ≥ A 将使中间灰区消失";
  }
  if (key === "threshold_a" && value <= b && b > 0) {
    return "⚠️ A ≤ B 将使中间灰区消失";
  }
  if (key.startsWith("pv_") && value > a && a > 0) {
    return "⚠️ PV > A 门槛超过自动通过阈值";
  }
  return null;
}

export default function ConfigEditPage() {
  const { profileId } = useParams<{ profileId: string }>();
  const navigate = useNavigate();
  const addNotification = useNotificationStore((s) => s.addNotification);

  const [profile, setProfile] = useState<ThresholdProfile | null>(null);
  const [draft, setDraft] = useState<Record<string, number>>({});
  const [keywords, setKeywords] = useState<string[]>([]);
  const [impact, setImpact] = useState<ImpactPreviewResult | null>(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(true);
  const versionRef = useRef<number>(0);

  /* 加载 profile */
  useEffect(() => {
    if (!profileId) return;
    (async () => {
      try {
        setLoading(true);
        const res = await configApi.listProfiles();
        const found = res.data.find((p: ThresholdProfile) => p.profile_id === profileId);
        if (!found) {
          addNotification({ message: "未找到配置", level: "warning" });
          navigate("/config");
          return;
        }
        setProfile(found);
        setDraft({ ...found.thresholds });
        versionRef.current = found.version;
      } catch {
        addNotification({ message: "加载配置失败", level: "urgent" });
      } finally {
        setLoading(false);
      }
    })();
  }, [profileId, navigate, addNotification]);

  /* debounced impact preview */
  const fetchImpact = useDebouncedCallback(
    async (current: Record<string, number>, proposed: Record<string, number>) => {
      if (!profileId) return;
      try {
        setImpactLoading(true);
        const res = await configApi.impactPreview(profileId, current, proposed);
        setImpact(res as unknown as ImpactPreviewResult);
      } catch {
        // ignore preview failures
      } finally {
        setImpactLoading(false);
      }
    },
    500,
  );

  const handleThresholdChange = useCallback(
    (key: string, value: number) => {
      setDraft((prev) => {
        const next = { ...prev, [key]: value };
        if (profile) {
          fetchImpact(profile.thresholds, next);
        }
        return next;
      });
    },
    [profile, fetchImpact],
  );

  /* Save with optimistic locking */
  const handleSave = async () => {
    if (!profileId || !profile || !reason.trim()) return;
    try {
      setSaving(true);
      const res = await configApi.updateThresholds(profileId, draft, reason);
      setProfile(res);
      versionRef.current = res.version;
      setImpact(null);
      setReason("");
      addNotification({ message: "配置已保存", level: "info" });
    } catch (err: unknown) {
      const e = err as { response?: { status?: number } };
      if (e?.response?.status === 409) {
        addNotification({
          message: "版本冲突：有人已修改此配置，请刷新后重试",
          level: "urgent",
        });
      } else {
        addNotification({ message: "保存失败", level: "urgent" });
      }
    } finally {
      setSaving(false);
    }
  };

  const hasChanges = profile
    ? Object.keys(draft).some((k) => draft[k] !== profile.thresholds[k])
    : false;

  if (loading) {
    return <div style={{ padding: 24, color: "#64748B" }}>加载中…</div>;
  }

  if (!profile) {
    return <div style={{ padding: 24, color: "#64748B" }}>未找到配置</div>;
  }

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 18, color: "#E2E8F4" }}>
            编辑配置 — {profile.profile_id}
          </h2>
          <div style={{ fontSize: 11, color: "#64748B", marginTop: 4 }}>
            版本 {profile.version} · {profile.is_active ? "活跃" : "非活跃"}
            {profile.category && ` · ${profile.category}`}
            {profile.industry && ` · ${profile.industry}`}
          </div>
        </div>
        <button
          onClick={() => navigate("/config")}
          style={{ padding: "4px 12px", backgroundColor: "transparent", border: "1px solid #2D3548", borderRadius: 4, color: "#94A3B8", cursor: "pointer", fontSize: 12 }}
        >
          返回列表
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        {/* Left: Thresholds */}
        <div>
          <h3 style={{ fontSize: 14, color: "#94A3B8", margin: "0 0 12px" }}>阈值设置</h3>
          <div style={{ padding: 16, backgroundColor: "#1B2233", border: "1px solid #2D3548", borderRadius: 8 }}>
            {Object.entries(draft)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([key, value]) => (
                <ThresholdSlider
                  key={key}
                  label={key}
                  value={value}
                  onChange={(v) => handleThresholdChange(key, v)}
                  warning={getWarnings(key, value, draft)}
                />
              ))}
          </div>

          {/* SKU validity mode */}
          <div style={{ marginTop: 16, padding: "12px 16px", backgroundColor: "#1B2233", border: "1px solid #2D3548", borderRadius: 8 }}>
            <div style={{ fontSize: 12, color: "#94A3B8", marginBottom: 8 }}>SKU 有效性模式</div>
            <div style={{ display: "flex", gap: 8 }}>
              {(["strict", "lenient"] as const).map((mode) => (
                <button
                  key={mode}
                  style={{
                    padding: "4px 12px",
                    backgroundColor: profile.sku_validity_mode === mode ? "#22D3EE22" : "transparent",
                    border: `1px solid ${profile.sku_validity_mode === mode ? "#22D3EE44" : "#2D3548"}`,
                    borderRadius: 4,
                    color: profile.sku_validity_mode === mode ? "#22D3EE" : "#94A3B8",
                    cursor: "pointer",
                    fontSize: 12,
                  }}
                >
                  {mode === "strict" ? "严格" : "宽松"}
                </button>
              ))}
            </div>
          </div>

          {/* Confidence weights */}
          <div style={{ marginTop: 16 }}>
            <h3 style={{ fontSize: 14, color: "#94A3B8", margin: "0 0 12px" }}>置信度权重</h3>
            <div style={{ padding: 16, backgroundColor: "#1B2233", border: "1px solid #2D3548", borderRadius: 8 }}>
              {Object.entries(profile.confidence_weights).map(([key, weight]) => (
                <div key={key} style={{ display: "flex", justifyContent: "space-between", fontSize: 12, padding: "4px 0", borderBottom: "1px solid #2D354833" }}>
                  <span style={{ color: "#94A3B8" }}>{key}</span>
                  <span style={{ color: "#E2E8F4" }}>{weight}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: Impact + Keywords + Save */}
        <div>
          <h3 style={{ fontSize: 14, color: "#94A3B8", margin: "0 0 12px" }}>影响预览</h3>
          <ImpactPreviewPanel result={impact} loading={impactLoading} />

          <div style={{ marginTop: 24 }}>
            <h3 style={{ fontSize: 14, color: "#94A3B8", margin: "0 0 12px" }}>关键词库</h3>
            <KeywordManager
              keywords={keywords}
              onAdd={(kw) => setKeywords((prev) => [...prev, kw])}
              onRemove={(kw) => setKeywords((prev) => prev.filter((k) => k !== kw))}
              onBulkImport={(kws) => setKeywords((prev) => [...new Set([...prev, ...kws])])}
            />
          </div>

          {/* Save */}
          <div style={{ marginTop: 24, padding: 16, backgroundColor: "#1B2233", border: "1px solid #2D3548", borderRadius: 8 }}>
            <div style={{ fontSize: 12, color: "#94A3B8", marginBottom: 8 }}>变更原因（必填）</div>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="请描述本次变更的原因…"
              style={{
                width: "100%",
                minHeight: 60,
                padding: 8,
                backgroundColor: "#0F172A",
                border: "1px solid #2D3548",
                borderRadius: 4,
                color: "#E2E8F4",
                fontSize: 12,
                resize: "vertical",
                boxSizing: "border-box",
              }}
            />
            <button
              onClick={handleSave}
              disabled={saving || !hasChanges || !reason.trim()}
              style={{
                marginTop: 12,
                width: "100%",
                padding: "8px 16px",
                backgroundColor: hasChanges && reason.trim() ? "#22D3EE22" : "#33415522",
                border: `1px solid ${hasChanges && reason.trim() ? "#22D3EE44" : "#2D3548"}`,
                borderRadius: 4,
                color: hasChanges && reason.trim() ? "#22D3EE" : "#64748B",
                cursor: hasChanges && reason.trim() ? "pointer" : "not-allowed",
                fontSize: 13,
                fontWeight: 500,
              }}
            >
              {saving ? "保存中…" : "保存配置"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
