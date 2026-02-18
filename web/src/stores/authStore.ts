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

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      userId: "",
      username: "",
      displayName: "",
      role: "operator" as const,
      annotatorId: null,
      token: null,
      merchantId: null,
      isLoggedIn: false,
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
