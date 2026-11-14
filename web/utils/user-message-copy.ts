import { formatBytes } from '@/modules/session-files/attachment-view-model';
import type { SessionFileSnapshot } from '@/modules/session-files/types';
import type { AttachedConnector } from '@/new-components/connector/types';
import type { SuiteMessageReference } from '@/types/suite';

export interface UserMessageCopyContext {
  userQuery?: string;
  attachedSuite?: SuiteMessageReference;
  attachedKnowledge?: { name: string; desc?: string; vector_type: string };
  attachedSkill?: { name: string };
  attachedDb?: { db_name: string; db_type: string };
  attachedConnectors?: readonly AttachedConnector[];
  attachedFiles?: readonly SessionFileSnapshot[];
}

type ReferenceLabel =
  | 'suite_reference_label'
  | 'evidence_source_knowledge'
  | 'skill_label'
  | 'database_label'
  | 'copy_connector_label'
  | 'file_type_generic';

/** Copy display snapshots, in card order, with full names rather than truncated DOM text. */
export function userMessageCopyText(context: UserMessageCopyContext, label: (key: ReferenceLabel) => string): string {
  const { attachedSuite, attachedKnowledge, attachedSkill, attachedDb } = context;
  const parts: string[] = [];
  const reference = (key: ReferenceLabel, name: string, detail?: string) =>
    `[${label(key)}] ${name}${detail ? ` · ${detail}` : ''}`;

  if (attachedSuite) parts.push(reference('suite_reference_label', attachedSuite.display, attachedSuite.command));
  if (attachedKnowledge) {
    parts.push(
      reference(
        'evidence_source_knowledge',
        attachedKnowledge.name,
        attachedKnowledge.desc || attachedKnowledge.vector_type,
      ),
    );
  }
  if (attachedSkill) parts.push(reference('skill_label', attachedSkill.name));
  if (attachedDb) parts.push(reference('database_label', attachedDb.db_name, attachedDb.db_type));
  for (const connector of context.attachedConnectors ?? []) {
    parts.push(reference('copy_connector_label', connector.display_name, connector.connector_type));
  }
  for (const file of [...(context.attachedFiles ?? [])].sort((a, b) => a.ordinal - b.ordinal)) {
    parts.push(reference('file_type_generic', file.name, `${file.media_type} · ${formatBytes(file.size)}`));
  }
  if (context.userQuery) parts.push(context.userQuery);
  return parts.join('\n\n');
}
