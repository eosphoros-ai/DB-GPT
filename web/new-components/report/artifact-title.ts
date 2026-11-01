import type { ReportArtifact } from '@/types/report';
import { reportText } from './report-i18n';

/** Internal artifact identifiers are for linking, not drawer headings. */
export function artifactTitle(artifact: ReportArtifact): string {
  const candidates = artifact.type === 'reference' ? [artifact.source_name, artifact.name] : [artifact.name];
  const title = candidates.find(value => {
    const name = value?.trim();
    return (
      name &&
      name !== artifact.artifact_id &&
      !/^(?:python|sql|reference|chart)-[a-f0-9-]{16,}$/i.test(name) &&
      !/^(?:python|sql|reference)$/i.test(name)
    );
  });
  if (title) return title.trim();
  if (artifact.type === 'python') return reportText('evidence_title_python');
  if (artifact.type === 'sql') return reportText('evidence_title_sql');
  if (artifact.type === 'chart') return reportText('evidence_title_chart');
  return artifact.reference_type === 'knowledge'
    ? reportText('evidence_title_knowledge')
    : reportText('evidence_title_reference');
}
