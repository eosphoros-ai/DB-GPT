import { AutoChart, BackEndChartType, getChartType } from '@/components/chart/autoChart';
import { formatSql } from '@/utils';
import { Datum } from '@antv/ava';
import { Table, Tabs, TabsProps } from 'antd';
import { useMemo } from 'react';
import { CodePreview } from './code-preview';

/** Render structured chart content using the GPT visualization components. */
function ChartView({ data, type, sql }: { data: Datum[]; type: BackEndChartType; sql: string }) {
  // SQL results need not contain a primary key and may contain duplicate values.
  // Use each row's position in this immutable result snapshot as its identity.
  const rows = useMemo(() => (data ?? []).map((record, rowIndex) => ({ record, rowIndex })), [data]);
  const columns = data?.[0]
    ? Object.keys(data?.[0])?.map(item => {
        return {
          title: item,
          dataIndex: ['record', item],
          key: item,
        };
      })
    : [];
  const ChartItem = {
    key: 'chart',
    label: 'Chart',
    children: <AutoChart data={data} chartType={getChartType(type)} />,
  };
  const SqlItem = {
    key: 'sql',
    label: 'SQL',
    children: <CodePreview language='sql' code={formatSql(sql ?? '', 'mysql') as string} />,
  };
  const DataItem = {
    key: 'data',
    label: 'Data',
    children: <Table rowKey='rowIndex' dataSource={rows} columns={columns} scroll={{ x: 'auto' }} />,
  };
  const TabItems: TabsProps['items'] = type === 'response_table' ? [DataItem, SqlItem] : [ChartItem, SqlItem, DataItem];

  return <Tabs defaultActiveKey={type === 'response_table' ? 'data' : 'chart'} items={TabItems} size='small' />;
}

export default ChartView;
