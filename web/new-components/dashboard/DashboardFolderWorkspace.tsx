import {
  createDashboardFolder,
  deleteDashboardFolder,
  renameDashboardFolder,
  type DashboardFolder,
} from '@/client/api/dashboard';
import { dashboardText as dt, useDashboardTranslation } from '@/new-components/dashboard/dashboard-i18n';
import {
  DeleteOutlined,
  EditOutlined,
  FolderAddOutlined,
  FolderOutlined,
  MoreOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { Breadcrumb, Button, Dropdown, Empty, Input, Modal, Popconfirm, message } from 'antd';
import { useState } from 'react';
import styles from './DashboardFolderWorkspace.module.css';

export default function DashboardFolderWorkspace({
  folders,
  value,
  onChange,
  onRefresh,
  foldersOnly = false,
}: {
  foldersOnly?: boolean;
  folders: DashboardFolder[];
  value: string | undefined;
  onChange: (id: string | undefined) => void;
  onRefresh: () => Promise<void>;
}) {
  useDashboardTranslation();
  const [editing, setEditing] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);
  const current = folders.find(f => f.id === value);
  const root = value === 'folders';
  const open = (id = '') => {
    setEditing(id);
    setName(folders.find(f => f.id === id)?.name || '');
  };
  const save = async () => {
    if (busy || !name.trim()) return;
    setBusy(true);
    try {
      const r = editing ? await renameDashboardFolder(editing, name) : await createDashboardFolder(name);
      if (!r.data.success) throw new Error(r.data.err_msg || dt('保存失败'));
      await onRefresh();
      setEditing(null);
      if (!editing) onChange('folders');
    } catch (e) {
      message.error(e instanceof Error ? e.message : dt('保存失败'));
    } finally {
      setBusy(false);
    }
  };
  const menu = (id: string) => ({
    items: [{ key: 'rename', label: dt('重命名'), icon: <EditOutlined /> }],
    onClick: () => open(id),
  });
  const matches = folders.filter(f => f.name.toLowerCase().includes(search.trim().toLowerCase()));
  return (
    <>
      <div className={styles.navigation} aria-label={dt('看板文件夹')}>
        {!foldersOnly && (
          <div className={styles.views}>
            <Button type={root || current ? 'primary' : 'text'} onClick={() => onChange('folders')}>
              {dt('所有文件夹')}
            </Button>
            <Button type={value === undefined ? 'primary' : 'text'} onClick={() => onChange(undefined)}>
              {dt('所有看板')}
            </Button>
            <Button type={value === 'unfiled' ? 'primary' : 'text'} onClick={() => onChange('unfiled')}>
              {dt('未分类')}
            </Button>
          </div>
        )}
        {root ? (
          <Input
            className={styles.search}
            aria-label={dt('搜索文件夹')}
            placeholder={dt('搜索文件夹')}
            prefix={<SearchOutlined />}
            value={search}
            allowClear
            onChange={e => setSearch(e.target.value)}
          />
        ) : (
          <Button icon={<FolderAddOutlined />} onClick={() => open()}>
            {dt('新建文件夹')}
          </Button>
        )}
      </div>
      {root ? (
        <Dropdown
          trigger={['contextMenu']}
          menu={{
            items: [{ key: 'new', label: dt('新建文件夹'), icon: <FolderAddOutlined /> }],
            onClick: () => open(),
          }}
        >
          <div className={styles.grid} aria-label={dt('文件夹列表')}>
            <button
              type='button'
              aria-label={dt('新建文件夹')}
              className={`${styles.tile} ${styles.create}`}
              onClick={() => open()}
            >
              <FolderAddOutlined />
              <strong>{dt('新建文件夹')}</strong>
              <span>{dt('按项目或业务整理看板')}</span>
            </button>
            {matches.map(folder => (
              <Dropdown key={folder.id} trigger={['contextMenu']} menu={menu(folder.id)}>
                <article className={styles.folder} onContextMenu={event => event.stopPropagation()}>
                  <button
                    type='button'
                    className={styles.tile}
                    aria-label={dt('打开文件夹 {{value0}}', { value0: folder.name })}
                    onClick={() => onChange(folder.id)}
                  >
                    <FolderOutlined />
                    <strong title={folder.name}>{folder.name}</strong>
                    <span>
                      {folder.count ?? 0} {dt('个看板')}
                    </span>
                  </button>
                  <Dropdown trigger={['click']} menu={menu(folder.id)}>
                    <Button
                      className={styles.more}
                      type='text'
                      aria-label={dt('{{value0}}文件夹操作', { value0: folder.name })}
                      icon={<MoreOutlined />}
                    />
                  </Dropdown>
                </article>
              </Dropdown>
            ))}
            {search && !matches.length && <Empty description={dt('没有匹配的文件夹')} />}
          </div>
        </Dropdown>
      ) : (
        current && (
          <div className={styles.breadcrumb}>
            <Breadcrumb
              items={[
                { title: <button onClick={() => onChange('folders')}>{dt('所有文件夹')}</button> },
                { title: current.name },
              ]}
            />
            <div className={styles.views}>
              <Button aria-label={dt('重命名文件夹')} icon={<EditOutlined />} onClick={() => open(current.id)} />
              <Popconfirm
                title={dt('删除文件夹？看板会回到未分类，不会删除看板。')}
                onConfirm={async () => {
                  try {
                    const r = await deleteDashboardFolder(current.id);
                    if (!r.data.success) throw new Error(r.data.err_msg || dt('删除失败'));
                    await onRefresh();
                    onChange('folders');
                  } catch (e) {
                    message.error(e instanceof Error ? e.message : dt('删除文件夹失败，请重试'));
                  }
                }}
              >
                <Button aria-label={dt('删除文件夹')} icon={<DeleteOutlined />} />
              </Popconfirm>
            </div>
          </div>
        )
      )}
      <Modal
        title={editing ? dt('重命名文件夹') : dt('新建文件夹')}
        open={editing !== null}
        onCancel={() => {
          if (!busy) setEditing(null);
        }}
        onOk={() => void save()}
        confirmLoading={busy}
        okButtonProps={{ disabled: !name.trim() }}
      >
        <Input
          aria-label={dt('文件夹名称')}
          placeholder={dt('例如：Apple 财务分析')}
          value={name}
          maxLength={80}
          onChange={e => setName(e.target.value)}
          onPressEnter={() => void save()}
        />
      </Modal>
    </>
  );
}
