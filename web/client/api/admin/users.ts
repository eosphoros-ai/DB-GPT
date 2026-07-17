import {
  AdminResult,
  AdminRoleInfo,
  AdminUser,
  AdminUserCreate,
  AdminUserListParams,
  AdminUserUpdate,
  Page,
} from '@/types/admin';
import api from '@/utils/ctx-axios';

const USERS_BASE = '/api/v1/admin/users';

export const listAdminUsers = (params: AdminUserListParams = {}) =>
  api.get<unknown, AdminResult<Page<AdminUser>>>(USERS_BASE, { params });

export const getAdminUser = (userId: string) =>
  api.get<unknown, AdminResult<AdminUser>>(`${USERS_BASE}/${encodeURIComponent(userId)}`);

export const createAdminUser = (body: AdminUserCreate) => api.post<unknown, AdminResult<AdminUser>>(USERS_BASE, body);

export const updateAdminUser = (userId: string, body: AdminUserUpdate) =>
  api.patch<unknown, AdminResult<AdminUser>>(`${USERS_BASE}/${encodeURIComponent(userId)}`, body);

export const toggleUserActive = (userId: string, activate: boolean) =>
  api.post<unknown, AdminResult<AdminUser>>(
    `${USERS_BASE}/${encodeURIComponent(userId)}/${activate ? 'activate' : 'deactivate'}`,
    {},
  );

export const setUserPassword = (userId: string, password: string) =>
  api.post<unknown, AdminResult<null>>(`${USERS_BASE}/${encodeURIComponent(userId)}/set-password`, {
    new_password: password,
  });

export const listAdminRoles = () => api.get<unknown, AdminResult<AdminRoleInfo[]>>('/api/v1/admin/roles');
