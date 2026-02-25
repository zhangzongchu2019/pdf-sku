import { useEffect, useState, useCallback } from "react";
import { configApi } from "../api/config";
import type { LLMProviderEntry, LLMAccount } from "../api/config";
import { useNotificationStore } from "../stores/notificationStore";
import StatusBadge from "../components/common/StatusBadge";
import { formatPercent, formatDate } from "../utils/format";
import type { ThresholdProfile, CalibrationRecord } from "../types/models";

/* ─── Pipeline 并发规则卡片 ─── */
interface ConcurrencyRule {
  min_pages: number;
  concurrency: number;
  provider_name?: string;
}

function PipelineConcurrencyCard({ providerNames }: { providerNames: string[] }) {
  const notify = useNotificationStore((s) => s.add);
  const [rules, setRules] = useState<ConcurrencyRule[]>([]);
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    configApi.getPipelineConcurrency()
      .then((res) => { setRules(res.rules); setLoaded(true); })
      .catch((e: any) => notify({ type: "error", message: "加载并发规则失败: " + e.message }));
  }, []);

  const updateRule = (idx: number, field: keyof ConcurrencyRule, value: number | string) => {
    setRules((prev) => prev.map((r, i) => i === idx ? { ...r, [field]: value } : r));
  };

  const addRule = () => {
    const maxPages = rules.length > 0 ? Math.max(...rules.map((r) => r.min_pages)) : 0;
    setRules([...rules, { min_pages: maxPages + 10, concurrency: 5, provider_name: "" }]);
  };

  const removeRule = (idx: number) => {
    if (rules.length <= 1) return;
    setRules(rules.filter((_, i) => i !== idx));
  };

  const handleSave = async () => {
    for (const r of rules) {
      if (r.min_pages < 1 || r.concurrency < 1) {
        notify({ type: "error", message: "页数阈值和并发数必须 >= 1" });
        return;
      }
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

  const selectStyle: React.CSSProperties = {
    padding: "4px 8px",
    backgroundColor: "#0F172A",
    border: "1px solid #2D3548",
    borderRadius: 4,
    color: "#E2E8F4",
    fontSize: 13,
  };

  const numInputStyle: React.CSSProperties = {
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
      <h3>Pipeline 并行处理</h3>
      <p style={{ fontSize: 12, color: "#94A3B8", marginBottom: 12 }}>
        根据 PDF 页数和 Provider 自动调整并行任务数。Provider 专属规则优先，无匹配则回退到全局默认。
      </p>

      <table className="data-table" style={{ marginBottom: 12 }}>
        <thead>
          <tr>
            <th style={{ width: 40 }}>#</th>
            <th>Provider</th>
            <th>页数阈值 (&ge;)</th>
            <th>并行任务数</th>
            <th style={{ width: 60 }}>操作</th>
          </tr>
        </thead>
        <tbody>
          {rules
            .slice()
            .sort((a, b) => (a.provider_name || "").localeCompare(b.provider_name || "") || a.min_pages - b.min_pages)
            .map((rule, idx) => (
            <tr key={idx}>
              <td style={{ color: "#64748B" }}>{idx + 1}</td>
              <td>
                <select
                  value={rule.provider_name || ""}
                  onChange={(e) => {
                    const realIdx = rules.indexOf(rule);
                    updateRule(realIdx, "provider_name", e.target.value);
                  }}
                  style={selectStyle}
                >
                  <option value="">全局默认</option>
                  {providerNames.map((n) => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </td>
              <td>
                <input
                  type="number"
                  min={1}
                  value={rule.min_pages}
                  onChange={(e) => {
                    const realIdx = rules.indexOf(rule);
                    updateRule(realIdx, "min_pages", parseInt(e.target.value) || 1);
                  }}
                  style={numInputStyle}
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
                  style={numInputStyle}
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

/* ─── LLM 账号管理卡片 ─── */
function LLMAccountCard() {
  const notify = useNotificationStore((s) => s.add);
  const [accounts, setAccounts] = useState<LLMAccount[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", provider_type: "gemini", api_base: "", api_key: "" });
  const [creating, setCreating] = useState(false);

  const loadAccounts = useCallback(async () => {
    try {
      const res = await configApi.getLLMAccounts();
      setAccounts(res.accounts);
      setLoaded(true);
    } catch (e: any) {
      notify({ type: "error", message: "加载账号失败: " + e.message });
    }
  }, [notify]);

  useEffect(() => { loadAccounts(); }, [loadAccounts]);

  const handleCreate = async () => {
    if (!form.name || !form.api_key) {
      notify({ type: "error", message: "名称和 API Key 为必填" });
      return;
    }
    setCreating(true);
    try {
      await configApi.createLLMAccount(form);
      notify({ type: "success", message: `账号 "${form.name}" 已创建` });
      setForm({ name: "", provider_type: "gemini", api_base: "", api_key: "" });
      setShowForm(false);
      loadAccounts();
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
    setCreating(false);
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`确定删除账号 "${name}"？此操作不可恢复。`)) return;
    try {
      await configApi.deleteLLMAccount(id);
      notify({ type: "success", message: `账号 "${name}" 已删除` });
      loadAccounts();
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
  };

  if (!loaded) return null;

  const inputStyle: React.CSSProperties = {
    padding: "4px 8px",
    backgroundColor: "#0F172A",
    border: "1px solid #2D3548",
    borderRadius: 4,
    color: "#E2E8F4",
    fontSize: 13,
    width: "100%",
  };

  return (
    <div className="card" style={{ marginBottom: 24 }}>
      <h3>LLM 账号管理</h3>
      <p style={{ fontSize: 12, color: "#94A3B8", marginBottom: 12 }}>
        管理 API Key 凭据（加密存储），Provider 通过引用账号名获取凭据。
      </p>

      {accounts.length > 0 && (
        <table className="data-table" style={{ marginBottom: 12 }}>
          <thead>
            <tr>
              <th>名称</th>
              <th>类型</th>
              <th>接口 URL</th>
              <th>Key (脱敏)</th>
              <th>创建时间</th>
              <th style={{ width: 60 }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((a) => (
              <tr key={a.id}>
                <td style={{ fontWeight: 600 }}>{a.name}</td>
                <td>
                  <span style={{
                    display: "inline-block", padding: "1px 6px", fontSize: 10,
                    borderRadius: 3, backgroundColor: "#3B82F618", border: "1px solid #3B82F633", color: "#60A5FA",
                  }}>
                    {a.provider_type}
                  </span>
                </td>
                <td style={{ fontSize: 12, color: "#94A3B8", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis" }}>
                  {a.api_base || "(默认)"}
                </td>
                <td style={{ fontFamily: "monospace", fontSize: 12, color: "#64748B" }}>{a.api_key_masked}</td>
                <td style={{ fontSize: 12, color: "#64748B" }}>{a.created_at ? formatDate(a.created_at) : "-"}</td>
                <td>
                  <button
                    className="btn btn-sm btn-danger"
                    onClick={() => handleDelete(a.id, a.name)}
                    style={{ padding: "2px 8px", fontSize: 12 }}
                  >
                    删除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {accounts.length === 0 && !showForm && (
        <p style={{ color: "#64748B", fontSize: 13, marginBottom: 12 }}>暂无账号，点击下方按钮添加。</p>
      )}

      {showForm && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 12, maxWidth: 600 }}>
          <div>
            <label style={{ fontSize: 11, color: "#94A3B8" }}>名称 *</label>
            <input style={inputStyle} placeholder="如: gemini-direct" value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label style={{ fontSize: 11, color: "#94A3B8" }}>类型 *</label>
            <select style={inputStyle} value={form.provider_type}
              onChange={(e) => setForm({ ...form, provider_type: e.target.value })}>
              <option value="gemini">Gemini</option>
              <option value="qwen">Qwen</option>
              <option value="openrouter">OpenRouter</option>
              <option value="custom">Custom</option>
            </select>
          </div>
          <div>
            <label style={{ fontSize: 11, color: "#94A3B8" }}>接口 URL (留空用默认)</label>
            <input style={inputStyle} placeholder="https://..." value={form.api_base}
              onChange={(e) => setForm({ ...form, api_base: e.target.value })} />
          </div>
          <div>
            <label style={{ fontSize: 11, color: "#94A3B8" }}>API Key *</label>
            <input type="password" style={inputStyle} placeholder="sk-..." value={form.api_key}
              onChange={(e) => setForm({ ...form, api_key: e.target.value })} />
          </div>
          <div style={{ gridColumn: "1 / -1", display: "flex", gap: 8 }}>
            <button className="btn btn-primary btn-sm" onClick={handleCreate} disabled={creating}>
              {creating ? "创建中..." : "确认创建"}
            </button>
            <button className="btn btn-outline btn-sm" onClick={() => setShowForm(false)}>取消</button>
          </div>
        </div>
      )}

      {!showForm && (
        <button className="btn btn-outline btn-sm" onClick={() => setShowForm(true)}>+ 添加账号</button>
      )}
    </div>
  );
}

/* ─── LLM Provider 配置卡片 (优先级排序) ─── */
function LLMProviderConfigCard({ onProvidersLoaded }: { onProvidersLoaded?: (names: string[]) => void }) {
  const notify = useNotificationStore((s) => s.add);
  const [providers, setProviders] = useState<LLMProviderEntry[]>([]);
  const [expandedName, setExpandedName] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const loadProviders = useCallback(async () => {
    try {
      const res = await configApi.getLLMProviders();
      setProviders(res.providers);
      setLoaded(true);
    } catch {
      // Fallback to legacy API
      try {
        const res = await configApi.getLLMProviderConfigs();
        const legacy: LLMProviderEntry[] = Object.entries(res.configs).map(([name, cfg], idx) => ({
          name,
          provider_type: name,
          access_mode: "direct" as const,
          proxy_service: null,
          model: "",
          priority: idx,
          enabled: true,
          account_name: "",
          qpm_limit: 60,
          tpm_limit: 100000,
          ...cfg,
        }));
        setProviders(legacy);
        setLoaded(true);
      } catch (e: any) {
        notify({ type: "error", message: "加载 LLM 配置失败: " + e.message });
      }
    }
  }, [notify]);

  useEffect(() => { loadProviders(); }, [loadProviders]);

  useEffect(() => {
    if (loaded && onProvidersLoaded) {
      onProvidersLoaded(providers.map((p) => p.name));
    }
  }, [loaded, providers, onProvidersLoaded]);

  const handleMoveUp = async (idx: number) => {
    if (idx <= 0) return;
    const newOrder = [...providers];
    [newOrder[idx - 1], newOrder[idx]] = [newOrder[idx], newOrder[idx - 1]];
    const orderedNames = newOrder.map((p) => p.name);
    try {
      const res = await configApi.reorderLLMProviders(orderedNames);
      setProviders(res.providers);
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
  };

  const handleMoveDown = async (idx: number) => {
    if (idx >= providers.length - 1) return;
    const newOrder = [...providers];
    [newOrder[idx], newOrder[idx + 1]] = [newOrder[idx + 1], newOrder[idx]];
    const orderedNames = newOrder.map((p) => p.name);
    try {
      const res = await configApi.reorderLLMProviders(orderedNames);
      setProviders(res.providers);
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
  };

  const handleToggle = async (name: string, enabled: boolean) => {
    try {
      await configApi.toggleLLMProvider(name, enabled);
      setProviders((prev) =>
        prev.map((p) => p.name === name ? { ...p, enabled } : p)
      );
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
  };

  const handleSaveConfig = async (name: string, updates: Partial<Pick<LLMProviderEntry, "timeout_seconds" | "vlm_timeout_seconds" | "max_retries" | "qpm_limit" | "tpm_limit">>) => {
    setSaving(name);
    try {
      const res = await configApi.updateLLMProvider(name, updates);
      setProviders((prev) =>
        prev.map((p) => p.name === name ? res.provider : p)
      );
      notify({ type: "success", message: `${name} 配置已保存` });
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
    setSaving(null);
  };

  if (!loaded) return null;
  if (providers.length === 0) return null;

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

  const badgeStyle = (mode: string): React.CSSProperties => ({
    display: "inline-block",
    padding: "1px 6px",
    fontSize: 10,
    borderRadius: 3,
    marginLeft: 6,
    backgroundColor: mode === "direct" ? "#10B98118" : "#8B5CF618",
    border: `1px solid ${mode === "direct" ? "#10B98133" : "#8B5CF633"}`,
    color: mode === "direct" ? "#10B981" : "#8B5CF6",
  });

  return (
    <div className="card" style={{ marginBottom: 24 }}>
      <h3>LLM Provider 优先级</h3>
      <p style={{ fontSize: 12, color: "#94A3B8", marginBottom: 12 }}>
        按优先级排序，故障时自动 Fallback 到下一个启用的 Provider。
      </p>

      <table className="data-table" style={{ marginBottom: 12 }}>
        <thead>
          <tr>
            <th style={{ width: 40 }}>#</th>
            <th style={{ width: 60 }}>排序</th>
            <th>Provider</th>
            <th>模型</th>
            <th>账号</th>
            <th style={{ width: 70 }}>启用</th>
            <th style={{ width: 60 }}>展开</th>
          </tr>
        </thead>
        <tbody>
          {providers.map((p, idx) => (
            <>
              <tr key={p.name} style={{ opacity: p.enabled ? 1 : 0.5 }}>
                <td style={{ color: "#64748B" }}>{idx + 1}</td>
                <td>
                  <button
                    className="btn btn-sm btn-outline"
                    onClick={() => handleMoveUp(idx)}
                    disabled={idx === 0}
                    style={{ padding: "0 4px", fontSize: 11, marginRight: 2 }}
                    title="上移"
                  >
                    ↑
                  </button>
                  <button
                    className="btn btn-sm btn-outline"
                    onClick={() => handleMoveDown(idx)}
                    disabled={idx === providers.length - 1}
                    style={{ padding: "0 4px", fontSize: 11 }}
                    title="下移"
                  >
                    ↓
                  </button>
                </td>
                <td>
                  <span style={{ fontWeight: 600 }}>{p.name}</span>
                  <span style={badgeStyle(p.access_mode)}>
                    {p.access_mode === "direct" ? "直连" : p.proxy_service || "代理"}
                  </span>
                </td>
                <td style={{ fontSize: 12, color: "#94A3B8" }}>{p.model || "-"}</td>
                <td style={{ fontSize: 12, color: "#94A3B8" }}>{p.account_name || "-"}</td>
                <td>
                  <label style={{ cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={p.enabled}
                      onChange={(e) => handleToggle(p.name, e.target.checked)}
                      style={{ marginRight: 4 }}
                    />
                    {p.enabled ? "开" : "关"}
                  </label>
                </td>
                <td>
                  <button
                    className="btn btn-sm btn-outline"
                    onClick={() => setExpandedName(expandedName === p.name ? null : p.name)}
                    style={{ padding: "0 8px", fontSize: 11 }}
                  >
                    {expandedName === p.name ? "收起" : "配置"}
                  </button>
                </td>
              </tr>
              {expandedName === p.name && (
                <tr key={`${p.name}-config`}>
                  <td colSpan={7} style={{ padding: "8px 16px", backgroundColor: "#0F172A" }}>
                    <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
                      <label style={{ fontSize: 12 }}>
                        超时(s):
                        <input
                          type="number" min={1}
                          defaultValue={p.timeout_seconds}
                          id={`timeout-${p.name}`}
                          style={{ ...inputStyle, marginLeft: 4 }}
                        />
                      </label>
                      <label style={{ fontSize: 12 }}>
                        VLM超时(s):
                        <input
                          type="number" min={1}
                          defaultValue={p.vlm_timeout_seconds}
                          id={`vlm-timeout-${p.name}`}
                          style={{ ...inputStyle, marginLeft: 4 }}
                        />
                      </label>
                      <label style={{ fontSize: 12 }}>
                        重试:
                        <input
                          type="number" min={0} max={10}
                          defaultValue={p.max_retries}
                          id={`retries-${p.name}`}
                          style={{ ...inputStyle, marginLeft: 4 }}
                        />
                      </label>
                      <label style={{ fontSize: 12 }}>
                        QPM:
                        <input
                          type="number" min={1}
                          defaultValue={p.qpm_limit ?? 60}
                          id={`qpm-${p.name}`}
                          style={{ ...inputStyle, marginLeft: 4 }}
                        />
                      </label>
                      <label style={{ fontSize: 12 }}>
                        TPM:
                        <input
                          type="number" min={1}
                          defaultValue={p.tpm_limit ?? 100000}
                          id={`tpm-${p.name}`}
                          style={{ ...inputStyle, marginLeft: 4 }}
                        />
                      </label>
                      <button
                        className="btn btn-primary btn-sm"
                        disabled={saving === p.name}
                        style={{ padding: "2px 12px", fontSize: 12 }}
                        onClick={() => {
                          const ts = parseInt((document.getElementById(`timeout-${p.name}`) as HTMLInputElement)?.value) || p.timeout_seconds;
                          const vts = parseInt((document.getElementById(`vlm-timeout-${p.name}`) as HTMLInputElement)?.value) || p.vlm_timeout_seconds;
                          const mr = parseInt((document.getElementById(`retries-${p.name}`) as HTMLInputElement)?.value) ?? p.max_retries;
                          const qpm = parseInt((document.getElementById(`qpm-${p.name}`) as HTMLInputElement)?.value) || 60;
                          const tpm = parseInt((document.getElementById(`tpm-${p.name}`) as HTMLInputElement)?.value) || 100000;
                          handleSaveConfig(p.name, { timeout_seconds: ts, vlm_timeout_seconds: vts, max_retries: mr, qpm_limit: qpm, tpm_limit: tpm });
                        }}
                      >
                        {saving === p.name ? "..." : "保存"}
                      </button>
                    </div>
                  </td>
                </tr>
              )}
            </>
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
  const [providerNames, setProviderNames] = useState<string[]>([]);

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

      {/* LLM 账号管理 */}
      <LLMAccountCard />

      {/* Pipeline 并发规则 */}
      <PipelineConcurrencyCard providerNames={providerNames} />

      {/* LLM Provider 配置 */}
      <LLMProviderConfigCard onProvidersLoaded={setProviderNames} />

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
