import { PlusOutlined } from '@ant-design/icons';
import { App, Badge, Button, Form, Input, Modal, Space, Table } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useCallback, useEffect, useState } from 'react';

import {
  createAccountSet,
  getAccountSetImpact,
  listAccountSets,
  toggleAccountSetActive,
  updateAccountSet,
} from '@/client/api/admin';
import AdminLayout from '@/new-components/admin/AdminLayout';
import {
  AdminPageHeader,
  formatAdminDate,
  getAdminErrorMessage,
  requireAdminData,
} from '@/new-components/admin/AdminPage';
import ConfirmModal from '@/new-components/admin/ConfirmModal';
import { AccountSet, AccountSetImpact } from '@/types/admin';

interface AccountSetFormValues {
  name: string;
  description?: string;
}
const PAGE_SIZE = 20;

export default function AccountSetsPage() {
  const { message } = App.useApp();
  const [form] = Form.useForm<AccountSetFormValues>();
  const [items, setItems] = useState<AccountSet[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<AccountSet | null>(null);
  const [saving, setSaving] = useState(false);
  const [deactivateTarget, setDeactivateTarget] = useState<AccountSet | null>(null);
  const [impact, setImpact] = useState<AccountSetImpact | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = requireAdminData(await listAccountSets({ page, page_size: PAGE_SIZE }));
      setItems(data.items);
      setTotal(data.total);
    } catch (error) {
      message.error(getAdminErrorMessage(error, '账套列表加载失败'));
    } finally {
      setLoading(false);
    }
  }, [message, page]);

  useEffect(() => {
    void load();
  }, [load]);

  const openForm = (accountSet?: AccountSet) => {
    setEditing(accountSet || null);
    form.setFieldsValue(
      accountSet
        ? { name: accountSet.name, description: accountSet.description || undefined }
        : { name: '', description: '' },
    );
    setModalOpen(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      const values = await form.validateFields();
      requireAdminData(
        editing ? await updateAccountSet(editing.account_set_id, values) : await createAccountSet(values),
      );
      message.success(editing ? '账套已更新' : '账套已创建');
      setModalOpen(false);
      void load();
    } catch (error) {
      if (!(error as { errorFields?: unknown }).errorFields) message.error(getAdminErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const prepareDeactivate = async (accountSet: AccountSet) => {
    try {
      setImpact(requireAdminData(await getAccountSetImpact(accountSet.account_set_id)));
      setDeactivateTarget(accountSet);
    } catch (error) {
      message.error(getAdminErrorMessage(error, '影响范围加载失败'));
    }
  };

  const toggle = async (accountSet: AccountSet, reason?: string) => {
    const confirmation =
      accountSet.is_active && impact
        ? { reason: reason || '', confirm_impact: true as const, impact_token: impact.impact_token }
        : undefined;
    requireAdminData(await toggleAccountSetActive(accountSet.account_set_id, !accountSet.is_active, confirmation));
    message.success(accountSet.is_active ? '账套已停用' : '账套已启用');
    setDeactivateTarget(null);
    setImpact(null);
    void load();
  };

  const activate = async (accountSet: AccountSet) => {
    try {
      await toggle(accountSet);
    } catch (error) {
      message.error(getAdminErrorMessage(error));
    }
  };

  const columns: ColumnsType<AccountSet> = [
    { title: '账套名称', dataIndex: 'name', width: 220 },
    { title: '说明', dataIndex: 'description', ellipsis: true },
    {
      title: '状态',
      dataIndex: 'is_active',
      width: 100,
      render: active => <Badge status={active ? 'success' : 'default'} text={active ? '启用' : '停用'} />,
    },
    { title: '创建时间', dataIndex: 'gmt_created', width: 190, render: formatAdminDate },
    {
      title: '操作',
      width: 150,
      render: (_, item) => (
        <Space>
          <Button type='link' onClick={() => openForm(item)}>
            编辑
          </Button>
          <Button
            danger={item.is_active}
            type='link'
            onClick={() => (item.is_active ? void prepareDeactivate(item) : void activate(item))}
          >
            {item.is_active ? '停用' : '启用'}
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <AdminLayout>
      <AdminPageHeader
        title='账套管理'
        description='维护资源归属使用的稳定内部账套目录。'
        extra={
          <Button icon={<PlusOutlined />} type='primary' onClick={() => openForm()}>
            新建账套
          </Button>
        }
      />
      <Table
        rowKey='account_set_id'
        columns={columns}
        dataSource={items}
        loading={loading}
        scroll={{ x: 850 }}
        pagination={{ current: page, pageSize: PAGE_SIZE, total, showSizeChanger: false, onChange: setPage }}
      />
      <Modal
        open={modalOpen}
        title={editing ? '编辑账套' : '新建账套'}
        confirmLoading={saving}
        onCancel={() => setModalOpen(false)}
        onOk={() => void save()}
      >
        <Form form={form} layout='vertical' requiredMark={false}>
          <Form.Item label='账套名称' name='name' rules={[{ required: true, whitespace: true }]}>
            <Input maxLength={255} />
          </Form.Item>
          <Form.Item label='说明' name='description'>
            <Input.TextArea maxLength={4000} rows={4} showCount />
          </Form.Item>
        </Form>
      </Modal>
      <ConfirmModal
        open={!!deactivateTarget}
        title='确认停用账套'
        description={`停用“${deactivateTarget?.name || ''}”后，相关资源将无法被非系统管理员使用。`}
        impact={
          impact
            ? `影响 ${impact.user_grant_count} 个用户账套授权、${impact.resource_grant_count} 个资源授权和 ${impact.resource_count} 个资源。`
            : undefined
        }
        requireReason
        onCancel={() => {
          setDeactivateTarget(null);
          setImpact(null);
        }}
        onConfirm={async reason => {
          if (deactivateTarget) await toggle(deactivateTarget, reason);
        }}
      />
    </AdminLayout>
  );
}
