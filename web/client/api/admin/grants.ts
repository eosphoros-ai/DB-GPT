import {
  AdminResource,
  AdminResourceType,
  AdminResult,
  GrantListParams,
  Page,
  ResourceGrantListParams,
  RevokeImpact,
  UserAccountGrant,
  UserResourceGrant,
} from '@/types/admin';
import api from '@/utils/ctx-axios';

const userPath = (userId: string) => `/api/v1/admin/users/${encodeURIComponent(userId)}`;

export const getUserAccountGrants = (userId: string, params: GrantListParams = {}) =>
  api.get<unknown, AdminResult<Page<UserAccountGrant>>>(`${userPath(userId)}/account-grants`, { params });

export const grantUserAccount = (userId: string, accountSetId: string) =>
  api.post<unknown, AdminResult<UserAccountGrant>>(`${userPath(userId)}/account-grants`, {
    account_set_id: accountSetId,
  });

export const getUserAccountGrantImpact = (userId: string, grantId: string) =>
  api.get<unknown, AdminResult<RevokeImpact>>(
    `${userPath(userId)}/account-grants/${encodeURIComponent(grantId)}/impact`,
  );

export const revokeUserAccountGrant = (userId: string, grantId: string, reason: string, impactToken: string) =>
  api.delete<unknown, AdminResult<RevokeImpact>>(`${userPath(userId)}/account-grants/${encodeURIComponent(grantId)}`, {
    data: { reason, impact_token: impactToken, confirm_impact: true },
  });

export const getUserResourceGrants = (userId: string, params: ResourceGrantListParams = {}) =>
  api.get<unknown, AdminResult<Page<UserResourceGrant>>>(`${userPath(userId)}/resource-grants`, { params });

export const getAvailableResources = (userId: string) =>
  api.get<unknown, AdminResult<AdminResource[]>>(`${userPath(userId)}/resource-grants/available`);

export const grantUserResource = (userId: string, resourceType: AdminResourceType, resourceId: string) =>
  api.post<unknown, AdminResult<UserResourceGrant>>(`${userPath(userId)}/resource-grants`, {
    resource_type: resourceType,
    resource_id: resourceId,
  });

export const revokeUserResourceGrant = (userId: string, grantId: string, reason: string) =>
  api.delete<unknown, AdminResult<UserResourceGrant>>(
    `${userPath(userId)}/resource-grants/${encodeURIComponent(grantId)}`,
    { data: { reason } },
  );
