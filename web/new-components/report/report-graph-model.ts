import type { ReportArtifact, ReportRun } from '../../types/report';
import { artifactTitle } from './artifact-title';
import { reportText } from './report-i18n';
import {
  artifactSourceName,
  isKnowledgeReference,
  knowledgeSpaceId,
  knowledgeSpaceName,
  referenceFileName,
  type KnowledgeSpaceNames,
} from './report-source';

export type Stage = 'source' | 'execution' | 'output';
export type NodeType =
  'database' | 'knowledge' | 'memory' | 'step' | 'sql' | 'python' | 'chart' | 'file' | 'tool' | 'skill' | 'report';
export type SourceGroup = 'DATABASE' | 'KNOWLEDGE BASE' | 'MEMORY' | 'FILE' | 'WEB';
export type Relation = 'READS' | 'DERIVES_FROM' | 'INCLUDED_IN' | 'PRODUCES' | 'REFERENCES';
export interface GeneratedReportFile {
  id: string;
  name: string;
  type: string;
  filePath?: string;
  content?: unknown;
  stepId?: string;
}
export interface GraphNode {
  id: string;
  stage: Stage;
  type: NodeType;
  title: string;
  subtitle?: string;
  sourceGroup?: SourceGroup;
  parentId?: string;
  artifact?: ReportArtifact;
  artifacts?: ReportArtifact[];
  file?: GeneratedReportFile;
  order?: number;
  tables?: string[];
}
export interface GraphEdge {
  id: string;
  from: string;
  to: string;
  relation: Relation;
  count?: number;
}
const record = (value: unknown): Record<string, any> =>
  value && typeof value === 'object' ? (value as Record<string, any>) : {};
const string = (value: unknown) => (typeof value === 'string' || typeof value === 'number' ? String(value).trim() : '');
const pathKey = (value: unknown) =>
  string(value)
    .replace(/\\/g, '/')
    .replace(/[?#].*$/, '');
const unique = (values: string[]) => [...new Set(values.filter(Boolean))];
const actionTitle = (action: string) => {
  if (action === 'sql_query') return reportText('evidence_graph_action_sql');
  if (action === 'code_interpreter') return reportText('evidence_graph_action_python');
  if (action === 'execute_analysis') return reportText('evidence_graph_action_analysis');
  if (action === 'knowledge.semantic_search' || action === 'knowledge_retrieve')
    return reportText('evidence_graph_action_knowledge_search');
  if (action === 'knowledge.cat') return reportText('evidence_graph_action_knowledge_read');
  if (action === 'knowledge.grep') return reportText('evidence_graph_action_knowledge_grep');
  return action;
};
export function executionStatus(artifacts: readonly ReportArtifact[]): string {
  const states = unique(artifacts.map(artifact => artifact.status || ''));
  if (!states.length) return reportText('evidence_graph_status_unrecorded');
  if (states.length > 1)
    return states.includes('failed')
      ? reportText('evidence_graph_partial_failed')
      : reportText('evidence_graph_inconsistent');
  if (states[0] === 'succeeded') return reportText('evidence_graph_status_succeeded');
  if (states[0] === 'failed') return reportText('evidence_graph_status_failed');
  if (states[0] === 'cancelled') return reportText('evidence_graph_status_cancelled');
  if (states[0] === 'timed_out') return reportText('evidence_graph_status_timed_out');
  return reportText('evidence_graph_status_unrecorded');
}
const artifactPaths = (artifact: ReportArtifact) =>
  unique(
    [
      artifact.uri,
      artifact.output?.uri,
      artifact.metadata?.file_path,
      artifact.metadata?.path,
      artifact.metadata?.output_path,
      artifact.metadata?.source_path,
      artifact.metadata?.image_url,
      artifact.locator?.path,
    ].map(pathKey),
  );
const filePath = (file: GeneratedReportFile) =>
  pathKey(
    file.filePath ||
      record(file.content).file_path ||
      record(file.content).path ||
      (typeof file.content === 'string' && !file.content.includes('<') ? file.content : ''),
  );

export function buildGraph(
  run?: ReportRun | null,
  files?: readonly GeneratedReportFile[],
  names: KnowledgeSpaceNames = {},
) {
  const document = run?.document;
  const artifacts = document?.artifacts || [];
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];
  const nodeMap = new Map<string, GraphNode>();
  const execution = new Map<string, string>();
  const sourceReferences = new Map<string, string>();
  const byArtifact = new Map(artifacts.map(artifact => [artifact.artifact_id, artifact]));
  const isDerivativeCapture = (artifact: ReportArtifact) =>
    ['code_interpreter.image', 'report_chart.prepare', 'template_chart.prepare', 'chart_action.render'].includes(
      artifact.execution?.action || '',
    ) && artifact.input_artifact_ids?.some(id => byArtifact.has(id) && byArtifact.get(id)?.type !== 'reference');
  const spaceIdsByName = new Map<string, string>();
  artifacts.filter(isKnowledgeReference).forEach(artifact => {
    const id = knowledgeSpaceId(artifact);
    if (/^\d+$/.test(id)) spaceIdsByName.set(knowledgeSpaceName(artifact, names), id);
  });
  const add = (node: GraphNode, evidence?: ReportArtifact) => {
    let existing = nodeMap.get(node.id);
    if (!existing) {
      existing = { ...node, artifacts: [] };
      nodeMap.set(node.id, existing);
      nodes.push(existing);
    }
    if (evidence && !existing.artifacts!.some(item => item.artifact_id === evidence.artifact_id)) {
      existing.artifacts!.push(evidence);
      existing.artifact ||= evidence;
    }
    return existing;
  };
  const edge = (from: string | undefined, to: string | undefined, relation: Relation) => {
    if (!from || !to || from === to) return;
    const id = JSON.stringify([from, relation, to]);
    if (!edges.some(item => item.id === id)) edges.push({ id, from, to, relation });
  };

  artifacts.forEach((artifact, index) => {
    let stepId: string | undefined;
    // Reference snapshots describe source evidence, not independent analysis executions.
    // Historical captures allocate an ID per slice, so treating them as steps duplicates retrievals.
    if (artifact.type !== 'reference' && !isDerivativeCapture(artifact)) {
      const context = artifact.execution || {};
      const stepIdentity = context.step_id
        ? JSON.stringify([context.conv_uid, context.task_id || '', context.run_id || '', context.step_id])
        : artifact.artifact_id;
      stepId = `step:${stepIdentity}`;
      const step = add(
        { id: stepId, stage: 'execution', type: 'step', title: artifactTitle(artifact), order: index },
        artifact,
      );
      execution.set(artifact.artifact_id, stepId);
      if (step.artifacts!.length === 1 && (isKnowledgeReference(artifact) || !artifact.name)) {
        step.title = actionTitle(context.action || '') || context.action || artifactTitle(artifact);
      }
      step.subtitle = `${unique(step.artifacts!.map(item => item.execution?.action || '')).join(' · ')} · ${executionStatus(step.artifacts!)}`;
      step.tables = unique(
        step.artifacts!.flatMap(item => {
          const tables = record(item.metadata?.lineage).tables || item.metadata?.tables;
          return Array.isArray(tables) ? tables.map(String) : [];
        }),
      );
    }

    if (isKnowledgeReference(artifact)) {
      const spaceName = knowledgeSpaceName(artifact, names);
      const space = spaceIdsByName.get(spaceName) || knowledgeSpaceId(artifact) || spaceName;
      const rootId = `knowledge:${space}`;
      add(
        {
          id: rootId,
          stage: 'source',
          type: 'knowledge',
          sourceGroup: 'KNOWLEDGE BASE',
          title: knowledgeSpaceName(artifact, names),
          subtitle: reportText('evidence_graph_knowledge_subtitle'),
        },
        artifact,
      );
      const locator = artifact.locator || {};
      // Keep distinct documents separate even when they share a filename.
      const documentKey =
        string(locator.document_id || locator.doc_id) || pathKey(locator.path) || referenceFileName(artifact);
      const fileId = `knowledge-file:${JSON.stringify([space, documentKey])}`;
      const node = add(
        {
          id: fileId,
          stage: 'source',
          type: 'file',
          sourceGroup: 'KNOWLEDGE BASE',
          parentId: rootId,
          title: referenceFileName(artifact),
        },
        artifact,
      );
      node.subtitle = reportText('evidence_graph_cited_references', { count: node.artifacts!.length });
      edge(rootId, fileId, 'INCLUDED_IN');
      sourceReferences.set(artifact.artifact_id, fileId);
      edge(fileId, stepId, 'READS');
    } else if (artifact.database || artifact.type === 'sql') {
      const name = artifactSourceName(artifact);
      const id = `database:${name === '-' ? 'unknown' : name}`;
      add(
        {
          id,
          stage: 'source',
          type: 'database',
          sourceGroup: 'DATABASE',
          title: name === '-' ? reportText('evidence_graph_database_name_missing') : name,
          subtitle: reportText('evidence_graph_database_subtitle'),
        },
        artifact,
      );
      if (artifact.type === 'reference') sourceReferences.set(artifact.artifact_id, id);
      edge(id, stepId, 'READS');
    } else if (['file', 'memory', 'web'].includes(artifact.reference_type || '')) {
      // A generated file is an output/dependency, not an uploaded data source.
      if (artifact.reference_type === 'file' && artifact.input_artifact_ids?.length) return;
      const kind = artifact.reference_type;
      const identity = pathKey(artifact.locator?.path || artifact.uri) || artifact.source_id || artifact.artifact_id;
      const id = `source:${kind}:${identity}`;
      add(
        {
          id,
          stage: 'source',
          type: kind === 'memory' ? 'memory' : 'file',
          sourceGroup: kind === 'memory' ? 'MEMORY' : kind === 'web' ? 'WEB' : 'FILE',
          title: artifactSourceName(artifact),
          subtitle:
            kind === 'file'
              ? reportText('evidence_graph_uploaded_snapshot')
              : kind === 'web'
                ? reportText('evidence_graph_web_source')
                : reportText('evidence_graph_memory_subtitle'),
        },
        artifact,
      );
      sourceReferences.set(artifact.artifact_id, id);
      edge(id, stepId, 'READS');
    }
  });
  const producers = (id: string, seen = new Set<string>()): string[] => {
    if (seen.has(id)) return [];
    seen.add(id);
    const step = execution.get(id);
    if (step) return [step];
    return unique((byArtifact.get(id)?.input_artifact_ids || []).flatMap(input => producers(input, seen)));
  };
  artifacts.filter(isDerivativeCapture).forEach(artifact => {
    producers(artifact.artifact_id).forEach(id => {
      const step = nodeMap.get(id);
      if (step) add(step, artifact);
    });
  });
  nodes
    .filter(node => node.stage === 'execution')
    .forEach((node, index) => {
      node.title = `${index + 1}. ${node.title}`;
    });
  artifacts.forEach(artifact =>
    artifact.input_artifact_ids?.forEach(input => {
      const step = execution.get(artifact.artifact_id);
      if (step) {
        const source = sourceReferences.get(input);
        if (source) edge(source, step, 'READS');
        else producers(input).forEach(producer => edge(producer, step, 'DERIVES_FROM'));
      }
    }),
  );

  const reportEvidence = new Set<string>();
  document?.sections.forEach(section =>
    section.blocks.forEach(block => {
      block.evidence?.forEach(reference => reportEvidence.add(reference.artifact_id));
      [block.data_artifact_id, block.chart_artifact_id].filter(Boolean).forEach(id => reportEvidence.add(id!));
    }),
  );
  // Standalone callers can show a recorded report; task views pass their exact file list.
  const generated =
    files ?? (document?.sections.length ? [{ id: document.report_id, type: 'html', name: document.title }] : []);
  const seenFiles = new Set<string>();
  generated.forEach(file => {
    if (['table', 'chart', 'summary'].includes(file.type)) return;
    const path = filePath(file);
    if (!path && !/\.[a-z0-9]{1,8}$/i.test(file.name) && !['html', 'image', 'file'].includes(file.type)) return;
    const identity = path || file.id;
    if (seenFiles.has(identity)) return;
    seenFiles.add(identity);
    const isReport = file.type === 'html' || /\.html?$/i.test(file.name);
    const content = record(file.content);
    const explicitIds = [content.artifact_id, ...(Array.isArray(content.artifact_ids) ? content.artifact_ids : [])].map(
      string,
    );
    const matches = artifacts.filter(
      artifact =>
        explicitIds.includes(artifact.artifact_id) ||
        (path && artifactPaths(artifact).includes(path)) ||
        (file.stepId && (artifact.execution?.step_id === file.stepId || artifact.execution?.task_id === file.stepId)),
    );
    const output = add({
      id: `output:${identity}`,
      stage: 'output',
      type: isReport ? 'report' : 'file',
      title: file.name,
      subtitle: isReport ? reportText('evidence_graph_report_file') : reportText('evidence_graph_generated_file'),
      file,
    });
    matches.forEach(artifact => {
      add(output, artifact);
      producers(artifact.artifact_id).forEach(producer => edge(producer, output.id, 'PRODUCES'));
    });
    if (isReport)
      reportEvidence.forEach(id => {
        const source = sourceReferences.get(id);
        if (source) edge(source, output.id, 'REFERENCES');
        else producers(id).forEach(producer => edge(producer, output.id, 'PRODUCES'));
      });
  });
  return { nodes, edges };
}

export type TraversalDirection = 'upstream' | 'downstream' | 'both';
export function relatedNodes(start: string, edges: GraphEdge[], direction: TraversalDirection = 'both'): Set<string> {
  if (direction === 'both')
    return new Set([...relatedNodes(start, edges, 'upstream'), ...relatedNodes(start, edges, 'downstream')]);
  const found = new Set([start]);
  const queue = [start];
  while (queue.length) {
    const current = queue.shift()!;
    edges.forEach(edge => {
      const next =
        direction === 'upstream' && edge.to === current
          ? edge.from
          : direction === 'downstream' && edge.from === current
            ? edge.to
            : undefined;
      if (next && !found.has(next)) {
        found.add(next);
        queue.push(next);
      }
    });
  }
  return found;
}
export function withContainers(related: Set<string>, nodes: GraphNode[]) {
  const found = new Set(related);
  const byId = new Map(nodes.map(node => [node.id, node]));
  related.forEach(id => {
    let parent = byId.get(id)?.parentId;
    while (parent && !found.has(parent)) {
      found.add(parent);
      parent = byId.get(parent)?.parentId;
    }
  });
  return found;
}
export function projectedEdges(edges: GraphEdge[], nodes: GraphNode[], visible: Set<string>) {
  const byId = new Map(nodes.map(node => [node.id, node]));
  const project = (id: string): string | undefined =>
    visible.has(id) ? id : byId.get(id)?.parentId ? project(byId.get(id)!.parentId!) : undefined;
  const bundled = new Map<string, GraphEdge>();
  edges.forEach(edge => {
    const from = project(edge.from);
    const to = project(edge.to);
    if (!from || !to || from === to || byId.get(from)?.stage === byId.get(to)?.stage) return;
    const id = JSON.stringify([from, edge.relation, to]);
    const existing = bundled.get(id);
    if (existing) existing.count = (existing.count || 1) + 1;
    else bundled.set(id, { ...edge, id, from, to, count: 1 });
  });
  return [...bundled.values()];
}
