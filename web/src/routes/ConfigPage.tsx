import { useEffect, useState } from "react";
import { configApi } from "../api/config";
import type { LLMProviderConfig } from "../api/config";
import { useNotificationStore } from "../stores/notificationStore";
import StatusBadge from "../components/common/StatusBadge";
import { formatPercent, formatDate } from "../utils/format";
import type { ThresholdProfile, CalibrationRecord } from "../types/models";

/* ─── Pipeline 并发规则卡片 ─── */
interface ConcurrencyRule {
  min_pages: number;
  concurrency: number;
}

function PipelineConcurrencyCard() {
  const notify = useNotificationStore((s) => s.add);
  const [rules, setRules] = useState<ConcurrencyRule[]>([]);
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    configApi.getPipelineConcurrency()
      .then((res) => { setRules(res.rules); setLoaded(true); })
      .catch((e: any) => notify({ type: "error", message: "加载并发规则失败: " + e.message }));
  }, []);

  const updateRule = (idx: number, field: "min_pages" | "concurrency", value: number) => {
    setRules((prev) => prev.map((r, i) => i === idx ? { ...r, [field]: value } : r));
  };

  const addRule = () => {
    const maxPages = rules.length > 0 ? Math.max(...rules.map((r) => r.min_pages)) : 0;
    setRules([...rules, { min_pages: maxPages + 10, concurrency: 5 }]);
  };

  const removeRule = (idx: number) => {
    if (rules.length <= 1) return;
    setRules(rules.filter((_, i) => i !== idx));
  };

  const handleSave = async () => {
    // Validate
    for (const r of rules) {
      if (r.min_pages < 1 || r.concurrency < 1) {
        notify({ type: "error", message: "页数阈值和并发数必须 >= 1" });
        return;
      }
    }
    const pages = rules.map((r) => r.min_pages);
    if (new Set(pages).size !== pages.length) {
      notify({ type: "error", message: "页数阈值不能重复" });
      return;
    }
    setSaving(true);
    try {
      const res = await configApi.setPipelineConcurrency(rules);
      setRules(res.rules);
      notify({ type: "success", message: "并发规则已保存" });
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
    setSaving(false);
  };

  if (!loaded) return null;

  return (
    <div className="card" style={{ marginBottom: 24 }}>
      <h3>Pipeline 并行处理</h3>
      <p style={{ fontSize: 12, color: "#94A3B8", marginBottom: 12 }}>
        根据 PDF 页数自动调整并行任务数。匹配规则：取页数 &ge; 阈值的最高一条。
      </p>

      <table className="data-table" style={{ marginBottom: 12 }}>
        <thead>
          <tr>
            <th style={{ width: 60 }}>#</th>
            <th>页数阈值 (&ge;)</th>
            <th>并行任务数</th>
            <th style={{ width: 60 }}>操作</th>
          </tr>
        </thead>
        <tbody>
          {rules
            .slice()
            .sort((a, b) => a.min_pages - b.min_pages)
            .map((rule, idx) => (
            <tr key={idx}>
              <td style={{ color: "#64748B" }}>{idx + 1}</td>
              <td>
                <input
                  type="number"
                  min={1}
                  value={rule.min_pages}
                  onChange={(e) => {
                    const realIdx = rules.indexOf(rule);
                    updateRule(realIdx, "min_pages", parseInt(e.target.value) || 1);
                  }}
                  style={{
                    width: 80,
                    padding: "4px 8px",
                    backgroundColor: "#0F172A",
                    border: "1px solid #2D3548",
                    borderRadius: 4,
                    color: "#E2E8F4",
                    fontSize: 13,
                    textAlign: "center",
                  }}
                />
                <span style={{ fontSize: 12, color: "#64748B", marginLeft: 6 }}>页</span>
              </td>
              <td>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={rule.concurrency}
                  onChange={(e) => {
                    const realIdx = rules.indexOf(rule);
                    updateRule(realIdx, "concurrency", parseInt(e.target.value) || 1);
                  }}
                  style={{
                    width: 80,
                    padding: "4px 8px",
                    backgroundColor: "#0F172A",
                    border: "1px solid #2D3548",
                    borderRadius: 4,
                    color: "#E2E8F4",
                    fontSize: 13,
                    textAlign: "center",
                  }}
                />
                <span style={{ fontSize: 12, color: "#64748B", marginLeft: 6 }}>个并行</span>
              </td>
              <td>
                <button
                  className="btn btn-sm btn-danger"
                  onClick={() => removeRule(rules.indexOf(rule))}
                  disabled={rules.length <= 1}
                  title="删除此规则"
                  style={{ padding: "2px 8px", fontSize: 12 }}
                >
                  删除
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ display: "flex", gap: 8 }}>
        <button className="btn btn-outline btn-sm" onClick={addRule}>+ 添加规则</button>
        <button className="btn btn-primary btn-sm" onClick={handleSave} disabled={saving}>
          {saving ? "保存中..." : "保存规则"}
        </button>
      </div>
    </div>
  );
}

/* ─── LLM Provider 配置卡片 ─── */
function LLMProviderConfigCard() {
  const notify = useNotificationStore((s) => s.add);
  const [draft, setDraft] = useState<Record<string, LLMProviderConfig>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    configApi.getLLMProviderConfigs()
      .then((res) => {
        setDraft(JSON.parse(JSON.stringify(res.configs)));
        setLoaded(true);
      })
      .catch((e: any) => notify({ type: "error", message: "加载 LLM 配置失败: " + e.message }));
  }, []);

  const updateField = (provider: string, field: keyof LLMProviderConfig, value: number) => {
    setDraft((prev) => ({
      ...prev,
      [provider]: { ...prev[provider], [field]: value },
    }));
  };

  const handleSave = async (provider: string) => {
    const cfg = draft[provider];
    if (cfg.timeout_seconds < 1 || cfg.vlm_timeout_seconds < 1) {
      notify({ type: "error", message: "超时值必须 >= 1" });
      return;
    }
    if (cfg.max_retries < 0 || cfg.max_retries > 10) {
      notify({ type: "error", message: "重试次数必须在 0-10 之间" });
      return;
    }
    setSaving(provider);
    try {
      const res = await configApi.setLLMProviderConfig(provider, cfg);
      setDraft((prev) => ({ ...prev, [provider]: { ...res.config } }));
      notify({ type: "success", message: `${provider} 配置已保存` });
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
    setSaving(null);
  };

  if (!loaded) return null;

  const inputStyle: React.CSSProperties = {
    width: 80,
    padding: "4px 8px",
    backgroundColor: "#0F172A",
    border: "1px solid #2D3548",
    borderRadius: 4,
    color: "#E2E8F4",
    fontSize: 13,
    textAlign: "center",
  };

  return (
    <div className="card" style={{ marginBottom: 24 }}>
      <h3>LLM Provider 配置</h3>
      <p style={{ fontSize: 12, color: "#94A3B8", marginBottom: 12 }}>
        每个 LLM 提供者的超时和重试参数，修改后立即生效（热更新）。
      </p>

      <table className="data-table" style={{ marginBottom: 12 }}>
        <thead>
          <tr>
            <th>Provider</th>
            <th>超时 (s)</th>
            <th>VLM 超时 (s)</th>
            <th>最大重试</th>
            <th style={{ width: 80 }}>操作</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(draft).map(([provider, cfg]) => (
            <tr key={provider}>
              <td style={{ fontWeight: 600 }}>{provider}</td>
              <td>
                <input
                  type="number"
                  min={1}
                  value={cfg.timeout_seconds}
                  onChange={(e) => updateField(provider, "timeout_seconds", parseInt(e.target.value) || 1)}
                  style={inputStyle}
                />
              </td>
              <td>
                <input
                  type="number"
                  min={1}
                  value={cfg.vlm_timeout_seconds}
                  onChange={(e) => updateField(provider, "vlm_timeout_seconds", parseInt(e.target.value) || 1)}
                  style={inputStyle}
                />
              </td>
              <td>
                <input
                  type="number"
                  min={0}
                  max={10}
                  value={cfg.max_retries}
                  onChange={(e) => updateField(provider, "max_retries", parseInt(e.target.value) || 0)}
                  style={inputStyle}
                />
              </td>
              <td>
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => handleSave(provider)}
                  disabled={saving === provider}
                  style={{ padding: "2px 12px", fontSize: 12 }}
                >
                  {saving === provider ? "..." : "保存"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ConfigPage() {
  const notify = useNotificationStore((s) => s.add);
  const [profile, setProfile] = useState<ThresholdProfile | null>(null);
  const [calibrations, setCalibrations] = useState<CalibrationRecord[]>([]);
  const [proposed, setProposed] = useState<Record<string, number>>({});
  const [preview, setPreview] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [reason, setReason] = useState("");

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [p, c] = await Promise.all([
        configApi.getActiveProfile(),
        configApi.getCalibrations(),
      ]);
      setProfile(p);
      setCalibrations(c.items);
      setProposed({ ...p.thresholds });
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
  };

  const handlePreview = async () => {
    if (!profile) return;
    setLoading(true);
    try {
      const result = await configApi.impactPreview(
        profile.profile_id, profile.thresholds, proposed
      );
      setPreview(result);
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
    setLoading(false);
  };

  const handleSave = async () => {
    if (!profile || !reason) {
      notify({ type: "error", message: "请填写变更原因" });
      return;
    }
    try {
      await configApi.updateThresholds(profile.profile_id, proposed, reason);
      notify({ type: "success", message: "阈值已更新" });
      setPreview(null);
      setReason("");
      loadData();
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
  };

  const handleApprove = async (id: string) => {
    try {
      await configApi.approveCalibration(id);
      notify({ type: "success", message: "已批准" });
      loadData();
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
  };

  const handleReject = async (id: string) => {
    const r = prompt("驳回原因:");
    if (!r) return;
    try {
      await configApi.rejectCalibration(id, r);
      notify({ type: "info", message: "已驳回" });
      loadData();
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
  };

  return (
    <div className="page config-page">
      <h2>系统配置</h2>

      {/* Pipeline 并发规则 */}
      <PipelineConcurrencyCard />

      {/* LLM Provider 配置 */}
      <LLMProviderConfigCard />

      {profile && (
        <div className="card">
          <h3>阈值配置 (v{profile.version})</h3>
          <div className="threshold-grid">
            {Object.entries(profile.thresholds).map(([key, value]) => (
              <div key={key} className="threshold-item">
                <label>{key} 阈值</label>
                <div className="threshold-control">
                  <input
                    type="range" min="0" max="1" step="0.01"
                    value={proposed[key] ?? value}
                    onChange={(e) => setProposed({ ...proposed, [key]: parseFloat(e.target.value) })}
                  />
                  <span className="threshold-value">
                    {formatPercent(proposed[key] ?? value)}
                    {proposed[key] !== undefined && proposed[key] !== value && (
                      <span className="threshold-delta">
                        (原: {formatPercent(value)})
                      </span>
                    )}
                  </span>
                </div>
              </div>
            ))}
          </div>

          <div className="config-actions">
            <button className="btn btn-outline" onClick={handlePreview} disabled={loading}>
              {loading ? "计算中..." : "预估影响"}
            </button>
            {preview && (
              <div className="impact-preview">
                <h4>影响预估 (基于 {preview.sample_count} 样本)</h4>
                <div className="preview-grid">
                  <div>自动率: {formatPercent(preview.current_auto_rate)} → {formatPercent(preview.projected_auto_rate)}
                    <span className={preview.delta_auto >= 0 ? "positive" : "negative"}>
                      ({preview.delta_auto >= 0 ? "+" : ""}{formatPercent(preview.delta_auto)})
                    </span>
                  </div>
                  <div>人工率: {formatPercent(preview.current_human_rate)} → {formatPercent(preview.projected_human_rate)}
                    <span className={preview.delta_human <= 0 ? "positive" : "negative"}>
                      ({preview.delta_human >= 0 ? "+" : ""}{formatPercent(preview.delta_human)})
                    </span>
                  </div>
                </div>
              </div>
            )}
            <div className="form-row">
              <input className="input" placeholder="变更原因 *"
                     value={reason} onChange={(e) => setReason(e.target.value)} />
              <button className="btn btn-primary" onClick={handleSave}>保存阈值</button>
            </div>
          </div>
        </div>
      )}

      <div className="card">
        <h3>校准建议 ({calibrations.length})</h3>
        {calibrations.length === 0 ? (
          <p className="text-muted">暂无待审批的校准建议</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr><th>ID</th><th>状态</th><th>样本数</th><th>建议</th><th>创建</th><th>操作</th></tr>
            </thead>
            <tbody>
              {calibrations.map((c) => (
                <tr key={c.calibration_id}>
                  <td className="td-mono">{c.calibration_id.slice(0, 8)}...</td>
                  <td><StatusBadge status={c.status} /></td>
                  <td>{c.sample_count}</td>
                  <td className="td-ellipsis">{JSON.stringify(c.suggested_adjustments).slice(0, 50)}</td>
                  <td>{formatDate(c.created_at)}</td>
                  <td>
                    {c.status === "PENDING" && (
                      <>
                        <button className="btn btn-sm btn-success" onClick={() => handleApprove(c.calibration_id)}>批准</button>
                        <button className="btn btn-sm btn-danger" onClick={() => handleReject(c.calibration_id)}>驳回</button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
