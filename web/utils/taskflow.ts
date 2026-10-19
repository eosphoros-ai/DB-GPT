/**
 * TaskFlow helpers: DSL manipulation, stream parsing and template handling.
 */
import { apiInterceptors } from '@/client/api';
import { addFlow, getFlowById } from '@/client/api/flow';
import type { IFlow } from '@/types/flow';
import type {
  ITaskflowDSL,
  ITaskflowNode,
  ITaskflowNodeKind,
  ITaskflowRef,
  ITaskflowStepMarker,
  TaskflowGroup,
} from '@/types/taskflow';

export const TASKFLOW_STEP_VIS_TAG = 'vis-flow-step';

/** Palette group order + colors (aligned with docs/design/taskflow-mockups). */
export const TASKFLOW_GROUPS: Array<{ key: TaskflowGroup; color: string; bg: string }> = [
  { key: 'source', color: '#2563eb', bg: '#eff6ff' },
  { key: 'analysis', color: '#7c3aed', bg: '#f5f3ff' },
  { key: 'control', color: '#d97706', bg: '#fffbeb' },
  { key: 'output', color: '#16a34a', bg: '#f0fdf4' },
  { key: 'boundary', color: '#16a34a', bg: '#f0fdf4' },
];

export function groupColor(group: TaskflowGroup): { color: string; bg: string } {
  return (
    TASKFLOW_GROUPS.find(g => g.key === group) ?? {
      color: '#57534e',
      bg: '#f5f5f4',
    }
  );
}

export function emptyDSL(): ITaskflowDSL {
  return {
    format: 'taskflow/1',
    nodes: [
      { id: 'n1', kind: 'start', config: {} },
      { id: 'n2', kind: 'output', config: {} },
    ],
    edges: [['n1', 'n2']],
  };
}

export function nextNodeId(dsl: ITaskflowDSL): string {
  let max = 0;
  for (const node of dsl.nodes) {
    const match = /^n(\d+)$/.exec(node.id);
    if (match) max = Math.max(max, parseInt(match[1], 10));
  }
  return `n${max + 1}`;
}

/** Content nodes of the DSL (everything between start and output). */
export function dslStepDefs(dsl?: ITaskflowDSL): ITaskflowNode[] {
  if (!dsl?.nodes) return [];
  return dsl.nodes;
}

export function countContentNodes(dsl?: ITaskflowDSL): number {
  if (!dsl?.nodes) return 0;
  return dsl.nodes.length;
}

// ---------------------------------------------------------------------------
// Stream parsing: vis-flow-step markers -> steps, remainder -> clean text
// ---------------------------------------------------------------------------

export interface ITaskflowSection {
  marker: ITaskflowStepMarker;
  /** The node output content that follows the marker (until the next one). */
  content: string;
}

export interface ParsedTaskflowStream {
  markers: ITaskflowStepMarker[];
  /** The answer text with all step markers removed. */
  cleanText: string;
  /** Per-node output sections, in execution order. */
  sections: ITaskflowSection[];
  /** Text outside any node section (before the first marker). */
  residual: string;
}

const STEP_BLOCK_RE = /```vis-flow-step\s*\n([\s\S]*?)```/g;

export function parseTaskflowStream(text: string): ParsedTaskflowStream {
  if (!text) return { markers: [], cleanText: '', sections: [], residual: '' };
  const markers: ITaskflowStepMarker[] = [];
  const sections: ITaskflowSection[] = [];

  // Split into [before, marker1, content1, marker2, content2, ...] spans.
  const spans: Array<{ type: 'text' | 'marker'; value: string }> = [];
  let lastIndex = 0;
  for (const match of text.matchAll(STEP_BLOCK_RE)) {
    const index = match.index ?? 0;
    if (index > lastIndex) {
      spans.push({ type: 'text', value: text.slice(lastIndex, index) });
    }
    spans.push({ type: 'marker', value: match[1] });
    lastIndex = index + match[0].length;
  }
  if (lastIndex < text.length) {
    spans.push({ type: 'text', value: text.slice(lastIndex) });
  }

  let residual = '';
  let pendingMarker: ITaskflowStepMarker | null = null;
  for (const span of spans) {
    if (span.type === 'marker') {
      try {
        const parsed = JSON.parse(span.value.trim());
        if (parsed && parsed.step_id) {
          pendingMarker = parsed as ITaskflowStepMarker;
          markers.push(pendingMarker);
          continue;
        }
      } catch {
        /* fall through: malformed marker treated as text */
      }
      if (pendingMarker) {
        pendingMarker = null;
      }
      residual += `\`\`\`vis-flow-step\n${span.value}\`\`\``;
      continue;
    }
    if (pendingMarker) {
      sections.push({ marker: pendingMarker, content: span.value.trim() });
      pendingMarker = null;
    } else {
      residual += span.value;
    }
  }
  // A trailing marker with no content still counts as a section.
  if (pendingMarker) {
    sections.push({ marker: pendingMarker, content: '' });
  }

  // Live step events re-send each completed step, then the final join output
  // repeats every marker. Deduplicate by step_id (keep the last occurrence)
  // so sections, markers and the narrative stay single-copy.
  const sectionMap = new Map<string, ITaskflowSection>();
  for (const section of sections) {
    sectionMap.set(section.marker.step_id, section);
  }
  const dedupedSections = Array.from(sectionMap.values());
  const markerMap = new Map<string, ITaskflowStepMarker>();
  for (const marker of markers) {
    markerMap.set(marker.step_id, marker);
  }
  const dedupedMarkers = Array.from(markerMap.values());

  // Structured agent steps (ReAct trace) live only in the transient running
  // frames; the canonical final frame carries the clean answer but no steps.
  // Merge: content from the last frame, steps from the last frame that had
  // any — so the trace stays visible after the run completes.
  const stepsByStepId = new Map<string, ITaskflowStepMarker['steps']>();
  for (const marker of markers) {
    if (marker.steps && marker.steps.length > 0) {
      stepsByStepId.set(marker.step_id, marker.steps);
    }
  }
  for (const marker of dedupedMarkers) {
    if (!marker.steps?.length && stepsByStepId.has(marker.step_id)) {
      marker.steps = stepsByStepId.get(marker.step_id);
    }
  }
  for (const section of dedupedSections) {
    if (!section.marker.steps?.length && stepsByStepId.has(section.marker.step_id)) {
      section.marker.steps = stepsByStepId.get(section.marker.step_id);
    }
  }

  const cleanText = [residual.trim(), ...dedupedSections.map(section => section.content)]
    .filter(Boolean)
    .join('\n\n')
    .trim();
  return {
    markers: dedupedMarkers,
    cleanText,
    sections: dedupedSections,
    residual: residual.trim(),
  };
}

/**
 * Remove all gpt-vis blocks (```vis-xxx ... ```) from text, leaving the
 * narrative/conclusion only. Used to show the flow's textual answer below the
 * run card while charts/tables stay inside their step details.
 */
const VIS_BLOCK_RE = /```vis-[a-z0-9_-]*\s*\n[\s\S]*?```/g;

export function stripVisBlocks(text: string): string {
  if (!text) return '';
  return text.replace(VIS_BLOCK_RE, '').trim();
}

/**
 * Remove the agent-node live trace narration (``💭 **Thinking** …``,
 * ``🔧 **tool** …``, ``👁 **Observation** …`` plus the collapsed-prefix line)
 * that TFAgentOperator appends to live frames. The structured trace lives in
 * the node card; the answer area must never show it.
 */
const NARRATION_LINE_RE = /^\s*(\u{1F4AD}|\u{1F527}|\u{1F441}|\u2705|\u2022|\u2026)/u;

export function stripFlowNarration(text: string): string {
  if (!text) return '';
  return text
    .split('\n')
    .filter(line => !NARRATION_LINE_RE.test(line))
    .join('\n')
    .trim();
}

// ---------------------------------------------------------------------------
// Template instantiation: a built-in template becomes a real flow on first use
// ---------------------------------------------------------------------------

// The server recompiles taskflow entities from their DSL on load, so existing
// instances self-heal when the compiler changes — no cache bump needed. Bump
// the version only if the instance *creation* params change (name/label/etc).
const TEMPLATE_INSTANCE_KEY = 'taskflow_template_instances_v3';

function readInstanceCache(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(TEMPLATE_INSTANCE_KEY) || '{}');
  } catch {
    return {};
  }
}

function writeInstanceCache(cache: Record<string, string>) {
  try {
    localStorage.setItem(TEMPLATE_INSTANCE_KEY, JSON.stringify(cache));
  } catch {
    /* ignore */
  }
}

/**
 * Resolve a runnable flow uid for a chat-menu flow reference. Built-in
 * templates are instantiated as deployed flows on first use (cached in
 * localStorage); user flows pass through directly.
 */
export async function resolveFlowUid(ref: ITaskflowRef): Promise<string | null> {
  if (!ref.isTemplate && ref.uid) return ref.uid;
  const cacheKey = ref.name;
  const cache = readInstanceCache();
  const cachedUid = cache[cacheKey];
  if (cachedUid) {
    const [, flow] = await apiInterceptors(getFlowById(cachedUid));
    if ((flow as IFlow | null)?.uid) return cachedUid;
  }
  if (!ref.taskflow_source) return null;
  const [err, created] = await apiInterceptors(
    addFlow({
      name: `${ref.name}_instance`,
      label: ref.label,
      description: ref.description,
      editable: true,
      state: 'deployed',
      flow_category: 'chat_flow',
      flow_format: 'taskflow',
      taskflow_source: ref.taskflow_source,
    }),
  );
  const uid = (created as IFlow | null)?.uid;
  if (err || !uid) return null;
  cache[cacheKey] = uid;
  writeInstanceCache(cache);
  return uid;
}

// ---------------------------------------------------------------------------
// Misc converters
// ---------------------------------------------------------------------------

export function flowToRef(flow: IFlow): ITaskflowRef | null {
  if (flow.flow_format !== 'taskflow' || !flow.taskflow_source) return null;
  return {
    uid: flow.uid,
    name: flow.name,
    label: flow.label,
    description: flow.description,
    isTemplate: false,
    nodeCount: flow.taskflow_source.nodes?.length ?? 0,
    taskflow_source: flow.taskflow_source as ITaskflowDSL,
  };
}

export function templateToRef(template: any): ITaskflowRef | null {
  if (template?.flow_format !== 'taskflow' || !template?.taskflow_source) return null;
  return {
    name: template.name,
    label: template.label,
    description: template.description,
    isTemplate: true,
    nodeCount: template.taskflow_source.nodes?.length ?? 0,
    taskflow_source: template.taskflow_source as ITaskflowDSL,
  };
}

export function kindSpecOf(
  manifest: ITaskflowNodeKind[] | null | undefined,
  kind: string,
): ITaskflowNodeKind | undefined {
  return manifest?.find(item => item.kind === kind);
}

/** Validate required config fields of a DSL node against its kind spec. */
export function missingRequiredFields(node: ITaskflowNode, spec?: ITaskflowNodeKind): string[] {
  if (!spec) return [];
  return spec.config_fields.filter(field => field.required && !node.config?.[field.name]).map(field => field.name);
}
