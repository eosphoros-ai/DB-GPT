import {
  createDashboardLiveShare,
  getDashboardLiveShare,
  publishDashboard,
  revokeDashboardLiveShare,
  type DashboardLiveShareStatus,
} from '@/client/api/dashboard';
import { Alert, App, Button, Input, Popconfirm, Segmented, Space } from 'antd';
import { useCallback, useEffect, useState } from 'react';

export default function DashboardLiveShareControl({
  dashboardId,
  currentRevision,
  open = true,
}: {
  dashboardId: string;
  currentRevision: number;
  open?: boolean;
}) {
  const { message } = App.useApp();
  const [status, setStatus] = useState<DashboardLiveShareStatus>({ active: false });
  const [mode, setMode] = useState('live');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    const response = await getDashboardLiveShare(dashboardId);
    if (!response.data.success) throw new Error(response.data.err_msg || '分享状态读取失败');
    setStatus(response.data.data);
  }, [dashboardId]);
  useEffect(() => {
    // Opening the panel starts a remote read; load sets state only after the API resolves.
    if (open) void load().catch(() => setError('分享状态读取失败，请重试'));
  }, [load, open]);
  const run = async (action: 'create' | 'revoke' | 'snapshot') => {
    setBusy(true);
    setError('');
    try {
      if (action === 'revoke') await revokeDashboardLiveShare(dashboardId);
      else if (action === 'snapshot') await publishDashboard(dashboardId, currentRevision, {});
      else await createDashboardLiveShare(dashboardId);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '操作失败，请重试');
    } finally {
      setBusy(false);
    }
  };
  const path = mode === 'live' ? status.share_path : status.snapshot_share_path;
  const url = path && typeof window !== 'undefined' ? (status.public_base_url || window.location.origin) + path : '';
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      message.success('已复制分享链接');
    } catch {
      message.info('请选中下方链接复制');
    }
  };
  return (
    <section
      className='mb-5 rounded-lg border border-[var(--app-border)] bg-[var(--app-surface-muted)] p-4'
      aria-label='持续更新分享'
    >
      <h3 className='mb-3 font-semibold'>分享看板</h3>
      <Segmented
        block
        value={mode}
        onChange={value => {
          setMode(String(value));
          setError('');
        }}
        options={[
          { value: 'live', label: '跟随数据源更新' },
          { value: 'snapshot', label: '固定发布时的数据' },
        ]}
      />
      <p className='my-3 text-sm text-[var(--app-muted)]'>
        {mode === 'live'
          ? '持续更新分享：保持已发布的布局与查询，页面可见时每分钟检查源数据。无需重复发布。'
          : '固定快照：保留发布时的数据，适合提交报告和对比历史。源数据变化不会改变这个快照。'}
      </p>
      {mode === 'live' && status.active && status.expires_at && (
        <p className='mb-2 text-xs text-[var(--app-muted)]'>
          有效至：{new Date(status.expires_at).toLocaleString('zh-CN')}
        </p>
      )}
      {url && (
        <div className='mb-3 flex flex-wrap gap-2'>
          <Input
            className='min-w-0 basis-full sm:basis-auto sm:flex-1'
            aria-label='分享链接'
            value={url}
            readOnly
            onFocus={e => e.currentTarget.select()}
          />
          <Button type='primary' onClick={copy}>
            复制链接
          </Button>
          <Button href={url} target='_blank' rel='noreferrer'>
            打开
          </Button>
        </div>
      )}
      <Space wrap>
        {mode === 'live' && !status.active && (
          <Button type='primary' loading={busy} onClick={() => run('create')}>
            生成持续更新链接
          </Button>
        )}
        {mode === 'live' && status.active && (
          <>
            <Popconfirm title='重新生成后，已发出的旧链接会立即失效。继续？' onConfirm={() => run('create')}>
              <Button loading={busy}>更换链接</Button>
            </Popconfirm>
            <Popconfirm title='停用持续更新分享？' onConfirm={() => run('revoke')}>
              <Button danger disabled={busy}>
                停用链接
              </Button>
            </Popconfirm>
          </>
        )}
        {mode === 'snapshot' && (
          <Button loading={busy} onClick={() => run('snapshot')}>
            发布并生成新快照链接
          </Button>
        )}
        <Button
          disabled={busy}
          onClick={() =>
            load()
              .then(() => setError(''))
              .catch(() => setError('读取分享状态失败'))
          }
        >
          刷新状态
        </Button>
      </Space>
      {mode === 'live' && status.active && !url && (
        <Alert
          className='mt-3'
          type='info'
          showIcon
          message='旧链接仍然有效。打开一次原链接后，回到这里刷新状态即可找回；无需重新生成。'
        />
      )}
      {!status.public_base_url && (
        <p className='mt-2 text-xs text-[var(--app-muted)]'>当前是本机访问地址。外网演示启动后，这里会使用外网地址。</p>
      )}
      {error && <Alert className='mt-3' type='error' showIcon message={error} />}
    </section>
  );
}
