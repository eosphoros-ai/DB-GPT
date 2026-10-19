import type { ReportArtifact } from '../../types/report';
import { reportText } from './report-i18n';

export type KnowledgeSpaceNames = Record<string, string>;
const text = (value: unknown) => (typeof value === 'string' || typeof value === 'number' ? String(value).trim() : '');

export const isKnowledgeReference = (artifact: ReportArtifact) =>
  ['knowledge', 'kb'].includes(text(artifact.reference_type || artifact.metadata?.reference_type));

export function knowledgeSpaceId(artifact: ReportArtifact): string {
  const locator = artifact.locator || {};
  return text(
    locator.space_id || locator.knowledge_id || artifact.metadata?.space_id || artifact.metadata?.knowledge_id,
  );
}

export function knowledgeSpaceName(artifact: ReportArtifact, names: KnowledgeSpaceNames = {}): string {
  const locator = artifact.locator || {};
  const name = text(
    locator.space_name || locator.knowledge_name || artifact.metadata?.space_name || artifact.metadata?.knowledge_name,
  );
  const id = knowledgeSpaceId(artifact);
  return (
    name ||
    names[id] ||
    (id && !/^\d+$/.test(id)
      ? id
      : id
        ? reportText('evidence_source_knowledge_id', { id })
        : reportText('evidence_source_knowledge_missing'))
  );
}

export function referenceFileName(artifact: ReportArtifact): string {
  return (
    text(
      artifact.source_name || artifact.locator?.doc_name || artifact.locator?.document_name || artifact.locator?.path,
    ) || reportText('evidence_source_reference_missing')
  );
}

export function artifactSourceName(artifact: ReportArtifact, names: KnowledgeSpaceNames = {}): string {
  if (isKnowledgeReference(artifact)) return knowledgeSpaceName(artifact, names);
  return text(artifact.database || artifact.source_name || artifact.source_id) || '-';
}
