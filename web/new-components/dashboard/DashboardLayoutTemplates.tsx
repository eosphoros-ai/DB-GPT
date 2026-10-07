import { DashboardSchemaV1, DashboardSnapshot } from '@/types/dashboard';
import { ArrowRightOutlined, CheckOutlined, ExportOutlined } from '@ant-design/icons';
import { Checkbox, Modal } from 'antd';
import { useMemo, useState } from 'react';
import styles from './DashboardLayoutTemplates.module.css';
import DashboardRenderer from './DashboardRenderer';
import { resolveDashboardTheme } from './dashboard-appearance';
import {
  applyDashboardLayoutTemplate,
  DASHBOARD_LAYOUT_TEMPLATES,
  DashboardLayoutTemplate,
  DashboardLayoutTemplateId,
  getDashboardLayoutTemplate,
  templateDashboardLayout,
} from './dashboard-layout-templates';
import { DASHBOARD_TEMPLATES, DashboardTemplate } from './dashboard-templates';

/** A schematic of the actual packing policy; no sample values are presented as business data. */
export function DashboardLayoutThumbnail({ template }: { template: DashboardLayoutTemplate }) {
  const widgets = [
    ...Array.from({ length: template.metric_columns }, (_, index) => ({ id: `metric-${index}`, type: 'kpi' as const })),
    { id: 'trend', type: 'line' as const },
    { id: 'structure', type: 'bar' as const },
    { id: 'detail', type: 'table' as const },
  ];
  const layouts = templateDashboardLayout(widgets, template.id);
  const theme = resolveDashboardTheme(template.theme);
  const maxY = Math.max(...layouts.map(item => item.y + item.h));
  const unitY = 156 / maxY;
  return (
    <svg viewBox='0 0 304 212' role='img' aria-label={`${template.title}布局示意`} className={styles.thumbnail}>
      <rect width='304' height='212' rx='8' fill={theme.canvas} />
      <rect x='14' y='14' width='76' height='5' rx='2' fill={theme.text} opacity='.85' />
      <rect x='14' y='24' width='112' height='3' rx='1.5' fill={theme.muted} opacity='.35' />
      <rect x='246' y='14' width='44' height='12' rx='3' fill={theme.card} stroke={theme.border} />
      {layouts.map(item => {
        const x = 14 + item.x * 23;
        const y = 40 + item.y * unitY;
        const w = item.w * 23 - 5;
        const h = item.h * unitY - 5;
        const metric = item.widget_id.startsWith('metric');
        return (
          <g key={item.widget_id} transform={`translate(${x} ${y})`}>
            <rect
              width={w}
              height={h}
              rx={template.id === 'operations-detail' ? 2 : 4}
              fill={theme.card}
              stroke={theme.border}
              strokeWidth='.7'
            />
            <rect x='7' y='6' width={w * 0.4} height='2.5' rx='1' fill={theme.muted} opacity='.55' />
            {metric ? (
              <>
                <rect x='7' y='13' width={w * 0.3} height='5' rx='1' fill={theme.text} opacity='.85' />
                <rect x={w - 18} y='14' width='10' height='3' rx='1' fill={theme.primary} opacity='.7' />
              </>
            ) : item.widget_id === 'detail' ? (
              Array.from({ length: 5 }, (_, i) => (
                <g key={i} transform={`translate(7 ${17 + (i * (h - 22)) / 5})`}>
                  <rect width={w - 14} height={(h - 22) / 5 - 2} fill={i % 2 === 0 ? theme.canvas : theme.card} />
                  <rect y='2' width={(w - 14) * 0.32} height='2' fill={theme.muted} opacity='.4' />
                  <rect x={(w - 14) * 0.55} y='2' width={(w - 14) * 0.18} height='2' fill={theme.muted} opacity='.3' />
                  <rect
                    x={(w - 14) * 0.82}
                    y='1'
                    width={(w - 14) * 0.15}
                    height='4'
                    rx='1.5'
                    fill={theme.primary}
                    opacity='.25'
                  />
                </g>
              ))
            ) : (
              <svg
                x='7'
                y='17'
                width={w - 14}
                height={Math.max(h - 24, 8)}
                viewBox='0 0 100 40'
                preserveAspectRatio='none'
                aria-hidden='true'
              >
                {[10, 25, 39].map(yPos => (
                  <line key={yPos} x1='0' x2='100' y1={yPos} y2={yPos} stroke={theme.border} strokeWidth='.7' />
                ))}
                {item.widget_id === 'trend' ? (
                  <>
                    <polyline
                      points='0,30 12,27 24,30 36,17 48,22 60,11 72,16 84,7 100,10'
                      fill='none'
                      stroke={theme.primary}
                      strokeWidth='1.8'
                      vectorEffect='non-scaling-stroke'
                    />
                    <polyline
                      points='0,34 12,30 24,32 36,29 48,31 60,21 72,25 84,20 100,22'
                      fill='none'
                      stroke={theme.muted}
                      opacity='.45'
                      strokeWidth='1'
                      strokeDasharray='3 3'
                      vectorEffect='non-scaling-stroke'
                    />
                  </>
                ) : (
                  [26, 35, 19, 29, 14, 23].map((barHeight, i) => (
                    <rect
                      key={i}
                      x={i * 17}
                      y={40 - barHeight}
                      width='10'
                      height={barHeight}
                      rx='1'
                      fill={theme.primary}
                      opacity={1 - i * 0.1}
                    />
                  ))
                )}
              </svg>
            )}
          </g>
        );
      })}
      <text x='290' y='206' textAnchor='end' fontSize='6' fill={theme.muted}>
        布局示意
      </text>
    </svg>
  );
}

export function DashboardTemplateGallery({ onChoose }: { onChoose: (template: DashboardTemplate) => void }) {
  return (
    <div className={styles.gallery}>
      {DASHBOARD_TEMPLATES.map(business => {
        const template = getDashboardLayoutTemplate(business.layoutId)!;
        return (
          <article key={business.id} className={styles.galleryCard}>
            <button type='button' className={styles.galleryButton} onClick={() => onChoose(business)}>
              <DashboardLayoutThumbnail template={template} />
              <div className={styles.cardCopy}>
                <div className={styles.eyebrow}>
                  {template.eyebrow}
                  <span>{business.audience}</span>
                </div>
                <h3>{business.title}</h3>
                <p>{business.question}</p>
                <div className={styles.structure}>{template.structure}</div>
                <span className={styles.cta}>
                  生成规划 <ArrowRightOutlined />
                </span>
              </div>
            </button>
            <a href={template.source_url} target='_blank' rel='noreferrer' className={styles.source}>
              布局参考 · {template.source} <ExportOutlined />
            </a>
          </article>
        );
      })}
    </div>
  );
}

export function DashboardLayoutTemplatePicker({
  schema,
  snapshot,
  onApply,
  onClose,
}: {
  schema: DashboardSchemaV1;
  snapshot?: DashboardSnapshot | null;
  onApply: (id: DashboardLayoutTemplateId, withAppearance: boolean) => void;
  onClose: () => void;
}) {
  const [selectedId, setSelectedId] = useState<DashboardLayoutTemplateId>('trend-focus');
  const [withAppearance, setWithAppearance] = useState(true);
  const selected = getDashboardLayoutTemplate(selectedId)!;
  const preview = useMemo(
    () => applyDashboardLayoutTemplate(schema, selectedId, withAppearance),
    [schema, selectedId, withAppearance],
  );
  return (
    <Modal
      open
      title='选择看板布局'
      width={1180}
      style={{ top: 24 }}
      styles={{ body: { maxHeight: 'calc(100dvh - 180px)', overflowY: 'auto' } }}
      okText='应用模板'
      cancelText='取消'
      okButtonProps={{ disabled: schema.widgets.length === 0 }}
      onOk={() => onApply(selectedId, withAppearance)}
      onCancel={onClose}
    >
      <p className={styles.intro}>按当前组件预览布局。应用后可继续拖拽调整，也可一键撤销。</p>
      <div className={styles.choices} role='group' aria-label='布局模板'>
        {DASHBOARD_LAYOUT_TEMPLATES.map(template => (
          <button
            key={template.id}
            type='button'
            className={styles.choice}
            aria-pressed={selectedId === template.id}
            onClick={() => setSelectedId(template.id)}
          >
            <DashboardLayoutThumbnail template={template} />
            <span className={styles.choiceTitle}>
              {template.title}
              {selectedId === template.id && <CheckOutlined />}
            </span>
            <span className={styles.choiceSource}>{template.source}</span>
          </button>
        ))}
      </div>
      <div className={styles.previewHeading}>
        <div>
          <h3>{selected.title} · 当前看板预览</h3>
          <p>{selected.description}</p>
          <a href={selected.source_url} target='_blank' rel='noreferrer'>
            查看布局参考 <ExportOutlined />
          </a>
        </div>
        <Checkbox checked={withAppearance} onChange={event => setWithAppearance(event.target.checked)}>
          同时应用配套样式
        </Checkbox>
      </div>
      <div className={styles.preview} data-testid='dashboard-layout-preview'>
        {schema.widgets.length ? (
          <DashboardRenderer schema={preview} snapshot={snapshot} />
        ) : (
          <p>添加组件后即可预览和应用布局。</p>
        )}
      </div>
    </Modal>
  );
}
