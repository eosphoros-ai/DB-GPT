import api from '@/utils/ctx-axios';

import { AdminLoginResponse, AdminResult, AdminUser } from '@/types/admin';

const ADMIN_AUTH_BASE = '/api/v1/admin/auth';

export const adminLogin = (loginName: string, password: string) =>
  api.post<unknown, AdminResult<AdminLoginResponse>>(`${ADMIN_AUTH_BASE}/login`, {
    login_name: loginName,
    password,
  });

export const adminLogout = () => api.post<unknown, AdminResult<null>>(`${ADMIN_AUTH_BASE}/logout`, {});

export const getAdminCurrentUser = () => api.get<unknown, AdminResult<AdminUser>>(`${ADMIN_AUTH_BASE}/me`);
