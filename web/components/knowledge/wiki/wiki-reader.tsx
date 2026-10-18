/**
 * Wiki page reader with inline editing (optimistic lock + 409 conflict flow)
 * and revision drawer triggering.
 */
import { updateWikiPage } from '@/client/api';
import { WikiPage } from '@/types/wiki';
import { DeleteOutlined, EditOutlined, HistoryOutlined, ReloadOutlined, RollbackOutlined } from '@ant-design/icons';
import { Button, Empty, Input, Popconfirm, Spin, Tag, message } from 'antd';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { EDIT_SOURCE_LABELS } from './edit-source';
import WikiMarkdown, { WikiPageTypeTag } from './wiki-markdown';

interface WikiReaderProps {
  page: WikiPage | null;
  loading: boolean;
  onReload: (slug: string) => void;
  onOpenRevisions: () => void;
  onDelete: (slug: string) => void;
  onOpenSourceDoc: (documentId: number) => void;
}

export default function WikiReader({
  page,
  loading,
  onReload,
  onOpenRevisions,
  onDelete,
  onOpenSourceDoc,
}: WikiReaderProps) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({ title: '', summary: '', content: '' });
  const [editBaseVersion, setEditBaseVersion] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [conflict, setConflict] = useState<number | null>(null);

  const startEdit = () => {
    if (!page) return;
    setEditForm({ title: page.title, summary: page.summary || '', content: page.content || '' });
    setEditBaseVersion(page.version);
    setConflict(null);
    setEditing(true);
  };

  const save = async (overwriteVersion?: number) => {
    if (!page) return;
    setSaving(true);
    try {
      const data = await updateWikiPage(page.space_id, page.slug, {
        title: editForm.title,
        summary: editForm.summary,
        content: editForm.content,
        version: overwriteVersion ?? editBaseVersion ?? undefined,
      });
      setEditing(false);
      setConflict(null);
      message.success(t('wiki_save_success'));
      onReload(page.slug);
      void data;
    } catch (error: any) {
      const status = error?.response?.status;
      const detail = error?.response?.data?.detail ?? error?.response?.data?.err_msg;
      if (status === 409) {
        const currentVersion = typeof detail === 'object' && detail?.current_version ? detail.current_version : null;
        setConflict(currentVersion);
        message.error(t('wiki_version_conflict'));
      } else {
        message.error(typeof detail === 'string' ? detail : t('wiki_save_failed'));
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className='flex-1 flex items-center justify-center'>
        <Spin size='large' />
      </div>
    );
  }
  if (!page) {
    return (
      <div className='flex-1 flex items-center justify-center'>
        <Empty description={t('wiki_select_page_hint')} />
      </div>
    );
  }

  const sourceLabel = EDIT_SOURCE_LABELS[page.last_edit_source] || EDIT_SOURCE_LABELS.pipeline;

  return (
    <div className='flex-1 flex flex-col overflow-hidden'>
      {/* Header actions */}
      <div className='px-6 py-2.5 flex items-center gap-2 border-b dark:border-gray-700 bg-white dark:bg-[#232734]'>
        <WikiPageTypeTag type={page.page_type} />
        <Tag color='geekblue'>v{page.version}</Tag>
        <Tag color={sourceLabel.antdColor}>{t(sourceLabel.key)}</Tag>
        <span className='ml-auto flex gap-1.5'>
          {editing ? (
            <>
              <Button size='small' onClick={() => setEditing(false)} disabled={saving}>
                {t('cancel')}
              </Button>
              <Button size='small' type='primary' loading={saving} onClick={() => save()}>
                {t('wiki_save')}
              </Button>
            </>
          ) : (
            <>
              <Button size='small' icon={<EditOutlined />} onClick={startEdit}>
                {t('wiki_edit')}
              </Button>
              <Button size='small' icon={<HistoryOutlined />} onClick={onOpenRevisions}>
                {t('wiki_history')}
              </Button>
              <Popconfirm title={t('wiki_delete_confirm')} onConfirm={() => onDelete(page.slug)}>
                <Button size='small' danger icon={<DeleteOutlined />} />
              </Popconfirm>
            </>
          )}
        </span>
      </div>

      {/* Conflict alert */}
      {editing && conflict !== null && (
        <div className='mx-6 mt-3 px-3 py-2 rounded-md border border-orange-300 bg-orange-50 dark:bg-orange-900/20 dark:border-orange-700 text-sm text-orange-700 dark:text-orange-300 flex items-center gap-3'>
          <span>{t('wiki_version_conflict_desc', { current: conflict, base: editBaseVersion || 0 })}</span>
          <Button size='small' icon={<ReloadOutlined />} onClick={() => onReload(page.slug)}>
            {t('wiki_reload_latest')}
          </Button>
          <Button size='small' danger icon={<RollbackOutlined />} onClick={() => save(conflict)}>
            {t('wiki_overwrite')}
          </Button>
        </div>
      )}

      {/* Editor or content */}
      <div className='flex-1 overflow-auto px-6 md:px-10 py-5'>
        {editing ? (
          <div className='max-w-[860px] flex flex-col gap-3'>
            <Input
              value={editForm.title}
              onChange={e => setEditForm({ ...editForm, title: e.target.value })}
              placeholder={t('wiki_title_placeholder')}
            />
            <Input
              value={editForm.summary}
              onChange={e => setEditForm({ ...editForm, summary: e.target.value })}
              placeholder={t('wiki_summary_placeholder')}
            />
            <Input.TextArea
              value={editForm.content}
              onChange={e => setEditForm({ ...editForm, content: e.target.value })}
              rows={22}
              className='font-mono text-[13px]'
            />
          </div>
        ) : (
          <div className='max-w-[860px]'>
            <h1 className='text-2xl font-bold text-gray-900 dark:text-gray-100 m-0'>{page.title}</h1>
            {page.aliases && page.aliases.length > 0 && (
              <div className='mt-1 flex gap-1.5 flex-wrap'>
                {page.aliases.filter(Boolean).map(alias => (
                  <Tag key={alias}>{alias}</Tag>
                ))}
              </div>
            )}
            {page.summary && <p className='text-sm text-gray-500 dark:text-gray-400 mt-3'>{page.summary}</p>}
            <div className='mt-4'>
              {/* lazy import kept simple: direct import at top */}
              <WikiMarkdown content={page.content} onLinkClick={slug => onReload(slug)} />
            </div>

            {/* Backlinks + source docs */}
            <div className='mt-10 pt-4 border-t dark:border-gray-700 text-sm flex flex-col gap-2'>
              {page.in_links && page.in_links.length > 0 && (
                <div className='flex gap-2 items-start'>
                  <span className='text-gray-400 flex-none w-20'>{t('wiki_backlinks')}</span>
                  <div className='flex gap-2 flex-wrap'>
                    {page.in_links.map(slug => (
                      <a
                        key={slug}
                        className='text-[#4da3ff] border-b border-dashed border-[#4da3ff]/50 cursor-pointer'
                        onClick={() => onReload(slug)}
                      >
                        {slug}
                      </a>
                    ))}
                  </div>
                </div>
              )}
              {page.source_refs && page.source_refs.length > 0 && (
                <div className='flex gap-2 items-start'>
                  <span className='text-gray-400 flex-none w-20'>{t('wiki_source_docs')}</span>
                  <div className='flex gap-2 flex-wrap'>
                    {page.source_refs.map(ref => (
                      <a
                        key={ref.document_id}
                        className='text-[#4da3ff] border-b border-dashed border-[#4da3ff]/50 cursor-pointer'
                        onClick={() => onOpenSourceDoc(ref.document_id)}
                      >
                        📄 {ref.doc_name}
                      </a>
                    ))}
                  </div>
                </div>
              )}
              {page.gmt_modified && (
                <div className='text-xs text-gray-400'>
                  {t('wiki_updated_at')}: {page.gmt_modified.replace('T', ' ').slice(0, 16)}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
