import type { ChartConfig } from '@/new-components/charts/AdvancedCharts';
import { LinkOutlined } from '@ant-design/icons';
import { Table, Tooltip } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dynamic from 'next/dynamic';
import React from 'react';
import FindingCard from './FindingCard';
import { useSingleReportData as useReportData } from './ReportDataContext';
import styles from './financial-analysis.module.css';
import { isDefined, periodRange, topicStatusNote } from './report-data';
import type { FinancialFact, OpenEvidence, ReportSectionData } from './types';

const FinancialChart = dynamic(() => import('./FinancialChart'), {
  ssr: false,
  loading: () => <div className={styles.chartLoading} aria-label='正在加载图表' />,
});
export interface ReportSectionProps {
  onOpenEvidence: OpenEvidence;
}
const Missing: React.FC = () => <p className={styles.sectionDescription}>暂无可用数据</p>;
const TopicLimitations: React.FC<{ section: string }> = ({ section }) => {
  const { data } = useReportData();
  const topics = data.workflow?.topics.filter(
    topic =>
      topic.section === section &&
      ['failed', 'insufficient', 'needs_revision', 'running', 'pending'].includes(topic.status),
  );
  if (!topics?.length) return null;
  return (
    <div aria-label='本章节分析状态'>
      {topics.map(topic => (
        <p className={styles.sectionDescription} key={topic.id}>
          {topic.title}：{topicStatusNote(topic)}
          {!!topic.findingIds.length &&
            ['failed', 'needs_revision', 'running'].includes(topic.status) &&
            ' 以下保留上次已校验结果，当前修订尚未完成。'}
        </p>
      ))}
    </div>
  );
};
const Figure: React.FC<{ title: string; caption: string; config: ChartConfig }> = ({ title, caption, config }) => (
  <figure className={styles.figure}>
    <figcaption>
      <h3>{title}</h3>
      <span className={styles.meta}>{caption}</span>
    </figcaption>
    {config.data?.length ? (
      <FinancialChart
        config={{
          height: 280,
          showLegend: true,
          showGrid: false,
          showToolbar: false,
          enableZoom: false,
          smooth: false,
          animate: false,
          colors: ['#0069fe', '#94a3b8'],
          ...config,
        }}
      />
    ) : (
      <Missing />
    )}
  </figure>
);
const HealthTable: React.FC<ReportSectionProps> = ({ onOpenEvidence }) => {
  const { data } = useReportData();
  return (
    <dl className={styles.ratioTable}>
      {!data.healthMetrics.length && <Missing />}
      {data.healthMetrics.map(metric => (
        <div key={metric.id}>
          <dt>{metric.name}</dt>
          <dd>
            {metric.selection ? (
              <button type='button' onClick={() => onOpenEvidence(metric.selection!)}>
                {metric.displayValue || '未披露'} <LinkOutlined />
              </button>
            ) : (
              metric.displayValue || '未披露'
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
};
export const OverviewTab: React.FC<ReportSectionProps> = ({ onOpenEvidence }) => {
  const { data, analysisFindingMap, financialFactMap } = useReportData();
  const findings = data.sections.overview.findingIds.map(id => analysisFindingMap[id]).filter(isDefined);
  return (
    <div className={styles.reportFlow}>
      <TopicLimitations section='overview' />
      <section aria-label='财务快照' className={styles.snapshot}>
        {!data.metrics.length && <Missing />}
        {data.metrics.map(metric => {
          const [value, ...units] = (metric.displayValue || '未披露').split(' ');
          const evidenceId = metric.factIds?.length
            ? financialFactMap[metric.factIds[0]]?.evidenceExcerptIds[0]
            : undefined;
          return (
            <div className={styles.metric} key={metric.id}>
              <div className={styles.metricLabel}>
                {metric.name}
                <Tooltip
                  title={`${metric.informationKind === 'fact' ? '披露事实' : '确定性计算'} · ${metric.citationLabel}`}
                >
                  <button
                    type='button'
                    aria-label={`${metric.name}：查看${metric.citationLabel}`}
                    onClick={() => onOpenEvidence({ metricId: metric.id, evidenceId })}
                  >
                    <LinkOutlined />
                  </button>
                </Tooltip>
              </div>
              <div className={styles.metricValue}>
                {value}
                <span>{units.join(' ')}</span>
              </div>
              {metric.changeDisplay !== undefined ? (
                <div className={styles.metricChange} data-negative={metric.changeDisplay.startsWith('-')}>
                  {metric.changeDisplay} <span>{metric.changeLabel}</span>
                </div>
              ) : (
                metric.change !== undefined && (
                  <div
                    className={styles.metricChange}
                    data-negative={metric.change < 0 || metric.code === 'debt_ratio'}
                  >
                    {metric.change > 0 ? '+' : ''}
                    {metric.change}
                    {metric.changeUnit} <span>{metric.changeLabel}</span>
                  </div>
                )
              )}
            </div>
          );
        })}
      </section>
      <section aria-label='核心研究发现'>
        {findings[0] ? <FindingCard finding={findings[0]} onOpenEvidence={onOpenEvidence} /> : <Missing />}
      </section>
      <section className={styles.reportSection}>
        <h2>业绩趋势</h2>
        <p className={styles.sectionDescription}>
          {periodRange([...data.trends.revenue, ...data.trends.cashFlow])} · 收入与利润分别呈现，保留各自金额尺度。
        </p>
        <div className={styles.trendFigures}>
          <Figure
            title='营业收入'
            caption={`${data.trends.financialUnit} · 独立纵轴`}
            config={{
              chartType: 'column',
              data: data.trends.revenue,
              xField: 'year',
              yField: 'value',
              showLegend: false,
            }}
          />
          <Figure
            title='利润与经营现金流'
            caption={data.trends.financialUnit}
            config={{
              chartType: 'line',
              data: data.trends.cashFlow,
              xField: 'year',
              yField: 'value',
              seriesField: 'metric',
            }}
          />
        </div>
      </section>
      <section className={styles.reportSection}>
        <h2>其他研究发现</h2>
        {findings.slice(1).map(finding => (
          <FindingCard key={finding.id} finding={finding} onOpenEvidence={onOpenEvidence} compact />
        ))}
      </section>
      <section className={styles.reportSection}>
        <h2>财务健康</h2>
        <HealthTable onOpenEvidence={onOpenEvidence} />
      </section>
    </div>
  );
};
export const ProfitabilityTab: React.FC<ReportSectionProps> = ({ onOpenEvidence }) => {
  const { data, analysisFindingMap, calculationTraceMap, evidenceExcerptMap } = useReportData();
  const section = data.sections.profitability;
  const findings = section.findingIds.map(id => analysisFindingMap[id]).filter(isDefined);
  type RateRow = NonNullable<ReportSectionData['rateComparisons']>[number];
  const rateColumns: ColumnsType<RateRow> = [
    { title: '指标', dataIndex: 'name', key: 'name' },
    ...(
      [
        ['本期', 'currentCalculationId'],
        ['上期', 'previousCalculationId'],
        ['变动（百分点）', 'changeCalculationId'],
      ] as const
    ).map(([title, key]) => ({
      title,
      key,
      align: 'right' as const,
      render: (_: unknown, row: RateRow) => {
        const calculation = calculationTraceMap[row[key]];
        return calculation ? (
          <button
            type='button'
            title={calculation.name}
            onClick={() => onOpenEvidence({ calculationId: calculation.id })}
          >
            {calculation.displayResult} <LinkOutlined />
          </button>
        ) : (
          '不可计算'
        );
      },
    })),
  ];
  return (
    <div className={styles.reportFlow}>
      <TopicLimitations section='profitability' />
      <section>
        <h2>{section.title || '盈利质量'}</h2>
        <p className={styles.sectionDescription}>{section.description || '暂无分析结论'}</p>
        <Figure
          title='归母与扣非归母净利润'
          caption={`${periodRange(data.trends.profit)} · ${data.trends.profitUnit} · 披露事实`}
          config={{
            chartType: 'column',
            data: data.trends.profit,
            xField: 'year',
            yField: 'value',
            seriesField: 'metric',
          }}
        />
      </section>
      {findings[0] && <FindingCard finding={findings[0]} onOpenEvidence={onOpenEvidence} />}
      <section className={styles.reportSection}>
        <h2>非经常性影响</h2>
        <p className={styles.sectionDescription}>{findings[0]?.counterEvidence?.[0]}</p>
        <dl className={styles.ratioTable}>
          {!section.calculationIds?.length && <Missing />}
          {section.calculationIds?.map(id => (
            <div key={id}>
              <dt>{calculationTraceMap[id]?.name || '缺少计算记录'}</dt>
              <dd>
                <button type='button' onClick={() => onOpenEvidence({ calculationId: id })}>
                  {calculationTraceMap[id]?.displayResult || '不可计算'}
                </button>
              </dd>
            </div>
          ))}
        </dl>
        {section.evidenceIds?.map(
          id =>
            evidenceExcerptMap[id] && (
              <button
                key={id}
                type='button'
                className={styles.textLink}
                onClick={() => onOpenEvidence({ evidenceId: id })}
              >
                查看非经常性损益披露 · {id} →
              </button>
            ),
        )}
      </section>
      <section className={styles.reportSection}>
        {!!section.rateComparisons?.length && (
          <>
            <h2>毛利率与费用率</h2>
            <p className={styles.sectionDescription}>{section.comparisonLabel} · 点击数值查看公式与来源</p>
            <Table
              rowKey='id'
              size='middle'
              columns={rateColumns}
              dataSource={section.rateComparisons}
              pagination={false}
              scroll={{ x: 640 }}
            />
          </>
        )}
        <Figure
          title='期间费用率压力'
          caption={`占营业收入比例（%） · ${[...new Set(data.trends.expenses.map(item => item.year))].sort().join(' vs ') || '期间未提供'}`}
          config={{
            chartType: 'column',
            data: data.trends.expenses,
            xField: 'expense',
            yField: 'value',
            seriesField: 'year',
            colors: ['#94a3b8', '#0069fe'],
            height: 320,
          }}
        />
        {findings.slice(1).map(finding => (
          <FindingCard key={finding.id} finding={finding} onOpenEvidence={onOpenEvidence} />
        ))}
      </section>
    </div>
  );
};
export const CashFlowTab: React.FC<ReportSectionProps> = ({ onOpenEvidence }) => {
  const { data, analysisFindingMap, calculationTraceMap } = useReportData();
  const section = data.sections.cashflow;
  const finding = analysisFindingMap[section.findingIds[0]];
  const calculation = calculationTraceMap[section.calculationIds?.[0] || ''];
  return (
    <div className={styles.reportFlow}>
      <TopicLimitations section='cashflow' />
      <section>
        <h2>{section.title || '现金创造能否支撑账面利润？'}</h2>
        <div className={styles.cashHeadline}>
          <strong>{calculation?.displayResult || '不可计算'}</strong>
          <span>
            现金利润比 {section.comparisonLabel && <span className={styles.meta}>／ {section.comparisonLabel}</span>}
          </span>
        </div>
        <Figure
          title='归母净利润与经营现金流'
          caption={`${periodRange(data.trends.cashFlow)} · ${data.trends.financialUnit} · 披露事实`}
          config={{
            chartType: 'line',
            data: data.trends.cashFlow,
            xField: 'year',
            yField: 'value',
            seriesField: 'metric',
            height: 340,
          }}
        />
      </section>
      {finding && <FindingCard finding={finding} onOpenEvidence={onOpenEvidence} />}
      {data.workflow &&
        section.findingIds
          .slice(1)
          .map(id => analysisFindingMap[id])
          .filter(isDefined)
          .map(item => <FindingCard key={item.id} finding={item} onOpenEvidence={onOpenEvidence} />)}
      <section className={styles.reportSection}>
        <h2>现金流驱动与待核查事项</h2>
        <dl className={styles.driverTable}>
          <div>
            <dt>正向对冲</dt>
            <dd>{finding?.counterEvidence?.[0] || '暂无可用数据'}</dd>
          </div>
          <div>
            <dt>待核查</dt>
            <dd>{finding?.unresolvedQuestions?.[0] || '暂无可用数据'}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
};
export const BalanceTab: React.FC<ReportSectionProps> = ({ onOpenEvidence }) => {
  const { data, financialFactMap, analysisFindingMap } = useReportData();
  const section = data.sections.balance;
  return (
    <div className={styles.reportFlow}>
      <TopicLimitations section='balance' />
      <section>
        <h2>资本结构</h2>
        <p className={styles.sectionDescription}>
          {section.description || `${data.report.fiscalPeriod} · ${data.report.statementScope}`}
        </p>
        <dl className={styles.capitalTable}>
          {!section.factIds?.length && <Missing />}
          {section.factIds?.map(id => {
            const fact = financialFactMap[id];
            return (
              <div key={id}>
                <dt>{fact?.metricName || '缺少事实记录'}</dt>
                <dd>
                  {fact?.displayValue || '未披露'}
                  {fact && (
                    <button
                      type='button'
                      className={styles.textLink}
                      onClick={() => onOpenEvidence({ factId: id, evidenceId: fact.evidenceExcerptIds[0] })}
                    >
                      {fact.evidenceExcerptIds[0]} <LinkOutlined />
                    </button>
                  )}
                </dd>
              </div>
            );
          })}
        </dl>
      </section>
      <section className={styles.reportSection}>
        <h2>偿债与流动性</h2>
        <HealthTable onOpenEvidence={onOpenEvidence} />
      </section>
      {section.findingIds.map(
        id =>
          analysisFindingMap[id] && (
            <FindingCard key={id} finding={analysisFindingMap[id]!} onOpenEvidence={onOpenEvidence} />
          ),
      )}
    </div>
  );
};
interface StatementRow {
  key: string;
  item: string;
  facts: FinancialFact[];
}
export const StatementsTab: React.FC<ReportSectionProps> = ({ onOpenEvidence }) => {
  const { data, financialFactMap, evidenceExcerptMap } = useReportData();
  const rows: StatementRow[] = data.statements.rows.map(row => ({
    key: row.id,
    item: row.name,
    facts: row.factIds.map(id => financialFactMap[id]).filter(isDefined),
  }));
  const columns: ColumnsType<StatementRow> = [
    { title: '项目', dataIndex: 'item', key: 'item' },
    ...data.statements.periods.map(period => ({
      title: period.label,
      key: period.period,
      align: 'right' as const,
      render: (_: unknown, row: StatementRow) =>
        (() => {
          const fact = row.facts.find(item => item.fiscalPeriod === period.period);
          return fact?.displayValue || '未识别';
        })(),
    })),
    {
      title: '来源',
      key: 'evidence',
      render: (_, row) => {
        const ids = [...new Set(row.facts.flatMap(fact => fact.evidenceExcerptIds))].filter(
          id => evidenceExcerptMap[id],
        );
        return ids.length ? (
          <>
            {ids.map((id, index) => (
              <React.Fragment key={id}>
                {index > 0 && ' / '}
                <button type='button' className={styles.textLink} onClick={() => onOpenEvidence({ evidenceId: id })}>
                  {id}
                </button>
              </React.Fragment>
            ))}
          </>
        ) : (
          '暂无来源'
        );
      },
    },
  ];
  return (
    <section>
      <h2>关键报表项目</h2>
      <p className={styles.sectionDescription}>
        {data.report.statementScope} · 单位：{data.statements.unit}
      </p>
      <Table size='middle' columns={columns} dataSource={rows} pagination={false} scroll={{ x: 640 }} />
    </section>
  );
};
