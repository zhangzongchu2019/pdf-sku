import api from "./client";
import type { ThresholdProfile, CalibrationRecord } from "../types/models";

export interface LLMProviderConfig {
  timeout_seconds: number;
  vlm_timeout_seconds: number;
  max_retries: number;
}

export interface LLMProviderEntry {
  name: string;
  provider_type: string;
  access_mode: "direct" | "proxy";
  proxy_service: string | null;
  model: string;
  priority: number;
  enabled: boolean;
  timeout_seconds: number;
  vlm_timeout_seconds: number;
  max_retries: number;
  account_name: string;
  qpm_limit: number;
  tpm_limit: number;
}

export interface LLMAccount {
  id: number;
  name: string;
  provider_type: string;
  api_base: string;
  api_key_masked: string;
  created_at: string;
}

export const configApi = {
  getActiveProfile: () => api.get<ThresholdProfile>("/config/profiles/active"),

  listProfiles: () => api.get<{ data: ThresholdProfile[] }>("/config/profiles"),

  updateThresholds: (profileId: string, thresholds: Record<string, number>, reason: string) =>
    api.put<ThresholdProfile>(`/config/profiles/${profileId}`, {
      thresholds,
      change_reason: reason,
    }),

  createProfile: (thresholds: Record<string, number>, reason: string) =>
    api.post<ThresholdProfile>("/config/profiles", {
      thresholds,
      change_reason: reason,
    }),

  impactPreview: (profileId: string, current: Record<string, number>, proposed: Record<string, number>) =>
    api.post<{
      current_auto_rate: number; projected_auto_rate: number;
      current_human_rate: number; projected_human_rate: number;
      delta_auto: number; delta_human: number; sample_count: number;
    }>(`/config/profiles/${profileId}/impact-preview`, { current, proposed }),

  getCalibrations: async () => {
    const resp = await api.get<{ data: CalibrationRecord[] }>("/calibrations");
    return { items: resp.data };
  },

  approveCalibration: (id: string) =>
    api.post<void>(`/calibrations/${id}/approve`),

  rejectCalibration: (id: string, reason: string) =>
    api.post<void>(`/calibrations/${id}/reject`, { reason }),

  getPipelineConcurrency: () =>
    api.get<{ rules: Array<{ min_pages: number; concurrency: number; provider_name?: string }> }>("/system/pipeline-concurrency"),

  setPipelineConcurrency: (rules: Array<{ min_pages: number; concurrency: number; provider_name?: string }>) =>
    api.put<{ rules: Array<{ min_pages: number; concurrency: number; provider_name?: string }> }>("/system/pipeline-concurrency", { rules }),

  // Legacy per-provider config (backward compat)
  getLLMProviderConfigs: () =>
    api.get<{ configs: Record<string, LLMProviderConfig> }>("/system/llm-provider-configs"),

  setLLMProviderConfig: (provider: string, config: Partial<LLMProviderConfig>) =>
    api.put<{ provider: string; config: LLMProviderConfig }>(`/system/llm-provider-configs/${provider}`, config),

  // New multi-source priority providers
  getLLMProviders: () =>
    api.get<{ providers: LLMProviderEntry[] }>("/system/llm-providers"),

  reorderLLMProviders: (orderedNames: string[]) =>
    api.put<{ providers: LLMProviderEntry[] }>("/system/llm-providers/reorder", { ordered_names: orderedNames }),

  toggleLLMProvider: (name: string, enabled: boolean) =>
    api.put<{ provider: LLMProviderEntry }>(`/system/llm-providers/${name}/toggle`, { enabled }),

  updateLLMProvider: (name: string, updates: Partial<Pick<LLMProviderEntry, "timeout_seconds" | "vlm_timeout_seconds" | "max_retries" | "qpm_limit" | "tpm_limit">>) =>
    api.put<{ provider: LLMProviderEntry }>(`/system/llm-providers/${name}`, updates),

  // LLM Accounts
  getLLMAccounts: () =>
    api.get<{ accounts: LLMAccount[] }>("/system/llm-accounts"),

  createLLMAccount: (data: { name: string; provider_type: string; api_base: string; api_key: string }) =>
    api.post<{ account: LLMAccount }>("/system/llm-accounts", data),

  deleteLLMAccount: (id: number) =>
    api.delete<void>(`/system/llm-accounts/${id}`),
};
