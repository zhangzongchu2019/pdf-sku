import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

type AuthRole = "operator" | "uploader" | "annotator" | "admin";

interface AuthState {
  userId: string;
  username: string;
  displayName: string;
  role: AuthRole;
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

type PersistedAuthState = Pick<
  AuthState,
  "userId" | "username" | "displayName" | "role" | "annotatorId" | "token" | "merchantId" | "isLoggedIn"
>;

type PersistedAuthEnvelope = {
  state?: Partial<PersistedAuthState>;
  version?: number;
};

export const AUTH_STORAGE_KEY = "pdf-sku-auth";

const DEFAULT_AUTH_STATE: PersistedAuthState = {
  userId: "",
  username: "",
  displayName: "",
  role: "operator",
  annotatorId: null,
  token: null,
  merchantId: null,
  isLoggedIn: false,
};

function canUseLocalStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function normalizeRole(role: unknown): AuthRole {
  return role === "uploader" || role === "annotator" || role === "admin" || role === "operator"
    ? role
    : "operator";
}

function normalizeNullableString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function readPersistedAuthState(): Partial<PersistedAuthState> {
  if (!canUseLocalStorage()) {
    return {};
  }

  try {
    const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) {
      return {};
    }

    const parsed = JSON.parse(raw) as PersistedAuthEnvelope;
    const state = parsed?.state;
    if (!state || typeof state !== "object") {
      return {};
    }

    const token = normalizeNullableString(state.token);
    const userId = typeof state.userId === "string" ? state.userId : "";
    const username = typeof state.username === "string" ? state.username : "";
    const displayName = typeof state.displayName === "string" ? state.displayName : "";

    return {
      userId,
      username,
      displayName,
      role: normalizeRole(state.role),
      annotatorId: normalizeNullableString(state.annotatorId),
      token,
      merchantId: normalizeNullableString(state.merchantId),
      isLoggedIn: Boolean(state.isLoggedIn && token && userId && username),
    };
  } catch {
    return {};
  }
}

function getInitialAuthState(): Pick<AuthState, keyof PersistedAuthState | "hydrated"> {
  return {
    ...DEFAULT_AUTH_STATE,
    ...readPersistedAuthState(),
    hydrated: canUseLocalStorage(),
  };
}

export function getPersistedAuthToken(): string | null {
  return readPersistedAuthState().token ?? null;
}

export function getAuthToken(): string | null {
  return useAuthStore.getState().token || getPersistedAuthToken();
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      ...getInitialAuthState(),
      setAuth: (auth) =>
        set({
          userId: auth.userId,
          username: auth.username,
          displayName: auth.displayName || auth.username,
          role: auth.role as AuthRole,
          annotatorId: auth.role === "annotator" ? auth.userId : null,
          token: auth.token,
          merchantId: auth.merchantId ?? null,
          isLoggedIn: true,
          hydrated: true,
        }),
      setHydrated: (hydrated) => set({ hydrated }),
      logout: () =>
        set({
          ...DEFAULT_AUTH_STATE,
          hydrated: true,
        }),
    }),
    {
      name: AUTH_STORAGE_KEY,
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
