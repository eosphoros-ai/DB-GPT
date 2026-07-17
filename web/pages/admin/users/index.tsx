import { PlusOutlined } from '@ant-design/icons';
import { App, Badge, Button, Drawer, Form, Input, Modal, Popconfirm, Select, Space, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useCallback, useEffect, useState } from 'react';

import {
  createAdminUser,
  listAdminUsers,
  setUserPassword,
  toggleUserActive,
  updateAdminUser,
} from '@/client/api/admin';
import AdminLayout from '@/new-components/admin/AdminLayout';
import {
  AdminPageHeader,
  ROLE_COLORS,
  ROLE_LABELS,
  formatAdminDate,
  getAdminErrorMessage,
  requireAdminData,
} from '@/new-components/admin/AdminPage';
import ConfirmModal from '@/new-components/admin/ConfirmModal';
import { AdminRole, AdminUser } from '@/types/admin';

interface UserFormValues {
  login_name: string;
  display_name: string;
  role: AdminRole;
  initial_password?: string;
}

const PAGE_SIZE = 20;

export default function AdminUsersPage() {
  const { message } = App.useApp();
  const [form] = Form.useForm<UserFormValues>();
  const [passwordForm] = Form.useForm<{ password: string }>();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<AdminRole | undefined>();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [saving, setSaving] = useState(false);
  const [pendingRoleValues, setPendingRoleValues] = useState<UserFormValues | null>(null);
  const [passwordUser, setPasswordUser] = useState<AdminUser | null>(null);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const result = requireAdminData(
        await listAdminUsers({ page, page_size: PAGE_SIZE, login_name_like: search || undefined, role: roleFilter }),
      );
      setUsers(result.items);
      setTotal(result.total);
    } catch (error) {
      message.error(getAdminErrorMessage(error, '用户列表加载失败'));
    } finally {
      setLoading(false);
    }
  }, [message, page, roleFilter, search]);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  const openCreate = () => {
    setEditingUser(null);
    form.resetFields();
    form.setFieldsValue({ role: 'query_user' });
    setDrawerOpen(true);
  };

  const openEdit = (user: AdminUser) => {
    setEditingUser(user);
    form.setFieldsValue({ login_name: user.login_name, display_name: user.display_name, role: user.role });
    setDrawerOpen(true);
  };

  const saveUser = async (values: UserFormValues, reason?: string) => {
    setSaving(true);
    try {
      if (editingUser) {
        const roleChanged = values.role !== editingUser.role;
        requireAdminData(
          await updateAdminUser(editingUser.user_id, {
            display_name: values.display_name,
            ...(roleChanged ? { role: values.role, change_reason: reason, confirm_role_change: true } : {}),
          }),
        );
      } else {
        requireAdminData(
          await createAdminUser({
            login_name: values.login_name,
            display_name: values.display_name,
            role: values.role as Exclude<AdminRole, 'system_admin'>,
            initial_password: values.initial_password,
          }),
        );
      }
      message.success(editingUser ? '用户已更新' : '用户已创建');
      setDrawerOpen(false);
      setPendingRoleValues(null);
      void loadUsers();
    } catch (error) {
      message.error(getAdminErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const handleSubmit = (values: UserFormValues) => {
    if (editingUser && values.role !== editingUser.role) {
      setPendingRoleValues(values);
      return;
    }
    void saveUser(values);
  };

  const handleToggle = async (user: AdminUser) => {
    try {
      requireAdminData(await toggleUserActive(user.user_id, !user.is_active));
      message.success(user.is_active ? '用户已禁用' : '用户已启用');
      void loadUsers();
    } catch (error) {
      message.error(getAdminErrorMessage(error));
    }
  };

  const handlePasswordReset = async () => {
    if (!passwordUser) return;
    try {
      const values = await passwordForm.validateFields();
      const result = await setUserPassword(passwordUser.user_id, values.password);
      if (!result.success) throw new Error(result.err_msg || '密码设置失败');
      message.success('密码已重置，既有会话已撤销');
      setPasswordUser(null);
      passwordForm.resetFields();
    } catch (error) {
      if (!(error as { errorFields?: unknown }).errorFields) message.error(getAdminErrorMessage(error));
    }
  };

  const columns: ColumnsType<AdminUser> = [
    { title: '登录名', dataIndex: 'login_name', width: 160 },
    { title: '显示名', dataIndex: 'display_name', width: 180 },
    {
      title: '角色',
      dataIndex: 'role',
      width: 140,
      render: (role: AdminRole) => <Tag color={ROLE_COLORS[role]}>{ROLE_LABELS[role]}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      width: 100,
      render: (active: boolean) => <Badge status={active ? 'success' : 'default'} text={active ? '启用' : '禁用'} />,
    },
    { title: '创建时间', dataIndex: 'gmt_created', width: 190, render: formatAdminDate },
    {
      title: '操作',
      fixed: 'right',
      width: 220,
      render: (_, user) => (
        <Space size={4}>
          <Button type='link' onClick={() => openEdit(user)}>
            编辑
          </Button>
          <Button type='link' onClick={() => setPasswordUser(user)}>
            重置密码
          </Button>
          <Popconfirm
            title={`确认${user.is_active ? '禁用' : '启用'}该用户？`}
            description={user.is_active ? '禁用后，该用户的当前会话将失效。' : undefined}
            onConfirm={() => void handleToggle(user)}
          >
            <Button danger={user.is_active} type='link'>
              {user.is_active ? '禁用' : '启用'}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <AdminLayout>
      <AdminPageHeader
        title='用户管理'
        description='创建独立 DB-GPT 用户，维护固定角色和账号状态。'
        extra={
          <Button icon={<PlusOutlined />} type='primary' onClick={openCreate}>
            新建用户
          </Button>
        }
      />
      <div className='mb-4 flex flex-wrap gap-3'>
        <Input.Search
          allowClear
          className='w-full sm:w-72'
          placeholder='按登录名搜索'
          onSearch={value => {
            setPage(1);
            setSearch(value.trim());
          }}
        />
        <Select
          allowClear
          className='w-full sm:w-48'
          placeholder='全部角色'
          value={roleFilter}
          options={Object.entries(ROLE_LABELS).map(([value, label]) => ({ value, label }))}
          onChange={value => {
            setPage(1);
            setRoleFilter(value);
          }}
        />
      </div>
      <Table
        rowKey='user_id'
        columns={columns}
        dataSource={users}
        loading={loading}
        scroll={{ x: 1050 }}
        pagination={{ current: page, pageSize: PAGE_SIZE, total, showSizeChanger: false, onChange: setPage }}
      />

      <Drawer
        open={drawerOpen}
        title={editingUser ? '编辑用户' : '新建用户'}
        width={440}
        destroyOnHidden
        onClose={() => setDrawerOpen(false)}
        extra={
          <Button type='primary' loading={saving} onClick={() => form.submit()}>
            保存
          </Button>
        }
      >
        <Form form={form} layout='vertical' onFinish={handleSubmit} requiredMark={false}>
          <Form.Item label='登录名' name='login_name' rules={[{ required: true, whitespace: true }]}>
            <Input autoComplete='off' disabled={!!editingUser} maxLength={128} />
          </Form.Item>
          <Form.Item label='显示名' name='display_name' rules={[{ required: true, whitespace: true }]}>
            <Input maxLength={255} />
          </Form.Item>
          <Form.Item label='角色' name='role' rules={[{ required: true }]}>
            <Select
              options={Object.entries(ROLE_LABELS)
                .filter(([role]) => !!editingUser || role !== 'system_admin')
                .map(([value, label]) => ({ value, label }))}
            />
          </Form.Item>
          {!editingUser && (
            <Form.Item label='初始密码' name='initial_password' rules={[{ required: true, min: 8 }]}>
              <Input.Password autoComplete='new-password' maxLength={72} />
            </Form.Item>
          )}
        </Form>
      </Drawer>

      <ConfirmModal
        open={!!pendingRoleValues}
        title='确认变更用户角色'
        description={`角色将从“${editingUser ? ROLE_LABELS[editingUser.role] : ''}”变更为“${pendingRoleValues ? ROLE_LABELS[pendingRoleValues.role] : ''}”。`}
        impact={
          editingUser?.role === 'query_user'
            ? '将撤销该用户当前所有资源授权。'
            : pendingRoleValues?.role === 'system_admin'
              ? '将撤销该用户当前所有账套授权。'
              : '角色能力将在下一次请求时立即生效。'
        }
        requireReason
        onCancel={() => setPendingRoleValues(null)}
        onConfirm={async reason => {
          if (pendingRoleValues) await saveUser(pendingRoleValues, reason);
        }}
      />

      <Modal
        open={!!passwordUser}
        title={`重置密码：${passwordUser?.display_name || ''}`}
        okText='确认重置'
        onCancel={() => {
          setPasswordUser(null);
          passwordForm.resetFields();
        }}
        onOk={() => void handlePasswordReset()}
      >
        <Form form={passwordForm} layout='vertical' requiredMark={false}>
          <Form.Item label='新密码' name='password' rules={[{ required: true, min: 8 }]}>
            <Input.Password autoComplete='new-password' maxLength={72} />
          </Form.Item>
        </Form>
      </Modal>
    </AdminLayout>
  );
}
