import api from "./client";
import type { ThresholdProfile, CalibrationRecord } from "../types/models";

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
};
