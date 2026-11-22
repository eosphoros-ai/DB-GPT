import {
  getDashboardEditVersion,
  listDashboardEditVersions,
  listDashboardPublications,
  listDashboardRevisions,
  restoreDashboardEditVersion,
  restoreDashboardRevision,
  revokeDashboardPublication,
  rotateDashboardPublication,
} from '@/client/api';
import { dashboardText as dt, useDashboardTranslation } from '@/new-components/dashboard/dashboard-i18n';
import {
  DashboardEditVersionDetail,
  DashboardEditVersionRecord,
  DashboardRecord,
  DashboardRevisionRecord,
  DashboardShareRecord,
} from '@/types/dashboard';
import { CopyOutlined, EyeOutlined, ReloadOutlined, StopOutlined, UndoOutlined } from '@ant-design/icons';
import { App, Button, Divider, Drawer, Empty, Input, List, Popconfirm, Space, Spin, Tag } from 'antd';
import { useCallback, useEffect, useState, type CSSProperties } from 'react';
import styles from './DashboardLifecyclePanel.module.css';

const editSourceLabels: Record<string, string> = {
  get create() {
    return dt('首次创建');
  },
  get agent_create() {
    return dt('AI 创建');
  },
  get template_create() {
    return dt('模板创建');
  },
  get manual_save() {
    return dt('手动保存');
  },
  get manual_edit() {
    return dt('协作编辑');
  },
  get agent_edit() {
    return dt('AI 修改');
  },
  get ai_edit() {
    return dt('AI 修改');
  },
  get ai_annotation() {
    return dt('AI 提案应用');
  },
  get archive() {
    return dt('归档');
  },
  get unarchive() {
    return dt('取消归档');
  },
  get edit_version_restore() {
    return dt('历史版本恢复');
  },
  get published_revision_restore() {
    return dt('发布快照恢复');
  },
  get migration() {
    return dt('迁移基线');
  },
};

function DashboardVersionPreview({ version }: { version: DashboardEditVersionDetail }) {
  useDashboardTranslation();
  const widgetById = new Map(version.schema.widgets.map(widget => [widget.id, widget]));
  return (
    <div
      className='rounded-xl border border-[var(--app-border)] bg-[var(--app-surface)] p-4'
      data-testid='dashboard-version-preview'
    >
      <div className='flex flex-wrap items-center gap-2'>
        <strong>
          {dt('修订')} {version.revision} {dt('预览')}
        </strong>
        <Tag>{editSourceLabels[version.source] || version.source}</Tag>
        <span className='text-xs text-[var(--app-muted)]'>{dt('只读结构预览，不执行历史 SQL')}</span>
      </div>
      <div className='mt-2 text-sm font-medium'>{version.schema.dashboard.title}</div>
      <div className='mt-1 text-xs text-[var(--app-muted)]'>
        {version.schema.widgets.length} {dt('个组件 ·')} {version.schema.filters.length} {dt('个筛选器')}
      </div>
      <div
        className='mt-3 grid gap-2 rounded-lg border border-dashed border-[var(--app-border)] bg-[var(--app-surface)] p-2'
        style={{ gridTemplateColumns: 'repeat(12, minmax(0, 1fr))', gridAutoRows: 24 }}
      >
        {version.schema.layouts.desktop.map(layout => {
          const widget = widgetById.get(layout.widget_id);
          if (!widget) return null;
          return (
            <div
              key={layout.widget_id}
              className='overflow-hidden rounded border border-[var(--app-border)] bg-[var(--app-surface-muted)] p-2 text-xs text-[var(--app-muted)]'
              style={{
                gridColumn: `${layout.x + 1} / span ${layout.w}`,
                gridRow: `${layout.y + 1} / span ${Math.max(1, Math.min(layout.h, 6))}`,
              }}
              title={`${widget.title} · ${widget.type}`}
            >
              <div className='truncate font-medium text-[var(--app-text)]'>{widget.title}</div>
              <div className='mt-1 uppercase text-[var(--app-muted)]'>{widget.type}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

interface DashboardLifecyclePanelProps {
  themeStyle?: CSSProperties;
  dashboardId: string;
  currentRevision: number;
  open: boolean;
  onClose: () => void;
  onOpenPublish: () => void;
  onRecordChange: (record: DashboardRecord) => void;
}

export default function DashboardLifecyclePanel({
  themeStyle,
  dashboardId,
  currentRevision,
  open,
  onClose,
  onOpenPublish,
  onRecordChange,
}: DashboardLifecyclePanelProps) {
  useDashboardTranslation();
  const { message, modal } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [shares, setShares] = useState<DashboardShareRecord[]>([]);
  const [revisions, setRevisions] = useState<DashboardRevisionRecord[]>([]);
  const [editVersions, setEditVersions] = useState<DashboardEditVersionRecord[]>([]);
  const [previewVersion, setPreviewVersion] = useState<DashboardEditVersionDetail | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [shareResponse, revisionResponse, editVersionResponse] = await Promise.all([
        listDashboardPublications(dashboardId),
        listDashboardRevisions(dashboardId),
        listDashboardEditVersions(dashboardId),
      ]);
      setShares(shareResponse.data.data || []);
      setRevisions(revisionResponse.data.data || []);
      setEditVersions(editVersionResponse.data.data || []);
    } catch (error) {
      message.error(error instanceof Error ? error.message : dt('加载版本记录失败'));
    } finally {
      setLoading(false);
    }
  }, [dashboardId, message]);

  useEffect(() => {
    // Opening the drawer is the external event that starts the remote refresh.
    if (open) void load();
  }, [load, open]);

  const rotate = async (revision: number) => {
    const response = await rotateDashboardPublication(dashboardId, revision, 7 * 24 * 60 * 60);
    const url = `${window.location.origin}${response.data.data.share_path}`;
    modal.success({
      title: dt('已轮换分享链接'),
      content: (
        <div>
          <p className='mb-2 text-sm text-[var(--app-muted)]'>{dt('旧链接已立即失效，新链接将在 7 天后过期。')}</p>
          <Input value={url} readOnly onFocus={event => event.currentTarget.select()} />
          <Button
            className='mt-2'
            icon={<CopyOutlined />}
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(url);
                message.success(dt('已复制'));
              } catch {
                message.info(dt('请选中下方链接复制'));
              }
            }}
          >
            {dt('复制链接')}
          </Button>
        </div>
      ),
    });
    await load();
  };

  const revoke = async (revision: number) => {
    await revokeDashboardPublication(dashboardId, revision);
    message.success(dt('该发布版本的活动链接已撤销'));
    await load();
  };

  const restore = async (revision: number) => {
    try {
      const response = await restoreDashboardRevision(dashboardId, revision, currentRevision);
      onRecordChange(response.data.data);
      message.success(dt('已从发布快照创建新的草稿修订；旧快照保持不变'));
      onClose();
    } catch (error) {
      message.error(error instanceof Error ? error.message : dt('恢复版本失败'));
    }
  };

  const viewEditVersion = async (revision: number) => {
    setPreviewLoading(true);
    try {
      const response = await getDashboardEditVersion(dashboardId, revision);
      setPreviewVersion(response.data.data);
    } catch (error) {
      message.error(error instanceof Error ? error.message : dt('加载编辑修订失败'));
    } finally {
      setPreviewLoading(false);
    }
  };

  const restoreEditVersion = async (revision: number) => {
    try {
      const response = await restoreDashboardEditVersion(dashboardId, revision, currentRevision);
      onRecordChange(response.data.data);
      message.success(dt('已从编辑历史创建新的草稿修订；原修订保持不变'));
      onClose();
    } catch (error) {
      message.error(error instanceof Error ? error.message : dt('恢复编辑修订失败'));
    }
  };

  return (
    <Drawer
      title={dt('编辑版本、发布历史与分享')}
      className={styles.panel}
      rootStyle={themeStyle}
      width={640}
      open={open}
      onClose={onClose}
    >
      <p className='mb-4 text-sm text-[var(--app-muted)]'>
        {dt('合计保留最近 20 个版本，包含当前编辑和最新发布版本。编号持续递增，超期版本及对应固定链接会失效。')}
      </p>
      <Button className='mb-5' type='primary' onClick={onOpenPublish}>
        {dt('发布与分享')}
      </Button>
      <Spin spinning={loading}>
        <div className='mb-3 flex items-center'>
          <strong>{dt('编辑修订')}</strong>
          <Tag className='ml-2' color='blue'>
            {dt('当前')} {currentRevision}
          </Tag>
          <Button className='ml-auto' type='text' icon={<ReloadOutlined />} onClick={load}>
            {dt('刷新')}
          </Button>
        </div>
        {editVersions.length ? (
          <List
            dataSource={editVersions}
            renderItem={version => (
              <List.Item
                actions={[
                  <Button
                    key='view'
                    size='small'
                    icon={<EyeOutlined />}
                    onClick={() => viewEditVersion(version.revision)}
                  >
                    {dt('查看')}
                  </Button>,
                  <Popconfirm
                    key='restore-edit'
                    title={dt('恢复这个编辑修订？')}
                    description={dt('系统会追加一个新修订，不会覆盖现有修订或发布快照。')}
                    disabled={version.revision === currentRevision}
                    onConfirm={() => restoreEditVersion(version.revision)}
                  >
                    <Button size='small' disabled={version.revision === currentRevision} icon={<UndoOutlined />}>
                      {dt('恢复为新草稿')}
                    </Button>
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  title={
                    <Space wrap>
                      <span>
                        {dt('编辑修订')} {version.revision}
                      </span>
                      {version.revision === currentRevision && <Tag color='blue'>{dt('当前')}</Tag>}
                      <Tag>{editSourceLabels[version.source] || version.source}</Tag>
                    </Space>
                  }
                  description={`${version.actor_id} · ${new Date(version.created_at).toLocaleString()}`}
                />
              </List.Item>
            )}
          />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={dt('暂无可回看的编辑修订')} />
        )}
        <Spin spinning={previewLoading}>{previewVersion && <DashboardVersionPreview version={previewVersion} />}</Spin>

        <Divider />
        <div className='mb-3 flex items-center'>
          <strong>{dt('发布修订')}</strong>
        </div>
        {revisions.length ? (
          <List
            dataSource={revisions}
            renderItem={revision => (
              <List.Item
                actions={[
                  <Popconfirm
                    key='restore'
                    title={dt('恢复这个发布版本？')}
                    description={dt('系统会创建一个新的草稿修订，不会覆盖或篡改旧发布快照。')}
                    onConfirm={() => restore(revision.published_revision)}
                  >
                    <Button size='small' icon={<UndoOutlined />}>
                      {dt('恢复为新草稿')}
                    </Button>
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  title={dt('发布版本 {{value0}}', { value0: revision.published_revision })}
                  description={new Date(revision.published_at).toLocaleString()}
                />
              </List.Item>
            )}
          />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={dt('尚未发布过')} />
        )}

        <div className='mb-3 mt-8 font-semibold'>{dt('分享链接记录')}</div>
        {shares.length ? (
          <List
            dataSource={shares}
            renderItem={share => (
              <List.Item
                actions={[
                  <Button key='rotate' size='small' onClick={() => rotate(share.published_revision)}>
                    {share.active ? dt('轮换') : dt('重新签发')}
                  </Button>,
                  <Popconfirm
                    key='revoke'
                    title={dt('立即撤销活动链接？')}
                    onConfirm={() => revoke(share.published_revision)}
                  >
                    <Button size='small' danger disabled={!share.active} icon={<StopOutlined />}>
                      {dt('撤销')}
                    </Button>
                  </Popconfirm>,
                ]}
              >
                <Space direction='vertical' size={2}>
                  <Space>
                    <span>
                      {dt('发布版本')} {share.published_revision}
                    </span>
                    <Tag color={share.active ? 'green' : 'default'}>{share.active ? dt('有效') : dt('已失效')}</Tag>
                  </Space>
                  <span className='text-xs text-[var(--app-muted)]'>
                    {dt('创建：')}
                    {new Date(share.created_at).toLocaleString()}
                  </span>
                  <span className='text-xs text-[var(--app-muted)]'>
                    {dt('到期：')}
                    {share.expires_at ? new Date(share.expires_at).toLocaleString() : dt('长期有效')}
                  </span>
                </Space>
              </List.Item>
            )}
          />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={dt('暂无分享记录')} />
        )}
      </Spin>
    </Drawer>
  );
}
