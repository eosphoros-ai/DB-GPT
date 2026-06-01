import { Role, UserInfoResponse } from '@/types/userinfo';

interface Props {
  role: Role;
}

/**
 * 查询管理员列表（stub: no backend endpoint in this deployment).
 */
export const queryAdminList = (_data: Props): Promise<UserInfoResponse[]> => {
  return Promise.resolve([]);
};
