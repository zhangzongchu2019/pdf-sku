import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";
import { authApi } from "../api/auth";

export default function RegisterPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  const [form, setForm] = useState({
    username: "",
    password: "",
    confirmPassword: "",
    display_name: "",
    role: "uploader" as "uploader" | "annotator",
    merchant_id: "",
    specialties: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const update = (field: string, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!form.username.trim() || !form.password.trim()) {
      setError("请填写用户名和密码");
      return;
    }
    if (form.password.length < 6) {
      setError("密码至少 6 位");
      return;
    }
    if (form.password !== form.confirmPassword) {
      setError("两次密码不一致");
      return;
    }

    setLoading(true);
    try {
      const res = await authApi.register({
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
      setAuth({
        userId: res.user_id,
        username: res.username,
        displayName: res.display_name,
        role: res.role,
        token: res.token,
        merchantId: res.merchant_id,
      });
      navigate("/");
    } catch (err: any) {
      const msg = err?.body?.detail || err?.body?.message || err.message || "注册失败";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-header">
          <h1 className="auth-logo">📄 PDF-SKU</h1>
          <p className="auth-subtitle">注册新账号</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          {error && <div className="auth-error">{error}</div>}

          <div className="form-group">
            <label>用户名 *</label>
            <input
              type="text"
              value={form.username}
              onChange={(e) => update("username", e.target.value)}
              placeholder="2-64 个字符"
              className="input"
              autoFocus
            />
          </div>

          <div className="form-group">
            <label>显示名称</label>
            <input
              type="text"
              value={form.display_name}
              onChange={(e) => update("display_name", e.target.value)}
              placeholder="可选，默认同用户名"
              className="input"
            />
          </div>

          <div className="form-group">
            <label>密码 *</label>
            <input
              type="password"
              value={form.password}
              onChange={(e) => update("password", e.target.value)}
              placeholder="至少 6 位"
              className="input"
            />
          </div>

          <div className="form-group">
            <label>确认密码 *</label>
            <input
              type="password"
              value={form.confirmPassword}
              onChange={(e) => update("confirmPassword", e.target.value)}
              placeholder="再次输入密码"
              className="input"
            />
          </div>

          <div className="form-group">
            <label>账号类型 *</label>
            <div className="role-selector">
              <button
                type="button"
                className={`role-btn ${form.role === "uploader" ? "active" : ""}`}
                onClick={() => update("role", "uploader")}
              >
                📤 上传者
                <span className="role-desc">上传 PDF 目录文件</span>
              </button>
              <button
                type="button"
                className={`role-btn ${form.role === "annotator" ? "active" : ""}`}
                onClick={() => update("role", "annotator")}
              >
                ✏️ 标注员
                <span className="role-desc">人工标注 SKU 数据</span>
              </button>
            </div>
          </div>

          {form.role === "uploader" && (
            <div className="form-group">
              <label>商户 ID</label>
              <input
                type="text"
                value={form.merchant_id}
                onChange={(e) => update("merchant_id", e.target.value)}
                placeholder="例: merchant_001"
                className="input"
              />
            </div>
          )}

          {form.role === "annotator" && (
            <div className="form-group">
              <label>擅长品类</label>
              <input
                type="text"
                value={form.specialties}
                onChange={(e) => update("specialties", e.target.value)}
                placeholder="逗号分隔，例: electronics,food"
                className="input"
              />
            </div>
          )}

          <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
            {loading ? "注册中..." : "注册"}
          </button>

          <div className="auth-footer">
            已有账号？<Link to="/login">去登录</Link>
          </div>
        </form>
      </div>
    </div>
  );
}
