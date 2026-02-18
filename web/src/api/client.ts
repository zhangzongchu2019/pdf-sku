import { useAuthStore } from "../stores/authStore";

const API_BASE = import.meta.env.VITE_API_BASE || "/api/v1";

class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
    this.name = "ApiError";
  }
}

function getAuthHeaders(): Record<string, string> {
  const token = useAuthStore.getState().token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const { headers: customHeaders, ...restInit } = init ?? {};
  const res = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
      ...(customHeaders instanceof Headers
        ? Object.fromEntries(customHeaders.entries())
        : Array.isArray(customHeaders)
          ? Object.fromEntries(customHeaders)
          : customHeaders),
    },
    ...restInit,
  });
  if (!res.ok) {
    // 401 → 自动登出, 跳转登录
    if (res.status === 401) {
      useAuthStore.getState().logout();
      window.location.href = "/login";
      throw new ApiError(401, "登录已过期，请重新登录");
    }
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, `${res.status} ${res.statusText}`, body);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

export { ApiError };
export default api;
