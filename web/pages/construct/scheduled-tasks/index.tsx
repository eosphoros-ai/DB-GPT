import { useScheduledTask } from '@/hooks/use-scheduled-task';
import ConstructLayout from '@/new-components/layout/Construct';
import EditScheduledTaskDrawer from '@/new-components/scheduled-task/EditScheduledTaskDrawer';
import type { TaskResponse } from '@/types/scheduled-task';
import {
  ClockCircleOutlined,
  DeleteOutlined,
  EditOutlined,
  HistoryOutlined,
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { Button, Input, Popconfirm, Segmented, Spin, Switch, Tooltip, message } from 'antd';
import dayjs from 'dayjs';
import { useRouter } from 'next/router';
import { useCallback, useEffect, useMemo, useState } from 'react';

/** 格式化 ISO 时间字符串，去掉时区后缀，返回友好格式 */
function fmtTime(iso?: string | null): string | null {
  if (!iso) return null;
  const d = dayjs(iso);
  return d.isValid() ? d.format('YYYY-MM-DD HH:mm:ss') : iso;
}

type StatusFilter = 'all' | 'enabled' | 'disabled';

function ScheduledTasks() {
  const router = useRouter();
  const { listTasks, toggleTask, deleteTask } = useScheduledTask();
  const [tasks, setTasks] = useState<TaskResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');

  // 编辑抽屉状态
  const [editOpen, setEditOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<TaskResponse | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setTasks(await listTasks());
    } catch (e: any) {
      message.error(e?.message ?? '加载任务失败');
    } finally {
      setLoading(false);
    }
  }, [listTasks]);

  useEffect(() => {
    reload();
  }, [reload]);

  const onToggle = async (task: TaskResponse, enabled: boolean) => {
    try {
      await toggleTask(task.task_id, enabled);
      message.success(enabled ? '已启用' : '已暂停');
      reload();
    } catch (e: any) {
      message.error(e?.message ?? '操作失败');
    }
  };

  const onDelete = async (task: TaskResponse) => {
    try {
      await deleteTask(task.task_id);
      message.success('已删除');
      reload();
    } catch (e: any) {
      message.error(e?.message ?? '删除失败');
    }
  };

  const onEdit = (task: TaskResponse, e?: React.MouseEvent) => {
    e?.stopPropagation();
    setEditingTask(task);
    setEditOpen(true);
  };

  const onEditSaved = () => {
    reload();
  };

  /* ─── 筛选 ─── */
  const counters = useMemo(() => {
    const enabled = tasks.filter(t => t.enabled).length;
    return { enabled, disabled: tasks.length - enabled };
  }, [tasks]);

  const filteredTasks = useMemo(() => {
    const q = search.trim().toLowerCase();
    return tasks.filter(t => {
      // 状态筛选
      if (statusFilter === 'enabled' && !t.enabled) return false;
      if (statusFilter === 'disabled' && t.enabled) return false;
      // 搜索筛选
      if (!q) return true;
      return (
        t.task_name.toLowerCase().includes(q) ||
        (t.description ?? '').toLowerCase().includes(q) ||
        t.cron_expression.toLowerCase().includes(q)
      );
    });
  }, [tasks, search, statusFilter]);

  const hasAny = tasks.length > 0;
  const showEmptyFilter = hasAny && filteredTasks.length === 0;

  return (
    <ConstructLayout className='scrollable-tabs'>
      <div className='relative w-full bg-gradient-to-b from-[#f7f8fc] via-white to-[#f7f8fc] dark:from-[#1c2333] dark:via-[#1c2333] dark:to-[#161b29]'>
        <div className='max-w-[1400px] mx-auto p-4 md:p-6 lg:p-8'>
          {/* ───────────── HERO HEADER ───────────── */}
          <div className='mb-7'>
            <div className='flex items-start justify-between gap-4 flex-wrap mb-2'>
              <div>
                <h1 className='text-[26px] leading-tight font-bold text-gray-900 dark:text-white mb-1 flex items-center gap-2.5'>
                  <span className='inline-flex items-center justify-center w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-600 text-white shadow-[0_4px_14px_-4px_rgba(6,182,212,0.5)]'>
                    <ClockCircleOutlined className='text-lg' />
                  </span>
                  定时任务
                </h1>
                <p className='text-sm text-gray-500 dark:text-gray-400 ml-[46px]'>
                  管理定时执行的对话任务，支持自定义执行频率、启停控制和执行历史追溯
                </p>
              </div>

              <Button icon={<ReloadOutlined />} onClick={reload} loading={loading} className='h-9'>
                刷新
              </Button>
            </div>
          </div>

          {/* ───────────── TOOLBAR ───────────── */}
          <div className='flex items-center gap-3 mb-6 flex-wrap'>
            <Input
              prefix={<SearchOutlined className='text-gray-400' />}
              placeholder='搜索任务名称、描述...'
              value={search}
              onChange={e => setSearch(e.target.value)}
              allowClear
              className='w-[280px] h-[36px] backdrop-filter backdrop-blur-lg bg-white bg-opacity-60 border border-gray-200 rounded-lg dark:border-[#6f7f95] dark:bg-[#6f7f95] dark:bg-opacity-60'
            />

            <Segmented
              value={statusFilter}
              onChange={v => setStatusFilter(v as StatusFilter)}
              options={[
                { label: '全部', value: 'all' },
                {
                  label: (
                    <span className='inline-flex items-center gap-1'>
                      已启用
                      {counters.enabled > 0 && (
                        <span className='inline-flex items-center justify-center min-w-[16px] h-4 px-1 rounded-full text-[10px] font-medium bg-emerald-500 text-white'>
                          {counters.enabled}
                        </span>
                      )}
                    </span>
                  ),
                  value: 'enabled',
                },
                {
                  label: (
                    <span className='inline-flex items-center gap-1'>
                      已暂停
                      {counters.disabled > 0 && (
                        <span className='inline-flex items-center justify-center min-w-[16px] h-4 px-1 rounded-full text-[10px] font-medium bg-gray-400 text-white'>
                          {counters.disabled}
                        </span>
                      )}
                    </span>
                  ),
                  value: 'disabled',
                },
              ]}
              className='!bg-white/60 backdrop-blur-md rounded-lg dark:!bg-[#6f7f95]/40'
            />
          </div>

          {/* ───────────── LIST / EMPTY STATE ───────────── */}
          <Spin spinning={loading}>
            {!hasAny && !loading ? (
              <div className='flex flex-col items-center justify-center text-center py-24'>
                <div className='w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-100 to-cyan-100 dark:from-blue-900/30 dark:to-cyan-900/30 flex items-center justify-center mb-5'>
                  <ClockCircleOutlined className='text-3xl text-blue-500' />
                </div>
                <h3 className='text-lg font-semibold text-gray-800 dark:text-gray-100 mb-1'>暂无定时任务</h3>
                <p className='text-sm text-gray-500 dark:text-gray-400 max-w-md mb-5'>
                  在对话完成后，点击右侧面板的「保存为定时任务」按钮，即可创建定时执行的对话任务
                </p>
              </div>
            ) : showEmptyFilter ? (
              <div className='flex flex-col items-center justify-center text-center py-20'>
                <SearchOutlined className='text-3xl text-gray-300 dark:text-gray-600 mb-3' />
                <p className='text-sm text-gray-500 dark:text-gray-400 mb-3'>没有匹配的任务</p>
                <Button
                  size='small'
                  onClick={() => {
                    setSearch('');
                    setStatusFilter('all');
                  }}
                >
                  清除筛选
                </Button>
              </div>
            ) : (
              <div className='rounded-2xl border border-white/80 bg-white/80 backdrop-blur-lg shadow-[0_2px_12px_-4px_rgba(15,23,42,0.08)] dark:border-[#3a4456] dark:bg-[#2b303d]/70 overflow-hidden'>
                {/* 表头 */}
                <div className='grid grid-cols-[minmax(200px,1.4fr)_100px_150px_180px_120px_70px_130px] gap-3 px-5 py-3 text-[12px] font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider border-b border-gray-100 dark:border-gray-700/50 bg-gray-50/60 dark:bg-[#1a1f2e]/60'>
                  <div>任务名称</div>
                  <div className='text-center'>状态</div>
                  <div>Cron 表达式</div>
                  <div>下次执行</div>
                  <div>创建人</div>
                  <div className='text-center'>启用</div>
                  <div className='text-right'>操作</div>
                </div>

                {/* 列表行 */}
                {filteredTasks.map(task => (
                  <TaskRow
                    key={task.task_id}
                    task={task}
                    onToggle={onToggle}
                    onEdit={onEdit}
                    onDelete={onDelete}
                    onClick={() => router.push(`/construct/scheduled-tasks/${task.task_id}`)}
                  />
                ))}

                {/* 底部统计 */}
                {hasAny && (
                  <div className='px-5 py-3 border-t border-gray-100 dark:border-gray-700/50 text-[13px] text-gray-400 dark:text-gray-500'>
                    共 {filteredTasks.length} 条
                    {filteredTasks.length !== tasks.length && ` / 总计 ${tasks.length} 条`}
                  </div>
                )}
              </div>
            )}
          </Spin>
        </div>

        {/* ───────────── 编辑抽屉 ───────────── */}
        <EditScheduledTaskDrawer
          open={editOpen}
          onClose={() => {
            setEditOpen(false);
            setEditingTask(null);
          }}
          task={editingTask}
          onSaved={onEditSaved}
        />
      </div>
    </ConstructLayout>
  );
}

/* ─────────────────────────────────────────────────────────────────
   TaskRow — 单行任务列表项
   ────────────────────────────────────────────────────────────────── */

interface TaskRowProps {
  task: TaskResponse;
  onToggle: (task: TaskResponse, enabled: boolean) => void;
  onEdit: (task: TaskResponse, e?: React.MouseEvent) => void;
  onDelete: (task: TaskResponse) => void;
  onClick: () => void;
}

const TaskRow: React.FC<TaskRowProps> = ({ task, onToggle, onEdit, onDelete, onClick }) => {
  const enabled = task.enabled;

  return (
    <div
      className={`grid grid-cols-[minmax(200px,1.4fr)_100px_150px_180px_120px_70px_130px] gap-3 px-5 py-4 items-center border-b border-gray-50 dark:border-gray-700/30 cursor-pointer transition-colors hover:bg-gray-50/80 dark:hover:bg-white/[0.03] ${!enabled ? 'opacity-60' : ''}`}
      onClick={onClick}
      role='button'
      tabIndex={0}
      onKeyDown={e => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick();
        }
      }}
    >
      {/* 任务名称 + 描述 */}
      <div className='flex items-center gap-3 min-w-0'>
        <div
          className={`flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center text-white shadow-sm ${
            enabled
              ? 'bg-gradient-to-br from-blue-500 to-cyan-600'
              : 'bg-gradient-to-br from-gray-400 to-gray-500'
          }`}
        >
          <ClockCircleOutlined className='text-sm' />
        </div>
        <div className='min-w-0'>
          <div className='text-[14px] font-medium text-gray-900 dark:text-gray-100 truncate'>{task.task_name}</div>
          {task.description && (
            <div className='text-[11px] text-gray-400 dark:text-gray-500 truncate'>{task.description}</div>
          )}
        </div>
      </div>

      {/* 状态 */}
      <div className='text-center'>
        {enabled ? (
          <span className='inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'>
            <span className='w-1.5 h-1.5 rounded-full bg-emerald-500' />
            已启用
          </span>
        ) : (
          <span className='inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-gray-100 text-gray-500 dark:bg-gray-700/40 dark:text-gray-400'>
            <span className='w-1.5 h-1.5 rounded-full bg-gray-400' />
            已暂停
          </span>
        )}
      </div>

      {/* Cron 表达式 */}
      <div>
        <code className='text-[13px] text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-700/40 px-2 py-0.5 rounded font-mono'>
          {task.cron_expression}
        </code>
      </div>

      {/* 下次执行 */}
      <div className='text-[13px]'>
        {fmtTime(task.next_run_time) ? (
          <span className='text-cyan-600 dark:text-cyan-400 font-medium'>{fmtTime(task.next_run_time)}</span>
        ) : (
          <span className='text-gray-400 dark:text-gray-500'>-</span>
        )}
      </div>

      {/* 创建人 */}
      <div className='text-[13px] text-gray-500 dark:text-gray-400 truncate'>{task.user_name ?? '-'}</div>

      {/* 启用开关 */}
      <div className='flex justify-center' onClick={e => e.stopPropagation()}>
        <Switch
          checked={task.enabled}
          size='small'
          className='scheduled-switch'
          onChange={checked => onToggle(task, checked)}
        />
      </div>

      {/* 操作 */}
      <div className='flex items-center justify-end gap-1' onClick={e => e.stopPropagation()}>
        <Tooltip title='编辑'>
          <Button
            type='text'
            size='small'
            icon={<EditOutlined />}
            className='text-gray-400 hover:!text-cyan-600 hover:!bg-cyan-50 dark:hover:!bg-cyan-900/30'
            onClick={e => onEdit(task, e as unknown as React.MouseEvent)}
          />
        </Tooltip>
        <Tooltip title='执行历史'>
          <Button
            type='text'
            size='small'
            icon={<HistoryOutlined />}
            className='text-gray-400 hover:!text-cyan-600 hover:!bg-cyan-50 dark:hover:!bg-cyan-900/30'
            onClick={onClick}
          />
        </Tooltip>
        <Popconfirm
          title={`确认删除「${task.task_name}」？`}
          onConfirm={() => onDelete(task)}
          okText='删除'
          cancelText='取消'
          okButtonProps={{ danger: true }}
        >
          <Tooltip title='删除'>
            <Button
              type='text'
              size='small'
              danger
              icon={<DeleteOutlined />}
              className='hover:!bg-red-50 dark:hover:!bg-red-900/30'
            />
          </Tooltip>
        </Popconfirm>
      </div>
    </div>
  );
};

export default ScheduledTasks;
