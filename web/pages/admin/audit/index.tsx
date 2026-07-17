import { App, Button, DatePicker, Form, Input, Select, Space, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { Dayjs } from 'dayjs';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { getAuditEvents, listAdminUsers } from '@/client/api/admin';
import AdminLayout from '@/new-components/admin/AdminLayout';
import {
  AdminPageHeader,
  formatAdminDate,
  getAdminErrorMessage,
  requireAdminData,
} from '@/new-components/admin/AdminPage';
import { AdminUser, AuditEvent, AuditEventListParams, AuditResult } from '@/types/admin';

interface AuditFilterForm {
  dates?: [Dayjs, Dayjs];
  target_type?: string;
  action?: string;
  operator_user_id?: string;
  result?: AuditResult;
}

const RESULT_COLORS: Record<AuditResult, string> = { success: 'green', failed: 'red', denied: 'orange' };
const PAGE_SIZE = 20;

const prettySnapshot = (value?: string | null) => {
  if (!value) return '-';
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return value;
  }
};

export default function AuditPage() {
  const { message } = App.useApp();
  const [form] = Form.useForm<AuditFilterForm>();
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [filters, setFilters] = useState<AuditEventListParams>({});
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void listAdminUsers({ page_size: 100 })
      .then(result => setUsers(requireAdminData(result).items))
      .catch(error => message.error(getAdminErrorMessage(error, '操作者列表加载失败')));
  }, [message]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = requireAdminData(await getAuditEvents({ ...filters, page, page_size: PAGE_SIZE }));
      setEvents(data.items);
      setTotal(data.total);
    } catch (error) {
      message.error(getAdminErrorMessage(error, '审计日志加载失败'));
    } finally {
      setLoading(false);
    }
  }, [filters, message, page]);

  useEffect(() => {
    void load();
  }, [load]);

  const userMap = useMemo(() => new Map(users.map(item => [item.user_id, item.display_name])), [users]);
  const targetTypes = useMemo(() => Array.from(new Set(events.map(item => item.target_type))).sort(), [events]);

  const search = (values: AuditFilterForm) => {
    setPage(1);
    setFilters({
      target_type: values.target_type,
      action: values.action?.trim() || undefined,
      operator_user_id: values.operator_user_id,
      result: values.result,
      date_from: values.dates?.[0].startOf('day').toISOString(),
      date_to: values.dates?.[1].endOf('day').toISOString(),
    });
  };

  const columns: ColumnsType<AuditEvent> = [
    { title: '时间', dataIndex: 'event_time', width: 190, render: formatAdminDate },
    { title: '操作者', dataIndex: 'operator_user_id', width: 180, render: id => (id ? userMap.get(id) || id : '系统') },
    { title: '目标类型', dataIndex: 'target_type', width: 150 },
    { title: '目标 ID', dataIndex: 'target_id', width: 180, ellipsis: true },
    { title: '动作', dataIndex: 'action', ellipsis: true },
    {
      title: '结果',
      dataIndex: 'result',
      width: 100,
      render: (result: AuditResult) => <Tag color={RESULT_COLORS[result]}>{result}</Tag>,
    },
  ];

  return (
    <AdminLayout>
      <AdminPageHeader title='审计日志' description='安全事件只追加保存，展开记录可查看脱敏后的前后值摘要。' />
      <Form form={form} className='mb-2' layout='inline' onFinish={search}>
        <Form.Item name='dates'>
          <DatePicker.RangePicker />
        </Form.Item>
        <Form.Item name='target_type'>
          <Select
            allowClear
            showSearch
            className='w-40'
            placeholder='目标类型'
            options={targetTypes.map(value => ({ value, label: value }))}
          />
        </Form.Item>
        <Form.Item name='operator_user_id'>
          <Select
            allowClear
            showSearch
            className='w-44'
            optionFilterProp='label'
            placeholder='操作者'
            options={users.map(user => ({ value: user.user_id, label: user.display_name }))}
          />
        </Form.Item>
        <Form.Item name='result'>
          <Select
            allowClear
            className='w-32'
            placeholder='结果'
            options={Object.keys(RESULT_COLORS).map(value => ({ value, label: value }))}
          />
        </Form.Item>
        <Form.Item name='action'>
          <Input className='w-44' placeholder='动作代码' />
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type='primary' htmlType='submit'>
              查询
            </Button>
            <Button
              onClick={() => {
                form.resetFields();
                setPage(1);
                setFilters({});
              }}
            >
              重置
            </Button>
          </Space>
        </Form.Item>
      </Form>
      <Table
        rowKey='event_id'
        columns={columns}
        dataSource={events}
        loading={loading}
        scroll={{ x: 1000 }}
        expandable={{
          expandedRowRender: event => (
            <div className='grid grid-cols-1 gap-4 lg:grid-cols-2'>
              <div>
                <div className='mb-2 text-xs font-medium text-gray-500'>变更前</div>
                <pre className='m-0 max-h-72 overflow-auto whitespace-pre-wrap break-all rounded bg-gray-100 p-3 text-xs'>
                  {prettySnapshot(event.before_snapshot)}
                </pre>
              </div>
              <div>
                <div className='mb-2 text-xs font-medium text-gray-500'>变更后</div>
                <pre className='m-0 max-h-72 overflow-auto whitespace-pre-wrap break-all rounded bg-gray-100 p-3 text-xs'>
                  {prettySnapshot(event.after_snapshot)}
                </pre>
              </div>
              {event.deny_reason && (
                <div className='lg:col-span-2 text-sm text-red-600'>拒绝原因：{event.deny_reason}</div>
              )}
            </div>
          ),
        }}
        pagination={{ current: page, pageSize: PAGE_SIZE, total, showSizeChanger: false, onChange: setPage }}
      />
    </AdminLayout>
  );
}
