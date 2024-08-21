import { IFlow, UpdateFLowAdminsParams } from '@/types/flow';
import { POST } from '../index';

/**
 * 更新管理员
 */
export const updateFlowAdmins = (data: UpdateFLowAdminsParams) => {
  return POST<UpdateFLowAdminsParams, IFlow>(`/api/v1/serve/awel/flow/admins`, data);
};
