import {
  createDashboardSchedule,
  deleteDashboardSchedule,
  getDashboardSchedulerStatus,
  listDashboardScheduleRuns,
  listDashboardSchedules,
  runDashboardSchedule,
  toggleDashboardSchedule,
  updateDashboardSchedule,
} from '@/client/api';
import { type DashboardSchedulerStatus } from '@/client/api/dashboard';
import type {
  DashboardFilter,
  DashboardSchedule,
  DashboardScheduleCreate,
  DashboardScheduleRun,
  DashboardScheduleRunStatus,
} from '@/types/dashboard';
import {
  DeleteOutlined,
  EditOutlined,
  HistoryOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import {
  Alert,
  App,
  Button,
  Descriptions,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Typography,
} from 'antd';
import { type ReactNode, useCallback, useEffect, useMemo, useState } from 'react';
import { describeDashboardError } from './dashboard-errors';
import { scheduleDashboardFilterValues } from './dashboard-relative-date';
import DashboardRefreshFrequencyInput, { describeDashboardScheduleCron } from './DashboardRefreshFrequencyInput';

const { Text } = Typography;

type ScheduleForm = {
  task_name: string;
  description?: string;
  publish_after_refresh: boolean;
  timeout_seconds: number;
  max_attempts: number;
};

interface DashboardSchedulePanelProps {
  children?: ReactNode;
  dashboardId: string;
  filters: Record<string, unknown>;
  filterDefinitions: DashboardFilter[];
  open: boolean;
  onClose: () => void;
}

const statusColors: Record<DashboardScheduleRunStatus, string> = {
  running: 'processing',
  success: 'success',
  partial_success: 'warning',
  failed: 'error',
  timeout: 'error',
};

const statusLabels: Record<DashboardScheduleRunStatus, string> = {
  running: '运行中',
  success: '成功',
  partial_success: '部分成功',
  failed: '失败',
  timeout: '超时',
};

export default function DashboardSchedulePanel({
  children,
  dashboardId,
  filters,
  filterDefinitions,
  open,
  onClose,
}: DashboardSchedulePanelProps) {
  const { message, modal } = App.useApp();
  const [form] = Form.useForm<ScheduleForm>();
  const [cron, setCron] = useState('*/5 * * * *');
  const [schedules, setSchedules] = useState<DashboardSchedule[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [editing, setEditing] = useState<DashboardSchedule | null>(null);
  const [runs, setRuns] = useState<DashboardScheduleRun[]>([]);
  const [runsFor, setRunsFor] = useState<DashboardSchedule | null>(null);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [scheduler, setScheduler] = useState<DashboardSchedulerStatus | null>(null);
  const [latestRuns, setLatestRuns] = useState<Record<string, DashboardScheduleRun[]>>({});

  const loadSchedules = useCallback(async () => {
    setLoading(true);
    try {
      const [response, runtime] = await Promise.all([
        listDashboardSchedules(dashboardId),
        getDashboardSchedulerStatus(dashboardId),
      ]);
      if (!runtime.data.success) throw new Error('后台状态读取失败');
      setScheduler(runtime.data.data);
      setSchedules(response.data.data || []);
      const history = await Promise.all(
        (response.data.data || []).map(async schedule => {
          try {
            const r = await listDashboardScheduleRuns(dashboardId, schedule.task_id, 20);
            return [schedule.task_id, r.data.data || []] as const;
          } catch {
            return [schedule.task_id, []] as const;
          }
        }),
      );
      setLatestRuns(Object.fromEntries(history));
    } catch (error) {
      setScheduler(null);
      message.error(describeDashboardError(error, '读取刷新计划失败'));
    } finally {
      setLoading(false);
    }
  }, [dashboardId, message]);

  useEffect(() => {
    // Opening the drawer is the external event that starts the remote refresh.
    if (open) void loadSchedules();
  }, [loadSchedules, open]);

  const resetEditor = () => {
    setEditing(null);
    setCron('*/5 * * * *');
    form.setFieldsValue({
      task_name: '',
      description: '',
      publish_after_refresh: false,
      timeout_seconds: 180,
      max_attempts: 2,
    });
  };

  const editSchedule = (schedule: DashboardSchedule) => {
    setEditing(schedule);
    setCron(schedule.cron_expression);
    form.setFieldsValue({
      task_name: schedule.task_name,
      description: schedule.description || '',
      publish_after_refresh: schedule.payload.publish_after_refresh,
      timeout_seconds: schedule.payload.timeout_seconds,
      max_attempts: schedule.payload.max_attempts,
    });
  };

  const saveSchedule = async () => {
    let values: ScheduleForm;
    try {
      values = await form.validateFields();
    } catch {
      return;
    }
    if (cron.trim().split(/\s+/).length !== 5) {
      message.error('Cron 表达式必须包含 5 段');
      return;
    }

    const request: DashboardScheduleCreate = {
      ...values,
      cron_expression: cron,
      filters: scheduleDashboardFilterValues(filterDefinitions, filters),
    };
    setSaving(true);
    try {
      if (editing) {
        await updateDashboardSchedule(dashboardId, editing.task_id, request);
        message.success('刷新计划已更新');
      } else {
        await createDashboardSchedule(dashboardId, request);
        message.success('刷新计划已创建');
      }
      resetEditor();
      await loadSchedules();
    } catch (error) {
      message.error(describeDashboardError(error, editing ? '更新刷新计划失败' : '创建刷新计划失败'));
    } finally {
      setSaving(false);
    }
  };

  const toggleSchedule = async (schedule: DashboardSchedule, enabled: boolean) => {
    try {
      const response = await toggleDashboardSchedule(dashboardId, schedule.task_id, enabled);
      setSchedules(current => current.map(item => (item.task_id === schedule.task_id ? response.data.data : item)));
      message.success(enabled ? '刷新计划已启用' : '刷新计划已暂停');
    } catch (error) {
      message.error(describeDashboardError(error, '切换刷新计划失败'));
    }
  };

  const runNow = async (schedule: DashboardSchedule) => {
    setRunningId(schedule.task_id);
    try {
      const response = await runDashboardSchedule(dashboardId, schedule.task_id);
      const run = response.data.data;
      if (run.status === 'partial_success') {
        message.warning('刷新已完成，但部分组件失败，请查看运行记录');
      } else {
        message.success('刷新已完成');
      }
      if (runsFor?.task_id === schedule.task_id) await showRuns(schedule);
    } catch (error) {
      message.error(describeDashboardError(error, '立即刷新失败'));
    } finally {
      setRunningId(null);
    }
  };

  const removeSchedule = (schedule: DashboardSchedule) => {
    modal.confirm({
      title: '删除刷新计划？',
      content: `计划“${schedule.task_name}”将停止执行，已有运行记录一并停止展示。`,
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteDashboardSchedule(dashboardId, schedule.task_id);
          if (runsFor?.task_id === schedule.task_id) {
            setRunsFor(null);
            setRuns([]);
          }
          await loadSchedules();
          message.success('刷新计划已删除');
        } catch (error) {
          message.error(describeDashboardError(error, '删除刷新计划失败'));
        }
      },
    });
  };

  const showRuns = async (schedule: DashboardSchedule) => {
    setRunsFor(schedule);
    setLoadingRuns(true);
    try {
      const response = await listDashboardScheduleRuns(dashboardId, schedule.task_id);
      setRuns(response.data.data || []);
    } catch (error) {
      message.error(describeDashboardError(error, '读取运行记录失败'));
    } finally {
      setLoadingRuns(false);
    }
  };

  const runColumns = useMemo(
    () => [
      {
        title: '状态',
        dataIndex: 'status',
        width: 110,
        render: (status: DashboardScheduleRunStatus) => <Tag color={statusColors[status]}>{statusLabels[status]}</Tag>,
      },
      { title: '开始时间', dataIndex: 'started_at', width: 180, render: (value?: string) => value || '-' },
      { title: '尝试次数', dataIndex: 'attempt_count', width: 90 },
      {
        title: '结果',
        render: (_: unknown, run: DashboardScheduleRun) => (
          <div>
            <div>{run.result_summary || '-'}</div>
            {run.error_message && <Text type='danger'>{run.error_message}</Text>}
            {run.output_resource_id && (
              <a className='ml-2' href={run.output_resource_id} target='_blank' rel='noreferrer'>
                打开发布快照
              </a>
            )}
          </div>
        ),
      },
    ],
    [],
  );

  return (
    <Drawer title='定时刷新与运行记录' width={760} open={open} onClose={onClose} destroyOnClose={false}>
      {children}
      <Alert
        className='mb-3'
        showIcon
        type={scheduler?.running ? 'success' : 'warning'}
        message={scheduler?.message || '后台运行状态尚未确认，请重新加载。'}
      />
      <Alert
        className='mb-4'
        type='info'
        showIcon
        message='计划使用当前筛选条件刷新看板；只有全部组件成功时才允许自动发布。'
      />

      <div className='mb-5 rounded border border-gray-200 p-4 dark:border-gray-700'>
        <div className='mb-3 flex items-center justify-between'>
          <Text strong>{editing ? '编辑刷新计划' : '新建刷新计划'}</Text>
          {editing && <Button onClick={resetEditor}>取消编辑</Button>}
        </div>
        <Form
          form={form}
          layout='vertical'
          initialValues={{ publish_after_refresh: false, timeout_seconds: 180, max_attempts: 2 }}
        >
          <Form.Item name='task_name' label='计划名称' rules={[{ required: true, message: '请输入计划名称' }]}>
            <Input maxLength={256} placeholder='例如：每天早上刷新经营看板' />
          </Form.Item>
          <Form.Item name='description' label='说明'>
            <Input.TextArea maxLength={2000} rows={2} />
          </Form.Item>
          <Form.Item label='执行频率' required>
            <DashboardRefreshFrequencyInput value={cron} onChange={setCron} />
          </Form.Item>
          <Space size='large' align='start' wrap>
            <Form.Item name='publish_after_refresh' label='成功后发布' valuePropName='checked'>
              <Switch />
            </Form.Item>
            <Form.Item name='timeout_seconds' label='单次超时（秒）'>
              <InputNumber min={5} max={600} />
            </Form.Item>
            <Form.Item name='max_attempts' label='最多尝试次数'>
              <InputNumber min={1} max={5} />
            </Form.Item>
          </Space>
          <div>
            <Button
              type='primary'
              icon={editing ? <EditOutlined /> : <PlusOutlined />}
              loading={saving}
              onClick={saveSchedule}
            >
              {editing ? '保存修改' : '创建计划'}
            </Button>
          </div>
        </Form>
      </div>

      <div className='mb-3 flex items-center justify-between'>
        <Text strong>已有计划</Text>
        <Button icon={<ReloadOutlined />} loading={loading} onClick={loadSchedules}>
          重新加载
        </Button>
      </div>
      <Spin spinning={loading}>
        {schedules.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description='还没有刷新计划' />
        ) : (
          <div className='space-y-3'>
            {schedules.map(schedule => (
              <div key={schedule.task_id} className='rounded border border-gray-200 p-3 dark:border-gray-700'>
                <div className='flex items-start gap-3'>
                  <div className='min-w-0 flex-1'>
                    <div className='flex items-center gap-2'>
                      <Text strong>{schedule.task_name}</Text>
                      <Tag color={schedule.enabled && scheduler?.running ? 'green' : 'default'}>
                        {!schedule.enabled ? '已暂停' : scheduler?.running ? '运行中' : '等待后台启动'}
                      </Tag>
                    </div>
                    <Descriptions size='small' column={2} className='mt-2'>
                      <Descriptions.Item label='执行频率'>
                        <div>{describeDashboardScheduleCron(schedule.cron_expression)}</div>
                        <Text type='secondary' className='text-xs'>
                          {schedule.cron_expression}
                        </Text>
                      </Descriptions.Item>
                      <Descriptions.Item label='下次执行'>
                        {!schedule.enabled
                          ? '已暂停'
                          : !scheduler?.running
                            ? '后台未运行'
                            : schedule.next_run_time || '等待调度器计算'}
                      </Descriptions.Item>
                      <Descriptions.Item label='失败重试'>{schedule.payload.max_attempts} 次</Descriptions.Item>
                      <Descriptions.Item label='自动发布'>
                        {schedule.payload.publish_after_refresh ? '是' : '否'}
                      </Descriptions.Item>
                      <Descriptions.Item label='最近执行'>
                        {latestRuns[schedule.task_id]?.[0]
                          ? statusLabels[latestRuns[schedule.task_id][0].status]
                          : '暂无记录'}
                      </Descriptions.Item>
                      <Descriptions.Item label='上次成功'>
                        {latestRuns[schedule.task_id]?.find(run => run.status === 'success')?.finished_at ||
                          '最近 20 次内暂无成功记录'}
                      </Descriptions.Item>
                    </Descriptions>
                  </div>
                  <Switch checked={schedule.enabled} onChange={enabled => toggleSchedule(schedule, enabled)} />
                </div>
                <Space className='mt-2' wrap>
                  <Button
                    icon={<PlayCircleOutlined />}
                    loading={runningId === schedule.task_id}
                    onClick={() => runNow(schedule)}
                  >
                    立即运行
                  </Button>
                  <Button icon={<HistoryOutlined />} onClick={() => showRuns(schedule)}>
                    运行记录
                  </Button>
                  <Button icon={<EditOutlined />} onClick={() => editSchedule(schedule)}>
                    编辑
                  </Button>
                  <Button danger icon={<DeleteOutlined />} onClick={() => removeSchedule(schedule)}>
                    删除
                  </Button>
                </Space>
              </div>
            ))}
          </div>
        )}
      </Spin>

      {runsFor && (
        <div className='mt-6'>
          <div className='mb-2 flex items-center justify-between'>
            <Text strong>“{runsFor.task_name}”的运行记录</Text>
            <Button size='small' loading={loadingRuns} onClick={() => showRuns(runsFor)}>
              刷新记录
            </Button>
          </div>
          <Table<DashboardScheduleRun>
            rowKey='run_id'
            size='small'
            loading={loadingRuns}
            columns={runColumns}
            dataSource={runs}
            pagination={{ pageSize: 8 }}
          />
        </div>
      )}
    </Drawer>
  );
}
