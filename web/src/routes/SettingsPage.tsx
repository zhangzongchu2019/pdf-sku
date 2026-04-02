/**
 * 个人中心 /settings
 * 包含: 个人信息、修改密码、偏好设置、退出登录
 */
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useSettingsStore } from "../stores/settingsStore";
import { useAuthStore } from "../stores/authStore";
import { authApi, type UserInfo } from "../api/auth";

const ROLE_LABELS: Record<string, string> = {
  admin: "管理员", uploader: "上传者", annotator: "标注员", operator: "操作员",
};
const ROLE_COLORS: Record<string, string> = {
  admin: "#F59E0B", uploader: "#3B82F6", annotator: "#22C55E", operator: "#64748B",
};

/* ─── 个人信息卡片 ─── */
function ProfileCard() {
  const { userId, username, displayName, role, merchantId, token } = useAuthStore();
  const setAuth = useAuthStore((s) => s.setAuth);

  const [fullInfo, setFullInfo] = useState<UserInfo | null>(null);
  const [editing, setEditing] = useState(false);
  const [newDisplayName, setNewDisplayName] = useState(displayName);
  const [newMerchantId, setNewMerchantId] = useState(merchantId || "");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    authApi.me().then(setFullInfo).catch(() => {});
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMsg("");
    try {
      const res = await authApi.updateProfile({
        display_name: newDisplayName,
        merchant_id: (role === "uploader" || role === "admin") ? newMerchantId : undefined,
      });
      setAuth({ userId, username, displayName: res.display_name, role, token: token!, merchantId: res.merchant_id });
      setFullInfo((prev) => prev ? { ...prev, display_name: res.display_name, merchant_id: res.merchant_id } : prev);
      setMsg("个人信息已更新");
      setEditing(false);
      setTimeout(() => setMsg(""), 3000);
    } catch (err: any) {
      setMsg(err?.body?.detail || err.message || "更新失败");
    } finally {
      setSaving(false);
    }
  };

  const roleColor = ROLE_COLORS[role] || "#64748B";

  return (
    <div className="settings-section">
      <h3 className="settings-section-title">个人信息</h3>
      <div className="settings-card">
        {/* Avatar + Name header */}
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20, paddingBottom: 16, borderBottom: "1px solid var(--border)" }}>
          <div style={{
            width: 56, height: 56, borderRadius: "50%",
            background: `${roleColor}22`, border: `2px solid ${roleColor}`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 24, flexShrink: 0,
          }}>
            {role === "admin" ? "👑" : role === "annotator" ? "✏️" : "📤"}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 18, fontWeight: 600, color: "var(--text)" }}>
              {editing ? (
                <input
                  className="input"
                  value={newDisplayName}
                  onChange={(e) => setNewDisplayName(e.target.value)}
                  placeholder="显示名称"
                  style={{ fontSize: 16, padding: "4px 8px", maxWidth: 220, backgroundColor: "#0F172A", color: "#E2E8F4", border: "1px solid #2D3548" }}
                  autoFocus
                />
              ) : (
                displayName || username
              )}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
              <span style={{
                fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 10,
                background: `${roleColor}22`, color: roleColor,
              }}>
                {ROLE_LABELS[role] || role}
              </span>
              <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>@{username}</span>
            </div>
          </div>
          {editing ? (
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn btn-primary btn-sm" onClick={handleSave} disabled={saving}>
                {saving ? "保存中..." : "保存"}
              </button>
              <button className="btn btn-sm" onClick={() => { setEditing(false); setNewDisplayName(displayName); setNewMerchantId(merchantId || ""); }}>
                取消
              </button>
            </div>
          ) : (
            <button className="btn btn-sm" onClick={() => setEditing(true)} style={{ flexShrink: 0 }}>
              编辑资料
            </button>
          )}
        </div>

        {msg && (
          <div style={{
            fontSize: 13, marginBottom: 12, padding: "6px 12px", borderRadius: 4,
            background: msg.includes("失败") ? "#EF444418" : "#22C55E18",
            color: msg.includes("失败") ? "#EF4444" : "#22C55E",
          }}>
            {msg}
          </div>
        )}

        {/* Info rows */}
        <InfoRow label="用户 ID" value={userId} mono />
        <InfoRow label="用户名" value={username} mono />
        {(role === "uploader" || role === "admin") && (
          <div className="settings-row">
            <span className="settings-label">商户 ID</span>
            {editing ? (
              <input
                className="input"
                value={newMerchantId}
                onChange={(e) => setNewMerchantId(e.target.value)}
                placeholder="输入商户 ID"
                style={{ maxWidth: 220, backgroundColor: "#0F172A", color: "#E2E8F4", border: "1px solid #2D3548", fontSize: 13, padding: "4px 8px" }}
              />
            ) : (
              <span className="settings-value td-mono" style={{ userSelect: "text" }}>{merchantId || "—"}</span>
            )}
          </div>
        )}
        {fullInfo?.created_at && (
          <InfoRow label="注册时间" value={new Date(fullInfo.created_at).toLocaleString("zh-CN")} />
        )}
        {fullInfo?.last_login_at && (
          <InfoRow label="上次登录" value={new Date(fullInfo.last_login_at).toLocaleString("zh-CN")} />
        )}
      </div>
    </div>
  );
}

function InfoRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="settings-row">
      <span className="settings-label">{label}</span>
      <span className={`settings-value${mono ? " td-mono" : ""}`} style={{ userSelect: "text" }}>
        {value || "—"}
      </span>
    </div>
  );
}

/* ─── 修改密码卡片 ─── */
function ChangePasswordCard() {
  const [oldPwd, setOldPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMsg("");
    if (!oldPwd || !newPwd) { setMsg("请填写所有字段"); return; }
    if (newPwd.length < 6) { setMsg("新密码至少 6 位"); return; }
    if (newPwd !== confirmPwd) { setMsg("两次新密码不一致"); return; }
    setLoading(true);
    try {
      await authApi.changePassword(oldPwd, newPwd);
      setMsg("密码修改成功");
      setOldPwd(""); setNewPwd(""); setConfirmPwd("");
      setTimeout(() => setMsg(""), 3000);
    } catch (err: any) {
      setMsg(err?.body?.detail || err.message || "修改失败");
    } finally {
      setLoading(false);
    }
  };

  const isError = msg && !msg.includes("成功");

  return (
    <div className="settings-section">
      <h3 className="settings-section-title">修改密码</h3>
      <div className="settings-card">
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label style={{ fontSize: 13, color: "#94A3B8" }}>当前密码</label>
            <input className="input" type="password" value={oldPwd}
              onChange={(e) => setOldPwd(e.target.value)}
              style={{ maxWidth: 300, backgroundColor: "#0F172A", color: "#E2E8F4", border: "1px solid #2D3548" }} />
          </div>
          <div className="form-group">
            <label style={{ fontSize: 13, color: "#94A3B8" }}>新密码</label>
            <input className="input" type="password" value={newPwd}
              onChange={(e) => setNewPwd(e.target.value)} placeholder="至少 6 位"
              style={{ maxWidth: 300, backgroundColor: "#0F172A", color: "#E2E8F4", border: "1px solid #2D3548" }} />
          </div>
          <div className="form-group">
            <label style={{ fontSize: 13, color: "#94A3B8" }}>确认新密码</label>
            <input className="input" type="password" value={confirmPwd}
              onChange={(e) => setConfirmPwd(e.target.value)}
              style={{ maxWidth: 300, backgroundColor: "#0F172A", color: "#E2E8F4", border: "1px solid #2D3548" }} />
          </div>
          {msg && (
            <div style={{
              fontSize: 13, marginBottom: 8, padding: "6px 12px", borderRadius: 4,
              background: isError ? "#EF444418" : "#22C55E18",
              color: isError ? "#EF4444" : "#22C55E",
            }}>
              {msg}
            </div>
          )}
          <button type="submit" className="btn btn-primary btn-sm" disabled={loading}>
            {loading ? "修改中..." : "修改密码"}
          </button>
        </form>
      </div>
    </div>
  );
}

/* ─── Toggle 组件 ─── */
function Toggle({ active, onToggle, label }: { active: boolean; onToggle: () => void; label: string }) {
  return (
    <button
      onClick={onToggle}
      aria-label={label}
      style={{
        width: 40, height: 22, borderRadius: 11,
        backgroundColor: active ? "#22D3EE" : "#334155",
        position: "relative", cursor: "pointer",
        transition: "background-color 0.2s",
        border: "none", padding: 0, flexShrink: 0,
      }}
    >
      <span style={{
        width: 16, height: 16, borderRadius: "50%",
        backgroundColor: "#fff", position: "absolute",
        top: 3, left: active ? 21 : 3,
        transition: "left 0.2s",
      }} />
    </button>
  );
}

function PrefRow({ title, desc, children }: { title: string; desc: string; children: React.ReactNode }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: "12px 16px", backgroundColor: "#1E293B33",
      border: "1px solid #2D354866", borderRadius: 6,
    }}>
      <div>
        <div style={{ fontSize: 13, color: "var(--text)" }}>{title}</div>
        <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>{desc}</div>
      </div>
      {children}
    </div>
  );
}

/* ─── 主页面 ─── */
export default function SettingsPage() {
  const settings = useSettingsStore();
  const logout = useAuthStore((s) => s.logout);
  const role = useAuthStore((s) => s.role);
  const navigate = useNavigate();
  const isAnnotator = role === "annotator" || role === "admin";

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div style={{ padding: 24, maxWidth: 640, margin: "0 auto" }}>
      <h2 style={{ margin: "0 0 24px", fontSize: 20, color: "var(--text)" }}>个人中心</h2>

      <ProfileCard />
      <ChangePasswordCard />

      {/* 偏好设置 */}
      <div className="settings-section">
        <h3 className="settings-section-title">偏好设置</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <PrefRow title="深色主题" desc="切换深色/浅色模式">
            <Toggle active={settings.theme === "dark"} label="切换主题"
              onToggle={() => settings.setTheme(settings.theme === "dark" ? "light" : "dark")} />
          </PrefRow>

          {/* 标注员专属设置 */}
          {isAnnotator && (
            <>
              <PrefRow title="跳过提交确认" desc="提交标注时不弹出确认对话框">
                <Toggle active={settings.skipSubmitConfirm} label="跳过提交确认"
                  onToggle={() => settings.setSkipSubmitConfirm(!settings.skipSubmitConfirm)} />
              </PrefRow>

              <PrefRow title="休息提醒" desc="连续标注后提醒休息">
                <Toggle active={settings.enableRestReminder} label="休息提醒"
                  onToggle={() => settings.setEnableRestReminder(!settings.enableRestReminder)} />
              </PrefRow>

              {settings.enableRestReminder && (
                <PrefRow title="提醒间隔（分钟）" desc="连续工作多久后提醒">
                  <input type="number" min={10} max={180}
                    value={settings.restReminderMinutes}
                    onChange={(e) => settings.setRestReminderMinutes(Number(e.target.value))}
                    style={{
                      width: 64, padding: "4px 8px", backgroundColor: "#0F172A",
                      border: "1px solid #2D3548", borderRadius: 4,
                      color: "#E2E8F4", fontSize: 13, textAlign: "center",
                    }}
                  />
                </PrefRow>
              )}
            </>
          )}

          <PrefRow title="通知音效" desc="收到紧急通知时播放声音">
            <Toggle active={settings.enableSound} label="通知音效"
              onToggle={() => settings.setEnableSound(!settings.enableSound)} />
          </PrefRow>

          <PrefRow title="每页显示条数" desc="列表页面的默认分页大小">
            <select value={settings.preferredPageSize}
              onChange={(e) => settings.setPreferredPageSize(Number(e.target.value))}
              style={{
                padding: "4px 8px", backgroundColor: "#0F172A",
                border: "1px solid #2D3548", borderRadius: 4,
                color: "#E2E8F4", fontSize: 13,
              }}
            >
              {[10, 20, 50, 100].map((n) => (
                <option key={n} value={n} style={{ backgroundColor: "#0F172A", color: "#E2E8F4" }}>{n}</option>
              ))}
            </select>
          </PrefRow>
        </div>
      </div>

      {/* 退出登录 */}
      <div style={{ marginTop: 32, paddingTop: 20, borderTop: "1px solid var(--border)" }}>
        <button
          onClick={handleLogout}
          style={{
            width: "100%", padding: "10px 0", borderRadius: 6,
            backgroundColor: "#EF444418", border: "1px solid #EF444433",
            color: "#EF4444", fontSize: 14, fontWeight: 500,
            cursor: "pointer", transition: "background-color 0.15s",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "#EF444430")}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "#EF444418")}
        >
          退出登录
        </button>
      </div>
    </div>
  );
}
