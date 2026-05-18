import { GET, POST, DELETE, PUT } from '../';

export interface LoginParams {
  username: string;
  password: string;
}

export interface LoginResult {
  token: string;
  user_id: number;
  username: string;
  user_role: string;
  user_group_id: number | null;
  user_group_name: string | null;
  real_name: string | null;
}

export interface UserInfo {
  id: number;
  username: string;
  user_role: string;
  user_group_id: number | null;
  user_group_name: string | null;
  phone: string | null;
  email: string | null;
  real_name: string | null;
  avatar_url: string | null;
  gmt_created: string | null;
  gmt_modified: string | null;
}

export interface UserGroup {
  id: number;
  group_name: string;
  description: string | null;
}

export interface MenuItem {
  menu_key: string;
  menu_name: string;
}

export interface AddUserParams {
  username: string;
  password: string;
  user_group_id: number;
  user_role?: string;
  phone?: string;
  email?: string;
  real_name?: string;
}

export interface UpdateUserParams {
  user_group_id?: number;
  user_role?: string;
  phone?: string;
  email?: string;
  real_name?: string;
}

export const login = (data: LoginParams) => {
  return POST<LoginParams, LoginResult>('/api/v1/auth/login', data);
};

export const getUserList = () => {
  return GET<null, UserInfo[]>('/api/v1/user/list');
};

export const addUser = (data: AddUserParams) => {
  return POST<AddUserParams, UserInfo>('/api/v1/user/add', data);
};

export const deleteUser = (userId: number) => {
  return DELETE<null, boolean>(`/api/v1/user/${userId}`);
};

export const updateUser = (userId: number, data: UpdateUserParams) => {
  return PUT<UpdateUserParams, UserInfo>(`/api/v1/user/${userId}`, data);
};

export const getUserGroups = () => {
  return GET<null, UserGroup[]>('/api/v1/user/groups');
};

export const createUserGroup = (groupName: string, description: string) => {
  return POST<{ group_name: string; description: string }, UserGroup>(
    `/api/v1/user/groups?group_name=${encodeURIComponent(groupName)}&description=${encodeURIComponent(description)}`,
  );
};

export const getUserMenus = () => {
  return GET<null, MenuItem[]>('/api/v1/user/menus');
};

export const getGroupMenus = (groupId: number) => {
  return GET<null, string[]>(`/api/v1/user/group-menus/${groupId}`);
};

export const setGroupMenus = (data: { group_id: number; menu_keys: string[] }) => {
  return POST<{ group_id: number; menu_keys: string[] }, boolean>(
    '/api/v1/user/group-menus',
    data,
  );
};

// Kept for backward compat with chat-context.tsx
export const queryAdminList = (_data: { role: string }) => {
  return GET<null, UserInfo[]>('/api/v1/user/list');
};
