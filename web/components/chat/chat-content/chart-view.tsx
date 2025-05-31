import { AutoChart, BackEndChartType, getChartType } from '@/components/chart';
import { formatSql } from '@/utils';
import { ExportFormat, exportData } from '@/utils/data-export';
import { DownloadOutlined } from '@ant-design/icons';
import { Datum } from '@antv/ava';
import { Button, Dropdown, Input, MenuProps, Modal, Table, Tabs, TabsProps } from 'antd';
import { useState } from 'react';
import { CodePreview } from './code-preview';

const returnSqlVal = (val: string) => {
  const punctuationMap: any = {
    '，': ',',
    '。': '.',
    '？': '?',
    '！': '!',
    '：': ':',
    '；': ';',
    '“': '"',
    '”': '"',
    '‘': "'",
    '’': "'",
    '（': '(',
    '）': ')',
    '【': '[',
    '】': ']',
    '《': '<',
    '》': '>',
    '—': '-',
    '、': ',',
    '…': '...',
  };
  const regex = new RegExp(Object.keys(punctuationMap).join('|'), 'g');
  return val.replace(regex, match => punctuationMap[match]);
};
interface ChartViewProps {
  data?: Datum[];
  type?: BackEndChartType;
  sql?: string;
  content?: string;
  children?: React.ReactNode;
}

function ChartView({ data, type, sql, content, children }: ChartViewProps) {
  const [exportModalVisible, setExportModalVisible] = useState(false);
  const [exportType, setExportType] = useState<ExportFormat>('excel');
  const [fileName, setFileName] = useState('');

  // Parse content string if provided
  let chartData: {
    data: Datum[];
    type: BackEndChartType;
    sql: string;
  };

  if (content) {
    try {
      chartData = JSON.parse(content);
    } catch (e) {
      console.log(e, content);
      chartData = {
        type: 'response_table',
        sql: '',
        data: [],
      };
    }
  } else {
    chartData = {
      data: data || [],
      type: type || 'response_table',
      sql: sql || '',
    };
  }

  const columns = chartData?.data?.[0]
    ? Object.keys(chartData?.data?.[0])?.map(item => {
        return {
          title: item,
          dataIndex: item,
          key: item,
        };
      })
    : [];

  const showExportModal = (type: ExportFormat) => {
    setExportType(type);
    setFileName('');
    setExportModalVisible(true);
  };

  const handleExport = () => {
    try {
      exportData({
        data: chartData.data,
        format: exportType,
        fileName: fileName,
      });
      setExportModalVisible(false);
    } catch (error) {
      console.error('Export failed:', error);
    }
  };

  const exportMenuItems: MenuProps['items'] = [
    {
      key: 'excel',
      label: 'Export as Excel (.xlsx)',
      onClick: () => showExportModal('excel'),
    },
    {
      key: 'csv',
      label: 'Export as CSV (.csv)',
      onClick: () => showExportModal('csv'),
    },
    {
      key: 'json',
      label: 'Export as JSON (.json)',
      onClick: () => showExportModal('json'),
    },
  ];

  const ExportButton = (
    <Dropdown
      menu={{ items: exportMenuItems }}
      placement='bottomRight'
      disabled={!chartData?.data || chartData.data.length === 0}
    >
      <Button
        type='primary'
        size='small'
        icon={<DownloadOutlined />}
        disabled={!chartData?.data || chartData.data.length === 0}
      >
        Export Data
      </Button>
    </Dropdown>
  );

  const ChartItem = {
    key: 'chart',
    label: 'Chart',
    children: <AutoChart data={chartData?.data} chartType={getChartType(chartData?.type)} />,
  };

  const SqlItem = {
    key: 'sql',
    label: 'SQL',
    children: <CodePreview code={formatSql(returnSqlVal(chartData?.sql), 'mysql') as string} language={'sql'} />,
  };

  const DataItem = {
    key: 'data',
    label: 'Data',
    children: <Table dataSource={chartData?.data} columns={columns} scroll={{ x: true }} virtual={true} />,
  };

  const TabItems: TabsProps['items'] =
    chartData?.type === 'response_table' ? [DataItem, SqlItem] : [ChartItem, SqlItem, DataItem];

  return (
    <div>
      <Tabs
        defaultActiveKey={chartData?.type === 'response_table' ? 'data' : 'chart'}
        items={TabItems}
        size='small'
        tabBarExtraContent={ExportButton}
      />

      <Modal
        title={`Export as ${exportType.toUpperCase()}`}
        open={exportModalVisible}
        onOk={handleExport}
        onCancel={() => setExportModalVisible(false)}
        okText='Export'
        cancelText='Cancel'
      >
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', marginBottom: 8 }}>File Name (optional):</label>
          <Input
            placeholder={`Leave empty to use default name (chat_table_timestamp.${exportType})`}
            value={fileName}
            onChange={e => setFileName(e.target.value)}
            onPressEnter={handleExport}
          />
        </div>
        <div style={{ fontSize: '12px', color: '#666' }}>
          Default name format: chat_table_YYYY-MM-DDTHH-mm-ss.{exportType}
        </div>
      </Modal>

      {children}
    </div>
  );
}

export default ChartView;
