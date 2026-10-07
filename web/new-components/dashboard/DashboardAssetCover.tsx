import type { DashboardCover } from '@/client/api/dashboard';
import { getDashboardCover } from '@/client/api/dashboard';
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
  const [cover, setCover] = useState<DashboardCover | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    getDashboardCover(item.id)
      .then(r => {
        if (!r.data.success) throw new Error('预览读取失败');
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
      <Image unoptimized src={cover.image} width={960} height={600} alt={`${item.title}实际渲染预览`} />
      <span className={styles.coverStatus} title={failure || '封面为截图，打开看板查看数据'}>
        {generating
          ? '正在更新预览'
          : failure || error
            ? '预览更新失败 · 已保留原图'
            : cover.stale
              ? '历史预览 · 待更新'
              : `截图 ${cover.captured_at ? new Date(cover.captured_at).toLocaleString('zh-CN') : ''}`}
      </span>
    </>
  ) : (
    <div className={styles.assetCover}>
      <strong>{item.title}</strong>
      <span>
        {generating
          ? '正在生成真实预览…'
          : failure
            ? '预览暂未生成'
            : error
              ? '预览读取失败，请刷新重试'
              : '等待自动生成预览'}
      </span>
      <span>{failure || '生成后会自动显示；也可以直接打开看板'}</span>
    </div>
  );
}
