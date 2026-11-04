import { apiInterceptors, getFlowById, getFlowTemplates, getTaskflowNodeKinds, importFlow } from '@/client/api';
import { addFlow, updateFlowById } from '@/client/api/flow';
import DebugDrawer from '@/components/taskflow/editor/DebugDrawer';
import InsertEdge from '@/components/taskflow/editor/InsertEdge';
import NodePalette from '@/components/taskflow/editor/NodePalette';
import PropertyPanel from '@/components/taskflow/editor/PropertyPanel';
import TaskflowNodeCard, { TaskflowNodeCardData } from '@/components/taskflow/editor/TaskflowNodeCard';
import type { IFlow, IFlowUpdateParam } from '@/types/flow';
import type { ITaskflowDSL, ITaskflowNode, ITaskflowNodeKind } from '@/types/taskflow';
import { emptyDSL, kindSpecOf, missingRequiredFields, nextNodeId } from '@/utils/taskflow';
import { ArrowLeftOutlined, CheckOutlined, PlayCircleOutlined, UploadOutlined } from '@ant-design/icons';
import { useRequest } from 'ahooks';
import { Button, Input, Tag, Upload, message } from 'antd';
import { useRouter } from 'next/router';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import ReactFlow, { Background, Controls, Edge, Node, NodeProps } from 'reactflow';

import 'reactflow/dist/style.css';

const nodeTypes = { taskflowNode: (props: NodeProps<TaskflowNodeCardData>) => <TaskflowNodeCard {...props} /> };
const edgeTypes = { insert: InsertEdge };

function summaryOf(node: ITaskflowNode, spec: ITaskflowNodeKind | undefined, isZh: boolean): string {
  const config = node.config ?? {};
  switch (node.kind) {
    case 'start':
      return isZh ? '读取分析目标与对话上下文' : 'Read objective and chat context';
    case 'db_query':
      return config.datasource
        ? `${config.datasource} · ≤${config.max_rows ?? 1000} ${isZh ? '行' : 'rows'}`
        : isZh
          ? '未选择数据源'
          : 'No datasource selected';
    case 'file_data':
      return config.file_name || (isZh ? '未配置文件' : 'No file configured');
    case 'agent': {
      const goal = (config.goal || '').trim();
      const short = goal.length > 20 ? `${goal.slice(0, 20)}…` : goal;
      const toolCount = (config.tools?.length ?? 0) + (config.skills?.length ?? 0);
      const toolPart = toolCount > 0 ? ` · ${toolCount} ${isZh ? '项能力' : 'tools'}` : '';
      return short ? `${short}${toolPart}` : isZh ? `未配置目标${toolPart}` : `No goal configured${toolPart}`;
    }
    case 'ai_analysis':
      return config.model
        ? `${config.model}`
        : isZh
          ? '默认模型 · 围绕分析目标执行计算'
          : 'Default model · analyze upstream data';
    case 'visualize':
      return isZh ? `最多 ${config.max_charts ?? 4} 张图表` : `Up to ${config.max_charts ?? 4} charts`;
    case 'human_confirm':
      return config.message || (isZh ? '人工检查后继续' : 'Continue after review');
    case 'report':
      return isZh ? '生成结构化分析报告' : 'Generate a structured report';
    case 'output':
      return isZh ? '整理最终结果返回对话' : 'Assemble the final answer';
    default:
      return spec ? (isZh ? spec.desc : spec.desc_en) : '';
  }
}

function TaskflowEditor() {
  const router = useRouter();
  const { t, i18n } = useTranslation();
  const isZh = i18n.language?.startsWith('zh');

  const [dsl, setDsl] = useState<ITaskflowDSL>(() => emptyDSL());
  const [flowMeta, setFlowMeta] = useState<{
    uid?: string;
    name?: string;
    label: string;
    description?: string;
    state?: string;
    isTemplate?: boolean;
  }>({ label: '' });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [debugOpen, setDebugOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const dslRef = useRef(dsl);
  dslRef.current = dsl;

  const { data: manifestData } = useRequest(async () => apiInterceptors(getTaskflowNodeKinds()));
  const manifest = useMemo(() => {
    const [, data] = (manifestData as any) ?? [];
    return (data as ITaskflowNodeKind[] | null) ?? null;
  }, [manifestData]);

  // Load existing flow or template
  useEffect(() => {
    const { id, template } = router.query as { id?: string; template?: string };
    if (!router.isReady) return;
    (async () => {
      if (id) {
        const [, flow] = await apiInterceptors(getFlowById(id));
        const item = flow as IFlow | null;
        if (item?.taskflow_source) {
          setDsl(item.taskflow_source as ITaskflowDSL);
          setFlowMeta({
            uid: item.uid,
            name: item.name,
            label: item.label,
            description: item.description,
            state: item.state,
          });
        } else if (item) {
          message.warning(t('taskflow_not_taskflow_flow') as string);
        }
      } else if (template) {
        const [, res] = await apiInterceptors(getFlowTemplates());
        const items = ((res as any)?.items ?? []) as any[];
        const found = items.find(item => item.name === template);
        if (found?.taskflow_source) {
          setDsl(found.taskflow_source as ITaskflowDSL);
          setFlowMeta({
            label: `${found.label}`,
            description: found.description,
            isTemplate: true,
          });
        }
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router.isReady, router.query.id, router.query.template]);

  // -------------------------------------------------------------------------
  // DSL operations
  // -------------------------------------------------------------------------
  const addNode = useCallback((kind: ITaskflowNodeKind, insertAt?: [string, string]) => {
    setDsl(prev => {
      const id = nextNodeId(prev);
      const config: Record<string, any> = {};
      for (const field of kind.config_fields) {
        if (field.default !== undefined && field.default !== null) config[field.name] = field.default;
      }
      const newNode: ITaskflowNode = { id, kind: kind.kind, config };
      const nodes = [...prev.nodes];
      let edges = [...prev.edges];
      if (insertAt) {
        const [src, tgt] = insertAt;
        edges = edges.filter(e => !(e[0] === src && e[1] === tgt));
        edges.push([src, id], [id, tgt]);
        const tgtIndex = nodes.findIndex(n => n.id === tgt);
        nodes.splice(tgtIndex >= 0 ? tgtIndex : nodes.length, 0, newNode);
      } else {
        const output = nodes.find(n => n.kind === 'output');
        if (output) {
          const predecessors = edges.filter(e => e[1] === output.id).map(e => e[0]);
          edges = edges.filter(e => e[1] !== output.id);
          for (const pred of predecessors.length > 0 ? predecessors : ['n1']) {
            edges.push([pred, id]);
          }
          edges.push([id, output.id]);
          const outIndex = nodes.findIndex(n => n.id === output.id);
          nodes.splice(outIndex, 0, newNode);
        } else {
          nodes.push(newNode);
        }
      }
      setSelectedId(id);
      return { ...prev, nodes, edges };
    });
  }, []);

  const deleteNode = useCallback((id: string) => {
    setDsl(prev => {
      const target = prev.nodes.find(n => n.id === id);
      if (!target || target.kind === 'start' || target.kind === 'output') return prev;
      const predecessors = prev.edges.filter(e => e[1] === id).map(e => e[0]);
      const successors = prev.edges.filter(e => e[0] === id).map(e => e[1]);
      const edges = prev.edges.filter(e => e[0] !== id && e[1] !== id);
      if (predecessors.length === 1) {
        for (const succ of successors) edges.push([predecessors[0], succ]);
      }
      return { ...prev, nodes: prev.nodes.filter(n => n.id !== id), edges };
    });
    setSelectedId(current => (current === id ? null : current));
  }, []);

  const updateNode = useCallback((id: string, patch: { label?: string; config: Record<string, any> }) => {
    setDsl(prev => ({
      ...prev,
      nodes: prev.nodes.map(n => (n.id === id ? { ...n, label: patch.label ?? n.label, config: patch.config } : n)),
    }));
  }, []);

  // -------------------------------------------------------------------------
  // DSL -> ReactFlow
  // -------------------------------------------------------------------------
  const [insertRequest, setInsertRequest] = useState<[string, string] | null>(null);

  const orderedNodes = useMemo(() => {
    // Linear chain order following edges from start (fall back to declaration).
    const byId = new Map(dsl.nodes.map(n => [n.id, n] as const));
    const nextOf = new Map(dsl.edges.map(([s, t]) => [s, t] as const));
    const start = dsl.nodes.find(n => n.kind === 'start') ?? dsl.nodes[0];
    const chain: ITaskflowNode[] = [];
    const seen = new Set<string>();
    let current: ITaskflowNode | undefined = start;
    while (current && !seen.has(current.id)) {
      chain.push(current);
      seen.add(current.id);
      const nextId = nextOf.get(current.id);
      current = nextId ? byId.get(nextId) : undefined;
    }
    for (const node of dsl.nodes) {
      if (!seen.has(node.id)) chain.push(node);
    }
    return chain;
  }, [dsl]);

  const { rfNodes, rfEdges } = useMemo(() => {
    const nodes: Node<TaskflowNodeCardData>[] = orderedNodes.map((node, index) => ({
      id: node.id,
      type: 'taskflowNode',
      position: { x: 340, y: 40 + index * 118 },
      draggable: false,
      data: {
        node,
        spec: kindSpecOf(manifest, node.kind),
        index,
        summary: summaryOf(node, kindSpecOf(manifest, node.kind), isZh),
        onDelete: deleteNode,
      },
    }));
    const edges: Edge[] = dsl.edges.map(([src, tgt]) => ({
      id: `${src}->${tgt}`,
      source: src,
      target: tgt,
      type: 'insert',
      data: {
        insertAt: [src, tgt] as [string, string],
        onInsert: (at: [string, string]) => setInsertRequest(at),
      },
    }));
    return { rfNodes: nodes, rfEdges: edges };
  }, [orderedNodes, dsl.edges, manifest, isZh, deleteNode]);

  const selectedNode = useMemo(() => dsl.nodes.find(n => n.id === selectedId) ?? null, [dsl, selectedId]);

  // -------------------------------------------------------------------------
  // Save / publish
  // -------------------------------------------------------------------------
  const buildPayload = useCallback(
    (state: 'developing' | 'deployed'): IFlowUpdateParam => {
      const label = flowMeta.label?.trim() || (t('taskflow_untitled') as string);
      const name =
        flowMeta.name ||
        label
          .trim()
          .toLowerCase()
          .replace(/[^a-z0-9一-龥]+/g, '_')
          .replace(/^_+|_+$/g, '') ||
        `taskflow_${Date.now()}`;
      return {
        uid: flowMeta.uid,
        name,
        label,
        description: flowMeta.description,
        editable: true,
        state,
        flow_category: 'chat_flow',
        flow_format: 'taskflow',
        taskflow_source: dslRef.current,
      };
    },
    [flowMeta, t],
  );

  const validateAll = useCallback(
    (strict: boolean): boolean => {
      if (!manifest) return true;
      for (const node of dslRef.current.nodes) {
        const missing = missingRequiredFields(node, kindSpecOf(manifest, node.kind));
        if (missing.length > 0) {
          if (strict) {
            message.warning(
              `${node.label || node.kind}: ${t('taskflow_required_config_missing')} (${missing.join(', ')})`,
            );
            setSelectedId(node.id);
            return false;
          }
        }
      }
      return true;
    },
    [manifest, t],
  );

  const handleSave = useCallback(
    async (publish: boolean) => {
      if (saving) return;
      if (!validateAll(publish)) return;
      setSaving(true);
      try {
        const payload = buildPayload(publish ? 'deployed' : 'developing');
        const [err, res] = await apiInterceptors(payload.uid ? updateFlowById(payload.uid, payload) : addFlow(payload));
        if (err) {
          message.error(String((err as any)?.err_msg || err));
          return;
        }
        const saved = res as IFlow | null;
        message.success(t(publish ? 'taskflow_publish_success' : 'taskflow_save_success'));
        setFlowMeta(prev => ({
          ...prev,
          uid: saved?.uid ?? prev.uid,
          name: saved?.name ?? prev.name,
          state: publish ? 'deployed' : 'developing',
        }));
        if (!flowMeta.uid && saved?.uid) {
          router.replace({ pathname: '/taskflow/editor', query: { id: saved.uid } }, undefined, {
            shallow: true,
          });
        }
      } finally {
        setSaving(false);
      }
    },
    [buildPayload, flowMeta.uid, router, saving, t, validateAll],
  );

  const handleImport = useCallback(
    async (file: File) => {
      const formData: any = new FormData();
      formData.append('file', file);
      const [err, , res] = await apiInterceptors(importFlow(formData));
      if (err) {
        message.error(String(err));
        return false;
      }
      const flow = res?.data as any;
      if (flow?.taskflow_source) {
        setDsl(flow.taskflow_source as ITaskflowDSL);
        setFlowMeta({ label: flow.label ?? '', description: flow.description });
      } else {
        message.warning(t('taskflow_not_taskflow_flow') as string);
      }
      return false;
    },
    [t],
  );

  const stateTag = useMemo(() => {
    if (flowMeta.isTemplate) return <Tag color='blue'>{t('taskflow_builtin')}</Tag>;
    if (flowMeta.state === 'deployed' || flowMeta.state === 'running')
      return <Tag color='green'>{t('taskflow_published')}</Tag>;
    if (flowMeta.uid) return <Tag color='orange'>{t('taskflow_draft')}</Tag>;
    return null;
  }, [flowMeta, t]);

  return (
    <div className='flex flex-col h-screen overflow-hidden bg-gray-50 dark:bg-[#101114]'>
      {/* Top bar */}
      <div className='h-[54px] flex-none flex items-center gap-2.5 px-4 border-b border-gray-100 dark:border-white/10 bg-white dark:bg-[#16171a]'>
        <Button type='text' icon={<ArrowLeftOutlined />} onClick={() => router.push('/construct/taskflow')} />
        <Input
          variant='borderless'
          value={flowMeta.label}
          placeholder={t('taskflow_untitled') as string}
          onChange={e => setFlowMeta(prev => ({ ...prev, label: e.target.value }))}
          className='!w-56 !text-[15px] !font-bold'
        />
        {stateTag}
        <Input
          variant='borderless'
          value={flowMeta.description}
          placeholder={t('taskflow_desc_placeholder') as string}
          onChange={e => setFlowMeta(prev => ({ ...prev, description: e.target.value }))}
          className='!flex-1 !text-xs !text-gray-400'
        />
        <Upload accept='.json' showUploadList={false} beforeUpload={file => handleImport(file)}>
          <Button icon={<UploadOutlined />}>{t('taskflow_import')}</Button>
        </Upload>
        <Button icon={<PlayCircleOutlined />} onClick={() => setDebugOpen(true)}>
          {t('taskflow_debug')}
        </Button>
        <Button loading={saving} onClick={() => handleSave(false)}>
          {t('taskflow_save')}
        </Button>
        <Button type='primary' icon={<CheckOutlined />} loading={saving} onClick={() => handleSave(true)}>
          {t('taskflow_publish')}
        </Button>
      </div>

      {/* NL edit bar (P1 placeholder) */}
      <div className='px-4 pt-2.5 bg-white dark:bg-[#16171a]'>
        <div className='flex items-center gap-2.5 border border-gray-100 dark:border-white/10 rounded-lg px-3.5 py-2 text-[12.5px] text-gray-400 bg-gray-50 dark:bg-white/5'>
          <span className='text-violet-500'>✦</span>
          <span>{t('taskflow_nl_edit_placeholder')}</span>
          <Tag className='ml-auto !text-[10px]' color='default'>
            P1
          </Tag>
        </div>
      </div>

      {/* Body: palette / canvas / property */}
      <div className='flex-1 flex min-h-0'>
        <NodePalette manifest={manifest} onAdd={kind => addNode(kind)} />
        <div className='flex-1 min-w-0 relative'>
          <div className='absolute top-0 left-0 right-0 z-10 px-4 py-2 text-[11.5px] text-gray-400 bg-gray-50/80 dark:bg-[#101114]/80 backdrop-blur'>
            <b className='text-gray-500 font-semibold'>{t('taskflow_editor')}</b>
            <span className='ml-2'>{t('taskflow_canvas_hint')}</span>
          </div>
          <ReactFlow
            nodes={rfNodes}
            edges={rfEdges}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            onNodeClick={(_, node) => setSelectedId(node.id)}
            onPaneClick={() => setSelectedId(null)}
            fitView
            minZoom={0.4}
            maxZoom={1.5}
            nodesDraggable={false}
            nodesConnectable={false}
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={22} size={1} className='!stroke-gray-200 dark:!stroke-gray-700' />
            <Controls showInteractive={false} />
          </ReactFlow>
          {/* Insert-kind menu (anchored near top center for simplicity) */}
          {insertRequest && (
            <div className='absolute left-1/2 top-16 -translate-x-1/2 z-20 bg-white dark:bg-[#1f2126] border border-gray-100 dark:border-white/10 rounded-xl shadow-lg p-2 w-64'>
              <div className='text-[11px] font-semibold text-gray-400 px-2 py-1'>{t('taskflow_insert_node')}</div>
              {(manifest ?? [])
                .filter(item => item.group !== 'boundary')
                .map(item => (
                  <button
                    key={item.kind}
                    className='w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 text-left'
                    onClick={() => {
                      addNode(item, insertRequest);
                      setInsertRequest(null);
                    }}
                  >
                    <span className='text-sm'>{item.icon}</span>
                    <span className='text-[12.5px] text-gray-700 dark:text-gray-200'>
                      {isZh ? item.label : item.label_en}
                    </span>
                  </button>
                ))}
              <button
                className='w-full text-center text-[11px] text-gray-400 py-1 hover:text-gray-600'
                onClick={() => setInsertRequest(null)}
              >
                {t('cancel')}
              </button>
            </div>
          )}
        </div>
        <PropertyPanel
          node={selectedNode}
          spec={kindSpecOf(manifest, selectedNode?.kind ?? '')}
          onChange={updateNode}
        />
      </div>

      <DebugDrawer
        open={debugOpen}
        onClose={() => setDebugOpen(false)}
        buildPayload={() => buildPayload('developing') as unknown as Record<string, any>}
        dslNodes={orderedNodes}
      />
    </div>
  );
}

export default function TaskflowEditorPage() {
  return <TaskflowEditor />;
}
