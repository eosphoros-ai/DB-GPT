import {
  getDashboardPermissions,
  listDashboardAudit,
  listDashboardMembers,
  removeDashboardMember,
  upsertDashboardMember,
} from '@/client/api';
import { dashboardText as dt, useDashboardTranslation } from '@/new-components/dashboard/dashboard-i18n';
import {
  DashboardAction,
  DashboardAuditRecord,
  DashboardMemberRecord,
  DashboardPermissionRecord,
  DashboardRole,
} from '@/types/dashboard';
import { DeleteOutlined, ReloadOutlined, SafetyCertificateOutlined, UserAddOutlined } from '@ant-design/icons';
import {
  Alert,
  App,
  Button,
  Descriptions,
  Drawer,
  Empty,
  Input,
  Popconfirm,
  Skeleton,
  Space,
  Tabs,
  Tag,
  Timeline,
} from 'antd';
import axios from 'axios';
import { useCallback, useEffect, useState } from 'react';

interface DashboardAccessPanelProps {
  dashboardId: string;
  open: boolean;
  onClose: () => void;
}

const roleLabels: Record<DashboardRole, string> = {
  get owner() {
    return dt('所有者');
  },
  get editor() {
    return dt('编辑者');
  },
  get viewer() {
    return dt('查看者');
  },
};

const actionLabels: Record<DashboardAction, string> = {
  get view() {
    return dt('查看');
  },
  get edit() {
    return dt('编辑');
  },
  get query() {
    return dt('刷新数据');
  },
  get publish() {
    return dt('发布与分享');
  },
  get manage_access() {
    return dt('管理成员');
  },
  get manage_schedule() {
    return dt('管理定时任务');
  },
};

const auditLabels: Record<string, string> = {
  get 'dashboard.created'() {
    return dt('创建看板');
  },
  get 'dashboard.updated'() {
    return dt('保存看板');
  },
  get 'dashboard.archived'() {
    return dt('归档看板');
  },
  get 'dashboard.restored'() {
    return dt('恢复看板');
  },
  get 'dashboard.refreshed'() {
    return dt('刷新数据');
  },
  get 'dashboard.published'() {
    return dt('发布看板');
  },
  get 'dashboard.revision_restored'() {
    return dt('恢复历史版本');
  },
  get 'member.upserted'() {
    return dt('更新成员权限');
  },
  get 'member.removed'() {
    return dt('移除成员');
  },
  get 'publication.rotated'() {
    return dt('轮换分享链接');
  },
  get 'publication.revoked'() {
    return dt('撤销分享链接');
  },
  get 'schedule.created'() {
    return dt('创建定时任务');
  },
  get 'schedule.updated'() {
    return dt('更新定时任务');
  },
  get 'schedule.deleted'() {
    return dt('删除定时任务');
  },
};

const roleColor: Record<DashboardRole, string> = {
  owner: 'blue',
  editor: 'green',
  viewer: 'default',
};

const describeError = (error: unknown) => {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail || error.response?.data?.err_msg;
    if (typeof detail === 'string') return detail;
  }
  return error instanceof Error ? error.message : dt('管理信息加载失败');
};

export default function DashboardAccessPanel({ dashboardId, open, onClose }: DashboardAccessPanelProps) {
  useDashboardTranslation();
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [permission, setPermission] = useState<DashboardPermissionRecord | null>(null);
  const [members, setMembers] = useState<DashboardMemberRecord[]>([]);
  const [audit, setAudit] = useState<DashboardAuditRecord[]>([]);
  const [principalId, setPrincipalId] = useState('');
  const [role, setRole] = useState<Exclude<DashboardRole, 'owner'>>('viewer');

  const canManage = permission?.actions.includes('manage_access') ?? false;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const permissionResponse = await getDashboardPermissions(dashboardId);
      const nextPermission = permissionResponse.data.data;
      setPermission(nextPermission);
      if (!nextPermission.actions.includes('manage_access')) {
        setMembers([]);
        setAudit([]);
        return;
      }
      const [memberResponse, auditResponse] = await Promise.all([
        listDashboardMembers(dashboardId),
        listDashboardAudit(dashboardId),
      ]);
      setMembers(memberResponse.data.data || []);
      setAudit(auditResponse.data.data || []);
    } catch (reason) {
      setError(describeError(reason));
    } finally {
      setLoading(false);
    }
  }, [dashboardId]);

  useEffect(() => {
    if (!open) return undefined;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load, open]);

  const addMember = async () => {
    const cleanPrincipal = principalId.trim();
    if (!cleanPrincipal) {
      message.warning(dt('请输入成员账号'));
      return;
    }
    setSaving(true);
    try {
      await upsertDashboardMember(dashboardId, cleanPrincipal, role);
      setPrincipalId('');
      message.success(dt('成员权限已保存'));
      await load();
    } catch (reason) {
      message.error(describeError(reason));
    } finally {
      setSaving(false);
    }
  };

  const updateRole = async (member: DashboardMemberRecord, nextRole: Exclude<DashboardRole, 'owner'>) => {
    try {
      await upsertDashboardMember(dashboardId, member.principal_id, nextRole);
      message.success(dt('成员角色已更新'));
      await load();
    } catch (reason) {
      message.error(describeError(reason));
    }
  };

  const removeMember = async (member: DashboardMemberRecord) => {
    try {
      await removeDashboardMember(dashboardId, member.principal_id);
      message.success(dt('成员已移除'));
      await load();
    } catch (reason) {
      message.error(describeError(reason));
    }
  };

  return (
    <Drawer
      width={760}
      title={
        <span className='inline-flex items-center gap-2'>
          <SafetyCertificateOutlined className='text-blue-500' />
          {dt('权限与审计')}
        </span>
      }
      open={open}
      onClose={onClose}
      extra={<Button aria-label={dt('刷新权限信息')} icon={<ReloadOutlined />} onClick={() => void load()} />}
    >
      {loading ? (
        <Skeleton active paragraph={{ rows: 8 }} />
      ) : error ? (
        <Alert type='error' showIcon message={dt('无法读取管理信息')} description={error} />
      ) : permission ? (
        <Tabs
          items={[
            {
              key: 'members',
              label: dt('成员权限'),
              children: (
                <div className='space-y-5'>
                  <div className='rounded-xl border border-blue-100 bg-blue-50/70 p-4 dark:border-blue-900 dark:bg-blue-950/20'>
                    <Descriptions size='small' column={1} colon={false}>
                      <Descriptions.Item label={dt('当前账号')}>{permission.actor_id}</Descriptions.Item>
                      <Descriptions.Item label={dt('当前角色')}>
                        <Tag color={roleColor[permission.role]}>{roleLabels[permission.role]}</Tag>
                      </Descriptions.Item>
                      <Descriptions.Item label={dt('可执行操作')}>
                        <Space size={[4, 6]} wrap>
                          {permission.actions.map(action => (
                            <Tag key={action}>{actionLabels[action]}</Tag>
                          ))}
                        </Space>
                      </Descriptions.Item>
                    </Descriptions>
                  </div>

                  {canManage ? (
                    <div>
                      <div className='mb-2 font-medium'>{dt('添加或更新成员')}</div>
                      <Space.Compact block>
                        <Input
                          aria-label={dt('成员账号')}
                          placeholder={dt('输入 DB-GPT 用户账号')}
                          value={principalId}
                          onChange={event => setPrincipalId(event.target.value)}
                          onPressEnter={() => void addMember()}
                        />
                        <select
                          aria-label={dt('成员角色')}
                          className='w-32 border border-gray-300 bg-white px-3 text-sm outline-none focus:border-blue-500 dark:border-gray-700 dark:bg-gray-900'
                          value={role}
                          onChange={event => setRole(event.target.value as Exclude<DashboardRole, 'owner'>)}
                        >
                          <option value='viewer'>{dt('查看者')}</option>
                          <option value='editor'>{dt('编辑者')}</option>
                        </select>
                        <Button
                          type='primary'
                          icon={<UserAddOutlined />}
                          loading={saving}
                          onClick={() => void addMember()}
                        >
                          {dt('保存成员')}
                        </Button>
                      </Space.Compact>
                      <p className='mt-2 text-xs text-gray-400'>
                        {dt('查看者只能浏览；编辑者可以编辑并刷新；发布、成员管理和定时任务仅所有者可用。')}
                      </p>
                    </div>
                  ) : (
                    <Alert type='info' showIcon message={dt('你可以访问此看板，但没有成员管理权限。')} />
                  )}

                  {canManage ? (
                    <div className='space-y-2'>
                      {members.map(member => (
                        <div
                          key={member.principal_id}
                          className='flex flex-wrap items-center gap-3 rounded-xl border border-gray-100 p-3 dark:border-gray-800'
                        >
                          <div className='min-w-[180px] flex-1'>
                            <div className='font-medium text-gray-800 dark:text-gray-100'>{member.principal_id}</div>
                            <div className='mt-0.5 text-xs text-gray-400'>
                              {dt('由')} {member.created_by} {dt('添加 ·')}{' '}
                              {new Date(member.updated_at).toLocaleString()}
                            </div>
                          </div>
                          {member.role === 'owner' ? (
                            <Tag color={roleColor.owner}>{roleLabels.owner}</Tag>
                          ) : (
                            <select
                              aria-label={dt('{{value0}}角色', { value0: member.principal_id })}
                              value={member.role}
                              className='h-8 w-28 rounded-md border border-gray-300 bg-white px-2 text-sm outline-none focus:border-blue-500 dark:border-gray-700 dark:bg-gray-900'
                              onChange={event =>
                                void updateRole(member, event.target.value as Exclude<DashboardRole, 'owner'>)
                              }
                            >
                              <option value='editor'>{roleLabels.editor}</option>
                              <option value='viewer'>{roleLabels.viewer}</option>
                            </select>
                          )}
                          {member.role === 'owner' ? null : (
                            <Popconfirm
                              title={dt('移除成员 {{value0}}？', { value0: member.principal_id })}
                              description={dt('移除后，该成员将不能再访问这个看板。')}
                              okText={dt('移除')}
                              cancelText={dt('取消')}
                              onConfirm={() => void removeMember(member)}
                            >
                              <Button
                                danger
                                type='text'
                                aria-label={dt('移除成员 {{value0}}', { value0: member.principal_id })}
                                icon={<DeleteOutlined />}
                              />
                            </Popconfirm>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              ),
            },
            {
              key: 'audit',
              label: dt('操作记录{{value0}}', { value0: audit.length ? ` (${audit.length})` : '' }),
              disabled: !canManage,
              children: audit.length ? (
                <Timeline
                  items={audit.map(item => ({
                    color: item.action.includes('removed') || item.action.includes('revoked') ? 'red' : 'blue',
                    children: (
                      <div className='pb-2'>
                        <div className='flex flex-wrap items-center gap-2'>
                          <span className='font-medium'>{auditLabels[item.action] || item.action}</span>
                          <Tag>{item.actor_id}</Tag>
                          {item.target_id ? <span className='text-xs text-gray-400'>{item.target_id}</span> : null}
                        </div>
                        <div className='mt-1 text-xs text-gray-400'>{new Date(item.created_at).toLocaleString()}</div>
                        {Object.keys(item.details || {}).length ? (
                          <div className='mt-2 rounded bg-gray-50 px-3 py-2 font-mono text-xs text-gray-500 dark:bg-gray-900'>
                            {Object.entries(item.details)
                              .map(([key, value]) => `${key}: ${String(value)}`)
                              .join(' · ')}
                          </div>
                        ) : null}
                      </div>
                    ),
                  }))}
                />
              ) : (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={dt('暂无操作记录')} />
              ),
            },
          ]}
        />
      ) : null}
    </Drawer>
  );
}
