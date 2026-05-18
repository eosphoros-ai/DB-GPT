export type Role = 'normal' | 'admin';

export interface UserInfo {
  id: number;
  username: string;
  user_group_id: number | null;
  user_group_name: string | null;
  user_role: 'super_admin' | 'normal';
  phone: string | null;
  email: string | null;
  real_name: string | null;
  avatar_url: string | null;
  gmt_created: string;
  gmt_modified: string;
}

export interface LoginResponse {
  token: string;
  user_id: number;
  username: string;
  user_role: 'super_admin' | 'normal';
  user_group_id: number | null;
  user_group_name: string | null;
  real_name: string | null;
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

export type PostUserAddParams = {
  user_channel: string;
  user_no: string;
  avatar_url?: string;
  role?: Role;
  nick_name?: string;
  email?: string;
  user_id?: string;
};

export type MenuKey =
  | 'explore'
  | 'skills'
  | 'datasources'
  | 'knowledge'
  | 'app_management'
  | 'model_manage'
  | 'awel_workflow'
  | 'prompts'
  | 'models_evaluation'
  | 'user_management';

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
export interface UserInfoResponse extends PostUserAddParams {}
