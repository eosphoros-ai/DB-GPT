import { ChatContext } from '@/app/chat-context';
import { ArrowDownOutlined, ArrowUpOutlined, LinkOutlined, UploadOutlined } from '@ant-design/icons';
import { Line } from '@ant-design/plots';
import type { UploadFile } from 'antd';
import {
  Button,
  Card,
  Col,
  Collapse,
  Empty,
  Input,
  Progress,
  Radio,
  Row,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Tooltip,
  Typography,
  Upload,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { NextPage } from 'next';
import { useContext, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const { Text } = Typography;

interface MetricPoint {
  fiscal_period?: string | null;
  value?: number | null;
  source_type?: string | null;
  source_url?: string | null;
  source_file?: string | null;
  page?: number | null;
  table_name?: string | null;
  evidence?: string | null;
  extracted_at?: string | null;
}

interface MetricItem {
  name: string;
  report_type?: string | null;
  latest_yoy?: number | null;
  latest_qoq?: number | null;
  points: MetricPoint[];
}

interface BreakdownItem {
  name?: string | null;
  amount?: number | null;
  ratio?: number | null;
}

interface BreakdownRecord {
  fiscal_period?: string | null;
  report_type?: string | null;
  source_type?: string | null;
  source_url?: string | null;
  extracted_at?: string | null;
  items: BreakdownItem[];
}

interface AnalyzeResult {
  company: string;
  report: string;
  metrics: MetricItem[];
  segments: BreakdownRecord[];
  regions: BreakdownRecord[];
  citations: unknown[];
}

interface CompareResult {
  companies: string[];
  report: string;
  comparison: Record<string, unknown>[];
  metrics: Record<string, MetricItem[]>;
}

interface ProvenanceRow {
  key: string;
  metric: string;
  period?: string | null;
  value?: number | null;
  source_url?: string | null;
  source_file?: string | null;
  source_type?: string | null;
  evidence?: string | null;
  extracted_at?: string | null;
}

const METRIC_LABEL_KEYS: Record<string, string> = {
  revenue: 'finance_metric_revenue',
  gross_profit: 'finance_metric_gross_profit',
  net_profit: 'finance_metric_net_profit',
  operating_cash_flow: 'finance_metric_operating_cash_flow',
  gross_margin: 'finance_metric_gross_margin',
  net_margin: 'finance_metric_net_margin',
};

const SOURCE_TYPE_KEYS: Record<string, string> = {
  eastmoney: 'finance_source_eastmoney',
  baidu: 'finance_source_baidu',
  html: 'finance_source_web',
  pdf: 'finance_source_pdf',
  csv: 'finance_source_csv',
  excel: 'finance_source_excel',
  upload: 'finance_source_upload',
};

const fmtValue = (v?: number | null) => (v === null || v === undefined || Number.isNaN(v) ? '-' : v.toFixed(2));

const fmtAmount = (v?: number | null) =>
  v === null || v === undefined || Number.isNaN(v)
    ? '-'
    : v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const API_BASE = process.env.API_BASE_URL || '';

const Finance: NextPage = () => {
  const { t } = useTranslation();
  const { mode: themeMode } = useContext(ChatContext);
  const isDark = themeMode === 'dark';
  const [mode, setMode] = useState<'single' | 'compare'>('single');
  const [company, setCompany] = useState('');
  const [compareInput, setCompareInput] = useState('');
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null);

  const metricLabel = (name: string) => {
    let base = name;
    let suffix = '';
    if (name.endsWith('(quarterly)')) {
      base = name.replace(' (quarterly)', '');
      suffix = ` ${t('finance_quarterly_suffix')}`;
    }
    const key = METRIC_LABEL_KEYS[base];
    return (key ? t(key) : base) + suffix;
  };

  const sourceTypeLabel = (type?: string | null) => {
    if (!type) return '-';
    const key = SOURCE_TYPE_KEYS[type];
    return key ? t(key) : type;
  };

  const isSafeUrl = (url?: string | null): url is string => {
    if (!url) return false;
    try {
      const parsed = new URL(url, window.location.origin);
      return parsed.protocol === 'http:' || parsed.protocol === 'https:';
    } catch {
      return false;
    }
  };

  const reportCss = `
    .report-md { font-size: 14px; }
    .report-md h1 { font-size: 22px; font-weight: 700; margin: 0 0 16px; }
    .report-md h2 {
      font-size: 17px;
      font-weight: 600;
      margin: 28px 0 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid rgba(128, 128, 128, 0.25);
    }
    .report-md h3 { font-size: 15px; font-weight: 600; margin: 20px 0 8px; }
    .report-md table {
      border-collapse: collapse;
      margin: 12px auto;
      max-width: 680px;
      font-size: 14px;
    }
    .report-md th,
    .report-md td {
      border: 1px solid rgba(128, 128, 128, 0.3);
      padding: 8px 16px;
      text-align: center;
    }
    .report-md th { background: rgba(128, 128, 128, 0.12); font-weight: 600; }
    .report-md ul { padding-left: 22px; }
    .report-md li { margin: 6px 0; line-height: 1.7; }
    .report-md p { margin: 8px 0; line-height: 1.7; }
    .report-md blockquote {
      margin: 12px 0;
      padding: 8px 16px;
      border-left: 3px solid #1677ff;
      background: rgba(128, 128, 128, 0.08);
    }
  `;

  const runAnalysis = async () => {
    if (mode === 'compare') {
      const companies = compareInput
        .split(/[,，]/)
        .map(s => s.trim())
        .filter(Boolean);
      if (companies.length < 2) {
        message.warning(t('finance_compare_need_two'));
        return;
      }
      setLoading(true);
      setResult(null);
      setCompareResult(null);
      try {
        const res = await fetch(`${API_BASE}/api/v1/finance/compare`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ companies }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || data.message || res.statusText);
        setCompareResult(data);
      } catch (e) {
        message.error(t('finance_analyze_failed') + (e as Error).message);
      } finally {
        setLoading(false);
      }
      return;
    }

    if (!company.trim()) {
      message.warning(t('finance_enter_company'));
      return;
    }
    setLoading(true);
    setResult(null);
    setCompareResult(null);
    try {
      let res: Response;
      if (fileList.length) {
        const fd = new FormData();
        fd.append('company', company.trim());
        fileList.forEach(f => {
          if (f.originFileObj) fd.append('files', f.originFileObj);
        });
        res = await fetch(`${API_BASE}/api/v1/finance/analyze/upload`, { method: 'POST', body: fd });
      } else {
        res = await fetch(`${API_BASE}/api/v1/finance/analyze`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ company: company.trim() }),
        });
      }
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.message || res.statusText);
      setResult(data);
    } catch (e) {
      message.error(t('finance_analyze_failed') + (e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const provenanceRows = useMemo<ProvenanceRow[]>(() => {
    if (!result) return [];
    return result.metrics.flatMap(m =>
      m.points.map((p, idx) => ({
        key: `${m.name}-${idx}`,
        metric: m.name,
        period: p.fiscal_period,
        value: p.value,
        source_url: p.source_url,
        source_file: p.source_file,
        source_type: p.source_type,
        evidence: p.evidence,
        extracted_at: p.extracted_at,
      })),
    );
  }, [result]);

  const trendData = useMemo(() => {
    if (!result) return [];
    const rows: { period: string; metric: string; value: number }[] = [];
    result.metrics.forEach(m => {
      if (m.name !== 'revenue' && m.name !== 'net_profit') return;
      const label = metricLabel(m.name);
      m.points.forEach(p => {
        if (p.fiscal_period && p.value !== null && p.value !== undefined) {
          rows.push({ period: p.fiscal_period, metric: label, value: p.value });
        }
      });
    });
    return rows.sort((a, b) => a.period.localeCompare(b.period));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result, t]);

  const quarterlyTrendData = useMemo(() => {
    if (!result) return [];
    const metric = result.metrics.find(m => m.name === 'revenue (quarterly)');
    if (!metric) return [];
    return metric.points
      .filter(p => p.fiscal_period && p.value !== null && p.value !== undefined)
      .map(p => ({ period: p.fiscal_period, value: p.value }))
      .sort((a, b) => a.period.localeCompare(b.period));
  }, [result]);

  const columns: ColumnsType<ProvenanceRow> = [
    {
      title: t('finance_col_metric'),
      dataIndex: 'metric',
      width: 170,
      render: (name: string) => <Tag color='blue'>{metricLabel(name)}</Tag>,
    },
    {
      title: t('finance_col_period'),
      dataIndex: 'period',
      width: 100,
      render: (p?: string | null) => p || '-',
    },
    {
      title: t('finance_col_value'),
      dataIndex: 'value',
      width: 110,
      render: (v?: number | null) => fmtValue(v),
    },
    {
      title: t('finance_col_source_type'),
      dataIndex: 'source_type',
      width: 110,
      render: (type?: string | null) => {
        const label = sourceTypeLabel(type);
        const color =
          type === 'eastmoney'
            ? 'geekblue'
            : type === 'upload' || type === 'csv' || type === 'excel'
              ? 'purple'
              : 'default';
        return <Tag color={color}>{label}</Tag>;
      },
    },
    {
      title: t('finance_col_source'),
      dataIndex: 'source_url',
      render: (url: string | null, row: ProvenanceRow) => {
        const target = row.source_file || url;
        if (!target) return '-';
        if (!isSafeUrl(url)) return <Text>{target}</Text>;
        return (
          <a href={url} target='_blank' rel='noreferrer'>
            <Space size={4}>
              <LinkOutlined />
              {target.length > 48 ? `${target.slice(0, 48)}…` : target}
            </Space>
          </a>
        );
      },
    },
    {
      title: t('finance_col_evidence'),
      dataIndex: 'evidence',
      render: (evidence?: string | null) => {
        if (!evidence) return <Text type='secondary'>{t('finance_no_evidence')}</Text>;
        return (
          <Tooltip title={evidence} placement='topLeft' overlayStyle={{ maxWidth: 480 }}>
            <Text ellipsis style={{ maxWidth: 320 }}>
              {evidence}
            </Text>
          </Tooltip>
        );
      },
    },
    {
      title: t('finance_col_extracted_at'),
      dataIndex: 'extracted_at',
      width: 160,
      render: (at?: string | null) => (at ? dayjs(at).format('YYYY-MM-DD HH:mm:ss') : '-'),
    },
  ];

  const renderMetricCards = (metrics: MetricItem[]) =>
    metrics.map(m => {
      const latest = m.points[m.points.length - 1];
      const isQuarterly = m.report_type === 'quarterly' || m.name.endsWith('(quarterly)');
      const growth = isQuarterly ? m.latest_qoq : m.latest_yoy;
      return (
        <Col key={m.name} xs={24} sm={12} md={6}>
          <Card size='small'>
            <Statistic title={metricLabel(m.name)} value={latest?.value ?? undefined} precision={2} />
            <div style={{ marginTop: 8 }}>
              <Tag
                color={growth === null || growth === undefined ? 'default' : growth >= 0 ? 'green' : 'red'}
                icon={
                  growth === null || growth === undefined ? undefined : growth >= 0 ? (
                    <ArrowUpOutlined />
                  ) : (
                    <ArrowDownOutlined />
                  )
                }
              >
                {isQuarterly ? t('finance_latest_qoq') : t('finance_latest_yoy')}:{' '}
                {growth === null || growth === undefined ? '-' : `${growth.toFixed(2)}%`}
              </Tag>
            </div>
          </Card>
        </Col>
      );
    });

  const renderBreakdown = (title: string, records: BreakdownRecord[]) => {
    if (!records || !records.length) return null;
    return (
      <Card title={title} style={{ marginTop: 24 }}>
        {records.map((r, idx) => {
          const cols: ColumnsType<BreakdownItem> = [
            {
              title: t('finance_col_name'),
              dataIndex: 'name',
              render: (v?: string | null) => v || '-',
            },
            {
              title: t('finance_col_amount'),
              dataIndex: 'amount',
              align: 'right',
              render: (v?: number | null) => fmtAmount(v),
            },
            {
              title: t('finance_col_ratio'),
              dataIndex: 'ratio',
              width: 200,
              render: (v?: number | null) => {
                if (v === null || v === undefined) return '-';
                return (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Progress
                      percent={Math.min(100, v)}
                      size='small'
                      showInfo={false}
                      strokeColor='#1677ff'
                      style={{ flex: 1, margin: 0 }}
                    />
                    <Text style={{ width: 56, textAlign: 'right' }}>{v.toFixed(2)}%</Text>
                  </div>
                );
              },
            },
          ];
          return (
            <div key={`${title}-${idx}`} style={{ maxWidth: 560, margin: '0 auto' }}>
              <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 8 }}>
                <Space size='middle'>
                  <Text strong>{r.fiscal_period || '-'}</Text>
                  {r.source_type && <Tag color='geekblue'>{sourceTypeLabel(r.source_type)}</Tag>}
                  {isSafeUrl(r.source_url) && (
                    <a href={r.source_url} target='_blank' rel='noreferrer' style={{ fontSize: 12 }}>
                      <Space size={4}>
                        <LinkOutlined />
                        来源
                      </Space>
                    </a>
                  )}
                </Space>
              </div>
              <Table
                columns={cols}
                dataSource={r.items.map((it, i) => ({ ...it, key: i }))}
                pagination={false}
                size='small'
                style={{ marginBottom: 24 }}
              />
            </div>
          );
        })}
      </Card>
    );
  };

  const renderSingleResult = () => (
    <>
      <Card title={t('finance_kpi_title')} style={{ marginTop: 24 }}>
        <Row gutter={[16, 16]}>{renderMetricCards(result!.metrics)}</Row>
      </Card>

      {trendData.length > 1 && (
        <Card title={t('finance_trend_title')} style={{ marginTop: 24 }}>
          <Line
            data={trendData}
            xField='period'
            yField='value'
            seriesField='metric'
            colorField='metric'
            height={320}
            smooth
            theme={isDark ? 'classicDark' : 'classic'}
            axis={{ x: { title: false }, y: { title: false } }}
            legend={{ color: { position: 'top' } }}
          />
        </Card>
      )}

      {quarterlyTrendData.length > 1 && (
        <Card title={t('finance_quarterly_trend_title')} style={{ marginTop: 24 }}>
          <Line
            data={quarterlyTrendData}
            xField='period'
            yField='value'
            height={280}
            smooth
            theme={isDark ? 'classicDark' : 'classic'}
            axis={{ x: { title: false }, y: { title: false } }}
            point={{ size: 4 }}
          />
        </Card>
      )}

      {renderBreakdown(t('finance_segments_title'), result!.segments)}
      {renderBreakdown(t('finance_regions_title'), result!.regions)}

      <Card title={t('finance_provenance_title')} style={{ marginTop: 24 }}>
        {provenanceRows.length ? (
          <Table
            columns={columns}
            dataSource={provenanceRows}
            pagination={{ pageSize: 8, hideOnSinglePage: true }}
            size='small'
            scroll={{ x: 900 }}
          />
        ) : (
          <Empty description={t('finance_no_results')} />
        )}
      </Card>

      <Card style={{ marginTop: 24 }}>
        <Collapse
          defaultActiveKey={['report']}
          items={[
            {
              key: 'report',
              label: t('finance_full_report'),
              children: (
                <div className='report-md' style={{ lineHeight: 1.7 }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{result!.report}</ReactMarkdown>
                  <style>{reportCss}</style>
                </div>
              ),
            },
          ]}
        />
      </Card>
    </>
  );

  const renderCompareResult = () => {
    const companies = compareResult!.companies;
    const comparisonCols: ColumnsType<Record<string, unknown>> = [
      {
        title: t('finance_col_metric'),
        dataIndex: 'metric',
        render: (v: unknown) => metricLabel(String(v ?? '')),
      },
      {
        title: `${companies[0] ?? '-'} ${t('finance_compare_latest')}`,
        dataIndex: 'company_a_latest',
        render: (v: unknown) => fmtValue(v as number | null),
      },
      {
        title: `${companies[1] ?? '-'} ${t('finance_compare_latest')}`,
        dataIndex: 'company_b_latest',
        render: (v: unknown) => fmtValue(v as number | null),
      },
      {
        title: `${companies[0] ?? '-'} ${t('finance_compare_mean')}`,
        dataIndex: 'company_a_mean',
        render: (v: unknown) => fmtValue(v as number | null),
      },
      {
        title: `${companies[1] ?? '-'} ${t('finance_compare_mean')}`,
        dataIndex: 'company_b_mean',
        render: (v: unknown) => fmtValue(v as number | null),
      },
    ];
    return (
      <>
        <Card title={t('finance_compare_title')} style={{ marginTop: 24 }}>
          <Table
            columns={comparisonCols}
            dataSource={compareResult!.comparison.map((row, i) => ({ ...row, key: i }))}
            pagination={false}
            size='small'
          />
        </Card>

        {Object.entries(compareResult!.metrics).map(([c, metrics]) => (
          <Card title={`${c}`} style={{ marginTop: 24 }} key={c}>
            <Row gutter={[16, 16]}>{renderMetricCards(metrics)}</Row>
          </Card>
        ))}

        <Card style={{ marginTop: 24 }}>
          <Collapse
            defaultActiveKey={['report']}
            items={[
              {
                key: 'report',
                label: t('finance_full_report'),
                children: (
                  <div className='report-md' style={{ lineHeight: 1.7 }}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{compareResult!.report}</ReactMarkdown>
                    <style>{reportCss}</style>
                  </div>
                ),
              },
            ]}
          />
        </Card>
      </>
    );
  };

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto', height: '100vh', overflowY: 'auto' }}>
      <Card title={t('finance_page_title')}>
        <Space direction='vertical' style={{ width: '100%' }} size='middle'>
          <Radio.Group value={mode} onChange={e => setMode(e.target.value)}>
            <Radio.Button value='single'>{t('finance_single_mode')}</Radio.Button>
            <Radio.Button value='compare'>{t('finance_compare_mode')}</Radio.Button>
          </Radio.Group>

          {mode === 'single' ? (
            <Input.Search
              placeholder={t('finance_placeholder')}
              value={company}
              onChange={e => setCompany(e.target.value)}
              enterButton={
                <Button type='primary' loading={loading}>
                  {t('finance_analyze')}
                </Button>
              }
              onSearch={runAnalysis}
              size='large'
              allowClear
            />
          ) : (
            <Input.Search
              placeholder={t('finance_compare_placeholder')}
              value={compareInput}
              onChange={e => setCompareInput(e.target.value)}
              enterButton={
                <Button type='primary' loading={loading}>
                  {t('finance_compare')}
                </Button>
              }
              onSearch={runAnalysis}
              size='large'
              allowClear
            />
          )}

          {mode === 'single' && (
            <Upload
              fileList={fileList}
              onChange={({ fileList: fl }) => setFileList(fl)}
              beforeUpload={() => false}
              multiple
            >
              <Button icon={<UploadOutlined />}>{t('finance_upload')}</Button>
              <Text type='secondary' style={{ marginLeft: 12 }}>
                {t('finance_upload_hint')}
              </Text>
            </Upload>
          )}
        </Space>
      </Card>

      {loading && (
        <div style={{ textAlign: 'center', marginTop: 32 }}>
          <Spin tip={t('finance_loading')} />
        </div>
      )}

      {result && renderSingleResult()}
      {compareResult && renderCompareResult()}
    </div>
  );
};

export default Finance;
