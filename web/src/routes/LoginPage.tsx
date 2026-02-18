import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";
import { authApi } from "../api/auth";

export default function LoginPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!username.trim() || !password.trim()) {
      setError("请输入用户名和密码");
      return;
    }
    setLoading(true);
    try {
      const res = await authApi.login(username, password);
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
      const msg = err?.body?.detail || err?.body?.message || err.message || "登录失败";
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
          <p className="auth-subtitle">PDF 目录智能解析平台</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          <h2>登录</h2>

          {error && <div className="auth-error">{error}</div>}

          <div className="form-group">
            <label>用户名</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="请输入用户名"
              className="input"
              autoFocus
            />
          </div>

          <div className="form-group">
            <label>密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入密码"
              className="input"
            />
          </div>

          <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
            {loading ? "登录中..." : "登录"}
          </button>

          <div className="auth-footer">
            没有账号？<Link to="/register">注册新账号</Link>
          </div>
        </form>
      </div>
    </div>
  );
}
