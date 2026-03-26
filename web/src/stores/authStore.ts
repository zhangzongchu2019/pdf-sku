import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

interface AuthState {
  userId: string;
  username: string;
  displayName: string;
  role: "operator" | "uploader" | "annotator" | "admin";
  annotatorId: string | null;
  token: string | null;
  merchantId: string | null;
  isLoggedIn: boolean;
  hydrated: boolean;
  setAuth: (auth: {
    userId: string;
    username: string;
    displayName?: string;
    role: string;
    token: string;
    merchantId?: string | null;
  }) => void;
  setHydrated: (hydrated: boolean) => void;
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
      hydrated: false,
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
      setHydrated: (hydrated) => set({ hydrated }),
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
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        userId: state.userId,
        username: state.username,
        displayName: state.displayName,
        role: state.role,
        annotatorId: state.annotatorId,
        token: state.token,
        merchantId: state.merchantId,
        isLoggedIn: state.isLoggedIn,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHydrated(true);
      },
    },
  ),
);
