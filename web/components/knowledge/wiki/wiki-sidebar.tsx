/**
 * Wiki browser sidebar: status pill, search, type tabs, category tree.
 *
 * Folders expand on click, lazily listing the real pages under them
 * (filtered by the folder's page type). Page rows navigate on click.
 */
import { apiInterceptors, listWikiPages } from '@/client/api';
import { WikiCategoryNode, WikiPageLite, WikiPageType, WikiStatusResult, WikiTreeResult } from '@/types/wiki';
import { SearchOutlined } from '@ant-design/icons';
import { Badge, Button, Empty, Input, Spin, Tag } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { PAGE_TYPE_COLORS } from './wiki-markdown';

export type WikiContentTab = 'knowledge' | 'summary';

const TAB_TYPES: Record<WikiContentTab, string[]> = {
  knowledge: ['entity', 'concept', 'synthesis', 'comparison'],
  summary: ['summary'],
};

interface WikiSidebarProps {
  spaceId: string | number;
  status: WikiStatusResult | null;
  tree: WikiTreeResult | null;
  treeLoading: boolean;
  contentTab: WikiContentTab;
  onContentTabChange: (tab: WikiContentTab) => void;
  searchHits: WikiPageLite[];
  searchQuery: string;
  onSearchQueryChange: (value: string) => void;
  selectedSlug: string | null;
  onSelectPage: (slug: string) => void;
  onGenerate: () => void;
  generateLoading: boolean;
  tailLoading: boolean;
}

type TreeRow =
  | { kind: 'category'; key: string; cat: WikiCategoryNode; depth: number; label: string }
  | { kind: 'page'; key: string; page: WikiPageLite; depth: number };

export default function WikiSidebar(props: WikiSidebarProps) {
  const {
    spaceId,
    status,
    tree,
    treeLoading,
    contentTab,
    onContentTabChange,
    searchHits,
    searchQuery,
    onSearchQueryChange,
    selectedSlug,
    onSelectPage,
    onGenerate,
    generateLoading,
    tailLoading,
  } = props;
  const { t } = useTranslation();

  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [childrenByPath, setChildrenByPath] = useState<Record<string, WikiPageLite[]>>({});
  const [childLoading, setChildLoading] = useState<Set<string>>(new Set());

  const summaryTotal = status?.stats.pages_by_type?.summary || 0;
  const knowledgeTotal = (status?.stats.total_pages || 0) - summaryTotal - (status?.stats.pages_by_type?.index || 0);

  const categories = useMemo(() => {
    if (!tree) return [];
    return tree.categories.filter(c => TAB_TYPES[contentTab].includes(c.page_type));
  }, [tree, contentTab]);

  // regenerated wiki → drop cached folder children (keep expansion state)
  useEffect(() => {
    setChildrenByPath({});
  }, [tree]);

  const folderKeyOf = (cat: WikiCategoryNode) => `${cat.page_type}:${cat.path.join('/')}`;

  const toggleFolder = async (cat: WikiCategoryNode) => {
    const key = folderKeyOf(cat);
    const willExpand = !expanded.has(key);
    setExpanded(prev => {
      const next = new Set(prev);
      if (willExpand) next.add(key);
      else next.delete(key);
      return next;
    });
    if (!willExpand || childrenByPath[key]) return;
    // lazy load: pages under this exact category path, restricted to the
    // folder's own page type
    setChildLoading(prev => new Set(prev).add(key));
    const [, data] = await apiInterceptors(
      listWikiPages(spaceId, {
        category: cat.path.join('/'),
        page_type: cat.page_type,
        page: 1,
        page_size: 100,
      }),
    );
    setChildrenByPath(prev => ({ ...prev, [key]: data?.pages || [] }));
    setChildLoading(prev => {
      const next = new Set(prev);
      next.delete(key);
      return next;
    });
  };

  // Build the visible rows: categories whose ancestors are all expanded,
  // plus loaded page children of expanded folders.
  const rows = useMemo<TreeRow[]>(() => {
    const result: TreeRow[] = [];
    for (const cat of categories) {
      const depth = cat.path.length;
      if (depth > 1) {
        const parentKey = folderKeyOf({ page_type: cat.page_type, path: cat.path.slice(0, -1), count: 0 });
        if (!expanded.has(parentKey)) continue;
      }
      const key = folderKeyOf(cat);
      const label =
        depth === 0 ? t(contentTab === 'summary' ? 'wiki_tab_summary' : 'wiki_root_pages') : cat.path[depth - 1];
      result.push({ kind: 'category', key, cat, depth, label });
      if (expanded.has(key)) {
        for (const page of childrenByPath[key] || []) {
          result.push({ kind: 'page', key: `${key}:${page.slug}`, page, depth: depth + 1 });
        }
        if (childLoading.has(key)) {
          result.push({
            kind: 'page',
            key: `${key}:loading`,
            page: { slug: '__loading__' } as WikiPageLite,
            depth: depth + 1,
          });
        }
      }
    }
    return result;
  }, [categories, expanded, childrenByPath, childLoading, contentTab, t]);

  return (
    <div className='w-[290px] min-w-[290px] border-r dark:border-gray-700 bg-white dark:bg-[#1e2130] flex flex-col overflow-hidden'>
      {/* Status + generate */}
      <div className='px-3 pt-3 flex items-center gap-2 flex-wrap'>
        {status && status.pending_tasks > 0 ? (
          <Badge
            status='processing'
            text={
              <span className='text-xs text-orange-500'>
                {t('wiki_generating_n_tasks', { n: status.pending_tasks })}
              </span>
            }
          />
        ) : (
          <Badge status='success' text={<span className='text-xs text-gray-400'>{t('wiki_up_to_date')}</span>} />
        )}
        <Button size='small' type='primary' ghost loading={generateLoading} onClick={onGenerate} className='ml-auto'>
          {t('wiki_generate_rebuild')}
        </Button>
      </div>

      {/* Search */}
      <div className='px-3 pt-3'>
        <Input
          allowClear
          size='small'
          prefix={<SearchOutlined className='text-gray-400' />}
          placeholder={t('wiki_search_placeholder')}
          value={searchQuery}
          onChange={e => onSearchQueryChange(e.target.value)}
        />
      </div>

      {/* Type tabs */}
      <div className='px-3 pt-3 flex items-center gap-4 border-b dark:border-gray-700 pb-1.5 mx-0'>
        <span
          className={`text-sm cursor-pointer pb-1.5 -mb-1.5 ${
            contentTab === 'knowledge'
              ? 'font-semibold text-gray-800 dark:text-gray-100 border-b-2 border-[#034cff]'
              : 'text-gray-400'
          }`}
          onClick={() => onContentTabChange('knowledge')}
        >
          {t('wiki_tab_knowledge')} <span className='text-xs text-gray-400'>{knowledgeTotal}</span>
        </span>
        <span
          className={`text-sm cursor-pointer pb-1.5 -mb-1.5 ${
            contentTab === 'summary'
              ? 'font-semibold text-gray-800 dark:text-gray-100 border-b-2 border-[#034cff]'
              : 'text-gray-400'
          }`}
          onClick={() => onContentTabChange('summary')}
        >
          {t('wiki_tab_summary')} <span className='text-xs text-gray-400'>{summaryTotal}</span>
        </span>
      </div>

      {/* Tree / search results */}
      <div className='flex-1 overflow-auto py-2 px-1.5'>
        {searchQuery ? (
          searchHits.length > 0 ? (
            searchHits.map(hit => (
              <div
                key={hit.slug}
                className={`px-2 py-1.5 rounded-md cursor-pointer text-sm ${
                  selectedSlug === hit.slug
                    ? 'bg-[#034cff]/10 text-[#1f5eff] font-semibold'
                    : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'
                }`}
                onClick={() => onSelectPage(hit.slug)}
              >
                {hit.title}
                <span className='text-xs text-gray-400 ml-2'>v{hit.version}</span>
              </div>
            ))
          ) : (
            <Empty description={t('wiki_search_no_results')} className='mt-6' />
          )
        ) : treeLoading ? (
          <div className='flex justify-center mt-6'>
            <Spin size='small' />
          </div>
        ) : rows.length === 0 ? (
          <Empty description={t('wiki_empty_no_pages')} className='mt-6' />
        ) : (
          rows.map(row => {
            if (row.kind === 'page' && row.page.slug === '__loading__') {
              return (
                <div key={row.key} style={{ paddingLeft: 20 + row.depth * 14 }} className='py-1.5'>
                  <Spin size='small' />
                </div>
              );
            }
            if (row.kind === 'page') {
              const active = selectedSlug === row.page.slug;
              return (
                <div key={row.key} style={{ paddingLeft: row.depth * 14 + 8 }}>
                  <div
                    className={`px-2 py-1.5 rounded-md cursor-pointer flex items-center gap-1.5 text-sm ${
                      active
                        ? 'bg-[#034cff]/10 text-[#1f5eff] font-semibold'
                        : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'
                    }`}
                    onClick={() => onSelectPage(row.page.slug)}
                  >
                    <span style={{ color: PAGE_TYPE_COLORS[row.page.page_type as WikiPageType] || '#8e8b8b' }}>◈</span>
                    <span className='flex-1 truncate'>{row.page.title}</span>
                  </div>
                </div>
              );
            }
            const { cat } = row;
            const typeColor = PAGE_TYPE_COLORS[(cat.page_type as WikiPageType) || 'entity'] || '#8e8b8b';
            const isExpanded = expanded.has(row.key);
            return (
              <div key={row.key} style={{ paddingLeft: row.depth * 14 }}>
                <div
                  className='px-2 py-1.5 rounded-md cursor-pointer flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 select-none'
                  onClick={() => toggleFolder(cat)}
                >
                  <span className={`text-[10px] text-gray-400 w-3 ${isExpanded ? '' : ''}`}>
                    {isExpanded ? '▾' : '▸'}
                  </span>
                  <span className='flex-1 truncate font-medium'>{row.label}</span>
                  {cat.count > 0 && <span className='text-xs text-gray-400'>{cat.count}</span>}
                  <Tag color={typeColor} className='mr-0 leading-tight'>
                    {t(`wiki_type_${cat.page_type as WikiPageType}`)}
                  </Tag>
                </div>
              </div>
            );
          })
        )}
        {tailLoading && (
          <div className='flex justify-center py-2'>
            <Spin size='small' />
          </div>
        )}
      </div>
    </div>
  );
}
