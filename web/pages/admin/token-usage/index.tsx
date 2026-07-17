import { App, Button, DatePicker, Form, Select, Space, Statistic, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { Dayjs } from 'dayjs';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { getTokenUsageDaily, getTokenUsageSummary, listAccountSets, listAdminUsers } from '@/client/api/admin';
import { useAdminAuthGuard } from '@/hooks/use-admin-auth';
import AdminLayout from '@/new-components/admin/AdminLayout';
import { AdminPageHeader, ROLE_LABELS, getAdminErrorMessage, requireAdminData } from '@/new-components/admin/AdminPage';
import { AccountSet, AdminRole, AdminUser, TokenDailyStat, TokenUsageFilters, TokenUsageSummary } from '@/types/admin';

interface UsageFilterForm {
  dates?: [Dayjs, Dayjs];
  user_id?: string;
  account_set_id?: string;
  model?: string;
}

function TokenUsageContent() {
  const { message } = App.useApp();
  const { user } = useAdminAuthGuard();
  const [form] = Form.useForm<UsageFilterForm>();
  const [summary, setSummary] = useState<TokenUsageSummary | null>(null);
  const [daily, setDaily] = useState<TokenDailyStat[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [accountSets, setAccountSets] = useState<AccountSet[]>([]);
  const [filters, setFilters] = useState<TokenUsageFilters>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user?.role !== 'system_admin') return;
    void Promise.all([listAdminUsers({ page_size: 100 }), listAccountSets({ page_size: 100 })])
      .then(([userResult, accountResult]) => {
        setUsers(requireAdminData(userResult).items);
        setAccountSets(requireAdminData(accountResult).items);
      })
      .catch(error => message.error(getAdminErrorMessage(error, '筛选项加载失败')));
  }, [message, user?.role]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [summaryResult, dailyResult] = await Promise.all([getTokenUsageSummary(), getTokenUsageDaily(filters)]);
      setSummary(requireAdminData(summaryResult));
      setDaily(requireAdminData(dailyResult));
    } catch (error) {
      message.error(getAdminErrorMessage(error, 'Token 用量加载失败'));
    } finally {
      setLoading(false);
    }
  }, [filters, message]);

  useEffect(() => {
    void load();
  }, [load]);

  const userMap = useMemo(() => new Map(users.map(item => [item.user_id, item.display_name])), [users]);
  const accountSetMap = useMemo(
    () => new Map(accountSets.map(item => [item.account_set_id, item.name])),
    [accountSets],
  );
  const models = useMemo(() => Array.from(new Set(daily.map(item => item.model))).sort(), [daily]);
  const userOptions = useMemo(
    () =>
      user?.role === 'system_admin'
        ? users.map(item => ({ value: item.user_id, label: item.display_name }))
        : Array.from(new Set(daily.map(item => item.user_id))).map(id => ({ value: id, label: id })),
    [daily, user?.role, users],
  );
  const accountSetOptions = useMemo(
    () =>
      user?.role === 'system_admin'
        ? accountSets.map(item => ({ value: item.account_set_id, label: item.name }))
        : Array.from(new Set(daily.map(item => item.account_set_id).filter(Boolean))).map(id => ({
            value: id,
            label: id,
          })),
    [accountSets, daily, user?.role],
  );

  const search = (values: UsageFilterForm) => {
    setFilters({
      user_id: values.user_id,
      account_set_id: values.account_set_id,
      model: values.model,
      date_from: values.dates?.[0].format('YYYY-MM-DD'),
      date_to: values.dates?.[1].format('YYYY-MM-DD'),
    });
  };

  const columns: ColumnsType<TokenDailyStat> = [
    { title: '日期', dataIndex: 'stat_date', width: 120 },
    { title: '用户', dataIndex: 'user_id', width: 180, render: id => userMap.get(id) || id },
    {
      title: '角色',
      dataIndex: 'role_snapshot',
      width: 130,
      render: (role: AdminRole) => <Tag>{ROLE_LABELS[role]}</Tag>,
    },
    { title: '账套', dataIndex: 'account_set_id', width: 180, render: id => accountSetMap.get(id) || id || '-' },
    { title: '模型', dataIndex: 'model', ellipsis: true },
    { title: '输入 Token', dataIndex: 'input_tokens', width: 130, align: 'right' },
    { title: '输出 Token', dataIndex: 'output_tokens', width: 130, align: 'right' },
    { title: '总 Token', dataIndex: 'total_tokens', width: 130, align: 'right' },
    { title: '调用次数', dataIndex: 'call_count', width: 110, align: 'right' },
  ];

  return (
    <>
      <AdminPageHeader title='Token 用量' description='按 Asia/Shanghai 自然日统计，数据用于追溯和容量观察。' />
      <div className='mb-5 grid grid-cols-2 border border-solid border-gray-200 bg-white md:max-w-xl'>
        <div className='border-0 border-r border-solid border-gray-200 p-4'>
          <Statistic title={`${summary?.stat_date || '今日'}总 Token`} value={summary?.total_tokens || 0} />
        </div>
        <div className='p-4'>
          <Statistic title='调用次数' value={summary?.call_count || 0} />
        </div>
      </div>
      <Form form={form} className='mb-2' layout='inline' onFinish={search}>
        <Form.Item name='dates'>
          <DatePicker.RangePicker allowClear />
        </Form.Item>
        {user?.role !== 'query_user' && (
          <Form.Item name='user_id'>
            <Select
              allowClear
              showSearch
              className='w-48'
              optionFilterProp='label'
              placeholder='全部用户'
              options={userOptions}
            />
          </Form.Item>
        )}
        {user?.role !== 'query_user' && (
          <Form.Item name='account_set_id'>
            <Select
              allowClear
              showSearch
              className='w-48'
              optionFilterProp='label'
              placeholder='全部账套'
              options={accountSetOptions}
            />
          </Form.Item>
        )}
        <Form.Item name='model'>
          <Select
            allowClear
            showSearch
            className='w-48'
            placeholder='全部模型'
            options={models.map(model => ({ value: model, label: model }))}
          />
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type='primary' htmlType='submit'>
              查询
            </Button>
            <Button
              onClick={() => {
                form.resetFields();
                setFilters({});
              }}
            >
              重置
            </Button>
          </Space>
        </Form.Item>
      </Form>
      <Table
        rowKey={item => `${item.stat_date}:${item.user_id}:${item.account_set_id}:${item.model}`}
        columns={columns}
        dataSource={daily}
        loading={loading}
        scroll={{ x: 1150 }}
        pagination={{ pageSize: 20 }}
      />
    </>
  );
}

export default function TokenUsagePage() {
  return (
    <AdminLayout>
      <TokenUsageContent />
    </AdminLayout>
  );
}
