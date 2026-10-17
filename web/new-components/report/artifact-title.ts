import type { ReportArtifact } from '@/types/report';

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
  if (artifact.type === 'python') return '数据计算';
  if (artifact.type === 'sql') return '数据查询';
  if (artifact.type === 'chart') return '分析图表';
  return artifact.reference_type === 'knowledge' ? '知识库资料' : '引用资料';
}
