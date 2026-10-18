/**
 * Wiki browser container: sidebar + reader + revision drawer + status
 * polling (5s while generation tasks are pending, mirroring WeKnora's
 * three-layer polling model in its single-P0 form).
 */
import {
  apiInterceptors,
  deleteWikiPage,
  enableWiki,
  generateWiki,
  getWikiPage,
  getWikiStatus,
  getWikiTree,
  searchWikiPages,
} from '@/client/api';
import { WikiPage, WikiPageLite, WikiStatusResult, WikiTreeResult } from '@/types/wiki';
import { Button, Empty, Spin, message } from 'antd';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import WikiReader from './wiki-reader';
import WikiRevisionDrawer from './wiki-revision-drawer';
import WikiSidebar, { WikiContentTab } from './wiki-sidebar';

interface WikiBrowserProps {
  spaceId: string | number;
  spaceName: string;
}

export default function WikiBrowser({ spaceId, spaceName }: WikiBrowserProps) {
  const { t } = useTranslation();

  const [status, setStatus] = useState<WikiStatusResult | null>(null);
  const [tree, setTree] = useState<WikiTreeResult | null>(null);
  const [treeLoading, setTreeLoading] = useState(false);
  const [contentTab, setContentTab] = useState<WikiContentTab>('knowledge');
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [selectedPage, setSelectedPage] = useState<WikiPage | null>(null);
  const [pageLoading, setPageLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchHits, setSearchHits] = useState<WikiPageLite[]>([]);
  const [revisionOpen, setRevisionOpen] = useState(false);
  const [generateLoading, setGenerateLoading] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const searchSeqRef = useRef(0);

  // ---- status polling ----
  const refreshStatus = useCallback(async () => {
    const [, data] = await apiInterceptors(getWikiStatus(spaceId));
    if (data) setStatus(data);
    return data;
  }, [spaceId]);

  useEffect(() => {
    if (!spaceId) return;
    (async () => {
      const first = await refreshStatus();
      if (first && !first.wiki_enabled) return;
      setTreeLoading(true);
      const [, treeData] = await apiInterceptors(getWikiTree(spaceId));
      setTree(treeData || null);
      setTreeLoading(false);
    })();
  }, [spaceId, refreshStatus]);

  // poll while there are pending tasks
  useEffect(() => {
    if (!status || !status.wiki_enabled) return;
    const shouldPoll = status.pending_tasks > 0 || status.is_active;
    if (shouldPoll && !pollRef.current) {
      pollRef.current = setInterval(async () => {
        const next = await refreshStatus();
        if (next && next.pending_tasks === 0 && !next.is_active) {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          await refreshTree();
          // refresh the open page too
          if (selectedSlug) loadPage(selectedSlug);
        }
      }, 5000);
    }
    if (!shouldPoll && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (!shouldPoll && pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [status, spaceId, refreshStatus, selectedSlug]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- page loading ----
  const loadPage = useCallback(
    async (slug: string) => {
      setPageLoading(true);
      const [, data] = await apiInterceptors(getWikiPage(spaceId, slug));
      setSelectedPage(data || null);
      setPageLoading(false);
    },
    [spaceId],
  );

  const handleSelectPage = (slug: string) => {
    setSelectedSlug(slug);
    loadPage(slug);
  };

  // ---- search (debounced via seq guard) ----
  useEffect(() => {
    if (!searchQuery) {
      setSearchHits([]);
      return;
    }
    const seq = ++searchSeqRef.current;
    const timer = setTimeout(async () => {
      const [, data] = await apiInterceptors(searchWikiPages(spaceId, searchQuery, 20));
      if (searchSeqRef.current === seq) {
        setSearchHits((data?.results as unknown as WikiPageLite[]) || []);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, spaceId]);

  // ---- tree refresh on narrative changes ----
  const refreshTree = useCallback(async () => {
    const [, treeData] = await apiInterceptors(getWikiTree(spaceId));
    setTree(treeData || null);
  }, [spaceId]);

  const handleGenerate = async () => {
    setGenerateLoading(true);
    const [err] = await apiInterceptors(generateWiki(spaceId));
    if (err) {
      message.error(t('wiki_generate_failed'));
    } else {
      message.success(t('wiki_generate_accepted'));
      await refreshStatus();
      await refreshTree();
    }
    setGenerateLoading(false);
  };

  const handleDelete = async (slug: string) => {
    const [err] = await apiInterceptors(deleteWikiPage(spaceId, slug));
    if (err) {
      message.error(t('wiki_delete_failed'));
      return;
    }
    message.success(t('wiki_delete_success'));
    setSelectedSlug(null);
    setSelectedPage(null);
    await refreshTree();
    await refreshStatus();
  };

  const handleEnable = async () => {
    setGenerateLoading(true);
    const [err] = await apiInterceptors(enableWiki(spaceId));
    setGenerateLoading(false);
    if (err) {
      message.error(t('wiki_enable_failed'));
      return;
    }
    message.success(t('wiki_enable_success'));
    const next = await refreshStatus();
    if (next && next.wiki_enabled) {
      await refreshTree();
    }
  };

  const handleReverted = async (slug: string) => {
    await loadPage(slug);
    await refreshStatus();
  };

  if (status && !status.wiki_enabled) {
    return (
      <div className='h-full flex flex-col items-center justify-center bg-white dark:bg-[#232734] gap-4 px-8'>
        <Empty
          className='m-0'
          description={<span className='text-gray-400 max-w-[520px]'>{t('wiki_enable_hint')}</span>}
        />
        <Button type='primary' loading={generateLoading} onClick={handleEnable}>
          {t('wiki_enable_now')}
        </Button>
      </div>
    );
  }
  if (!status) {
    return (
      <div className='h-full flex items-center justify-center'>
        <Spin size='large' />
      </div>
    );
  }

  return (
    <div className='h-full flex flex-col overflow-hidden' data-space={spaceName}>
      <div className='flex-1 flex overflow-hidden'>
        <WikiSidebar
          spaceId={spaceId}
          status={status}
          tree={tree}
          treeLoading={treeLoading}
          contentTab={contentTab}
          onContentTabChange={tab => {
            setContentTab(tab);
          }}
          searchHits={searchHits}
          searchQuery={searchQuery}
          onSearchQueryChange={setSearchQuery}
          selectedSlug={selectedSlug}
          onSelectPage={handleSelectPage}
          onGenerate={handleGenerate}
          generateLoading={generateLoading}
          tailLoading={false}
        />
        <WikiReader
          page={selectedPage}
          loading={pageLoading}
          onReload={handleSelectPage}
          onOpenRevisions={() => setRevisionOpen(true)}
          onDelete={handleDelete}
          onOpenSourceDoc={() => {
            message.info(t('wiki_source_doc_hint'));
          }}
        />
      </div>

      <WikiRevisionDrawer
        open={revisionOpen}
        page={selectedPage}
        onClose={() => setRevisionOpen(false)}
        onReverted={handleReverted}
      />
    </div>
  );
}
