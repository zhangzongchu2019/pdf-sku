import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
  userId: string;
  role: "operator" | "annotator" | "admin";
  annotatorId: string | null;
  token: string | null;
  merchantId: string | null;
  setAuth: (auth: Partial<AuthState>) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      userId: "",
      role: "operator",
      annotatorId: null,
      token: null,
      merchantId: null,
      setAuth: (auth) => set(auth),
      logout: () =>
        set({ userId: "", role: "operator", annotatorId: null, token: null, merchantId: null }),
    }),
    { name: "pdf-sku-auth", storage: { getItem: (k) => { const v = sessionStorage.getItem(k); return v ? JSON.parse(v) : null; }, setItem: (k, v) => sessionStorage.setItem(k, JSON.stringify(v)), removeItem: (k) => sessionStorage.removeItem(k) } },
  ),
);
