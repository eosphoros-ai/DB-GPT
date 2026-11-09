import type { DashboardCover } from '@/client/api/dashboard';
import { getDashboardCover } from '@/client/api/dashboard';
import {
  dashboardDateLocale,
  dashboardText as dt,
  useDashboardTranslation,
} from '@/new-components/dashboard/dashboard-i18n';
import type { DashboardListItem } from '@/types/dashboard';
import Image from 'next/image';
import { useEffect, useState } from 'react';
import styles from './DashboardGallery.module.css';

export default function DashboardAssetCover({
  item,
  refreshKey = 0,
  onNeedsPreview,
  generating = false,
  failure,
}: {
  item: DashboardListItem;
  refreshKey?: number;
  onNeedsPreview?: (item: DashboardListItem) => void;
  generating?: boolean;
  failure?: string;
}) {
  useDashboardTranslation();
  const [cover, setCover] = useState<DashboardCover | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    getDashboardCover(item.id)
      .then(r => {
        if (!r.data.success) throw new Error(dt('预览读取失败'));
        if (active) {
          setCover(r.data.data);
          setError(false);
          if (!r.data.data.available || r.data.data.stale) onNeedsPreview?.(item);
        }
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
    };
  }, [item, refreshKey, onNeedsPreview]);
  return cover?.available && cover.image ? (
    <>
      <Image
        unoptimized
        src={cover.image}
        width={960}
        height={600}
        alt={dt('{{value0}}实际渲染预览', { value0: item.title })}
      />
      <span className={styles.coverStatus} title={failure || dt('封面为截图，打开看板查看数据')}>
        {generating
          ? dt('正在更新预览')
          : failure || error
            ? dt('预览更新失败 · 已保留原图')
            : cover.stale
              ? dt('历史预览 · 待更新')
              : dt('截图 {{value0}}', {
                  value0: cover.captured_at ? new Date(cover.captured_at).toLocaleString(dashboardDateLocale()) : '',
                })}
      </span>
    </>
  ) : (
    <div className={styles.assetCover}>
      <strong>{item.title}</strong>
      <span>
        {generating
          ? dt('正在生成真实预览…')
          : failure
            ? dt('预览暂未生成')
            : error
              ? dt('预览读取失败，请刷新重试')
              : dt('等待自动生成预览')}
      </span>
      <span>{failure || dt('生成后会自动显示；也可以直接打开看板')}</span>
    </div>
  );
}
