import { getDbList } from '@/client/api';
import { dashboardText as dt, useDashboardTranslation } from '@/new-components/dashboard/dashboard-i18n';
import { dashboardSourceLabel } from '@/new-components/dashboard/dashboard-source-label';
import { ADAPTED_SKILLS } from '@/new-components/skills/skill-catalog';
import { ArrowRightOutlined, FolderOutlined, SearchOutlined, StarFilled, StarOutlined } from '@ant-design/icons';
import { useRequest } from 'ahooks';
import { Alert, Button, Empty, Input, Modal, Spin } from 'antd';
import Image from 'next/image';
import { useRouter } from 'next/router';
import { useMemo, useState } from 'react';
import {
  AVAILABLE_CATALOG,
  catalogProof,
  GALLERY_DESIGN_SKILL_IDS,
  TEMPLATE_GALLERY_ORDER,
  type CatalogTemplate,
} from './dashboard-catalog';
import DashboardDesignTemplate from './DashboardDesignTemplate';
import styles from './DashboardGallery.module.css';
import DashboardTemplateCarousel from './DashboardTemplateCarousel';
import DashboardTemplateLayoutPreview from './DashboardTemplateLayoutPreview';
import { useTemplateFavorites } from './use-template-favorites';

const preferredPriority = (id: string) => {
  const index = TEMPLATE_GALLERY_ORDER.indexOf(id);
  return index < 0 ? TEMPLATE_GALLERY_ORDER.length : index;
};

export default function DashboardTemplateGallery({ featured = false }: { featured?: boolean }) {
  useDashboardTranslation();
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
      if (!response.data.success) throw new Error(response.data.err_msg || dt('数据源暂时无法读取'));
      const records = response.data.data as unknown as { db_name?: string; params?: { name?: string } }[];
      return records.map(item => item.db_name || item.params?.name || '').filter(Boolean);
    },
    { onError: () => {} },
  ); // Errors are shown in the gallery's retry alert.
  const available = useMemo(
    () =>
      sources.length ? [...AVAILABLE_CATALOG].sort((a, b) => preferredPriority(a.id) - preferredPriority(b.id)) : [],
    [sources],
  );
  const categories =
    collection === 'design' ? ['全部', '设计'] : ['全部', ...new Set(available.map(item => item.category)), '设计'];
  const filtered = available.filter(
    item =>
      (category === '全部' || item.category === category) &&
      collection !== 'design' &&
      (collection !== 'favorites' || favorites.includes(item.id)) &&
      `${item.title} ${item.description} ${dt(item.title)} ${dt(item.description)}`
        .toLowerCase()
        .includes(search.trim().toLowerCase()),
  );
  const matches = filtered;
  const designs = featured
    ? []
    : Object.entries(ADAPTED_SKILLS).filter(
        ([name, design]) =>
          GALLERY_DESIGN_SKILL_IDS.has(name) &&
          (category === '全部' || category === '设计') &&
          (collection !== 'favorites' || favorites.includes(`design:${name}`)) &&
          `${design.title} ${design.description} ${dt(design.title)} ${dt(design.description)}`
            .toLowerCase()
            .includes(search.trim().toLowerCase()),
      );
  const open = (item: CatalogTemplate) => {
    setSelected(item);
  };
  const startFromTemplate = (item: CatalogTemplate) =>
    void router.push({ pathname: '/', query: { creation_mode: 'dashboard', template: item.id } });
  const cards = matches.map(item => {
    const proof = catalogProof(item.id);
    return (
      <article key={item.id} className={styles.card} data-catalog-template={item.id}>
        <button
          type='button'
          className={styles.cover}
          aria-label={dt('预览模板 {{value0}}', { value0: dt(item.title) })}
          onClick={() => open(item)}
        >
          {proof?.previewKind === 'layout' ? (
            <DashboardTemplateLayoutPreview template={item} />
          ) : proof?.preview ? (
            <>
              <Image
                src={proof.preview}
                alt={dt('{{value0}}模板示例预览', { value0: dt(item.title) })}
                data-template-preview={item.id}
                width={800}
                height={500}
              />
              <span className={styles.designLabel}>{dt('示例预览')}</span>
            </>
          ) : (
            <div className={styles.assetCover}>
              <strong>{dt(item.title)}</strong>
              <span>{item.sourceNames[0]}</span>
            </div>
          )}
          <span className={styles.badge}>{dt(item.category)}</span>
          <span className={styles.coverAction}>{dt('查看模板')}</span>
        </button>
        <button
          type='button'
          className={styles.favorite}
          aria-label={dt('{{value0}}模板 {{value1}}', {
            value0: favorites.includes(item.id) ? dt('取消收藏') : dt('收藏'),
            value1: dt(item.title),
          })}
          aria-pressed={favorites.includes(item.id)}
          onClick={() => toggle(item.id)}
        >
          {favorites.includes(item.id) ? <StarFilled /> : <StarOutlined />}
        </button>
        <div className={styles.cardTitle}>
          <button type='button' onClick={() => open(item)}>
            {dt(item.title)}
          </button>
        </div>
        <p className={styles.description}>{dt(item.description)}</p>
        <div className={styles.meta}>
          <span>{dashboardSourceLabel(proof?.source || item.sourceNames[0])}</span>
          <button
            type='button'
            onClick={() => startFromTemplate(item)}
            aria-label={dt('使用模板 {{value0}}', { value0: dt(item.title) })}
          >
            {dt('使用')}
            <ArrowRightOutlined />
          </button>
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
        <nav className={styles.collections} aria-label={dt('模板文件夹')}>
          <button
            type='button'
            aria-pressed={collection === 'all'}
            onClick={() => {
              setCollection('all');
              setCategory('全部');
            }}
          >
            {dt('全部模板')}
          </button>
          <button
            type='button'
            aria-pressed={collection === 'design'}
            onClick={() => {
              setCollection('design');
              setCategory('全部');
            }}
          >
            {dt('风格技能')}
          </button>
          <button
            type='button'
            aria-pressed={collection === 'favorites'}
            onClick={() => {
              setCollection('favorites');
              setCategory('全部');
            }}
          >
            <FolderOutlined /> {dt('收藏夹')}{' '}
            <span>
              {
                favorites.filter(
                  id =>
                    AVAILABLE_CATALOG.some(item => item.id === id) ||
                    (id.startsWith('design:') && GALLERY_DESIGN_SKILL_IDS.has(id.slice(7))),
                ).length
              }
            </span>
          </button>
        </nav>
      )}
      {!featured && (
        <div className={styles.tools}>
          <div className={styles.categories} aria-label={dt('模板业务分类')}>
            {categories.map(item => (
              <button key={item} type='button' aria-pressed={category === item} onClick={() => setCategory(item)}>
                {dt(item)}
              </button>
            ))}
          </div>
          <Input
            className={styles.search}
            prefix={<SearchOutlined />}
            placeholder={dt('搜索模板')}
            aria-label={dt('搜索模板')}
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
          message={dt('暂时无法连接数据服务，请恢复连接后重试。')}
          action={
            <Button
              onClick={() => {
                void loadSources();
              }}
            >
              {dt('重试')}
            </Button>
          }
        />
      ) : loading ? (
        <Spin />
      ) : available.length < 2 && !designs.length ? (
        <Alert
          type='info'
          showIcon
          message={dt('可用模板不足，暂不展示模板广场')}
          description={dt('请先恢复模板数据源，或继续编辑已有看板。')}
          action={<Button onClick={() => router.push('/dashboards/?tab=all')}>{dt('全部看板')}</Button>}
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
              ? dt('没有匹配的模板')
              : collection === 'favorites'
                ? dt('还没有收藏模板，点击卡片右上角的星标即可收纳到这里。')
                : dt('当前分类没有模板')
          }
        />
      )}
      {selected && (
        <Modal
          open
          title={dt(selected.title)}
          onCancel={() => setSelected(null)}
          width={1000}
          footer={
            <Button type='primary' onClick={() => startFromTemplate(selected)}>
              {dt('选择数据并创建看板')}
            </Button>
          }
        >
          {catalogProof(selected.id)?.preview ? (
            <Image
              src={catalogProof(selected.id)!.preview!}
              alt={dt('{{value0}}模板示例预览', { value0: dt(selected.title) })}
              width={1200}
              height={750}
              style={{ width: '100%', height: 'auto' }}
            />
          ) : (
            <DashboardTemplateLayoutPreview template={selected} />
          )}
          <p>{dt(selected.description)}</p>
        </Modal>
      )}
    </>
  );
}
