import {
  getDashboardPermissions,
  listDashboardAudit,
  listDashboardMembers,
  removeDashboardMember,
  upsertDashboardMember,
} from '@/client/api';
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
  owner: '所有者',
  editor: '编辑者',
  viewer: '查看者',
};

const actionLabels: Record<DashboardAction, string> = {
  view: '查看',
  edit: '编辑',
  query: '刷新数据',
  publish: '发布与分享',
  manage_access: '管理成员',
  manage_schedule: '管理定时任务',
};

const auditLabels: Record<string, string> = {
  'dashboard.created': '创建看板',
  'dashboard.updated': '保存看板',
  'dashboard.archived': '归档看板',
  'dashboard.restored': '恢复看板',
  'dashboard.refreshed': '刷新数据',
  'dashboard.published': '发布看板',
  'dashboard.revision_restored': '恢复历史版本',
  'member.upserted': '更新成员权限',
  'member.removed': '移除成员',
  'publication.rotated': '轮换分享链接',
  'publication.revoked': '撤销分享链接',
  'schedule.created': '创建定时任务',
  'schedule.updated': '更新定时任务',
  'schedule.deleted': '删除定时任务',
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
  return error instanceof Error ? error.message : '管理信息加载失败';
};

export default function DashboardAccessPanel({ dashboardId, open, onClose }: DashboardAccessPanelProps) {
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
      message.warning('请输入成员账号');
      return;
    }
    setSaving(true);
    try {
      await upsertDashboardMember(dashboardId, cleanPrincipal, role);
      setPrincipalId('');
      message.success('成员权限已保存');
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
      message.success('成员角色已更新');
      await load();
    } catch (reason) {
      message.error(describeError(reason));
    }
  };

  const removeMember = async (member: DashboardMemberRecord) => {
    try {
      await removeDashboardMember(dashboardId, member.principal_id);
      message.success('成员已移除');
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
          权限与审计
        </span>
      }
      open={open}
      onClose={onClose}
      extra={<Button aria-label='刷新权限信息' icon={<ReloadOutlined />} onClick={() => void load()} />}
    >
      {loading ? (
        <Skeleton active paragraph={{ rows: 8 }} />
      ) : error ? (
        <Alert type='error' showIcon message='无法读取管理信息' description={error} />
      ) : permission ? (
        <Tabs
          items={[
            {
              key: 'members',
              label: '成员权限',
              children: (
                <div className='space-y-5'>
                  <div className='rounded-xl border border-blue-100 bg-blue-50/70 p-4 dark:border-blue-900 dark:bg-blue-950/20'>
                    <Descriptions size='small' column={1} colon={false}>
                      <Descriptions.Item label='当前账号'>{permission.actor_id}</Descriptions.Item>
                      <Descriptions.Item label='当前角色'>
                        <Tag color={roleColor[permission.role]}>{roleLabels[permission.role]}</Tag>
                      </Descriptions.Item>
                      <Descriptions.Item label='可执行操作'>
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
                      <div className='mb-2 font-medium'>添加或更新成员</div>
                      <Space.Compact block>
                        <Input
                          aria-label='成员账号'
                          placeholder='输入 DB-GPT 用户账号'
                          value={principalId}
                          onChange={event => setPrincipalId(event.target.value)}
                          onPressEnter={() => void addMember()}
                        />
                        <select
                          aria-label='成员角色'
                          className='w-32 border border-gray-300 bg-white px-3 text-sm outline-none focus:border-blue-500 dark:border-gray-700 dark:bg-gray-900'
                          value={role}
                          onChange={event => setRole(event.target.value as Exclude<DashboardRole, 'owner'>)}
                        >
                          <option value='viewer'>查看者</option>
                          <option value='editor'>编辑者</option>
                        </select>
                        <Button
                          type='primary'
                          icon={<UserAddOutlined />}
                          loading={saving}
                          onClick={() => void addMember()}
                        >
                          保存成员
                        </Button>
                      </Space.Compact>
                      <p className='mt-2 text-xs text-gray-400'>
                        查看者只能浏览；编辑者可以编辑并刷新；发布、成员管理和定时任务仅所有者可用。
                      </p>
                    </div>
                  ) : (
                    <Alert type='info' showIcon message='你可以访问此看板，但没有成员管理权限。' />
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
                              由 {member.created_by} 添加 · {new Date(member.updated_at).toLocaleString()}
                            </div>
                          </div>
                          {member.role === 'owner' ? (
                            <Tag color={roleColor.owner}>{roleLabels.owner}</Tag>
                          ) : (
                            <select
                              aria-label={`${member.principal_id}角色`}
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
                              title={`移除成员 ${member.principal_id}？`}
                              description='移除后，该成员将不能再访问这个看板。'
                              okText='移除'
                              cancelText='取消'
                              onConfirm={() => void removeMember(member)}
                            >
                              <Button
                                danger
                                type='text'
                                aria-label={`移除成员 ${member.principal_id}`}
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
              label: `操作记录${audit.length ? ` (${audit.length})` : ''}`,
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
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description='暂无操作记录' />
              ),
            },
          ]}
        />
      ) : null}
    </Drawer>
  );
}
