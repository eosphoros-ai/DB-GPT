import type { BackEndChartType } from '@/components/chart/autoChart/helpers';
import ChartView from '@/components/chat/chat-content/chart-view';
import type { ReportArtifact, ReportRun } from '@/types/report';
import type { Datum } from '@antv/ava';
import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { artifactTitle } from './artifact-title';
import { referenceLocation } from './reference-location';
import {
  buildGraph,
  executionStatus,
  projectedEdges,
  relatedNodes,
  withContainers,
  type GeneratedReportFile,
  type GraphEdge,
  type GraphNode,
  type NodeType,
  type SourceGroup,
  type TraversalDirection,
} from './report-graph-model';
import { artifactSourceName, referenceFileName, type KnowledgeSpaceNames } from './report-source';

type PointEdge = GraphEdge & { d: string; labelX: number; labelY: number };
const EMPTY_KNOWLEDGE_NAMES: KnowledgeSpaceNames = {};
const SOURCE_GROUP_LABEL: Record<SourceGroup, string> = {
  DATABASE: '数据库',
  'KNOWLEDGE BASE': '知识库',
  FILE: '上传文件',
  MEMORY: '会话记忆',
  WEB: '网页资料',
};
const META: Record<NodeType, { icon: string; label: string; color: string }> = {
  database: { icon: '库', label: '数据库', color: 'text-cyan-700 border-cyan-200 bg-cyan-50' },
  knowledge: { icon: 'KB', label: '知识库', color: 'text-violet-700 border-violet-200 bg-violet-50' },
  memory: { icon: '忆', label: '记忆', color: 'text-fuchsia-700 border-fuchsia-200 bg-fuchsia-50' },
  step: { icon: '步骤', label: '执行步骤', color: 'text-slate-700 border-slate-300 bg-white' },
  sql: { icon: 'SQL', label: 'SQL', color: 'text-blue-700 border-blue-200 bg-blue-50' },
  python: { icon: 'PY', label: 'Python', color: 'text-emerald-700 border-emerald-200 bg-emerald-50' },
  chart: { icon: '图', label: '图表', color: 'text-indigo-700 border-indigo-200 bg-indigo-50' },
  file: { icon: '文件', label: '文件', color: 'text-orange-700 border-orange-200 bg-orange-50' },
  tool: { icon: '工具', label: '工具', color: 'text-slate-700 border-slate-200 bg-slate-50' },
  skill: { icon: '技能', label: '技能', color: 'text-pink-700 border-pink-200 bg-pink-50' },
  report: { icon: '报告', label: '分析报告', color: 'text-blue-800 border-blue-300 bg-blue-50' },
};
const duration = (artifact?: ReportArtifact) => {
  const ms = artifact?.timing?.server_execution_ms ?? artifact?.duration_ms;
  return typeof ms === 'number' ? ms.toLocaleString() + ' ms' : '未记录';
};
const nativeChart = (artifact: any): { data: Datum[]; type: BackEndChartType; sql: string } | undefined => {
  const spec = artifact?.spec;
  const supported = [
    'response_line_chart',
    'response_bar_chart',
    'response_pie_chart',
    'response_scatter_chart',
    'response_area_chart',
    'response_heatmap_chart',
    'response_table',
  ];
  return spec?.renderer === 'vis-db-chart' && Array.isArray(spec.data) && supported.includes(spec.type)
    ? { data: spec.data, type: spec.type as BackEndChartType, sql: typeof spec.sql === 'string' ? spec.sql : '' }
    : undefined;
};

function NodeCard({
  node,
  dimmed,
  selected,
  onHover,
  onLeave,
  onOpen,
  expanded,
  onToggle,
  referenceCount = 0,
}: {
  node: GraphNode;
  dimmed: boolean;
  selected: boolean;
  onHover: () => void;
  onLeave: () => void;
  onOpen: () => void;
  expanded?: boolean;
  onToggle?: () => void;
  referenceCount?: number;
}) {
  const meta = META[node.type];
  return (
    <div className='relative'>
      <button
        type='button'
        data-provenance-node={node.id}
        onMouseEnter={onHover}
        onFocus={onHover}
        onMouseLeave={onLeave}
        onClick={onOpen}
        className={`relative z-10 w-full rounded-md border px-2.5 py-2 text-left transition duration-150 ${meta.color} ${selected ? 'ring-2 ring-blue-400 ring-offset-1' : ''} ${dimmed ? 'opacity-20' : 'hover:-translate-y-px hover:shadow-sm'}`}
      >
        <div className='flex min-w-0 items-center gap-1.5'>
          <span className='shrink-0 text-[9px] font-bold'>{meta.icon}</span>
          <span className='truncate text-xs font-semibold'>{node.title}</span>
          {referenceCount > 1 ? (
            <span className='ml-auto shrink-0 rounded bg-white/80 px-1 py-0.5 text-[9px] font-medium text-slate-500'>
              关联 {referenceCount}
            </span>
          ) : null}
        </div>
        <div className='mt-1 truncate text-[10px] opacity-70'>{node.subtitle || meta.label}</div>
      </button>
      {onToggle ? (
        <button
          type='button'
          aria-label={expanded ? '收起引用文件' : '展开引用文件'}
          onClick={event => {
            event.stopPropagation();
            onToggle();
          }}
          className='absolute right-1.5 top-1.5 z-20 h-4 w-4 rounded text-[11px] leading-4 text-slate-500 hover:bg-slate-200'
        >
          {expanded ? '-' : '+'}
        </button>
      ) : null}
    </div>
  );
}

type StageProps = {
  nodes: GraphNode[];
  visible: Set<string>;
  active: Set<string> | null;
  hovered?: string;
  hover: (id: string) => void;
  leave: () => void;
  open: (id: string) => void;
  references: Map<string, number>;
};

function StageCard({
  node,
  props,
  toggle,
  expanded,
}: {
  node: GraphNode;
  props: StageProps;
  toggle?: () => void;
  expanded?: boolean;
}) {
  return (
    <NodeCard
      node={node}
      selected={props.hovered === node.id}
      dimmed={!!props.active && !props.active.has(node.id)}
      onHover={() => props.hover(node.id)}
      onLeave={props.leave}
      onOpen={() => props.open(node.id)}
      referenceCount={props.references.get(node.id)}
      onToggle={toggle}
      expanded={expanded}
    />
  );
}

function SourceNodes(props: StageProps & { forceExpanded?: boolean }) {
  const [expanded, setExpanded] = useState(new Set<string>());
  const groups: SourceGroup[] = ['DATABASE', 'KNOWLEDGE BASE', 'FILE', 'MEMORY', 'WEB'];
  return (
    <div className='space-y-4'>
      {groups.map(group => {
        const roots = props.nodes.filter(
          node => node.sourceGroup === group && !node.parentId && props.visible.has(node.id),
        );
        if (!roots.length) return null;
        return (
          <div key={group} className='border-l border-slate-200 pl-3'>
            <div className='mb-2 text-[10px] font-bold tracking-[0.14em] text-slate-400'>
              {SOURCE_GROUP_LABEL[group]}
            </div>
            <div className='space-y-2'>
              {roots.map(root => {
                const children = props.nodes.filter(node => node.parentId === root.id && props.visible.has(node.id));
                const isExpanded = props.forceExpanded || expanded.has(root.id);
                const toggle = () =>
                  setExpanded(current => {
                    const next = new Set(current);
                    next.has(root.id) ? next.delete(root.id) : next.add(root.id);
                    return next;
                  });
                return (
                  <React.Fragment key={root.id}>
                    <StageCard
                      node={root}
                      props={props}
                      toggle={children.length ? toggle : undefined}
                      expanded={isExpanded}
                    />
                    {isExpanded && children.length ? (
                      <div className='ml-3 space-y-1.5 border-l border-violet-100 pl-2'>
                        {children.map(node => (
                          <StageCard key={node.id} node={node} props={props} />
                        ))}
                      </div>
                    ) : null}
                  </React.Fragment>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
function ExecutionNodes(props: StageProps) {
  return (
    <div className='space-y-2'>
      {props.nodes
        .filter(node => props.visible.has(node.id))
        .sort((a, b) => (a.order || 0) - (b.order || 0))
        .map(node => (
          <StageCard key={node.id} node={node} props={props} />
        ))}
    </div>
  );
}
function OutputNodes(props: StageProps) {
  return (
    <div className='space-y-2'>
      {props.nodes
        .filter(node => props.visible.has(node.id))
        .map(node => (
          <StageCard key={node.id} node={node} props={props} />
        ))}
    </div>
  );
}

function Details({
  node,
  nodes,
  edges,
  knowledgeNames,
  onFileOpen,
}: {
  node: GraphNode;
  nodes: GraphNode[];
  edges: GraphEdge[];
  knowledgeNames: KnowledgeSpaceNames;
  onFileOpen?: (file: GeneratedReportFile) => void;
}) {
  const artifacts = node.artifacts || [];
  const names = (side: 'input' | 'output') =>
    [
      ...new Set(
        edges
          .filter(edge => (side === 'input' ? edge.to === node.id : edge.from === node.id))
          .map(edge => nodes.find(item => item.id === (side === 'input' ? edge.from : edge.to))?.title)
          .filter(Boolean),
      ),
    ].join(' · ') || '无';
  return (
    <aside className='h-full overflow-y-auto border-l border-slate-200 bg-white p-5 text-sm'>
      <p className='text-[10px] font-bold text-slate-400'>{META[node.type].label}</p>
      <h3 className='mt-1 break-words text-base font-semibold text-slate-800'>{node.title}</h3>
      {node.file && onFileOpen ? (
        <button
          type='button'
          onClick={() => onFileOpen(node.file!)}
          className='mt-3 rounded border border-blue-200 px-3 py-1.5 text-xs text-blue-700'
        >
          打开文件
        </button>
      ) : null}
      {node.file?.filePath ? <p className='mt-3 break-all text-xs text-slate-500'>{node.file.filePath}</p> : null}
      {node.stage === 'execution' ? <p className='mt-3 text-xs text-slate-600'>{executionStatus(artifacts)}</p> : null}
      {node.tables?.length ? <p className='mt-3 text-xs text-slate-600'>输入表：{node.tables.join('、')}</p> : null}
      <div className='mt-4 space-y-3'>
        {artifacts.map(artifact => {
          const code = artifact.sql || artifact.code;
          const spec = nativeChart(artifact);
          const isReference = Boolean(artifact.reference_type);
          return (
            <details
              key={artifact.artifact_id}
              open={artifacts.length === 1}
              className='rounded border border-slate-200 p-3'
            >
              <summary className='cursor-pointer text-xs font-medium'>
                {isReference ? referenceFileName(artifact) : artifactTitle(artifact)}
              </summary>
              <dl className='mt-3 grid grid-cols-[80px_1fr] gap-y-2 text-xs text-slate-600'>
                <dt>执行耗时</dt>
                <dd>{duration(artifact)}</dd>
                <dt>状态</dt>
                <dd>{executionStatus([artifact])}</dd>
                <dt>工具</dt>
                <dd className='break-all'>{artifact.execution?.action || '未记录'}</dd>
                {artifact.metadata?.skill_name ? (
                  <>
                    <dt>技能</dt>
                    <dd>{String(artifact.metadata.skill_name)}</dd>
                  </>
                ) : null}
                {isReference || artifact.database ? (
                  <>
                    <dt>具体来源</dt>
                    <dd className='break-all'>{artifactSourceName(artifact, knowledgeNames)}</dd>
                  </>
                ) : null}
              </dl>
              {artifact.locator ? (
                <p className='mt-3 break-all text-xs text-teal-700'>引用位置：{referenceLocation(artifact.locator)}</p>
              ) : null}
              {artifact.excerpt ? (
                <blockquote className='mt-3 whitespace-pre-wrap border-l-2 border-teal-400 pl-2 text-xs leading-5 text-slate-600'>
                  {artifact.excerpt}
                </blockquote>
              ) : null}
              {code ? (
                <pre className='mt-3 max-h-60 overflow-auto whitespace-pre-wrap rounded bg-slate-900 p-3 text-[11px] text-slate-100'>
                  {code}
                </pre>
              ) : null}
              {artifact.result?.inline !== undefined ? (
                <details className='mt-3 text-xs'>
                  <summary className='cursor-pointer'>结果快照</summary>
                  <pre className='mt-2 max-h-60 overflow-auto whitespace-pre-wrap'>
                    {JSON.stringify(artifact.result.inline, null, 2)}
                  </pre>
                </details>
              ) : null}
              {spec ? (
                <div className='mt-3 overflow-hidden rounded border p-2'>
                  <ChartView data={spec.data} type={spec.type} sql={spec.sql} />
                </div>
              ) : null}
              {artifact.spec ? (
                <details className='mt-3 text-xs'>
                  <summary className='cursor-pointer'>图表规格与数据选择器</summary>
                  <pre className='mt-2 max-h-60 overflow-auto whitespace-pre-wrap'>
                    {JSON.stringify(artifact.spec, null, 2)}
                  </pre>
                </details>
              ) : null}
              {artifact.error ? <p className='mt-3 text-xs text-red-600'>{artifact.error}</p> : null}
            </details>
          );
        })}
      </div>
      <section className='mt-5'>
        <h4 className='mb-2 font-medium'>上游</h4>
        <p className='text-xs text-slate-600'>{names('input')}</p>
      </section>
      <section className='mt-4'>
        <h4 className='mb-2 font-medium'>下游</h4>
        <p className='text-xs text-slate-600'>{names('output')}</p>
      </section>
    </aside>
  );
}

export default function ClaimEvidenceGraph({
  run,
  reportRun,
  generatedFiles,
  knowledgeNames = EMPTY_KNOWLEDGE_NAMES,
  onFileOpen,
}: {
  run?: ReportRun | null;
  reportRun?: ReportRun | null;
  generatedFiles?: readonly GeneratedReportFile[];
  knowledgeNames?: KnowledgeSpaceNames;
  onFileOpen?: (file: GeneratedReportFile) => void;
  onArtifactFocus?: (stepId: string) => void;
}) {
  const activeRun = reportRun || run;
  const graph = useMemo(
    () => buildGraph(activeRun, generatedFiles, knowledgeNames),
    [activeRun, generatedFiles, knowledgeNames],
  );
  const [hovered, setHovered] = useState<string>();
  const [focus, setFocus] = useState<string>();
  const [fullscreen, setFullscreen] = useState(false);
  useEffect(() => {
    if (focus && !graph.nodes.some(node => node.id === focus)) setFocus(undefined);
  }, [focus, graph.nodes]);
  const canvasRef = useRef<HTMLDivElement>(null);
  const nodeRefs = useRef<Record<string, HTMLElement | null>>({});
  const [paths, setPaths] = useState<PointEdge[]>([]);
  const visible = useMemo(
    () =>
      focus ? withContainers(relatedNodes(focus, graph.edges), graph.nodes) : new Set(graph.nodes.map(node => node.id)),
    [focus, graph],
  );
  const active = useMemo(() => {
    if (hovered) {
      const node = graph.nodes.find(candidate => candidate.id === hovered);
      const direction: TraversalDirection =
        node?.stage === 'source' ? 'downstream' : node?.stage === 'output' ? 'upstream' : 'both';
      return withContainers(relatedNodes(hovered, graph.edges, direction), graph.nodes);
    }
    return focus ? withContainers(relatedNodes(focus, graph.edges), graph.nodes) : null;
  }, [hovered, focus, graph.edges, graph.nodes]);
  const referenceCounts = useMemo(() => {
    const counts = new Map<string, number>();
    graph.edges.forEach(edge => {
      counts.set(edge.from, (counts.get(edge.from) || 0) + 1);
      counts.set(edge.to, (counts.get(edge.to) || 0) + 1);
    });
    return counts;
  }, [graph.edges]);
  const measure = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    graph.nodes.forEach(node => {
      nodeRefs.current[node.id] = canvas.querySelector(`[data-provenance-node="${CSS.escape(node.id)}"]`)
        ?.parentElement as HTMLElement | null;
    });
    const rendered = new Set(
      graph.nodes.filter(node => visible.has(node.id) && nodeRefs.current[node.id]).map(node => node.id),
    );
    const edges = projectedEdges(graph.edges, graph.nodes, rendered);
    const root = canvas.getBoundingClientRect();
    const outgoing = new Map<string, GraphEdge[]>();
    const incoming = new Map<string, GraphEdge[]>();
    edges.forEach(edge => {
      outgoing.set(edge.from, [...(outgoing.get(edge.from) || []), edge]);
      incoming.set(edge.to, [...(incoming.get(edge.to) || []), edge]);
    });
    setPaths(
      edges.flatMap(edge => {
        const from = nodeRefs.current[edge.from]?.getBoundingClientRect();
        const to = nodeRefs.current[edge.to]?.getBoundingClientRect();
        if (!from || !to) return [];
        const fromGroup = outgoing.get(edge.from) || [];
        const toGroup = incoming.get(edge.to) || [];
        const fromIndex = fromGroup.findIndex(item => item.id === edge.id);
        const toIndex = toGroup.findIndex(item => item.id === edge.id);
        const x1 = from.right - root.left;
        const x2 = to.left - root.left;
        const y1 = from.top - root.top + Math.max(11, ((fromIndex + 1) / (fromGroup.length + 1)) * from.height);
        const y2 = to.top - root.top + Math.max(11, ((toIndex + 1) / (toGroup.length + 1)) * to.height);
        const lane = x1 + Math.min(Math.max(20, 18 + (fromIndex % 5) * 6), Math.max(20, (x2 - x1) * 0.6));
        return [{ ...edge, d: `M ${x1} ${y1} H ${lane} V ${y2} H ${x2}`, labelX: lane + 4, labelY: (y1 + y2) / 2 }];
      }),
    );
  }, [graph.edges, graph.nodes, visible]);
  useLayoutEffect(() => {
    const frame = requestAnimationFrame(measure);
    const canvas = canvasRef.current;
    const observer = typeof ResizeObserver === 'undefined' || !canvas ? undefined : new ResizeObserver(measure);
    if (canvas) observer?.observe(canvas);
    window.addEventListener('resize', measure);
    return () => {
      cancelAnimationFrame(frame);
      observer?.disconnect();
      window.removeEventListener('resize', measure);
    };
  }, [measure]);
  useEffect(() => {
    const exitOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        if (focus) setFocus(undefined);
        else setFullscreen(false);
      }
    };
    window.addEventListener('keydown', exitOnEscape);
    return () => window.removeEventListener('keydown', exitOnEscape);
  }, [focus]);
  if (!graph.nodes.length)
    return <div className='p-8 text-sm text-slate-500'>本次运行尚无可用于构建证据图谱的分析产物。</div>;
  const focusedNode = graph.nodes.find(node => node.id === focus);
  const isFocus = Boolean(focus);
  const isFullscreen = fullscreen || isFocus;
  const openNode = (id: string) => {
    setFocus(id);
  };
  const edgeActive = (edge: GraphEdge) => Boolean(hovered && active?.has(edge.from) && active?.has(edge.to));
  const stage = (title: string, hint: string, children: React.ReactNode) => (
    <section className='relative min-w-0 px-4 py-4'>
      <header className='mb-4'>
        <div className='text-xs font-semibold text-slate-800'>{title}</div>
        <div className='mt-0.5 text-[10px] text-slate-400'>{hint}</div>
      </header>
      {children}
    </section>
  );
  return (
    <div
      className={
        isFullscreen
          ? 'fixed inset-0 z-[1000] flex h-[100dvh] overflow-hidden bg-slate-50'
          : 'relative overflow-hidden rounded-lg bg-slate-50'
      }
    >
      <div className={isFullscreen ? 'flex min-h-0 min-w-0 flex-1 flex-col' : 'w-full'}>
        <div className='flex shrink-0 items-center justify-between border-b border-slate-200 bg-white px-5 py-3'>
          <div>
            <h2 className='text-sm font-semibold text-slate-800'>分析溯源图谱</h2>
            <p className='mt-0.5 text-xs text-slate-500'>数据来源 → 实际执行步骤 → 生成文件</p>
            {!isFullscreen ? (
              <p className='mt-1 text-[11px] text-slate-400'>树状主干 · 悬停节点查看跨分支引用 · 点击进入聚焦模式</p>
            ) : null}
          </div>
          <div className='flex items-center gap-2'>
            {isFocus ? (
              <button
                type='button'
                onClick={() => setFocus(undefined)}
                className='rounded border border-slate-300 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50'
              >
                ← 返回完整图谱
              </button>
            ) : null}
            <button
              type='button'
              aria-label={isFullscreen ? '退出全屏图谱' : '全屏查看图谱'}
              onClick={() => {
                if (isFullscreen) {
                  setFocus(undefined);
                  setFullscreen(false);
                } else setFullscreen(true);
              }}
              className='rounded border border-slate-300 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50'
            >
              {isFullscreen ? '↙ 退出全屏' : '⛶ 全屏查看'}
            </button>
          </div>
        </div>
        <div
          className={
            isFullscreen
              ? 'min-h-0 flex-1 overflow-x-auto overflow-y-auto overscroll-contain'
              : 'max-h-[calc(100vh-220px)] overflow-x-auto overflow-y-auto overscroll-contain'
          }
        >
          <div ref={canvasRef} className='relative min-h-full min-w-[1080px]'>
            <svg className='pointer-events-none absolute inset-0 z-0 h-full w-full overflow-visible' aria-hidden='true'>
              <defs>
                <marker id='provenance-arrow' markerWidth='6' markerHeight='6' refX='5' refY='3' orient='auto'>
                  <path d='M0,0 L6,3 L0,6' fill='none' stroke='currentColor' strokeWidth='1' />
                </marker>
              </defs>
              {paths.map(edge => (
                <g key={edge.id} className={edgeActive(edge) ? 'text-blue-500 opacity-90' : 'hidden'}>
                  <path
                    d={edge.d}
                    fill='none'
                    stroke='currentColor'
                    strokeWidth='1.6'
                    markerEnd='url(#provenance-arrow)'
                  />
                  {edgeActive(edge) ? (
                    <text
                      x={edge.labelX}
                      y={edge.labelY - 4}
                      textAnchor='middle'
                      className='fill-blue-600 text-[9px] font-medium'
                    >
                      {edge.relation}
                      {(edge.count || 1) > 1 ? ` · ${edge.count} 条` : ''}
                    </text>
                  ) : null}
                </g>
              ))}
            </svg>
            <div className='relative z-10 grid grid-cols-[minmax(230px,0.82fr)_minmax(380px,1.4fr)_minmax(250px,0.9fr)] divide-x divide-slate-200'>
              {stage(
                '1. 数据来源',
                '数据库 · 知识库 · 上传文件',
                <SourceNodes
                  nodes={graph.nodes.filter(node => node.stage === 'source')}
                  visible={visible}
                  active={hovered ? active : null}
                  hovered={hovered}
                  hover={setHovered}
                  leave={() => setHovered(undefined)}
                  open={openNode}
                  forceExpanded={isFocus}
                  references={referenceCounts}
                />,
              )}
              {stage(
                '2. 分析与执行',
                '每个步骤展示一次，点击查看执行详情',
                <ExecutionNodes
                  nodes={graph.nodes.filter(node => node.stage === 'execution')}
                  visible={visible}
                  active={hovered ? active : null}
                  hovered={hovered}
                  hover={setHovered}
                  leave={() => setHovered(undefined)}
                  open={openNode}
                  references={referenceCounts}
                />,
              )}
              {stage(
                '3. 最终产物',
                '与任务文件中的实际生成文件对应',
                <OutputNodes
                  nodes={graph.nodes.filter(node => node.stage === 'output')}
                  visible={visible}
                  active={hovered ? active : null}
                  hovered={hovered}
                  hover={setHovered}
                  leave={() => setHovered(undefined)}
                  open={openNode}
                  references={referenceCounts}
                />,
              )}
            </div>
          </div>
        </div>
      </div>
      {isFocus && focusedNode ? (
        <div className='min-h-0 w-[360px] shrink-0'>
          <Details
            node={focusedNode}
            nodes={graph.nodes}
            edges={graph.edges}
            knowledgeNames={knowledgeNames}
            onFileOpen={onFileOpen}
          />
        </div>
      ) : null}
    </div>
  );
}
