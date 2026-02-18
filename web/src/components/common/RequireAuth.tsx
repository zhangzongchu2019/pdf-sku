import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "../../stores/authStore";

/**
 * 路由守卫 — 未登录跳转 /login，角色不匹配显示 403。
 * @param roles  允许的角色列表，空 = 所有已登录用户
 */
export function RequireAuth({
  children,
  roles,
}: {
  children: React.ReactNode;
  roles?: string[];
}) {
  const { isLoggedIn, role } = useAuthStore();
  const location = useLocation();

  if (!isLoggedIn) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (roles && roles.length > 0 && !roles.includes(role)) {
    return (
      <div className="page" style={{ textAlign: "center", paddingTop: 80 }}>
        <h2>⛔ 403 无权限</h2>
        <p>当前角色 <strong>{role}</strong> 无法访问此页面。</p>
        <p>需要角色: {roles.join(" / ")}</p>
      </div>
    );
  }

  return <>{children}</>;
}
