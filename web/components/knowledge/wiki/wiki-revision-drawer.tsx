/**
 * Wiki revision history drawer: version list + incremental/cumulative/raw
 * diff views + revert-as-new-edit. Diff rendering ports WeKnora's unified
 * marker-based line diff.
 */
import { apiInterceptors, getWikiRevision, listWikiRevisions, revertWikiPage } from '@/client/api';
import { WikiPage, WikiRevision } from '@/types/wiki';
import { diffWikiRevision } from '@/utils/wiki/revision-diff';
import { RollbackOutlined } from '@ant-design/icons';
import { Button, Drawer, Segmented, Spin, Tag, message } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { EDIT_SOURCE_LABELS } from './edit-source';

interface WikiRevisionDrawerProps {
  open: boolean;
  page: WikiPage | null;
  onClose: () => void;
  onReverted: (slug: string) => void;
}

type DiffMode = 'incremental' | 'current' | 'raw';

export default function WikiRevisionDrawer({ open, page, onClose, onReverted }: WikiRevisionDrawerProps) {
  const { t } = useTranslation();
  const [revisions, setRevisions] = useState<WikiRevision[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [mode, setMode] = useState<DiffMode>('incremental');
  const [listLoading, setListLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [reverting, setReverting] = useState(false);
  const [currentSnapshot, setCurrentSnapshot] = useState<WikiRevision | null>(null);
  const [detailSeq, setDetailSeq] = useState(0);

  // Load list when opening
  useEffect(() => {
    if (!open || !page) return;
    setRevisions([]);
    setSelectedVersion(null);
    setMode('incremental');
    (async () => {
      setListLoading(true);
      const [, data] = await apiInterceptors(listWikiRevisions(page.space_id, page.slug));
      if (data) setRevisions(data.revisions || []);
      setListLoading(false);
      if (page.version > 1) setSelectedVersion(page.version - 1);
    })();
  }, [open, page?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Build current snapshot when page changes
  useEffect(() => {
    if (!page) {
      setCurrentSnapshot(null);
      return;
    }
    setCurrentSnapshot({
      version: page.version,
      title: page.title,
      summary: page.summary,
      content: page.content,
      edit_source: page.last_edit_source,
    } as WikiRevision);
  }, [page?.id, page?.version]); // eslint-disable-line react-hooks/exhaustive-deps

  const fromSnapshot = useMemo(() => {
    if (selectedVersion === null) return null;
    if (mode === 'current') {
      return revisions.find(r => r.version === selectedVersion) || null;
    }
    if (selectedVersion <= 1) {
      return { version: 0, title: '', summary: '', content: '' } as WikiRevision;
    }
    return revisions.find(r => r.version === selectedVersion - 1) || null;
  }, [mode, selectedVersion, revisions]);

  const toSnapshot = useMemo(() => {
    if (selectedVersion === null) return null;
    if (mode === 'current') return currentSnapshot;
    return revisions.find(r => r.version === selectedVersion) || null;
  }, [mode, selectedVersion, revisions, currentSnapshot]);

  // Load missing contents for the diff pair
  useEffect(() => {
    if (selectedVersion === null || !page) return;
    const seq = detailSeq + 1;
    setDetailSeq(seq);
    (async () => {
      setDetailLoading(true);
      try {
        const targets = [fromSnapshot, toSnapshot].filter(
          (snap): snap is WikiRevision => !!snap && snap.content === undefined,
        );
        for (const target of targets) {
          const [, data] = await apiInterceptors(getWikiRevision(page.space_id, page.slug, target.version));
          if (data && detailSeq === seq) {
            setRevisions(prev =>
              prev.map(rev =>
                rev.version === data.version
                  ? { ...rev, content: data.content, title: data.title, summary: data.summary, aliases: data.aliases }
                  : rev,
              ),
            );
          }
        }
      } finally {
        if (detailSeq === seq) setDetailLoading(false);
      }
    })();
  }, [selectedVersion, fromSnapshot?.version, toSnapshot?.version]); // eslint-disable-line react-hooks/exhaustive-deps

  const sections = useMemo(() => {
    if (mode === 'raw' || !fromSnapshot || !toSnapshot) return null;
    return diffWikiRevision(fromSnapshot, toSnapshot);
  }, [mode, fromSnapshot, toSnapshot]);

  const handleRevert = async () => {
    if (!page || selectedVersion === null) return;
    setReverting(true);
    const [err] = await apiInterceptors(revertWikiPage(page.space_id, page.slug, selectedVersion));
    setReverting(false);
    if (err) {
      message.error(t('wiki_revert_failed'));
      return;
    }
    message.success(t('wiki_revert_success'));
    onReverted(page.slug);
  };

  const renderLines = (lines: { type: string; text: string }[]) =>
    lines.map((line, index) => (
      <div
        key={index}
        className={`font-mono text-[12.5px] leading-[1.75] whitespace-pre-wrap break-all px-2 rounded ${
          line.type === 'add'
            ? 'bg-emerald-500/10 text-emerald-300'
            : line.type === 'del'
              ? 'bg-red-500/10 text-red-300'
              : 'text-gray-500'
        }`}
      >
        {line.type === 'add' ? '+' : line.type === 'del' ? '-' : ' '}
        {line.text}
      </div>
    ));

  return (
    <Drawer
      title={`${t('wiki_revision_history')} · ${page?.title || ''}`}
      open={open}
      width={780}
      onClose={onClose}
      destroyOnClose
    >
      <div className='flex gap-3 h-full min-h-0'>
        {/* Version list */}
        <div className='w-[230px] flex-none border-r dark:border-gray-700 pr-3 overflow-auto'>
          {page && (
            <div className={`px-3 py-2 rounded-lg mb-1 border border-emerald-500/40`}>
              <div className='font-semibold flex items-center gap-2'>
                v{page.version} <Tag color='success'>{t('wiki_current_version')}</Tag>
              </div>
              <div className='text-xs text-gray-400 flex justify-between'>
                <span>{t(EDIT_SOURCE_LABELS[page.last_edit_source]?.key || 'wiki_source_pipeline')}</span>
              </div>
            </div>
          )}
          {listLoading ? (
            <div className='flex justify-center py-4'>
              <Spin size='small' />
            </div>
          ) : (
            revisions.map(rev => (
              <div
                key={rev.version}
                className={`px-3 py-2 rounded-lg mb-1 cursor-pointer ${selectedVersion === rev.version ? 'bg-[#034cff]/10' : 'hover:bg-gray-100 dark:hover:bg-gray-800'}`}
                onClick={() => setSelectedVersion(rev.version)}
              >
                <div className='font-semibold text-sm'>v{rev.version}</div>
                <div className='text-xs text-gray-400 flex justify-between'>
                  <span>{t(EDIT_SOURCE_LABELS[rev.edit_source]?.key || 'wiki_source_pipeline')}</span>
                  <span>{rev.gmt_created ? rev.gmt_created.replace('T', ' ').slice(5, 16) : ''}</span>
                </div>
              </div>
            ))
          )}
          {page && page.version > 1 && selectedVersion !== null && (
            <Button
              size='small'
              icon={<RollbackOutlined />}
              loading={reverting}
              onClick={handleRevert}
              className='mt-2 w-full'
            >
              {t('wiki_revert_to', { version: selectedVersion })}
            </Button>
          )}
        </div>

        {/* Diff pane */}
        <div className='flex-1 min-w-0 overflow-auto'>
          <div className='flex items-center gap-3 mb-3 flex-wrap'>
            <span className='font-bold text-[15px]'>
              {mode === 'current'
                ? `v${selectedVersion ?? '-'} → ${t('wiki_current_version')}`
                : fromSnapshot && toSnapshot
                  ? `v${fromSnapshot.version} → v${toSnapshot.version}`
                  : ''}
            </span>
            <Segmented
              size='small'
              value={mode}
              onChange={value => setMode(value as DiffMode)}
              options={[
                { label: t('wiki_diff_incremental'), value: 'incremental' },
                { label: t('wiki_diff_current'), value: 'current' },
                { label: t('wiki_diff_raw'), value: 'raw' },
              ]}
            />
          </div>

          {detailLoading ? (
            <div className='flex justify-center py-6'>
              <Spin />
            </div>
          ) : selectedVersion === null ? (
            <div className='text-sm text-gray-400 mt-6'>{t('wiki_revision_pick_hint')}</div>
          ) : mode === 'raw' ? (
            <div className='bg-gray-50 dark:bg-[#1a1d29] border dark:border-gray-700 rounded-lg p-3'>
              {renderLines([
                { type: 'same', text: `# ${toSnapshot?.title || ''}` },
                { type: 'same', text: toSnapshot?.content || '' },
              ])}
            </div>
          ) : sections && sections.length > 0 ? (
            <div className='flex flex-col gap-3'>
              {sections.map(section => (
                <div key={section.field}>
                  <div className='text-xs text-gray-400 mb-1.5'>{t(`wiki_field_${section.field}`)}</div>
                  <div className='bg-gray-50 dark:bg-[#1a1d29] border dark:border-gray-700 rounded-lg p-2'>
                    {renderLines(section.lines)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className='text-sm text-gray-400 mt-6'>{t('wiki_diff_no_changes')}</div>
          )}
        </div>
      </div>
    </Drawer>
  );
}
