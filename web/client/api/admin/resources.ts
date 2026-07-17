import {
  AdminResource,
  AdminResourceListParams,
  AdminResourceType,
  AdminResult,
  Page,
  ResourceImpact,
} from '@/types/admin';
import api from '@/utils/ctx-axios';

const resourcePath = (type: AdminResourceType, id: string) =>
  `/api/v1/admin/resources/${type}/${encodeURIComponent(id)}`;

export const listAdminResources = (params: AdminResourceListParams = {}) =>
  api.get<unknown, AdminResult<Page<AdminResource>>>('/api/v1/admin/resources', { params });

export const getResourceImpact = (type: AdminResourceType, id: string, newAccountSetId: string) =>
  api.get<unknown, AdminResult<ResourceImpact>>(`${resourcePath(type, id)}/impact`, {
    params: { new_account_set_id: newAccountSetId },
  });

export const assignResourceAccountSet = (
  type: AdminResourceType,
  id: string,
  accountSetId: string,
  reason: string,
  impactToken: string,
) =>
  api.patch<unknown, AdminResult<AdminResource>>(`${resourcePath(type, id)}/account-set`, {
    account_set_id: accountSetId,
    reason,
    impact_token: impactToken,
    confirm_impact: true,
  });
