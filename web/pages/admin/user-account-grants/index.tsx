import { App, Checkbox, Empty, Select, Spin, Tag } from 'antd';
import { useCallback, useEffect, useMemo, useState } from 'react';

import {
  getUserAccountGrantImpact,
  getUserAccountGrants,
  grantUserAccount,
  listAccountSets,
  listAdminUsers,
  revokeUserAccountGrant,
} from '@/client/api/admin';
import AdminLayout from '@/new-components/admin/AdminLayout';
import { AdminPageHeader, ROLE_LABELS, getAdminErrorMessage, requireAdminData } from '@/new-components/admin/AdminPage';
import ConfirmModal from '@/new-components/admin/ConfirmModal';
import { AccountSet, AdminUser, RevokeImpact, UserAccountGrant } from '@/types/admin';

export default function UserAccountGrantsPage() {
  const { message } = App.useApp();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [accountSets, setAccountSets] = useState<AccountSet[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string>();
  const [grants, setGrants] = useState<UserAccountGrant[]>([]);
  const [loading, setLoading] = useState(true);
  const [grantLoading, setGrantLoading] = useState(false);
  const [revokeTarget, setRevokeTarget] = useState<UserAccountGrant | null>(null);
  const [revokeImpact, setRevokeImpact] = useState<RevokeImpact | null>(null);

  useEffect(() => {
    setLoading(true);
    void Promise.all([listAdminUsers({ page_size: 100 }), listAccountSets({ page_size: 100 })])
      .then(([userResult, accountResult]) => {
        setUsers(requireAdminData(userResult).items.filter(user => user.role !== 'system_admin'));
        setAccountSets(requireAdminData(accountResult).items);
      })
      .catch(error => message.error(getAdminErrorMessage(error, '授权基础数据加载失败')))
      .finally(() => setLoading(false));
  }, [message]);

  const loadGrants = useCallback(async () => {
    if (!selectedUserId) {
      setGrants([]);
      return;
    }
    setGrantLoading(true);
    try {
      setGrants(
        requireAdminData(await getUserAccountGrants(selectedUserId, { page_size: 100, is_active: true })).items,
      );
    } catch (error) {
      message.error(getAdminErrorMessage(error, '用户账套授权加载失败'));
    } finally {
      setGrantLoading(false);
    }
  }, [message, selectedUserId]);

  useEffect(() => {
    void loadGrants();
  }, [loadGrants]);

  const activeGrantByAccount = useMemo(
    () => new Map(grants.filter(grant => grant.is_active).map(grant => [grant.account_set_id, grant])),
    [grants],
  );

  const handleChange = async (accountSetId: string, checked: boolean) => {
    if (!selectedUserId) return;
    if (checked) {
      setGrantLoading(true);
      try {
        requireAdminData(await grantUserAccount(selectedUserId, accountSetId));
        message.success('账套授权已授予');
        void loadGrants();
      } catch (error) {
        message.error(getAdminErrorMessage(error));
        setGrantLoading(false);
      }
      return;
    }
    const grant = activeGrantByAccount.get(accountSetId);
    if (!grant) return;
    try {
      setRevokeImpact(requireAdminData(await getUserAccountGrantImpact(selectedUserId, grant.grant_id)));
      setRevokeTarget(grant);
    } catch (error) {
      message.error(getAdminErrorMessage(error, '影响范围加载失败'));
    }
  };

  const revoke = async (reason?: string) => {
    if (!selectedUserId || !revokeTarget || !revokeImpact) return;
    requireAdminData(
      await revokeUserAccountGrant(selectedUserId, revokeTarget.grant_id, reason || '', revokeImpact.impact_token),
    );
    message.success('账套授权已撤销');
    setRevokeTarget(null);
    setRevokeImpact(null);
    void loadGrants();
  };

  const selectedUser = users.find(user => user.user_id === selectedUserId);

  return (
    <AdminLayout>
      <AdminPageHeader title='用户账套授权' description='为运营管理员和查询用户分配可访问的账套范围。' />
      {loading ? (
        <div className='py-20 text-center'>
          <Spin />
        </div>
      ) : (
        <div className='grid min-h-[480px] grid-cols-1 border-0 border-t border-solid border-gray-200 lg:grid-cols-[320px_1fr]'>
          <section className='border-0 border-b border-solid border-gray-200 py-5 lg:border-b-0 lg:border-r lg:pr-6'>
            <label className='mb-2 block text-sm font-medium text-gray-700'>选择用户</label>
            <Select
              showSearch
              className='w-full'
              optionFilterProp='label'
              placeholder='按名称或登录名搜索'
              value={selectedUserId}
              options={users.map(user => ({ value: user.user_id, label: `${user.display_name} (${user.login_name})` }))}
              onChange={setSelectedUserId}
            />
            {selectedUser && (
              <div className='mt-4 text-sm text-gray-500'>
                当前角色：<Tag>{ROLE_LABELS[selectedUser.role]}</Tag>
              </div>
            )}
          </section>
          <section className='py-5 lg:pl-6'>
            {!selectedUserId ? (
              <Empty description='请先选择用户' />
            ) : grantLoading ? (
              <div className='py-16 text-center'>
                <Spin />
              </div>
            ) : accountSets.length === 0 ? (
              <Empty description='暂无账套' />
            ) : (
              <div className='grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3'>
                {accountSets.map(accountSet => (
                  <label
                    key={accountSet.account_set_id}
                    className='flex min-h-14 items-center gap-3 rounded border border-solid border-gray-200 px-4 py-3'
                  >
                    <Checkbox
                      checked={activeGrantByAccount.has(accountSet.account_set_id)}
                      disabled={!accountSet.is_active && !activeGrantByAccount.has(accountSet.account_set_id)}
                      onChange={event => void handleChange(accountSet.account_set_id, event.target.checked)}
                    />
                    <span className='min-w-0'>
                      <span className='block truncate text-sm text-gray-900'>{accountSet.name}</span>
                      {!accountSet.is_active && <span className='text-xs text-gray-400'>已停用</span>}
                    </span>
                  </label>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
      <ConfirmModal
        open={!!revokeTarget}
        title='确认撤销账套授权'
        description='撤销后，该用户不能再访问该账套及其受保护资源。'
        impact={revokeImpact ? `将同时撤销 ${revokeImpact.affected_resource_grants} 个资源授权。` : undefined}
        impactItems={revokeImpact?.affected_grants_detail.map(item => ({
          label: String(item.resource_type || '资源'),
          value: String(item.resource_name || item.resource_id || '-'),
        }))}
        requireReason
        onCancel={() => {
          setRevokeTarget(null);
          setRevokeImpact(null);
        }}
        onConfirm={revoke}
      />
    </AdminLayout>
  );
}
