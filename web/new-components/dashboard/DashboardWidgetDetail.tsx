import { dashboardText as dt, useDashboardTranslation } from '@/new-components/dashboard/dashboard-i18n';
import type { DashboardSchemaV1, DashboardWidget, DashboardWidgetResult } from '@/types/dashboard';
import { Empty, Modal, Table, Tabs } from 'antd';
import type { DashboardThemeTokens } from './dashboard-appearance';
import styles from './DashboardShowcase.module.css';
import DashboardWidgetCard, { rowsToObjects } from './DashboardWidgetCard';

export default function DashboardWidgetDetail({
  widget,
  result,
  schema,
  theme,
  onClose,
  getContainer,
}: {
  widget: DashboardWidget;
  result?: DashboardWidgetResult;
  schema: DashboardSchemaV1;
  theme: DashboardThemeTokens;
  onClose: () => void;
  getContainer: () => HTMLElement;
}) {
  useDashboardTranslation();
  const rows = rowsToObjects(result);
  return (
    <Modal
      open
      title={dt('{{value0}} · 明细查看', { value0: widget.title })}
      onCancel={onClose}
      footer={null}
      width='min(1120px, 94vw)'
      getContainer={getContainer}
      destroyOnClose
    >
      <p className={styles.detailCaption}>
        {dt('按当前筛选结果显示')}
        {result ? dt('，共 {{value0}} 行', { value0: result.row_count }) : ''}
        {dt('。表格保留查询返回的原始数值。')}
      </p>
      <Tabs
        items={[
          {
            key: 'chart',
            label: dt('图表'),
            children: (
              <div className={styles.detailChart}>
                <DashboardWidgetCard
                  widget={widget}
                  result={result}
                  metricContext={schema.metric_context}
                  theme={theme}
                />
              </div>
            ),
          },
          {
            key: 'data',
            label: dt('数据明细'),
            children: result?.error ? (
              <p role='alert'>{result.error.message}</p>
            ) : rows.length ? (
              <Table
                size='small'
                scroll={{ x: 'max-content', y: '55vh' }}
                pagination={{ pageSize: 10, showSizeChanger: false }}
                rowKey='__key'
                dataSource={rows.map((r, index) => ({ ...r, __key: index }))}
                columns={(result?.columns || []).map(field => ({
                  title: widget.query.output_fields.find(f => f.name === field)?.label || field,
                  dataIndex: field,
                  key: field,
                  render: (value: unknown) => (value == null ? '—' : String(value)),
                }))}
              />
            ) : (
              <Empty description={dt('当前筛选没有数据')} />
            ),
          },
        ]}
      />
    </Modal>
  );
}
