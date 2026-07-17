import { App, Button, Modal, Select, Space, Switch, Table, Tabs, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { assignResourceAccountSet, getResourceImpact, listAccountSets, listAdminResources } from '@/client/api/admin';
import { useAdminAuthGuard } from '@/hooks/use-admin-auth';
import AdminLayout from '@/new-components/admin/AdminLayout';
import {
  AdminPageHeader,
  RESOURCE_LABELS,
  getAdminErrorMessage,
  requireAdminData,
} from '@/new-components/admin/AdminPage';
import ConfirmModal from '@/new-components/admin/ConfirmModal';
import { AccountSet, AdminResource, AdminResourceType, ResourceImpact } from '@/types/admin';

const RESOURCE_TYPES: AdminResourceType[] = ['DATASOURCE', 'KNOWLEDGE_BASE', 'AGENT'];
const PAGE_SIZE = 20;

function AdminResourcesContent() {
  const { message } = App.useApp();
  const { user } = useAdminAuthGuard();
  const [resourceType, setResourceType] = useState<AdminResourceType>('DATASOURCE');
  const [resources, setResources] = useState<AdminResource[]>([]);
  const [accountSets, setAccountSets] = useState<Array<Pick<AccountSet, 'account_set_id' | 'name' | 'is_active'>>>([]);
  const [unassigned, setUnassigned] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [assignTarget, setAssignTarget] = useState<AdminResource | null>(null);
  const [targetAccountSetId, setTargetAccountSetId] = useState<string>();
  const [impact, setImpact] = useState<ResourceImpact | null>(null);

  const loadAccountOptions = useCallback(async () => {
    try {
      if (user?.role === 'system_admin') {
        const data = requireAdminData(await listAccountSets({ page_size: 100, is_active: true }));
        setAccountSets(data.items);
      } else {
        const scoped = requireAdminData(await listAdminResources({ page_size: 100 })).items;
        const ids = Array.from(new Set(scoped.map(item => item.account_set_id).filter((id): id is string => !!id)));
        setAccountSets(ids.map(id => ({ account_set_id: id, name: id, is_active: true })));
      }
    } catch (error) {
      message.error(getAdminErrorMessage(error, '可用账套范围加载失败'));
    }
  }, [message, user?.role]);

  const loadResources = useCallback(async () => {
    setLoading(true);
    try {
      const data = requireAdminData(
        await listAdminResources({ page, page_size: PAGE_SIZE, resource_type: resourceType, unassigned }),
      );
      setResources(data.items);
      setTotal(data.total);
    } catch (error) {
      message.error(getAdminErrorMessage(error, '资源列表加载失败'));
    } finally {
      setLoading(false);
    }
  }, [message, page, resourceType, unassigned]);

  useEffect(() => {
    void loadAccountOptions();
  }, [loadAccountOptions]);
  useEffect(() => {
    void loadResources();
  }, [loadResources]);

  const accountSetMap = useMemo(
    () => new Map(accountSets.map(item => [item.account_set_id, item.name])),
    [accountSets],
  );

  const prepareImpact = async () => {
    if (!assignTarget || !targetAccountSetId) return;
    try {
      setImpact(
        requireAdminData(
          await getResourceImpact(assignTarget.resource_type, assignTarget.resource_id, targetAccountSetId),
        ),
      );
    } catch (error) {
      message.error(getAdminErrorMessage(error, '影响范围加载失败'));
    }
  };

  const assign = async (reason?: string) => {
    if (!assignTarget || !targetAccountSetId || !impact) return;
    requireAdminData(
      await assignResourceAccountSet(
        assignTarget.resource_type,
        assignTarget.resource_id,
        targetAccountSetId,
        reason || '',
        impact.impact_token,
      ),
    );
    message.success('资源账套已更新');
    setAssignTarget(null);
    setTargetAccountSetId(undefined);
    setImpact(null);
    void loadResources();
    void loadAccountOptions();
  };

  const columns: ColumnsType<AdminResource> = [
    { title: '资源名称', dataIndex: 'name', ellipsis: true },
    { title: '资源 ID', dataIndex: 'resource_id', width: 180, ellipsis: true },
    {
      title: '所属账套',
      dataIndex: 'account_set_id',
      width: 220,
      render: (id?: string | null) =>
        id ? <span>{accountSetMap.get(id) || id}</span> : <Tag color='orange'>未归属</Tag>,
    },
    {
      title: '操作',
      width: 120,
      render: (_, resource) => (
        <Button
          type='link'
          onClick={() => {
            setAssignTarget(resource);
            setTargetAccountSetId(resource.account_set_id || undefined);
          }}
        >
          分配账套
        </Button>
      ),
    },
  ];

  return (
    <>
      <AdminPageHeader
        title='资源管理'
        description='维护数据源、知识库和智能体的账套归属；未归属资源默认拒绝非系统管理员访问。'
        extra={
          <Space>
            <span className='text-sm text-gray-500'>仅显示未归属</span>
            <Switch
              checked={unassigned}
              onChange={value => {
                setPage(1);
                setUnassigned(value);
              }}
            />
          </Space>
        }
      />
      <Tabs
        activeKey={resourceType}
        items={RESOURCE_TYPES.map(type => ({ key: type, label: RESOURCE_LABELS[type] }))}
        onChange={key => {
          setPage(1);
          setResourceType(key as AdminResourceType);
        }}
      />
      <Table
        rowKey={item => `${item.resource_type}:${item.resource_id}`}
        columns={columns}
        dataSource={resources}
        loading={loading}
        scroll={{ x: 760 }}
        pagination={{ current: page, pageSize: PAGE_SIZE, total, showSizeChanger: false, onChange: setPage }}
      />

      <Modal
        open={!!assignTarget && !impact}
        title={`分配账套：${assignTarget?.name || ''}`}
        okText='查看影响并继续'
        okButtonProps={{ disabled: !targetAccountSetId || targetAccountSetId === assignTarget?.account_set_id }}
        onCancel={() => {
          setAssignTarget(null);
          setTargetAccountSetId(undefined);
        }}
        onOk={() => void prepareImpact()}
      >
        <label className='mb-2 block text-sm font-medium text-gray-700'>目标账套</label>
        <Select
          showSearch
          className='w-full'
          optionFilterProp='label'
          placeholder='选择目标账套'
          value={targetAccountSetId}
          options={accountSets
            .filter(item => item.is_active)
            .map(item => ({ value: item.account_set_id, label: item.name }))}
          onChange={setTargetAccountSetId}
        />
      </Modal>
      <ConfirmModal
        open={!!impact}
        title='确认变更资源账套'
        description={`资源“${assignTarget?.name || ''}”将移动到“${accountSetMap.get(targetAccountSetId || '') || targetAccountSetId || ''}”。`}
        impact={
          impact
            ? `将撤销 ${impact.affected_resource_grants} 个直接资源授权和 ${impact.affected_agent_grants} 个关联智能体授权。`
            : undefined
        }
        impactItems={impact?.affected_grants_detail.map(item => ({
          label: String(item.resource_type || '授权'),
          value: String(item.resource_name || item.resource_id || '-'),
        }))}
        requireReason
        onCancel={() => setImpact(null)}
        onConfirm={assign}
      />
    </>
  );
}

export default function AdminResourcesPage() {
  return (
    <AdminLayout>
      <AdminResourcesContent />
    </AdminLayout>
  );
}
