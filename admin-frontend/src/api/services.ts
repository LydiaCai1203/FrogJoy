import client from './client';
import type {
  Token, UserListResponse, UserDetail, UserStats,
  OverviewStats, GrowthPoint, ReadingStatsPoint, ActiveUserItem,
  SystemSettings,
} from './types';

export const authApi = {
  login: (email: string, password: string) =>
    client.post<Token>('/auth/login', { email, password }),
};

export const usersApi = {
  list: (params: { page?: number; page_size?: number; search?: string; sort_by?: string; sort_order?: string }) =>
    client.get<UserListResponse>('/users/', { params }),
  get: (userId: string) =>
    client.get<UserDetail>(`/users/${userId}`),
  update: (userId: string, data: { is_active?: boolean; is_admin?: boolean }) =>
    client.patch(`/users/${userId}`, data),
  stats: (userId: string) =>
    client.get<UserStats>(`/users/${userId}/stats`),
};

export const dashboardApi = {
  overview: () =>
    client.get<OverviewStats>('/dashboard/overview'),
  userGrowth: (days = 30) =>
    client.get<{ data: GrowthPoint[] }>('/dashboard/user-growth', { params: { days } }),
  readingStats: (days = 30) =>
    client.get<{ data: ReadingStatsPoint[] }>('/dashboard/reading-stats', { params: { days } }),
  activeUsers: (days = 7, limit = 20) =>
    client.get<{ data: ActiveUserItem[] }>('/dashboard/active-users', { params: { days, limit } }),
};

export const settingsApi = {
  get: () =>
    client.get<SystemSettings>('/settings/'),
  update: (data: Partial<SystemSettings>) =>
    client.put<SystemSettings>('/settings/', data),
};
