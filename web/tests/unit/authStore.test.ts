import { beforeEach, describe, expect, it, vi } from "vitest";

const AUTH_STORAGE_KEY = "pdf-sku-auth";

describe("authStore", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetModules();
  });

  it("restores auth state synchronously from localStorage", async () => {
    localStorage.setItem(
      AUTH_STORAGE_KEY,
      JSON.stringify({
        state: {
          userId: "user-1",
          username: "alice",
          displayName: "Alice",
          role: "uploader",
          annotatorId: null,
          token: "token-123",
          merchantId: "merchant-1",
          isLoggedIn: true,
        },
        version: 0,
      }),
    );

    const { useAuthStore, getAuthToken } = await import("../../src/stores/authStore");
    const state = useAuthStore.getState();

    expect(state.hydrated).toBe(true);
    expect(state.isLoggedIn).toBe(true);
    expect(state.username).toBe("alice");
    expect(state.role).toBe("uploader");
    expect(state.token).toBe("token-123");
    expect(getAuthToken()).toBe("token-123");
  });

  it("ignores malformed persisted auth data", async () => {
    localStorage.setItem(AUTH_STORAGE_KEY, "{invalid json");

    const { useAuthStore, getAuthToken } = await import("../../src/stores/authStore");
    const state = useAuthStore.getState();

    expect(state.hydrated).toBe(true);
    expect(state.isLoggedIn).toBe(false);
    expect(state.token).toBeNull();
    expect(getAuthToken()).toBeNull();
  });
});
