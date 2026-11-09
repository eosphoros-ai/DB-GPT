import {
  createDashboardFolder,
  deleteDashboardFolder,
  renameDashboardFolder,
  type DashboardFolder,
} from '@/client/api/dashboard';
import { dashboardText as dt, useDashboardTranslation } from '@/new-components/dashboard/dashboard-i18n';
import { DeleteOutlined, EditOutlined, FolderAddOutlined, FolderOutlined } from '@ant-design/icons';
import { Button, Dropdown, Input, Modal, Popconfirm, Space, message } from 'antd';
import { useState } from 'react';

export default function DashboardFolderBar({
  folders,
  value,
  onChange,
  onRefresh,
}: {
  folders: DashboardFolder[];
  value: string | undefined;
  onChange: (id: string | undefined) => void;
  onRefresh: () => Promise<void>;
}) {
  useDashboardTranslation();
  const [editing, setEditing] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const open = (id = '') => {
    setEditing(id);
    setName(folders.find(f => f.id === id)?.name || '');
  };
  const save = async () => {
    setBusy(true);
    try {
      const r = editing ? await renameDashboardFolder(editing, name) : await createDashboardFolder(name);
      if (!r.data.success) throw new Error(r.data.err_msg || dt('保存失败'));
      await onRefresh();
      setEditing(null);
      onChange(r.data.data.id);
    } catch (e) {
      message.error(e instanceof Error ? e.message : dt('保存失败'));
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <Dropdown
        trigger={['contextMenu']}
        menu={{ items: [{ key: 'new', label: dt('新建文件夹'), icon: <FolderAddOutlined /> }], onClick: () => open() }}
      >
        <div className='mb-5 min-h-12 rounded-lg border border-[var(--app-border)] p-3' aria-label={dt('看板文件夹')}>
          <Space wrap>
            <Button type={!value ? 'primary' : 'text'} onClick={() => onChange(undefined)}>
              {dt('所有文件夹')}
            </Button>
            <Button type={value === 'unfiled' ? 'primary' : 'text'} onClick={() => onChange('unfiled')}>
              {dt('未分类')}
            </Button>
            {folders.map(folder => (
              <Dropdown
                key={folder.id}
                trigger={['contextMenu']}
                menu={{
                  items: [{ key: 'rename', label: dt('重命名'), icon: <EditOutlined /> }],
                  onClick: () => open(folder.id),
                }}
              >
                <Button
                  aria-label={folder.name}
                  className='max-w-[190px]'
                  title={folder.name}
                  type={value === folder.id ? 'primary' : 'text'}
                  icon={<FolderOutlined />}
                  onClick={() => onChange(folder.id)}
                >
                  <span className='truncate'>{folder.name}</span>
                </Button>
              </Dropdown>
            ))}
            <Button aria-label={dt('新建文件夹')} icon={<FolderAddOutlined />} onClick={() => open()}>
              {dt('新建文件夹')}
            </Button>
            {value && value !== 'unfiled' && (
              <>
                <Button aria-label={dt('重命名文件夹')} icon={<EditOutlined />} onClick={() => open(value)} />
                <Popconfirm
                  title={dt('删除文件夹？看板会回到未分类，不会删除看板。')}
                  onConfirm={async () => {
                    try {
                      await deleteDashboardFolder(value);
                      await onRefresh();
                      onChange(undefined);
                    } catch {
                      message.error(dt('删除失败，请重试'));
                    }
                  }}
                >
                  <Button aria-label={dt('删除文件夹')} icon={<DeleteOutlined />} />
                </Popconfirm>
              </>
            )}
          </Space>
        </div>
      </Dropdown>
      <Modal
        title={editing ? dt('重命名文件夹') : dt('新建文件夹')}
        open={editing !== null}
        onCancel={() => setEditing(null)}
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
          onPressEnter={() => {
            if (name.trim()) void save();
          }}
        />
      </Modal>
    </>
  );
}
