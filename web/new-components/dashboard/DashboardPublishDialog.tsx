import { getDashboardLiveShare, revokeDashboardLiveShare, type DashboardLiveShareStatus } from '@/client/api/dashboard';
import { CheckCircleFilled, CopyOutlined, FileImageOutlined, SyncOutlined } from '@ant-design/icons';
import { Alert, App, Button, Input, Modal, Popconfirm } from 'antd';
import { useEffect, useState } from 'react';
import styles from './DashboardPublishDialog.module.css';

export type DashboardPublishMode = 'live' | 'snapshot';
export interface DashboardPublishedLinks {
  mode: DashboardPublishMode;
  url: string;
  snapshotUrl: string;
  expiresAt?: string | null;
}

export default function DashboardPublishDialog({
  dashboardId,
  busy,
  onPublish,
  onClose,
}: {
  dashboardId: string;
  busy: boolean;
  onPublish: (mode: DashboardPublishMode) => Promise<DashboardPublishedLinks | undefined>;
  onClose: () => void;
}) {
  const { message } = App.useApp();
  const [mode, setMode] = useState<DashboardPublishMode>('snapshot');
  const [status, setStatus] = useState<DashboardLiveShareStatus | null>(null);
  const [result, setResult] = useState<DashboardPublishedLinks | null>(null);
  const [revoking, setRevoking] = useState(false);
  const currentPath = mode === 'live' ? status?.share_path : status?.snapshot_share_path;
  const currentUrl =
    currentPath && typeof window !== 'undefined'
      ? `${status?.public_base_url || window.location.origin}${currentPath}`
      : '';
  const revoke = async () => {
    setRevoking(true);
    try {
      const response = await revokeDashboardLiveShare(dashboardId);
      if (!response.data.success) throw new Error(response.data.err_msg || '停用失败');
      setStatus(previous => (previous ? { ...previous, active: false, share_path: null } : previous));
      message.success('已停用持续更新链接');
    } catch {
      message.error('停用失败，请重试');
    } finally {
      setRevoking(false);
    }
  };
  useEffect(() => {
    let active = true;
    void getDashboardLiveShare(dashboardId)
      .then(response => {
        if (active && response.data.success) setStatus(response.data.data);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [dashboardId]);
  const publish = async () => {
    const links = await onPublish(mode);
    if (links) setResult(links);
  };
  const copy = async () => {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.url);
      message.success('已复制分享链接');
    } catch {
      message.info('请选中下方链接复制');
    }
  };
  return (
    <Modal
      open
      title={result ? '发布完成' : '发布看板'}
      width={620}
      onCancel={onClose}
      closable={!busy && !revoking}
      maskClosable={!busy && !revoking}
      keyboard={!busy && !revoking}
      footer={
        result ? (
          <Button type='primary' onClick={onClose}>
            完成
          </Button>
        ) : (
          <>
            <Button disabled={busy || revoking} onClick={onClose}>
              取消
            </Button>
            <Button type='primary' loading={busy} disabled={revoking} onClick={() => void publish()}>
              {mode === 'live' ? '发布并跟随更新' : '发布固定快照'}
            </Button>
          </>
        )
      }
    >
      {result ? (
        <div className={styles.result}>
          <CheckCircleFilled className={styles.success} />
          <h3>{result.mode === 'live' ? '数据会随数据源更新' : '已保留此刻的数据'}</h3>
          <p>
            {result.mode === 'live'
              ? '访客打开页面后，每分钟检查数据变化。布局和指标口径保持此次发布的版本。'
              : '这个链接的数据保持不变，适合报告交付与历史对照。'}
          </p>
          <Input
            aria-label='发布分享链接'
            value={result.url}
            readOnly
            onFocus={event => event.currentTarget.select()}
          />
          <div className={styles.actions}>
            <Button icon={<CopyOutlined />} onClick={() => void copy()}>
              复制链接
            </Button>
            <Button type='primary' href={result.url} target='_blank' rel='noreferrer'>
              打开分享页
            </Button>
          </div>
          {result.expiresAt && <small>有效至 {new Date(result.expiresAt).toLocaleString('zh-CN')}</small>}
          {result.mode === 'live' && (
            <a href={result.snapshotUrl} target='_blank' rel='noreferrer'>
              查看本次固定快照
            </a>
          )}
        </div>
      ) : (
        <>
          <p className={styles.intro}>选择访客看到的数据如何更新。发布前会保存草稿并检查查询与筛选。</p>
          <div className={styles.options} role='radiogroup' aria-label='发布数据方式'>
            {(
              [
                {
                  id: 'live',
                  icon: <SyncOutlined />,
                  title: '跟随数据源更新',
                  description: '适合日常看板。数据变化自动呈现，无需重复发布。',
                  detail: '页面打开时，每分钟检查',
                },
                {
                  id: 'snapshot',
                  icon: <FileImageOutlined />,
                  title: '固定发布时的数据',
                  description: '适合汇报与归档。保留本次发布的数值，方便核对。',
                  detail: '固定快照，内容保持不变',
                },
              ] as const
            ).map(option => (
              <button
                key={option.id}
                type='button'
                role='radio'
                aria-checked={mode === option.id}
                disabled={busy || revoking}
                onClick={() => setMode(option.id)}
                className={styles.option}
              >
                <span className={styles.icon}>{option.icon}</span>
                <strong>{option.title}</strong>
                <p>{option.description}</p>
                <small>{option.detail}</small>
              </button>
            ))}
          </div>
          {mode === 'live' && status?.active && (
            <Alert
              className='mt-4'
              type='warning'
              showIcon
              message='重新发布持续更新会生成新链接，原持续更新链接将失效。'
            />
          )}
          {(currentUrl || (mode === 'live' && status?.active)) && (
            <div className={`${styles.actions} mt-4`}>
              {currentUrl && (
                <Button href={currentUrl} target='_blank' rel='noreferrer'>
                  打开当前分享
                </Button>
              )}
              {mode === 'live' && status?.active && (
                <Popconfirm title='停用后，原持续更新链接将无法访问。' onConfirm={revoke}>
                  <Button danger loading={revoking} disabled={busy}>
                    停用持续更新
                  </Button>
                </Popconfirm>
              )}
            </div>
          )}
          <p className={styles.note}>分享页供访客只读查看。编辑草稿不会自动改变已发布的布局。</p>
        </>
      )}
    </Modal>
  );
}
