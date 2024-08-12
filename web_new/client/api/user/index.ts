import { Role, UserInfoResponse } from '@/types/userinfo';
import { GET } from '../index';

interface Props {
  role: Role;
}

/**
 * 查询管理员列表
 */
export const queryAdminList = (data: Props) => {
  return GET<Props, UserInfoResponse[]>(`/api/v1/users`, data);
};
