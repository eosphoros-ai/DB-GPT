import { addUser, apiInterceptors, deleteUser, getUserGroups, getUserList, updateUser } from '@/client/api';
import type { AddUserParams, UpdateUserParams, UserGroup, UserInfo } from '@/client/api/user';
import { STORAGE_USERINFO_KEY } from '@/utils/constants/index';
import { PlusOutlined } from '@ant-design/icons';
import { Button, Form, Input, Modal, Popconfirm, Select, Space, Table, message } from 'antd';
import { useRouter } from 'next/router';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

export default function UserManagementPage() {
  const router = useRouter();
  const { t, i18n } = useTranslation();
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [groups, setGroups] = useState<UserGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editUser, setEditUser] = useState<UserInfo | null>(null);
  const [form] = Form.useForm();
  const [editForm] = Form.useForm();

  const isSuperAdmin = useCallback(() => {
    try {
      const raw = localStorage.getItem(STORAGE_USERINFO_KEY);
      if (raw) {
        const info = JSON.parse(raw);
        return info.role === 'super_admin';
      }
    } catch {
      /* empty */
    }
    return false;
  }, []);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const [, data] = await apiInterceptors(getUserList());
      if (data) {
        setUsers(data);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchGroups = useCallback(async () => {
    try {
      const [, data] = await apiInterceptors(getUserGroups());
      if (data) {
        setGroups(data);
      }
    } catch {
      /* empty */
    }
  }, []);

  useEffect(() => {
    if (!isSuperAdmin()) {
      message.error(t('user_access_denied'));
      router.replace('/');
      return;
    }
    fetchUsers();
    fetchGroups();
  }, [fetchUsers, fetchGroups, isSuperAdmin, router, t]);

  const handleAdd = async (values: AddUserParams) => {
    const [err] = await apiInterceptors(addUser(values));
    if (!err) {
      message.success(t('user_created'));
      setModalOpen(false);
      form.resetFields();
      fetchUsers();
    }
  };

  const handleDelete = async (userId: number) => {
    const [err] = await apiInterceptors(deleteUser(userId));
    if (!err) {
      message.success(t('user_deleted'));
      fetchUsers();
    }
  };

  const handleEdit = (user: UserInfo) => {
    setEditUser(user);
    editForm.setFieldsValue({
      user_group_id: user.user_group_id,
      user_role: user.user_role,
      phone: user.phone,
      email: user.email,
      real_name: user.real_name,
    });
  };

  const handleEditSubmit = async (values: UpdateUserParams) => {
    if (!editUser) return;
    const [err] = await apiInterceptors(updateUser(editUser.id, values));
    if (!err) {
      message.success(t('user_updated'));
      setEditUser(null);
      editForm.resetFields();
      fetchUsers();
    }
  };

  const columns = useMemo(
    () => [
      {
        title: t('user_id'),
        dataIndex: 'id',
        key: 'id',
        width: 60,
      },
      {
        title: t('user_name'),
        dataIndex: 'username',
        key: 'username',
      },
      {
        title: t('user_group'),
        dataIndex: 'user_group_name',
        key: 'user_group_name',
        render: (text: string) => text || '-',
      },
      {
        title: t('user_role'),
        dataIndex: 'user_role',
        key: 'user_role',
        render: (text: string) => (text === 'super_admin' ? t('user_super_admin') : t('user_normal')),
      },
      {
        title: t('user_phone'),
        dataIndex: 'phone',
        key: 'phone',
        render: (text: string) => text || '-',
      },
      {
        title: t('user_email'),
        dataIndex: 'email',
        key: 'email',
        render: (text: string) => text || '-',
      },
      {
        title: t('user_real_name'),
        dataIndex: 'real_name',
        key: 'real_name',
        render: (text: string) => text || '-',
      },
      {
        title: t('user_created_time'),
        dataIndex: 'gmt_created',
        key: 'gmt_created',
        render: (text: string) => text || '-',
      },
      {
        title: t('user_actions'),
        key: 'actions',
        width: 160,
        render: (_: unknown, record: UserInfo) => (
          <Space>
            <Button size='small' onClick={() => handleEdit(record)}>
              {t('user_edit')}
            </Button>
            <Popconfirm
              title={t('user_delete_confirm')}
              onConfirm={() => handleDelete(record.id)}
              okText={t('yes')}
              cancelText={t('no')}
            >
              <Button size='small' danger>
                {t('user_delete')}
              </Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [t, i18n.language],
  );

  return (
    <div className='p-6'>
      <div className='flex items-center justify-between mb-4'>
        <h1 className='text-xl font-bold'>{t('user_management')}</h1>
        <Button
          type='primary'
          icon={<PlusOutlined />}
          onClick={() => {
            setModalOpen(true);
            form.resetFields();
          }}
        >
          {t('user_add')}
        </Button>
      </div>

      <Table
        key={i18n.language}
        dataSource={users}
        columns={columns}
        rowKey='id'
        loading={loading}
        pagination={{ pageSize: 20 }}
      />

      {/* Add User Modal */}
      <Modal
        title={t('user_add')}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        destroyOnClose
      >
        <Form form={form} layout='vertical' onFinish={handleAdd}>
          <Form.Item
            name='username'
            label={t('user_name')}
            rules={[{ required: true, message: t('user_username_required') }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name='password'
            label={t('user_password_label')}
            rules={[{ required: true, message: t('user_password_required') }]}
          >
            <Input.Password />
          </Form.Item>
          <Form.Item
            name='user_group_id'
            label={t('user_group_label')}
            rules={[{ required: true, message: t('user_group_required') }]}
          >
            <Select options={groups.map(g => ({ label: g.group_name, value: g.id }))} />
          </Form.Item>
          <Form.Item name='user_role' label={t('user_role_label')} initialValue='normal'>
            <Select
              options={[
                { label: t('user_normal'), value: 'normal' },
                { label: t('user_super_admin'), value: 'super_admin' },
              ]}
            />
          </Form.Item>
          <Form.Item name='real_name' label={t('user_real_name_label')}>
            <Input />
          </Form.Item>
          <Form.Item name='phone' label={t('user_phone_label')}>
            <Input />
          </Form.Item>
          <Form.Item name='email' label={t('user_email_label')}>
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      {/* Edit User Modal */}
      <Modal
        title={t('user_edit')}
        open={!!editUser}
        onCancel={() => setEditUser(null)}
        onOk={() => editForm.submit()}
        destroyOnClose
      >
        <Form form={editForm} layout='vertical' onFinish={handleEditSubmit}>
          <Form.Item name='user_group_id' label={t('user_group_label')}>
            <Select options={groups.map(g => ({ label: g.group_name, value: g.id }))} />
          </Form.Item>
          <Form.Item name='user_role' label={t('user_role_label')}>
            <Select
              options={[
                { label: t('user_normal'), value: 'normal' },
                { label: t('user_super_admin'), value: 'super_admin' },
              ]}
            />
          </Form.Item>
          <Form.Item name='real_name' label={t('user_real_name_label')}>
            <Input />
          </Form.Item>
          <Form.Item name='phone' label={t('user_phone_label')}>
            <Input />
          </Form.Item>
          <Form.Item name='email' label={t('user_email_label')}>
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
