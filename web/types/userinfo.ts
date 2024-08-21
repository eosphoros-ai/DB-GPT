export type Role = 'normal' | 'admin';
export type PostUserAddParams = {
  user_channel: string;
  user_no: string;
  avatar_url?: string;
  role?: Role;
  nick_name?: string;
  email?: string;
  user_id?: string;
};

export interface UserInfoResponse extends PostUserAddParams {}
