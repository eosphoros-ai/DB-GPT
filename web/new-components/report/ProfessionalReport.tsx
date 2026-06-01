import { ColumnAnalysis, DatasetAnalysisSummary } from '@/new-components/analysis';
import AdvancedChart, { ChartType, createChartConfig } from '@/new-components/charts';
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  BarChartOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  DownloadOutlined,
  FileImageOutlined,
  FilePdfOutlined,
  FileTextOutlined,
  PrinterOutlined,
  ShareAltOutlined,
  TableOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { Button, Card, Col, Divider, Dropdown, Progress, Row, Space, Spin, Statistic, Table, Tag, message } from 'antd';
import React, { useMemo, useRef, useState } from 'react';

export interface ReportMetric {
  label: string;
  value: number | string;
  change?: number;
  changeLabel?: string;
  prefix?: string;
  suffix?: string;
  color?: string;
}

export interface ReportChart {
  id: string;
  title: string;
  chartType: ChartType;
  data: any[];
  xField: string;
  yField: string;
  seriesField?: string;
  description?: string;
}

export interface ReportTable {
  id: string;
  title: string;
  columns: { title: string; dataIndex: string; key: string }[];
  rows: Record<string, any>[];
}

export interface ReportInsight {
  type: 'success' | 'warning' | 'info';
  title: string;
  description: string;
}

export interface ProfessionalReportProps {
  title: string;
  subtitle?: string;
  generatedAt?: Date;
  executiveSummary?: string;
  keyMetrics?: ReportMetric[];
  charts?: ReportChart[];
  tables?: ReportTable[];
  insights?: ReportInsight[];
  dataAnalysis?: ColumnAnalysis[];
  rawContent?: string;
  onExport?: (format: 'pdf' | 'png') => void;
}

const MetricCard: React.FC<{ metric: ReportMetric }> = ({ metric }) => (
  <Card size='small' className='metric-card h-full'>
    <Statistic
      title={<span className='text-xs text-gray-500 uppercase tracking-wider'>{metric.label}</span>}
      value={metric.value}
      prefix={metric.prefix}
      suffix={metric.suffix}
      valueStyle={{
        fontSize: '1.5rem',
        fontWeight: 700,
        color: metric.color || '#111827',
      }}
    />
    {metric.change !== undefined && (
      <div className={`flex items-center gap-1 mt-2 text-sm ${metric.change >= 0 ? 'text-green-500' : 'text-red-500'}`}>
        {metric.change >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
        <span className='font-medium'>{Math.abs(metric.change).toFixed(1)}%</span>
        {metric.changeLabel && <span className='text-gray-400 ml-1'>{metric.changeLabel}</span>}
      </div>
    )}
  </Card>
);

const InsightCard: React.FC<{ insight: ReportInsight }> = ({ insight }) => {
  const config = {
    success: {
      icon: <CheckCircleOutlined />,
      color: 'text-green-600',
      bg: 'bg-green-50 dark:bg-green-900/20',
      border: 'border-green-200 dark:border-green-800',
    },
    warning: {
      icon: <WarningOutlined />,
      color: 'text-amber-600',
      bg: 'bg-amber-50 dark:bg-amber-900/20',
      border: 'border-amber-200 dark:border-amber-800',
    },
    info: {
      icon: <FileTextOutlined />,
      color: 'text-blue-600',
      bg: 'bg-blue-50 dark:bg-blue-900/20',
      border: 'border-blue-200 dark:border-blue-800',
    },
  }[insight.type];

  return (
    <div className={`p-4 rounded-xl border ${config.bg} ${config.border}`}>
      <div className={`flex items-center gap-2 mb-2 ${config.color}`}>
        {config.icon}
        <span className='font-semibold'>{insight.title}</span>
      </div>
      <p className='text-sm text-gray-600 dark:text-gray-300 leading-relaxed'>{insight.description}</p>
    </div>
  );
};

export const ProfessionalReport: React.FC<ProfessionalReportProps> = ({
  title,
  subtitle,
  generatedAt = new Date(),
  executiveSummary,
  keyMetrics = [],
  charts = [],
  tables = [],
  insights = [],
  dataAnalysis,
  rawContent,
  onExport,
}) => {
  const reportRef = useRef<HTMLDivElement>(null);
  const [exporting, setExporting] = useState(false);
  const [exportFormat, setExportFormat] = useState<'pdf' | 'png' | null>(null);

  const handleExport = async (format: 'pdf' | 'png') => {
    setExporting(true);
    setExportFormat(format);

    try {
      if (onExport) {
        onExport(format);
      } else {
        await exportReport(format);
      }
      message.success(`Report exported as ${format.toUpperCase()}`);
    } catch (error) {
      message.error(`Failed to export report: ${error}`);
    } finally {
      setExporting(false);
      setExportFormat(null);
    }
  };

  const exportReport = async (format: 'pdf' | 'png') => {
    if (!reportRef.current) return;

    const html2canvas = (await import('html2canvas')).default;

    const canvas = await html2canvas(reportRef.current, {
      scale: 2,
      useCORS: true,
      allowTaint: true,
      backgroundColor: '#ffffff',
    });

    if (format === 'png') {
      const link = document.createElement('a');
      link.download = `${title.replace(/\s+/g, '_')}_report.png`;
      link.href = canvas.toDataURL('image/png');
      link.click();
      return;
    }

    if (format === 'pdf') {
      const { jsPDF } = await import('jspdf');
      const imgData = canvas.toDataURL('image/png');
      const pdf = new jsPDF({
        orientation: canvas.width > canvas.height ? 'landscape' : 'portrait',
        unit: 'px',
        format: [canvas.width, canvas.height],
      });
      pdf.addImage(imgData, 'PNG', 0, 0, canvas.width, canvas.height);
      pdf.save(`${title.replace(/\s+/g, '_')}_report.pdf`);
      return;
    }
  };

  const exportMenuItems = [
    {
      key: 'pdf',
      label: 'Export as PDF',
      icon: <FilePdfOutlined />,
      onClick: () => handleExport('pdf'),
    },
    {
      key: 'png',
      label: 'Export as Image',
      icon: <FileImageOutlined />,
      onClick: () => handleExport('png'),
    },
    {
      type: 'divider' as const,
    },
    {
      key: 'print',
      label: 'Print Report',
      icon: <PrinterOutlined />,
      onClick: () => window.print(),
    },
  ];

  const summaryStats = useMemo(() => {
    if (!dataAnalysis?.length) return null;

    const numericCols = dataAnalysis.filter(a => a.type === 'number');
    const totalAnomalies = dataAnalysis.reduce((sum, a) => sum + a.anomalies.length, 0);
    const avgQuality = dataAnalysis.reduce((sum, a) => sum + a.quality.score, 0) / dataAnalysis.length;
    const trendingUp = numericCols.filter(a => a.trend?.direction === 'up').length;
    const trendingDown = numericCols.filter(a => a.trend?.direction === 'down').length;

    return { numericCols: numericCols.length, totalAnomalies, avgQuality, trendingUp, trendingDown };
  }, [dataAnalysis]);

  return (
    <div className='professional-report'>
      <div className='report-toolbar flex items-center justify-between mb-6 px-1'>
        <div className='flex items-center gap-3'>
          <div className='flex items-center gap-2 text-xs text-gray-400'>
            <CalendarOutlined />
            <span>
              {generatedAt.toLocaleDateString()} {generatedAt.toLocaleTimeString()}
            </span>
          </div>
          {summaryStats && (
            <>
              <Tag color='blue'>{dataAnalysis?.length} columns analyzed</Tag>
              {summaryStats.totalAnomalies > 0 && <Tag color='warning'>{summaryStats.totalAnomalies} anomalies</Tag>}
            </>
          )}
        </div>

        <Space>
          <Dropdown menu={{ items: exportMenuItems }} trigger={['click']}>
            <Button
              type='primary'
              icon={<DownloadOutlined />}
              loading={exporting}
              className='bg-gradient-to-r from-blue-600 to-indigo-600 border-none'
            >
              {exporting ? `Exporting ${exportFormat?.toUpperCase()}...` : 'Export Report'}
            </Button>
          </Dropdown>
          <Button icon={<ShareAltOutlined />}>Share</Button>
        </Space>
      </div>

      <div
        ref={reportRef}
        className='report-content bg-white dark:bg-[#1f2024] rounded-2xl border border-gray-200 dark:border-gray-800 overflow-hidden'
      >
        <div className='report-header bg-gradient-to-r from-slate-900 to-slate-800 text-white p-8'>
          <h1 className='text-3xl font-bold mb-2'>{title}</h1>
          {subtitle && <p className='text-lg text-gray-300'>{subtitle}</p>}
          <div className='mt-4 flex items-center gap-4 text-sm text-gray-400'>
            <span className='flex items-center gap-1'>
              <CalendarOutlined />
              {generatedAt.toLocaleDateString()}
            </span>
            <span>•</span>
            <span>Powered by 中涣信息 Intelligence</span>
          </div>
        </div>

        <div className='report-body p-8 space-y-8'>
          {executiveSummary && (
            <section className='executive-summary'>
              <h2 className='text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4 flex items-center gap-2'>
                <FileTextOutlined className='text-blue-500' />
                Executive Summary
              </h2>
              <div className='prose prose-sm dark:prose-invert max-w-none bg-gray-50 dark:bg-[#1a1b1e] rounded-xl p-6 border border-gray-100 dark:border-gray-700'>
                <p className='text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap'>
                  {executiveSummary}
                </p>
              </div>
            </section>
          )}

          {keyMetrics.length > 0 && (
            <section className='key-metrics'>
              <h2 className='text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4 flex items-center gap-2'>
                <BarChartOutlined className='text-green-500' />
                Key Metrics
              </h2>
              <Row gutter={[16, 16]}>
                {keyMetrics.map((metric, index) => (
                  <Col key={index} xs={12} sm={8} md={6}>
                    <MetricCard metric={metric} />
                  </Col>
                ))}
              </Row>
            </section>
          )}

          {dataAnalysis && dataAnalysis.length > 0 && (
            <section className='data-analysis-section'>
              <h2 className='text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4 flex items-center gap-2'>
                <TableOutlined className='text-purple-500' />
                Data Analysis Overview
              </h2>
              <Card size='small' className='mb-4'>
                <DatasetAnalysisSummary analyses={dataAnalysis} />
              </Card>

              <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
                {dataAnalysis.slice(0, 4).map((analysis, index) => (
                  <Card
                    key={index}
                    size='small'
                    title={
                      <div className='flex items-center justify-between'>
                        <span className='font-medium'>{analysis.column}</span>
                        <Tag color={analysis.type === 'number' ? 'blue' : 'green'}>{analysis.type}</Tag>
                      </div>
                    }
                  >
                    <div className='space-y-2 text-sm'>
                      <div className='flex justify-between'>
                        <span className='text-gray-500'>Records:</span>
                        <span className='font-medium'>{analysis.stats.count}</span>
                      </div>
                      <div className='flex justify-between'>
                        <span className='text-gray-500'>Unique:</span>
                        <span className='font-medium'>{analysis.stats.uniqueCount}</span>
                      </div>
                      {analysis.type === 'number' && analysis.stats.mean !== undefined && (
                        <>
                          <div className='flex justify-between'>
                            <span className='text-gray-500'>Mean:</span>
                            <span className='font-medium'>{analysis.stats.mean.toFixed(2)}</span>
                          </div>
                          <div className='flex justify-between'>
                            <span className='text-gray-500'>Std Dev:</span>
                            <span className='font-medium'>{analysis.stats.stdDev?.toFixed(2)}</span>
                          </div>
                        </>
                      )}
                      <div className='flex justify-between items-center'>
                        <span className='text-gray-500'>Quality:</span>
                        <Progress
                          percent={analysis.quality.score}
                          size='small'
                          style={{ width: 80 }}
                          strokeColor={
                            analysis.quality.score >= 80
                              ? '#52c41a'
                              : analysis.quality.score >= 50
                                ? '#faad14'
                                : '#ff4d4f'
                          }
                        />
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </section>
          )}

          {charts.length > 0 && (
            <section className='visualizations'>
              <h2 className='text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4 flex items-center gap-2'>
                <BarChartOutlined className='text-indigo-500' />
                Visualizations
              </h2>
              <div className='grid grid-cols-1 lg:grid-cols-2 gap-6'>
                {charts.map(chart => (
                  <Card
                    key={chart.id}
                    size='small'
                    title={<span className='font-medium'>{chart.title}</span>}
                    extra={<Tag>{chart.chartType}</Tag>}
                  >
                    {chart.description && <p className='text-xs text-gray-500 mb-3'>{chart.description}</p>}
                    <AdvancedChart
                      config={createChartConfig(chart.data, {
                        chartType: chart.chartType,
                        xField: chart.xField,
                        yField: chart.yField,
                        seriesField: chart.seriesField,
                        height: 250,
                      })}
                    />
                  </Card>
                ))}
              </div>
            </section>
          )}

          {tables.length > 0 && (
            <section className='data-tables'>
              <h2 className='text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4 flex items-center gap-2'>
                <TableOutlined className='text-cyan-500' />
                Data Tables
              </h2>
              {tables.map(table => (
                <Card key={table.id} size='small' title={table.title} className='mb-4'>
                  <Table
                    columns={table.columns}
                    dataSource={table.rows}
                    size='small'
                    pagination={{ pageSize: 5 }}
                    scroll={{ x: true }}
                    rowKey={(_, idx) => String(idx)}
                  />
                </Card>
              ))}
            </section>
          )}

          {insights.length > 0 && (
            <section className='insights'>
              <h2 className='text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4 flex items-center gap-2'>
                <CheckCircleOutlined className='text-emerald-500' />
                Key Insights
              </h2>
              <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
                {insights.map((insight, index) => (
                  <InsightCard key={index} insight={insight} />
                ))}
              </div>
            </section>
          )}

          {rawContent && (
            <section className='raw-content'>
              <Divider />
              <div className='prose prose-sm dark:prose-invert max-w-none'>
                <div className='whitespace-pre-wrap text-gray-700 dark:text-gray-300'>{rawContent}</div>
              </div>
            </section>
          )}
        </div>

        <div className='report-footer bg-gray-50 dark:bg-[#1a1b1e] border-t border-gray-200 dark:border-gray-800 p-6'>
          <div className='flex items-center justify-between text-xs text-gray-400'>
            <span>Generated by 中涣信息 Intelligent Data Analysis Platform</span>
            <span>© {new Date().getFullYear()} All rights reserved</span>
          </div>
        </div>
      </div>

      {exporting && (
        <div className='fixed inset-0 bg-black/50 flex items-center justify-center z-50'>
          <div className='bg-white dark:bg-gray-800 rounded-xl p-6 text-center'>
            <Spin size='large' />
            <p className='mt-4 text-gray-600 dark:text-gray-300'>Generating {exportFormat?.toUpperCase()} report...</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProfessionalReport;
