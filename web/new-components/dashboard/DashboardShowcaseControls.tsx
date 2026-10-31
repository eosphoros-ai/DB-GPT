import { dashboardText as dt, useDashboardTranslation } from '@/new-components/dashboard/dashboard-i18n';
import type { DashboardSchemaV1, DashboardSnapshot } from '@/types/dashboard';
import {
  ExpandOutlined,
  FullscreenExitOutlined,
  PieChartOutlined,
  ReloadOutlined,
  ShopOutlined,
  SoundOutlined,
  TableOutlined,
} from '@ant-design/icons';
import { useEffect, useState, type RefObject } from 'react';
import styles from './DashboardShowcase.module.css';

export function DashboardMarketingRail({ onNavigate }: { onNavigate: (id: string) => void }) {
  useDashboardTranslation();
  return (
    <aside className={styles.marketingRail} aria-label={dt('营销沙盘章节')}>
      <div className={styles.identity}>
        <ShopOutlined />
        <strong>
          DB-GPT<small>{dt('门店营销沙盘')}</small>
        </strong>
      </div>
      <span className={styles.railLabel}>{dt('经营视角')}</span>
      {[
        { id: 'campaigns', label: dt('营销总览'), icon: <ShopOutlined /> },
        { id: 'trend', label: dt('活动表现'), icon: <SoundOutlined /> },
        { id: 'channels', label: dt('渠道贡献'), icon: <PieChartOutlined /> },
        { id: 'ledger', label: dt('活动明细'), icon: <TableOutlined /> },
      ].map(item => (
        <button key={item.id} type='button' onClick={() => onNavigate(item.id)}>
          {item.icon}
          {item.label}
        </button>
      ))}
      <div className={styles.railFoot}>
        {dt('让每一次触达')}
        <br />
        {dt('都有迹可循。')}
      </div>
    </aside>
  );
}

export default function DashboardShowcaseControls({
  schema,
  snapshot,
  rootRef,
  filters,
  onChange,
}: {
  schema: DashboardSchemaV1;
  snapshot?: DashboardSnapshot | null;
  rootRef: RefObject<HTMLDivElement | null>;
  filters?: Record<string, unknown>;
  onChange?: (filters: Record<string, unknown>) => void;
}) {
  useDashboardTranslation();
  const [fullscreen, setFullscreen] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const sync = () => setFullscreen(document.fullscreenElement === rootRef.current);
    document.addEventListener('fullscreenchange', sync);
    return () => document.removeEventListener('fullscreenchange', sync);
  }, [rootRef]);
  const metadata = schema.metadata.compatibility?.catalog_presentation as
    | { demo_source?: string; reference_source?: string; source_label?: string; source_kind?: string }
    | undefined;
  const demo = metadata?.demo_source === schema.dashboard.data_source_id;
  const referenceSource = metadata?.reference_source === schema.dashboard.data_source_id;
  const values = filters || snapshot?.filters || {};
  return (
    <div className={styles.controls}>
      <span className={styles.sourceBadge} data-demo={demo}>
        {referenceSource ? metadata?.source_label : demo ? dt('合成演示 · 历史样本') : dt('已连接数据源')}
      </span>
      {onChange && (
        <div className={styles.scopeControls}>
          {schema.filters
            .filter(filter => filter.type === 'select')
            .map(filter => (
              <label key={filter.id}>
                <span>{filter.label}</span>
                <select
                  aria-label={dt('展示筛选：{{value0}}', { value0: filter.label })}
                  value={String(values[filter.id] ?? filter.default ?? 'all')}
                  onChange={e => onChange({ ...values, [filter.id]: e.target.value })}
                >
                  {filter.options.map(option => (
                    <option key={String(option.value)} value={String(option.value)}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          <button
            type='button'
            title={dt('重置展示筛选')}
            aria-label={dt('重置展示筛选')}
            onClick={() => onChange(Object.fromEntries(schema.filters.map(f => [f.id, f.default ?? 'all'])))}
          >
            <ReloadOutlined />
          </button>
        </div>
      )}
      <button
        aria-label={fullscreen ? dt('退出全屏') : dt('全屏展示')}
        className={styles.fullscreenButton}
        type='button'
        onClick={async () => {
          setError('');
          try {
            if (document.fullscreenElement === rootRef.current) await document.exitFullscreen();
            else await rootRef.current?.requestFullscreen();
          } catch {
            setError(dt('当前浏览器未允许全屏，请在普通预览中查看。'));
          }
        }}
      >
        {fullscreen ? <FullscreenExitOutlined /> : <ExpandOutlined />}
        {fullscreen ? dt('退出全屏') : dt('全屏展示')}
      </button>
      {error && <span role='alert'>{error}</span>}
    </div>
  );
}
