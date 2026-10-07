import type { DashboardSchemaV1 } from '@/types/dashboard';
import { HeartOutlined } from '@ant-design/icons';
import styles from './DashboardResearchScene.module.css';

export function DashboardResearchRail({
  schema,
  onNavigate,
}: {
  schema: DashboardSchemaV1;
  onNavigate: (id: string) => void;
}) {
  const metadata = schema.metadata.compatibility?.catalog_presentation as
    | { chapters?: { id: string; label: string }[] }
    | undefined;
  const chapters = metadata?.chapters?.filter(item => schema.widgets.some(widget => widget.id === item.id)) || [];
  return (
    <aside className={styles.rail} aria-label='研究报告章节'>
      <div className={styles.railContent}>
        <div className={styles.brand}>
          <HeartOutlined />
          <strong>
            DB-GPT<small>RESEARCH NOTES</small>
          </strong>
        </div>
        <nav>
          {chapters.map((item, index) => (
            <button type='button' key={item.id} onClick={() => onNavigate(item.id)}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              {item.label}
            </button>
          ))}
        </nav>
        <p className={styles.railCaption}>
          沿着数据，
          <br />
          读懂每一组差异。
        </p>
      </div>
    </aside>
  );
}
