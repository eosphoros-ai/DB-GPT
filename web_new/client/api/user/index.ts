import { Role, UserInfoResponse } from '@/types/userinfo';
import { GET } from '../index';

interface Props {
  role: Role;
}

/**
 * 查询管理员列表
 */
export const queryAdminList = (data: Props) => {
  return [{
      nick_name: "dbgpt",
      role: "admin",
      user_id: "001",
      user_no: "001",
      }];
};
