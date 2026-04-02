import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
  userId: string;
  username: string;
  displayName: string;
  role: "operator" | "uploader" | "annotator" | "admin";
  annotatorId: string | null;
  token: string | null;
  merchantId: string | null;
  isLoggedIn: boolean;
  setAuth: (auth: {
    userId: string;
    username: string;
    displayName?: string;
    role: string;
    token: string;
    merchantId?: string | null;
  }) => void;
  logout: () => void;
}

/** 同步读取 localStorage 中的持久化状态，避免 hydration 时间差 */
function readPersistedState(): Partial<AuthState> {
  try {
    const raw = localStorage.getItem("pdf-sku-auth");
    if (raw) {
      const parsed = JSON.parse(raw);
      return parsed?.state ?? {};
    }
  } catch { /* ignore */ }
  return {};
}

const restored = readPersistedState();

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      userId: (restored.userId as string) || "",
      username: (restored.username as string) || "",
      displayName: (restored.displayName as string) || "",
      role: (restored.role as AuthState["role"]) || "operator",
      annotatorId: (restored.annotatorId as string | null) ?? null,
      token: (restored.token as string | null) ?? null,
      merchantId: (restored.merchantId as string | null) ?? null,
      isLoggedIn: (restored.isLoggedIn as boolean) || false,
      setAuth: (auth) =>
        set({
          userId: auth.userId,
          username: auth.username,
          displayName: auth.displayName || auth.username,
          role: auth.role as AuthState["role"],
          annotatorId: auth.role === "annotator" ? auth.userId : null,
          token: auth.token,
          merchantId: auth.merchantId ?? null,
          isLoggedIn: true,
        }),
      logout: () =>
        set({
          userId: "",
          username: "",
          displayName: "",
          role: "operator",
          annotatorId: null,
          token: null,
          merchantId: null,
          isLoggedIn: false,
        }),
    }),
    {
      name: "pdf-sku-auth",
      storage: {
        getItem: (k) => {
          const v = localStorage.getItem(k);
          return v ? JSON.parse(v) : null;
        },
        setItem: (k, v) => localStorage.setItem(k, JSON.stringify(v)),
        removeItem: (k) => localStorage.removeItem(k),
      },
    },
  ),
);
