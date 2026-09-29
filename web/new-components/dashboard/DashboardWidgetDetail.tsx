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
  const rows = rowsToObjects(result);
  return (
    <Modal
      open
      title={`${widget.title} · 明细查看`}
      onCancel={onClose}
      footer={null}
      width='min(1120px, 94vw)'
      getContainer={getContainer}
      destroyOnClose
    >
      <p className={styles.detailCaption}>
        按当前筛选结果显示{result ? `，共 ${result.row_count} 行` : ''}。表格保留查询返回的原始数值。
      </p>
      <Tabs
        items={[
          {
            key: 'chart',
            label: '图表',
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
            label: '数据明细',
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
              <Empty description='当前筛选没有数据' />
            ),
          },
        ]}
      />
    </Modal>
  );
}
