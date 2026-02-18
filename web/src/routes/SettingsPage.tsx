/**
 * 设置页 /settings
 * 包含: 个人信息修改、修改密码、偏好设置
 */
import { useState } from "react";
import { useSettingsStore } from "../stores/settingsStore";
import { useAuthStore } from "../stores/authStore";
import { authApi } from "../api/auth";

/* ─── 个人信息卡片 ─── */
function ProfileCard() {
  const { username, displayName, role, merchantId } = useAuthStore();
  const setAuth = useAuthStore((s) => s.setAuth);
  const token = useAuthStore((s) => s.token);
  const userId = useAuthStore((s) => s.userId);

  const [editing, setEditing] = useState(false);
  const [newDisplayName, setNewDisplayName] = useState(displayName);
  const [newMerchantId, setNewMerchantId] = useState(merchantId || "");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const handleSave = async () => {
    setSaving(true);
    setMsg("");
    try {
      const res = await authApi.updateProfile({
        display_name: newDisplayName,
        merchant_id: role === "uploader" ? newMerchantId : undefined,
      });
      // 更新本地状态
      setAuth({
        userId,
        username,
        displayName: res.display_name,
        role,
        token: token!,
        merchantId: res.merchant_id,
      });
      setMsg("✅ 个人信息已更新");
      setEditing(false);
      setTimeout(() => setMsg(""), 3000);
    } catch (err: any) {
      setMsg("❌ " + (err?.body?.detail || err.message || "更新失败"));
    } finally {
      setSaving(false);
    }
  };

  const ROLE_LABELS: Record<string, string> = {
    admin: "管理员", uploader: "上传者", annotator: "标注员",
  };

  return (
    <div className="settings-section">
      <h3 className="settings-section-title">👤 个人信息</h3>
      <div className="settings-card">
        <div className="settings-row">
          <span className="settings-label">用户名</span>
          <span className="settings-value td-mono">{username}</span>
        </div>
        <div className="settings-row">
          <span className="settings-label">角色</span>
          <span className="settings-value">{ROLE_LABELS[role] || role}</span>
        </div>
        <div className="settings-row">
          <span className="settings-label">显示名称</span>
          {editing ? (
            <input className="input input-sm" value={newDisplayName} onChange={(e) => setNewDisplayName(e.target.value)} style={{ maxWidth: 200 }} />
          ) : (
            <span className="settings-value">{displayName}</span>
          )}
        </div>
        {role === "uploader" && (
          <div className="settings-row">
            <span className="settings-label">商户 ID</span>
            {editing ? (
              <input className="input input-sm" value={newMerchantId} onChange={(e) => setNewMerchantId(e.target.value)} style={{ maxWidth: 200 }} />
            ) : (
              <span className="settings-value td-mono">{merchantId || "—"}</span>
            )}
          </div>
        )}
        {msg && <div style={{ fontSize: 13, marginTop: 8 }}>{msg}</div>}
        <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
          {editing ? (
            <>
              <button className="btn btn-primary btn-sm" onClick={handleSave} disabled={saving}>
                {saving ? "保存中..." : "保存"}
              </button>
              <button className="btn btn-sm" onClick={() => { setEditing(false); setNewDisplayName(displayName); setNewMerchantId(merchantId || ""); }}>
                取消
              </button>
            </>
          ) : (
            <button className="btn btn-sm" onClick={() => setEditing(true)}>✏️ 编辑</button>
          )}
        </div>
      </div>
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
    if (!oldPwd || !newPwd) { setMsg("❌ 请填写所有字段"); return; }
    if (newPwd.length < 6) { setMsg("❌ 新密码至少 6 位"); return; }
    if (newPwd !== confirmPwd) { setMsg("❌ 两次新密码不一致"); return; }
    setLoading(true);
    try {
      await authApi.changePassword(oldPwd, newPwd);
      setMsg("✅ 密码修改成功");
      setOldPwd(""); setNewPwd(""); setConfirmPwd("");
      setTimeout(() => setMsg(""), 3000);
    } catch (err: any) {
      setMsg("❌ " + (err?.body?.detail || err.message || "修改失败"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="settings-section">
      <h3 className="settings-section-title">🔒 修改密码</h3>
      <div className="settings-card">
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>当前密码</label>
            <input className="input" type="password" value={oldPwd} onChange={(e) => setOldPwd(e.target.value)} style={{ maxWidth: 300 }} />
          </div>
          <div className="form-group">
            <label>新密码</label>
            <input className="input" type="password" value={newPwd} onChange={(e) => setNewPwd(e.target.value)} placeholder="至少 6 位" style={{ maxWidth: 300 }} />
          </div>
          <div className="form-group">
            <label>确认新密码</label>
            <input className="input" type="password" value={confirmPwd} onChange={(e) => setConfirmPwd(e.target.value)} style={{ maxWidth: 300 }} />
          </div>
          {msg && <div style={{ fontSize: 13, marginBottom: 8 }}>{msg}</div>}
          <button type="submit" className="btn btn-primary btn-sm" disabled={loading}>
            {loading ? "修改中..." : "修改密码"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const settings = useSettingsStore();

  const toggleStyle = (active: boolean): React.CSSProperties => ({
    width: 40,
    height: 22,
    borderRadius: 11,
    backgroundColor: active ? "#22D3EE" : "#334155",
    position: "relative",
    cursor: "pointer",
    transition: "background-color 0.2s",
    border: "none",
    padding: 0,
  });

  const dotStyle = (active: boolean): React.CSSProperties => ({
    width: 16,
    height: 16,
    borderRadius: "50%",
    backgroundColor: "#fff",
    position: "absolute",
    top: 3,
    left: active ? 21 : 3,
    transition: "left 0.2s",
  });

  return (
    <div style={{ padding: 24, maxWidth: 640, margin: "0 auto" }}>
      {/* 个人信息 */}
      <ProfileCard />

      {/* 修改密码 */}
      <ChangePasswordCard />

      {/* 偏好设置 */}
      <div className="settings-section">
        <h3 className="settings-section-title">⚙️ 偏好设置</h3>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {/* Theme */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", backgroundColor: "#1E293B33", border: "1px solid #2D354866", borderRadius: 6 }}>
          <div>
            <div style={{ fontSize: 13, color: "#E2E8F4" }}>深色主题</div>
            <div style={{ fontSize: 11, color: "#64748B", marginTop: 2 }}>切换深色/浅色模式</div>
          </div>
          <button
            style={toggleStyle(settings.theme === "dark")}
            onClick={() => settings.setTheme(settings.theme === "dark" ? "light" : "dark")}
            aria-label="切换主题"
          >
            <span style={dotStyle(settings.theme === "dark")} />
          </button>
        </div>

        {/* Skip submit confirm */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", backgroundColor: "#1E293B33", border: "1px solid #2D354866", borderRadius: 6 }}>
          <div>
            <div style={{ fontSize: 13, color: "#E2E8F4" }}>跳过提交确认</div>
            <div style={{ fontSize: 11, color: "#64748B", marginTop: 2 }}>提交标注时不弹出确认对话框</div>
          </div>
          <button
            style={toggleStyle(settings.skipSubmitConfirm)}
            onClick={() => settings.setSkipSubmitConfirm(!settings.skipSubmitConfirm)}
            aria-label="跳过提交确认"
          >
            <span style={dotStyle(settings.skipSubmitConfirm)} />
          </button>
        </div>

        {/* Enable rest reminder */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", backgroundColor: "#1E293B33", border: "1px solid #2D354866", borderRadius: 6 }}>
          <div>
            <div style={{ fontSize: 13, color: "#E2E8F4" }}>休息提醒</div>
            <div style={{ fontSize: 11, color: "#64748B", marginTop: 2 }}>连续标注后提醒休息</div>
          </div>
          <button
            style={toggleStyle(settings.enableRestReminder)}
            onClick={() => settings.setEnableRestReminder(!settings.enableRestReminder)}
            aria-label="休息提醒"
          >
            <span style={dotStyle(settings.enableRestReminder)} />
          </button>
        </div>

        {/* Rest reminder minutes */}
        {settings.enableRestReminder && (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", backgroundColor: "#1E293B33", border: "1px solid #2D354866", borderRadius: 6 }}>
            <div>
              <div style={{ fontSize: 13, color: "#E2E8F4" }}>提醒间隔（分钟）</div>
              <div style={{ fontSize: 11, color: "#64748B", marginTop: 2 }}>连续工作多久后提醒</div>
            </div>
            <input
              type="number"
              min={10}
              max={180}
              value={settings.restReminderMinutes}
              onChange={(e) => settings.setRestReminderMinutes(Number(e.target.value))}
              style={{
                width: 64,
                padding: "4px 8px",
                backgroundColor: "#0F172A",
                border: "1px solid #2D3548",
                borderRadius: 4,
                color: "#E2E8F4",
                fontSize: 13,
                textAlign: "center",
              }}
            />
          </div>
        )}

        {/* Enable sound */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", backgroundColor: "#1E293B33", border: "1px solid #2D354866", borderRadius: 6 }}>
          <div>
            <div style={{ fontSize: 13, color: "#E2E8F4" }}>通知音效</div>
            <div style={{ fontSize: 11, color: "#64748B", marginTop: 2 }}>收到紧急通知时播放声音</div>
          </div>
          <button
            style={toggleStyle(settings.enableSound)}
            onClick={() => settings.setEnableSound(!settings.enableSound)}
            aria-label="通知音效"
          >
            <span style={dotStyle(settings.enableSound)} />
          </button>
        </div>

        {/* Preferred page size */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", backgroundColor: "#1E293B33", border: "1px solid #2D354866", borderRadius: 6 }}>
          <div>
            <div style={{ fontSize: 13, color: "#E2E8F4" }}>每页显示条数</div>
            <div style={{ fontSize: 11, color: "#64748B", marginTop: 2 }}>列表页面的默认分页大小</div>
          </div>
          <select
            value={settings.preferredPageSize}
            onChange={(e) => settings.setPreferredPageSize(Number(e.target.value))}
            style={{
              padding: "4px 8px",
              backgroundColor: "#0F172A",
              border: "1px solid #2D3548",
              borderRadius: 4,
              color: "#E2E8F4",
              fontSize: 13,
            }}
          >
            {[10, 20, 50, 100].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
