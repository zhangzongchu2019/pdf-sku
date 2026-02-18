/**
 * 用户管理页 /admin/users — 仅管理员可访问
 * 功能: 查看所有用户、创建用户、启用/禁用、重置密码、修改角色
 */
import { useEffect, useState, useCallback } from "react";
import { authApi, type UserInfo } from "../api/auth";

const ROLE_LABELS: Record<string, string> = {
  admin: "管理员",
  uploader: "上传者",
  annotator: "标注员",
};

const ROLE_COLORS: Record<string, string> = {
  admin: "#722ed1",
  uploader: "#1890ff",
  annotator: "#52c41a",
};

/* ─── Create User Dialog ─── */
function CreateUserDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState({
    username: "",
    password: "",
    display_name: "",
    role: "uploader" as "uploader" | "annotator" | "admin",
    merchant_id: "",
    specialties: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const update = (k: string, v: string) => setForm((p) => ({ ...p, [k]: v }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!form.username.trim() || !form.password.trim()) {
      setError("用户名和密码必填");
      return;
    }
    if (form.password.length < 6) {
      setError("密码至少 6 位");
      return;
    }
    setLoading(true);
    try {
      await authApi.createUser({
        username: form.username,
        password: form.password,
        display_name: form.display_name || form.username,
        role: form.role,
        merchant_id: form.role === "uploader" ? form.merchant_id || undefined : undefined,
        specialties:
          form.role === "annotator" && form.specialties
            ? form.specialties.split(",").map((s) => s.trim()).filter(Boolean)
            : undefined,
      });
      onCreated();
      onClose();
      setForm({ username: "", password: "", display_name: "", role: "uploader", merchant_id: "", specialties: "" });
    } catch (err: any) {
      setError(err?.body?.detail || err.message || "创建失败");
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>创建用户</h3>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={handleSubmit}>
          {error && <div className="auth-error">{error}</div>}

          <div className="form-group">
            <label>用户名 *</label>
            <input className="input" value={form.username} onChange={(e) => update("username", e.target.value)} placeholder="2-64 个字符" />
          </div>
          <div className="form-group">
            <label>密码 *</label>
            <input className="input" type="password" value={form.password} onChange={(e) => update("password", e.target.value)} placeholder="至少 6 位" />
          </div>
          <div className="form-group">
            <label>显示名称</label>
            <input className="input" value={form.display_name} onChange={(e) => update("display_name", e.target.value)} placeholder="可选" />
          </div>
          <div className="form-group">
            <label>角色 *</label>
            <div className="role-selector">
              {(["uploader", "annotator", "admin"] as const).map((r) => (
                <button
                  key={r}
                  type="button"
                  className={`role-btn ${form.role === r ? "active" : ""}`}
                  onClick={() => update("role", r)}
                >
                  <span>{r === "uploader" ? "📤" : r === "annotator" ? "✏️" : "👑"}</span>
                  <span>{ROLE_LABELS[r]}</span>
                </button>
              ))}
            </div>
          </div>
          {form.role === "uploader" && (
            <div className="form-group">
              <label>商户 ID</label>
              <input className="input" value={form.merchant_id} onChange={(e) => update("merchant_id", e.target.value)} placeholder="可选" />
            </div>
          )}
          {form.role === "annotator" && (
            <div className="form-group">
              <label>擅长领域</label>
              <input className="input" value={form.specialties} onChange={(e) => update("specialties", e.target.value)} placeholder="逗号分隔, 如: 电子, 家具" />
            </div>
          )}
          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 16 }}>
            <button type="button" className="btn" onClick={onClose}>取消</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? "创建中..." : "创建"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ─── Reset Password Dialog ─── */
function ResetPasswordDialog({
  user,
  onClose,
  onDone,
}: {
  user: UserInfo | null;
  onClose: () => void;
  onDone: () => void;
}) {
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user) return;
    if (newPassword.length < 6) {
      setError("密码至少 6 位");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await authApi.adminUpdateUser(user.user_id, { reset_password: newPassword });
      onDone();
      onClose();
      setNewPassword("");
    } catch (err: any) {
      setError(err?.body?.detail || err.message || "操作失败");
    } finally {
      setLoading(false);
    }
  };

  if (!user) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>重置密码 — {user.display_name || user.username}</h3>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={handleSubmit}>
          {error && <div className="auth-error">{error}</div>}
          <div className="form-group">
            <label>新密码</label>
            <input className="input" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="至少 6 位" autoFocus />
          </div>
          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 16 }}>
            <button type="button" className="btn" onClick={onClose}>取消</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? "重置中..." : "确认重置"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ─── Main Page ─── */
export default function UserManagePage() {
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterRole, setFilterRole] = useState<string>("");
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [resetTarget, setResetTarget] = useState<UserInfo | null>(null);
  const [actionMsg, setActionMsg] = useState("");

  const fetchUsers = useCallback(async () => {
    try {
      const res = await authApi.listUsers();
      setUsers(res.data);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const toggleStatus = async (u: UserInfo) => {
    try {
      await authApi.toggleUserStatus(u.user_id, !u.is_active);
      setActionMsg(`${u.username} 已${u.is_active ? "禁用" : "启用"}`);
      fetchUsers();
      setTimeout(() => setActionMsg(""), 3000);
    } catch {
      /* ignore */
    }
  };

  const filtered = users.filter((u) => {
    if (filterRole && u.role !== filterRole) return false;
    if (search) {
      const q = search.toLowerCase();
      return u.username.toLowerCase().includes(q) || (u.display_name || "").toLowerCase().includes(q);
    }
    return true;
  });

  const stats = {
    total: users.length,
    admin: users.filter((u) => u.role === "admin").length,
    uploader: users.filter((u) => u.role === "uploader").length,
    annotator: users.filter((u) => u.role === "annotator").length,
    disabled: users.filter((u) => !u.is_active).length,
  };

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 18 }}>👥 用户管理</h2>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          ＋ 创建用户
        </button>
      </div>

      {/* Stats cards */}
      <div className="metrics-grid" style={{ marginBottom: 20 }}>
        <div className="metrics-card">
          <div className="metrics-title">总用户</div>
          <div className="metrics-value">{stats.total}</div>
        </div>
        <div className="metrics-card" style={{ borderLeftColor: ROLE_COLORS.uploader }}>
          <div className="metrics-title">上传者</div>
          <div className="metrics-value">{stats.uploader}</div>
        </div>
        <div className="metrics-card" style={{ borderLeftColor: ROLE_COLORS.annotator }}>
          <div className="metrics-title">标注员</div>
          <div className="metrics-value">{stats.annotator}</div>
        </div>
        <div className="metrics-card" style={{ borderLeftColor: ROLE_COLORS.admin }}>
          <div className="metrics-title">管理员</div>
          <div className="metrics-value">{stats.admin}</div>
        </div>
      </div>

      {/* Action message */}
      {actionMsg && (
        <div style={{ background: "#f6ffed", border: "1px solid #b7eb8f", color: "#389e0d", padding: "8px 12px", borderRadius: 6, marginBottom: 12, fontSize: 13 }}>
          ✅ {actionMsg}
        </div>
      )}

      {/* Filter bar */}
      <div className="filter-bar" style={{ marginBottom: 16 }}>
        <input
          className="input"
          style={{ maxWidth: 240 }}
          placeholder="🔍 搜索用户名 / 显示名称"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {["", "uploader", "annotator", "admin"].map((r) => (
          <button
            key={r}
            className={`btn btn-filter ${filterRole === r ? "active" : ""}`}
            onClick={() => setFilterRole(r)}
          >
            {r ? ROLE_LABELS[r] : "全部"}
          </button>
        ))}
      </div>

      {/* User table */}
      {loading ? (
        <div className="loading-container"><div className="loading-spinner" /></div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <span className="empty-icon">👤</span>
          <p>暂无用户</p>
        </div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>用户名</th>
              <th>显示名称</th>
              <th>角色</th>
              <th>商户ID</th>
              <th>状态</th>
              <th>创建时间</th>
              <th>最后登录</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((u) => (
              <tr key={u.user_id}>
                <td className="td-mono">{u.username}</td>
                <td>{u.display_name}</td>
                <td>
                  <span
                    className="status-badge"
                    style={{ background: `${ROLE_COLORS[u.role] || "#999"}18`, color: ROLE_COLORS[u.role] || "#999" }}
                  >
                    {ROLE_LABELS[u.role] || u.role}
                  </span>
                </td>
                <td className="td-mono">{u.merchant_id || "—"}</td>
                <td>
                  <span className={`status-badge`} style={{
                    background: u.is_active ? "#f6ffed" : "#fff2f0",
                    color: u.is_active ? "#389e0d" : "#cf1322",
                  }}>
                    {u.is_active ? "正常" : "已禁用"}
                  </span>
                </td>
                <td style={{ fontSize: 12, color: "#8c8c8c" }}>
                  {u.created_at ? new Date(u.created_at).toLocaleDateString("zh-CN") : "—"}
                </td>
                <td style={{ fontSize: 12, color: "#8c8c8c" }}>
                  {u.last_login_at ? new Date(u.last_login_at).toLocaleString("zh-CN") : "从未登录"}
                </td>
                <td>
                  <div style={{ display: "flex", gap: 4 }}>
                    <button
                      className="btn btn-sm btn-ghost"
                      title="重置密码"
                      onClick={() => setResetTarget(u)}
                    >
                      🔑
                    </button>
                    <button
                      className={`btn btn-sm ${u.is_active ? "btn-ghost" : "btn-ghost"}`}
                      title={u.is_active ? "禁用" : "启用"}
                      onClick={() => toggleStatus(u)}
                      style={{ color: u.is_active ? "#cf1322" : "#389e0d" }}
                    >
                      {u.is_active ? "🚫" : "✅"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <CreateUserDialog open={showCreate} onClose={() => setShowCreate(false)} onCreated={fetchUsers} />
      <ResetPasswordDialog user={resetTarget} onClose={() => setResetTarget(null)} onDone={fetchUsers} />
    </div>
  );
}
