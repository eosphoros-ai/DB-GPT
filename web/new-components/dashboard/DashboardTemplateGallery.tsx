import { getDbList } from '@/client/api';
import { dashboardSourceLabel } from '@/new-components/dashboard/dashboard-source-label';
import { ADAPTED_SKILLS } from '@/new-components/skills/skill-catalog';
import { FolderOutlined, SearchOutlined, StarFilled, StarOutlined } from '@ant-design/icons';
import { useRequest } from 'ahooks';
import { Alert, Button, Empty, Input, Spin } from 'antd';
import Image from 'next/image';
import { useRouter } from 'next/router';
import { useMemo, useState } from 'react';
import { AVAILABLE_CATALOG, catalogProof, type CatalogTemplate } from './dashboard-catalog';
import DashboardDesignTemplate from './DashboardDesignTemplate';
import styles from './DashboardGallery.module.css';
import DashboardTemplateCarousel from './DashboardTemplateCarousel';
import DashboardTemplateSetup from './DashboardTemplateSetup';
import { useTemplateFavorites } from './use-template-favorites';

// Group the navigation without changing the more specific labels on each card.
const categoryGroups: Record<string, string[]> = {
  经营销售: ['营销', '销售', '经营', '客户', '电商'],
  财务分析: ['财务'],
  行业运营: ['运营', '供应链', '能源', '制造'],
  科技服务: ['科技', 'IT 服务'],
  研究教育: ['研究分析', '教育'],
  数据大屏: ['大屏'],
};
const groupCategory = (category: string) =>
  Object.keys(categoryGroups).find(group => categoryGroups[group].includes(category)) || category;

const showcaseOrder = [
  'clinical-insight',
  'cardio-journal',
  'voice-observatory',
  'store-marketing',
  'national-command',
  'healthcare-command',
  'rural-finance',
  'brand-revenue',
];
const catalogPriority = (id: string) => {
  const index = showcaseOrder.indexOf(id);
  return index < 0 ? showcaseOrder.length : index;
};

// The user's selected styles and data templates share one display order.
const preferredTemplates = [
  'design:learnhub-viz-design',
  'design:brutal-viz-design',
  'design:pawspa-viz-design',
  'design:serenityspa-viz-design',
  'voice-observatory',
  'store-marketing',
  'national-command',
  'brand-revenue',
  'business-dossier',
  'store-coverage',
  'northwind-revenue',
  'northwind-freight',
];
const preferredPriority = (id: string) => {
  const index = preferredTemplates.indexOf(id);
  return index < 0 ? preferredTemplates.length : index;
};

export default function DashboardTemplateGallery({ featured = false }: { featured?: boolean }) {
  const router = useRouter();
  const [category, setCategory] = useState('全部');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<CatalogTemplate | null>(null);
  const [collection, setCollection] = useState<'all' | 'design' | 'favorites'>('all');
  const { favorites, toggle } = useTemplateFavorites();
  const {
    data: sources = [],
    loading,
    error,
    refresh: loadSources,
  } = useRequest(
    async () => {
      const response = await getDbList();
      if (!response.data.success) throw new Error(response.data.err_msg || '数据源暂时无法读取');
      const records = response.data.data as unknown as { db_name?: string; params?: { name?: string } }[];
      return records.map(item => item.db_name || item.params?.name || '').filter(Boolean);
    },
    { onError: () => {} },
  ); // Errors are shown in the gallery's retry alert.
  const available = useMemo(
    () =>
      sources.length
        ? [...AVAILABLE_CATALOG].sort(
            (a, b) => catalogPriority(a.id) - catalogPriority(b.id) || Number(!!b.style) - Number(!!a.style),
          )
        : [],
    [sources],
  );
  const availableCategories = new Set(available.map(item => groupCategory(item.category)));
  const categories = [
    '全部',
    ...Object.keys(categoryGroups).filter(group => availableCategories.has(group)),
    ...[...availableCategories].filter(group => !categoryGroups[group]),
    '风格技能',
  ];
  const filtered = available.filter(
    item =>
      (category === '全部' || groupCategory(item.category) === category) &&
      collection !== 'design' &&
      (collection !== 'favorites' || favorites.includes(item.id)) &&
      `${item.title} ${item.description} ${item.category}`.includes(search.trim()),
  );
  const featuredIds = [
    'brand-revenue',
    'retail-overview',
    'growth-map',
    'retail-terminal',
    'service-desk',
    'sales-receipt',
  ];
  const matches = featured ? featuredIds.flatMap(id => filtered.filter(item => item.id === id)) : filtered;
  const designs = featured
    ? []
    : Object.entries(ADAPTED_SKILLS).filter(
        ([name, design]) =>
          (category === '全部' || category === '风格技能') &&
          (collection !== 'favorites' || favorites.includes(`design:${name}`)) &&
          `${design.title} ${design.description}`.includes(search.trim()),
      );
  const open = (item: CatalogTemplate) => {
    setSelected(item);
  };
  const cards = matches.map(item => {
    const proof = catalogProof(item.id);
    return (
      <article key={item.id} className={styles.card} data-catalog-template={item.id}>
        <button type='button' className={styles.cover} aria-label={`预览模板 ${item.title}`} onClick={() => open(item)}>
          {proof?.preview ? (
            <Image src={proof.preview} alt={`${item.title}实际生成预览`} width={640} height={400} />
          ) : (
            <div className={styles.assetCover}>
              <strong>{item.title}</strong>
              <span>{item.sourceNames[0]}</span>
            </div>
          )}
          <span className={styles.badge}>{item.category}</span>
          <span className={styles.coverAction}>查看模板</span>
        </button>
        <button
          type='button'
          className={styles.favorite}
          aria-label={`${favorites.includes(item.id) ? '取消收藏' : '收藏'}模板 ${item.title}`}
          aria-pressed={favorites.includes(item.id)}
          onClick={() => toggle(item.id)}
        >
          {favorites.includes(item.id) ? <StarFilled /> : <StarOutlined />}
        </button>
        <div className={styles.cardTitle}>
          <button type='button' onClick={() => open(item)}>
            {item.title}
          </button>
        </div>
        <p className={styles.description}>{item.description}</p>
        <div className={styles.meta}>
          <span>{dashboardSourceLabel(proof?.source || item.sourceNames[0])}</span>
        </div>
      </article>
    );
  });
  const orderedCards = [
    ...cards.map((card, index) => ({ id: matches[index].id, card })),
    ...designs.map(([name]) => ({
      id: `design:${name}`,
      card: (
        <DashboardDesignTemplate
          key={`design:${name}`}
          name={name}
          favorite={favorites.includes(`design:${name}`)}
          onFavorite={() => toggle(`design:${name}`)}
        />
      ),
    })),
  ].sort((a, b) => preferredPriority(a.id) - preferredPriority(b.id));
  return (
    <>
      {!featured && (
        <nav className={styles.collections} aria-label='模板文件夹'>
          <button
            type='button'
            aria-pressed={collection === 'all'}
            onClick={() => {
              setCollection('all');
              setCategory('全部');
            }}
          >
            全部模板
          </button>
          <button
            type='button'
            aria-pressed={collection === 'design'}
            onClick={() => {
              setCollection('design');
              setCategory('全部');
            }}
          >
            风格技能
          </button>
          <button
            type='button'
            aria-pressed={collection === 'favorites'}
            onClick={() => {
              setCollection('favorites');
              setCategory('全部');
            }}
          >
            <FolderOutlined /> 收藏夹{' '}
            <span>
              {
                favorites.filter(
                  id =>
                    AVAILABLE_CATALOG.some(item => item.id === id) ||
                    (id.startsWith('design:') && ADAPTED_SKILLS[id.slice(7)]),
                ).length
              }
            </span>
          </button>
        </nav>
      )}
      {!featured && (
        <div className={styles.tools}>
          {collection !== 'design' && (
            <nav className={styles.categories} aria-label='模板业务分类'>
              {categories.map(item => (
                <button
                  key={item}
                  type='button'
                  title={categoryGroups[item]?.join('、')}
                  aria-pressed={category === item}
                  onClick={() => setCategory(item)}
                >
                  {item}
                </button>
              ))}
            </nav>
          )}
          <Input
            className={styles.search}
            prefix={<SearchOutlined />}
            placeholder='搜索模板'
            aria-label='搜索模板'
            value={search}
            allowClear
            onChange={event => setSearch(event.target.value)}
          />
        </div>
      )}
      {error ? (
        <Alert
          type='error'
          showIcon
          message='暂时无法连接数据服务，请恢复连接后重试。'
          action={
            <Button
              onClick={() => {
                void loadSources();
              }}
            >
              重试
            </Button>
          }
        />
      ) : loading ? (
        <Spin />
      ) : available.length < 2 && !designs.length ? (
        <Alert
          type='info'
          showIcon
          message='可用模板不足，暂不展示模板广场'
          description='请先恢复模板数据源，或继续编辑已有看板。'
          action={<Button onClick={() => router.push('/dashboards/?tab=all')}>全部看板</Button>}
        />
      ) : matches.length || designs.length ? (
        featured ? (
          <DashboardTemplateCarousel>{cards}</DashboardTemplateCarousel>
        ) : (
          <div className={styles.grid}>{orderedCards.map(item => item.card)}</div>
        )
      ) : (
        <Empty
          description={
            search
              ? '没有匹配的模板'
              : collection === 'favorites'
                ? '还没有收藏模板，点击卡片右上角的星标即可收纳到这里。'
                : '当前分类没有模板'
          }
        />
      )}
      {selected && <DashboardTemplateSetup template={selected} sources={sources} onClose={() => setSelected(null)} />}
    </>
  );
}
