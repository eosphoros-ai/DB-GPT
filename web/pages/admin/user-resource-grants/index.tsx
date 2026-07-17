import { App, Checkbox, Empty, Select, Spin, Tabs, Tag, Tooltip } from 'antd';
import { useCallback, useEffect, useMemo, useState } from 'react';

import {
  getAvailableResources,
  getUserAccountGrants,
  getUserResourceGrants,
  grantUserResource,
  listAccountSets,
  listAdminResources,
  listAdminUsers,
  revokeUserResourceGrant,
} from '@/client/api/admin';
import AdminLayout from '@/new-components/admin/AdminLayout';
import {
  AdminPageHeader,
  RESOURCE_LABELS,
  getAdminErrorMessage,
  requireAdminData,
} from '@/new-components/admin/AdminPage';
import ConfirmModal from '@/new-components/admin/ConfirmModal';
import {
  AccountSet,
  AdminResource,
  AdminResourceType,
  AdminUser,
  UserAccountGrant,
  UserResourceGrant,
} from '@/types/admin';

const RESOURCE_TYPES: AdminResourceType[] = ['DATASOURCE', 'KNOWLEDGE_BASE', 'AGENT'];

export default function UserResourceGrantsPage() {
  const { message } = App.useApp();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [accountSets, setAccountSets] = useState<AccountSet[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string>();
  const [accountGrants, setAccountGrants] = useState<UserAccountGrant[]>([]);
  const [resourceGrants, setResourceGrants] = useState<UserResourceGrant[]>([]);
  const [resources, setResources] = useState<AdminResource[]>([]);
  const [available, setAvailable] = useState<AdminResource[]>([]);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [revokeTarget, setRevokeTarget] = useState<UserResourceGrant | null>(null);

  useEffect(() => {
    setLoading(true);
    void Promise.all([
      listAdminUsers({ page_size: 100, role: 'query_user', is_active: true }),
      listAccountSets({ page_size: 100 }),
      ...RESOURCE_TYPES.map(resourceType => listAdminResources({ page_size: 100, resource_type: resourceType })),
    ])
      .then(([userResult, accountResult, ...resourceResults]) => {
        setUsers(requireAdminData(userResult).items);
        setAccountSets(requireAdminData(accountResult).items);
        setResources(resourceResults.flatMap(result => requireAdminData(result).items));
      })
      .catch(error => message.error(getAdminErrorMessage(error, '资源授权基础数据加载失败')))
      .finally(() => setLoading(false));
  }, [message]);

  const loadDetails = useCallback(async () => {
    if (!selectedUserId) {
      setAccountGrants([]);
      setResourceGrants([]);
      setAvailable([]);
      return;
    }
    setDetailLoading(true);
    try {
      const [accountResult, grantResult, availableResult] = await Promise.all([
        getUserAccountGrants(selectedUserId, { page_size: 100, is_active: true }),
        getUserResourceGrants(selectedUserId, { page_size: 100, is_active: true }),
        getAvailableResources(selectedUserId),
      ]);
      setAccountGrants(requireAdminData(accountResult).items);
      setResourceGrants(requireAdminData(grantResult).items);
      setAvailable(requireAdminData(availableResult));
    } catch (error) {
      message.error(getAdminErrorMessage(error, '用户资源授权加载失败'));
    } finally {
      setDetailLoading(false);
    }
  }, [message, selectedUserId]);

  useEffect(() => {
    void loadDetails();
  }, [loadDetails]);

  const activeGrantMap = useMemo(
    () => new Map(resourceGrants.map(grant => [`${grant.resource_type}:${grant.resource_id}`, grant])),
    [resourceGrants],
  );
  const availableKeys = useMemo(
    () => new Set(available.map(resource => `${resource.resource_type}:${resource.resource_id}`)),
    [available],
  );
  const accountSetIds = useMemo(() => new Set(accountGrants.map(grant => grant.account_set_id)), [accountGrants]);
  const accountSetMap = useMemo(
    () => new Map(accountSets.map(item => [item.account_set_id, item.name])),
    [accountSets],
  );

  const changeGrant = async (resource: AdminResource, checked: boolean) => {
    if (!selectedUserId) return;
    const key = `${resource.resource_type}:${resource.resource_id}`;
    if (!checked) {
      const grant = activeGrantMap.get(key);
      if (grant) setRevokeTarget(grant);
      return;
    }
    setDetailLoading(true);
    try {
      requireAdminData(await grantUserResource(selectedUserId, resource.resource_type, resource.resource_id));
      message.success(`${RESOURCE_LABELS[resource.resource_type]}授权已授予`);
      void loadDetails();
    } catch (error) {
      message.error(getAdminErrorMessage(error));
      setDetailLoading(false);
    }
  };

  const revoke = async (reason?: string) => {
    if (!selectedUserId || !revokeTarget) return;
    requireAdminData(await revokeUserResourceGrant(selectedUserId, revokeTarget.grant_id, reason || 'ADMIN_REVOKE'));
    message.success('资源授权已撤销');
    setRevokeTarget(null);
    void loadDetails();
  };

  const renderResourceList = (resourceType: AdminResourceType) => {
    const visible = resources.filter(
      resource =>
        resource.resource_type === resourceType &&
        resource.account_set_id &&
        accountSetIds.has(resource.account_set_id),
    );
    if (visible.length === 0) return <Empty description='当前用户的账套范围内暂无资源' />;
    return (
      <div className='grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3'>
        {visible.map(resource => {
          const key = `${resource.resource_type}:${resource.resource_id}`;
          const checked = activeGrantMap.has(key);
          const dependencyBlocked = resourceType === 'AGENT' && !checked && !availableKeys.has(key);
          const checkbox = (
            <Checkbox
              checked={checked}
              disabled={dependencyBlocked}
              onChange={event => void changeGrant(resource, event.target.checked)}
            >
              <span className='inline-block max-w-56 truncate align-bottom'>{resource.name}</span>
            </Checkbox>
          );
          return (
            <div className='min-h-16 rounded border border-solid border-gray-200 px-4 py-3' key={key}>
              {dependencyBlocked ? (
                <Tooltip title='依赖资源未完成授权，或依赖资源与智能体不在同一账套'>{checkbox}</Tooltip>
              ) : (
                checkbox
              )}
              <div className='ml-6 mt-1 truncate text-xs text-gray-400'>
                {accountSetMap.get(resource.account_set_id || '') || resource.account_set_id}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <AdminLayout>
      <AdminPageHeader
        title='查询用户资源授权'
        description='资源授权必须位于用户已授权账套内，智能体同时校验受保护依赖。'
      />
      {loading ? (
        <div className='py-20 text-center'>
          <Spin />
        </div>
      ) : (
        <>
          <div className='mb-4 max-w-xl'>
            <label className='mb-2 block text-sm font-medium text-gray-700'>查询用户</label>
            <Select
              showSearch
              className='w-full'
              optionFilterProp='label'
              placeholder='选择查询用户'
              value={selectedUserId}
              options={users.map(user => ({ value: user.user_id, label: `${user.display_name} (${user.login_name})` }))}
              onChange={setSelectedUserId}
            />
          </div>
          {!selectedUserId ? (
            <Empty description='请先选择查询用户' />
          ) : detailLoading ? (
            <div className='py-16 text-center'>
              <Spin />
            </div>
          ) : (
            <>
              <div className='mb-4 flex flex-wrap items-center gap-2 text-sm text-gray-500'>
                已授权账套：
                {accountGrants.length ? (
                  accountGrants.map(grant => (
                    <Tag key={grant.grant_id}>{accountSetMap.get(grant.account_set_id) || grant.account_set_id}</Tag>
                  ))
                ) : (
                  <span>暂无</span>
                )}
              </div>
              <Tabs
                items={RESOURCE_TYPES.map(resourceType => ({
                  key: resourceType,
                  label: RESOURCE_LABELS[resourceType],
                  children: renderResourceList(resourceType),
                }))}
              />
            </>
          )}
        </>
      )}
      <ConfirmModal
        open={!!revokeTarget}
        title='确认撤销资源授权'
        description='撤销依赖资源时，相关智能体授权也可能被自动撤销。'
        impact={
          revokeTarget ? `${RESOURCE_LABELS[revokeTarget.resource_type]} ID：${revokeTarget.resource_id}` : undefined
        }
        requireReason
        onCancel={() => setRevokeTarget(null)}
        onConfirm={revoke}
      />
    </AdminLayout>
  );
}
