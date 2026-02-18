import api from "./client";

export interface LoginResponse {
  user_id: string;
  username: string;
  display_name: string;
  role: string;
  merchant_id?: string;
  token: string;
}

export interface RegisterResponse extends LoginResponse {}

export interface UserInfo {
  user_id: string;
  username: string;
  display_name: string;
  role: string;
  is_active: boolean;
  merchant_id: string | null;
  specialties: string[] | null;
  created_at: string | null;
  last_login_at: string | null;
}

export const authApi = {
  login: (username: string, password: string) =>
    api.post<LoginResponse>("/auth/login", { username, password }),

  register: (data: {
    username: string;
    password: string;
    display_name?: string;
    role: "uploader" | "annotator";
    merchant_id?: string;
    specialties?: string[];
  }) => api.post<RegisterResponse>("/auth/register", data),

  me: () => api.get<{
    user_id: string;
    username: string;
    display_name: string;
    role: string;
    merchant_id: string | null;
    specialties: string[] | null;
    is_active: boolean;
    created_at: string | null;
    last_login_at: string | null;
  }>("/auth/me"),

  updateProfile: (data: {
    display_name?: string;
    merchant_id?: string;
    specialties?: string[];
  }) => api.patch<{ user_id: string; username: string; display_name: string; role: string; merchant_id: string | null; specialties: string[] | null }>("/auth/me", data),

  changePassword: (old_password: string, new_password: string) =>
    api.post<{ ok: boolean; message: string }>("/auth/me/change-password", { old_password, new_password }),

  // Admin APIs
  listUsers: () =>
    api.get<{ data: UserInfo[] }>("/auth/users"),

  createUser: (data: {
    username: string;
    password: string;
    display_name?: string;
    role: "uploader" | "annotator" | "admin";
    merchant_id?: string;
    specialties?: string[];
  }) => api.post<{ user_id: string; username: string; role: string; display_name: string }>("/auth/users", data),

  toggleUserStatus: (userId: string, is_active: boolean) =>
    api.patch<{ ok: boolean; user_id: string; is_active: boolean }>(`/auth/users/${userId}/status`, { is_active }),

  adminUpdateUser: (userId: string, data: {
    display_name?: string;
    role?: string;
    merchant_id?: string;
    specialties?: string[];
    reset_password?: string;
  }) => api.patch<{ user_id: string; username: string; display_name: string; role: string; is_active: boolean; merchant_id: string | null }>(`/auth/users/${userId}`, data),
};
