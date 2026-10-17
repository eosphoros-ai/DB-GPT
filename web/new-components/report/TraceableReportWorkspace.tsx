import { getStandaloneReportRun } from '@/client/api/report/standalone';
import type { BackEndChartType } from '@/components/chart/autoChart/helpers';
import ChartView from '@/components/chat/chat-content/chart-view';
import type { EvidenceReference, ReportArtifact, ReportBlock, ReportRun } from '@/types/report';
import type { Datum } from '@antv/ava';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { format as formatSql } from 'sql-formatter';
import ClaimEvidenceGraph from './ClaimEvidenceGraph';
import { artifactTitle } from './artifact-title';
import type { GeneratedReportFile } from './report-graph-model';
import { artifactSourceName, type KnowledgeSpaceNames } from './report-source';
import { useKnowledgeSpaceNames } from './use-knowledge-space-names';

export type TraceableReportView = 'report' | 'evidence';

interface TraceableReportWorkspaceProps {
  reportId: string;
  reportRunId: string;
  view: TraceableReportView;
  onArtifactFocus?: (stepId: string) => void;
  generatedFiles?: readonly GeneratedReportFile[];
  onFileOpen?: (file: GeneratedReportFile) => void;
}

const MAX_CHARS = 1_500;
const display = (value: unknown) => {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value.slice(0, MAX_CHARS);
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  try {
    return JSON.stringify(value, null, 2).slice(0, MAX_CHARS);
  } catch {
    return String(value).slice(0, MAX_CHARS);
  }
};

const formatMilliseconds = (duration?: number) => {
  if (duration === undefined || duration === null) return '未采集';
  return duration === 0 ? '< 1 ms' : `${duration} ms`;
};

const artifactTiming = (artifact: ReportArtifact) => {
  const timing = artifact.timing;
  return {
    server: formatMilliseconds(timing?.server_execution_ms ?? artifact.duration_ms),
  };
};

const artifactLabel = (artifact: ReportArtifact) => artifactDisplayName(artifact);
const artifactKind = (artifact: ReportArtifact) => {
  if (artifact.type === 'sql') return 'SQL';
  if (artifact.type === 'python') return artifact.language?.toUpperCase() || 'PY';
  if (artifact.type === 'chart') return 'CHART';
  if (artifact.reference_type === 'knowledge') return 'KB';
  if (artifact.reference_type === 'memory') return 'MEM';
  if (artifact.reference_type === 'model') return 'AI';
  return artifact.reference_type?.toUpperCase() || 'SOURCE';
};
const sourceCategory = (artifact: ReportArtifact) => {
  if (artifact.reference_type === 'knowledge') return '知识库';
  if (artifact.reference_type === 'web') return '网页资料';
  if (artifact.reference_type === 'memory') return '会话记忆';
  if (artifact.reference_type === 'model') return '模型推理';
  if (artifact.database || ['sql', 'python', 'chart'].includes(artifact.type)) return '数据库';
  return '任务输入';
};

const formatSqlForDisplay = (sql: string) => {
  try {
    return formatSql(sql, { language: 'sqlite' });
  } catch {
    return sql;
  }
};

const CollapsibleCode: React.FC<{ title: string; content: string; sql?: boolean }> = ({
  title,
  content,
  sql = false,
}) => {
  const rendered = sql ? formatSqlForDisplay(content) : content;
  const isLong = rendered.length > 480 || rendered.split('\n').length > 8;
  if (!isLong)
    return (
      <section>
        <p className='mb-2 text-xs font-semibold text-slate-500'>{title}</p>
        <pre className='max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-950 p-3 text-[11px] leading-5 text-slate-100'>
          {rendered}
        </pre>
      </section>
    );
  return (
    <details className='rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-white/[0.04]'>
      <summary className='cursor-pointer text-xs font-semibold text-slate-600 dark:text-slate-300'>
        {title}（点击展开）
      </summary>
      <pre className='mt-3 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-950 p-3 text-[11px] leading-5 text-slate-100'>
        {rendered}
      </pre>
    </details>
  );
};

const artifactDisplayName = (artifact: ReportArtifact) => {
  const text = `${artifact.name || ''}\n${artifact.sql || ''}`.toLowerCase();
  if (artifact.type === 'chart') return '分析图表';
  if (artifact.type === 'python') return '数据计算';
  if (/payment.*(sum|amount)|sum.*payment/.test(text)) return '支付方式金额统计';
  if (/count\s*\(.*order|total_orders/.test(text)) return '订单总量统计';
  if (/installment|分期/.test(text)) return '分期情况统计';
  if (/avg|average|客单价/.test(text)) return '平均值与客单价计算';
  if (/date|month|月度|trend/.test(text)) return '经营趋势统计';
  if (artifact.type === 'sql') return '业务数据查询';
  if (artifact.reference_type === 'knowledge') return '知识库依据';
  return artifactKind(artifact) === 'AI' ? '模型分析依据' : '分析执行产物';
};

const tableData = (artifact?: ReportArtifact): { columns: string[]; rows: unknown[][] } => {
  const inline = artifact?.result?.inline;
  if (inline && typeof inline === 'object' && !Array.isArray(inline)) {
    const payload = inline as { columns?: unknown; rows?: unknown };
    if (Array.isArray(payload.columns) && Array.isArray(payload.rows))
      return {
        columns: payload.columns.slice(0, 8).map(String),
        rows: payload.rows
          .slice(0, 8)
          .filter(Array.isArray)
          .map(row => (row as unknown[]).slice(0, 8)),
      };
  }
  return { columns: [], rows: [] };
};

const EvidenceTag: React.FC<{ reference: EvidenceReference; artifact?: ReportArtifact; onClick: () => void }> = ({
  reference,
  artifact,
  onClick,
}) => (
  <button
    type='button'
    onClick={event => {
      event.stopPropagation();
      onClick();
    }}
    className='rounded-md border border-blue-100 bg-blue-50 px-1.5 py-0.5 text-[10px] font-semibold text-blue-700 transition hover:border-blue-300 hover:bg-blue-100 dark:border-blue-500/20 dark:bg-blue-500/10 dark:text-blue-300'
  >
    {artifact ? artifactKind(artifact) : 'MISSING'}
    <span className='ml-1 font-normal opacity-70'>{reference.role}</span>
  </button>
);

const EvidenceDrawer: React.FC<{
  artifact?: ReportArtifact;
  reference?: EvidenceReference;
  block?: ReportBlock;
  onClose: () => void;
  knowledgeNames: KnowledgeSpaceNames;
}> = ({ artifact, block, onClose, knowledgeNames }) => {
  if (!artifact) return null;
  const result = tableData(artifact);
  const code = artifact.sql || artifact.code || artifact.excerpt;
  const timing = artifactTiming(artifact);
  return (
    <div className='fixed inset-0 z-50 flex justify-end' role='dialog' aria-modal='true' aria-label='证据详情'>
      <button
        type='button'
        aria-label='关闭证据详情'
        onClick={onClose}
        className='absolute inset-0 cursor-default bg-slate-950/40 backdrop-blur-[1px]'
      />
      <aside className='relative flex h-full w-full max-w-[460px] flex-col overflow-hidden bg-white shadow-2xl dark:bg-[#15161b]'>
        <header className='border-b border-slate-200 px-5 py-5 dark:border-slate-700'>
          <div className='flex items-start justify-between gap-4'>
            <div className='min-w-0'>
              <span className='rounded bg-blue-50 px-2 py-1 text-[10px] font-bold text-blue-700 dark:bg-blue-500/15 dark:text-blue-300'>
                {artifact.type.toUpperCase()} ·{' '}
                {artifact.status === 'succeeded' ? '执行成功' : artifact.status || '已捕获'}
              </span>
              <h2 className='mt-3 break-words text-lg font-semibold text-slate-900 dark:text-slate-100'>
                {artifactTitle(artifact)}
              </h2>
              <p className='mt-1 text-xs text-slate-500'>
                {block ? `报告块：${block.title || block.type}` : '真实执行产物'}
              </p>
            </div>
            <button
              type='button'
              onClick={onClose}
              className='rounded px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 dark:hover:bg-white/10'
            >
              关闭
            </button>
          </div>
        </header>
        <div className='flex-1 space-y-5 overflow-y-auto p-5'>
          <div className='grid grid-cols-1 gap-3 text-xs'>
            <div className='rounded-lg border border-slate-200 p-3 dark:border-slate-700'>
              <p className='text-slate-400'>执行耗时</p>
              <strong className='mt-1 block text-slate-800 dark:text-slate-100'>{timing.server}</strong>
            </div>
          </div>
          <section>
            <p className='mb-2 text-xs font-semibold text-slate-500'>来源类型</p>
            <div className='rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-700 dark:border-slate-700 dark:bg-white/[0.04] dark:text-slate-200'>
              {sourceCategory(artifact)}
            </div>
          </section>
          {artifact.type !== 'python' && artifact.type !== 'chart' && (
            <section>
              <p className='mb-2 text-xs font-semibold text-slate-500'>具体来源</p>
              <div className='rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-700 dark:border-slate-700 dark:bg-white/[0.04] dark:text-slate-200'>
                {artifactSourceName(artifact, knowledgeNames)}
              </div>
            </section>
          )}
          {code && (
            <CollapsibleCode
              title={artifact.sql ? '执行 SQL' : artifact.code ? `执行 ${artifact.language || 'Python'}` : '引用内容'}
              content={display(code)}
              sql={Boolean(artifact.sql)}
            />
          )}
          {result.columns.length > 0 && (
            <section>
              <p className='mb-2 text-xs font-semibold text-slate-500'>结果快照</p>
              <div className='overflow-auto rounded-lg border border-emerald-100'>
                <p className='bg-emerald-50 px-3 py-2 text-xs text-emerald-800'>
                  {artifact.row_count ?? result.rows.length} rows
                </p>
                <table className='min-w-full text-left text-xs'>
                  <thead>
                    <tr>
                      {result.columns.map(column => (
                        <th className='border-t bg-slate-50 px-2 py-2 font-medium' key={column}>
                          {column}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((row, index) => (
                      <tr key={index}>
                        {row.map((cell, cellIndex) => (
                          <td className='border-t px-2 py-2' key={cellIndex}>
                            {display(cell)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </div>
      </aside>
    </div>
  );
};

const nativeChartSpec = (
  artifact?: ReportArtifact,
): { data: Datum[]; sql: string; type: BackEndChartType } | undefined => {
  const spec = artifact?.spec;
  if (!spec || spec.renderer !== 'vis-db-chart' || !Array.isArray(spec.data) || typeof spec.type !== 'string')
    return undefined;
  const types: BackEndChartType[] = [
    'response_line_chart',
    'response_bar_chart',
    'response_pie_chart',
    'response_scatter_chart',
    'response_area_chart',
    'response_heatmap_chart',
    'response_table',
  ];
  if (!types.includes(spec.type as BackEndChartType)) return undefined;
  return {
    data: spec.data as Datum[],
    sql: typeof spec.sql === 'string' ? spec.sql : '',
    type: spec.type as BackEndChartType,
  };
};

const NativeChartBlock: React.FC<{ artifact?: ReportArtifact; onEvidence: () => void }> = ({
  artifact,
  onEvidence,
}) => {
  const spec = nativeChartSpec(artifact);
  if (!spec)
    return (
      <div className='mt-4 rounded-lg border border-dashed border-blue-200 bg-blue-50/40 p-5 text-sm text-blue-800 dark:border-blue-500/20 dark:bg-blue-500/10 dark:text-blue-200'>
        <strong>图表规格不可重放</strong>
        <p className='mt-1 text-xs opacity-75'>
          该历史图表没有保存原生 vis-db-chart 数据。可打开证据查看原始执行产物。
        </p>
        <button
          type='button'
          onClick={onEvidence}
          className='mt-3 rounded-md border border-blue-200 bg-white px-2 py-1 text-xs font-semibold text-blue-700'
        >
          查看证据
        </button>
      </div>
    );
  return (
    <div className='mt-4 rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-[#191a1f]'>
      <div className='mb-2 flex items-center justify-between gap-3'>
        <p className='text-xs text-slate-500'>DB-GPT 原生图表</p>
        <button
          type='button'
          onClick={onEvidence}
          className='rounded-md border border-blue-200 bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-700 hover:bg-blue-100'
        >
          查看图表证据
        </button>
      </div>
      <ChartView data={spec.data} type={spec.type} sql={spec.sql} />
    </div>
  );
};

const ReportBlockCard: React.FC<{
  block: ReportBlock;
  artifacts: Map<string, ReportArtifact>;
  onSelect: (artifact: ReportArtifact, reference: EvidenceReference, block: ReportBlock) => void;
}> = ({ block, artifacts, onSelect }) => {
  const resultArtifact =
    block.type === 'table'
      ? artifacts.get(block.data_artifact_id || '')
      : block.type === 'chart'
        ? artifacts.get(block.chart_artifact_id || '')
        : undefined;
  const data = tableData(resultArtifact);
  const metric = block.type === 'metric';
  const chartReference =
    block.evidence.find(reference => reference.artifact_id === resultArtifact?.artifact_id) || block.evidence[0];
  return (
    <article
      className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-blue-300 dark:border-slate-700 dark:bg-[#191a1f] ${metric ? '' : 'md:col-span-2'}`}
    >
      <div className='flex flex-wrap items-start justify-between gap-3'>
        <h3 className='text-sm font-semibold text-slate-800 dark:text-slate-100'>{block.title || block.type}</h3>
        <div className='flex flex-wrap gap-1'>
          {block.evidence.map(reference => (
            <EvidenceTag
              key={`${block.block_id}-${reference.artifact_id}`}
              reference={reference}
              artifact={artifacts.get(reference.artifact_id)}
              onClick={() => {
                const artifact = artifacts.get(reference.artifact_id);
                if (artifact) onSelect(artifact, reference, block);
              }}
            />
          ))}
        </div>
      </div>
      {metric && (
        <p className='mt-5 text-3xl font-bold tracking-tight text-slate-900 dark:text-white'>
          {display(block.display_value ?? block.value)}{' '}
          <span className='text-base font-medium text-slate-500'>{display(block.unit)}</span>
        </p>
      )}
      {block.type === 'table' &&
        (data.columns.length ? (
          <div className='mt-4 overflow-auto'>
            <table className='min-w-full text-left text-xs'>
              <thead>
                <tr>
                  {data.columns.map(column => (
                    <th className='border-b bg-slate-50 px-2 py-2 font-medium dark:bg-white/[0.04]' key={column}>
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row, index) => (
                  <tr key={index}>
                    {row.map((cell, cellIndex) => (
                      <td className='border-b px-2 py-2' key={cellIndex}>
                        {display(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className='mt-4 text-sm text-slate-500'>暂无可展示的结果快照</p>
        ))}
      {block.type === 'chart' && (
        <NativeChartBlock
          artifact={resultArtifact}
          onEvidence={() => {
            if (resultArtifact && chartReference) onSelect(resultArtifact, chartReference, block);
          }}
        />
      )}
      {(block.type === 'insight' || block.type === 'text') && (
        <p className='mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-700 dark:text-slate-300'>
          {display(block.content || block.description)}
        </p>
      )}
    </article>
  );
};

const ReportDashboard: React.FC<{ run: ReportRun; knowledgeNames: KnowledgeSpaceNames }> = ({
  run,
  knowledgeNames,
}) => {
  const [selected, setSelected] = useState<{
    artifact: ReportArtifact;
    reference: EvidenceReference;
    block: ReportBlock;
  }>();
  const artifacts = useMemo(
    () => new Map(run.document.artifacts.map(artifact => [artifact.artifact_id, artifact])),
    [run],
  );
  const sections = run.document.sections.filter(section => section.blocks.some(block => block.evidence.length > 0));
  if (!sections.length)
    return (
      <div className='rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900'>
        这是旧版未绑定摘要 Run：已保存 {run.document.artifacts.length}{' '}
        个执行产物，但报告块尚未建立证据关联。请重新执行任务以生成可追溯分析报告。
      </div>
    );
  return (
    <div className='space-y-8'>
      <header className='rounded-2xl bg-gradient-to-br from-[#162582] to-[#4338a3] px-6 py-7 text-white shadow-sm'>
        <p className='text-xs font-semibold uppercase tracking-[0.18em] text-blue-200'>
          Traceable Report · Schema v{run.schema_version}
        </p>
        <h1 className='mt-3 text-2xl font-bold leading-9'>{run.document.title}</h1>
        <p className='mt-3 text-sm text-blue-100'>
          真实执行产物 {run.document.artifacts.length} 个 · ReportRun Revision {run.revision}
        </p>
      </header>
      {sections.map(section => (
        <section key={section.section_id}>
          <div className='mb-3 flex items-center justify-between'>
            <h2 className='border-l-4 border-blue-600 pl-3 text-lg font-bold text-slate-900 dark:text-white'>
              {section.title}
            </h2>
            <span className='text-xs text-slate-400'>{section.blocks.length} 个报告块</span>
          </div>
          <div className='grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3'>
            {section.blocks.map(block => (
              <ReportBlockCard
                key={block.block_id}
                block={block}
                artifacts={artifacts}
                onSelect={(artifact, reference, selectedBlock) =>
                  setSelected({ artifact, reference, block: selectedBlock })
                }
              />
            ))}
          </div>
        </section>
      ))}
      <EvidenceDrawer
        artifact={selected?.artifact}
        reference={selected?.reference}
        block={selected?.block}
        onClose={() => setSelected(undefined)}
        knowledgeNames={knowledgeNames}
      />
    </div>
  );
};

export const TraceableReportWorkspace: React.FC<TraceableReportWorkspaceProps> = ({
  reportId,
  reportRunId,
  view,
  generatedFiles,
  onFileOpen,
}) => {
  const [run, setRun] = useState<ReportRun>();
  const knowledgeNames = useKnowledgeSpaceNames(run?.document.artifacts || []);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await getStandaloneReportRun(reportId, reportRunId);
      if (!response.success) throw new Error(response.err_msg || 'Report not available');
      setRun(response.data);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '无法加载本轮可追溯报告');
    } finally {
      setLoading(false);
    }
  }, [reportId, reportRunId]);
  useEffect(() => {
    load();
  }, [load]);
  if (loading)
    return (
      <div className='grid h-full min-h-[240px] place-items-center text-sm text-slate-500'>
        正在加载本轮分析产物与证据…
      </div>
    );
  if (error || !run)
    return (
      <div className='m-5 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800'>
        报告暂不可用：{error || '未知错误'}{' '}
        <button type='button' onClick={load} className='ml-2 underline'>
          重试
        </button>
      </div>
    );
  return view === 'evidence' ? (
    <ClaimEvidenceGraph
      run={run}
      generatedFiles={generatedFiles}
      knowledgeNames={knowledgeNames}
      onFileOpen={onFileOpen}
    />
  ) : (
    <ReportDashboard run={run} knowledgeNames={knowledgeNames} />
  );
};

export default TraceableReportWorkspace;
