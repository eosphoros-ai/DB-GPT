import { POST } from '@/client/api';
import type { ReportArtifact } from '@/types/report';
import { useEffect, useState } from 'react';
import { isKnowledgeReference, knowledgeSpaceId, type KnowledgeSpaceNames } from './report-source';

/** Resolve numeric identities in historical snapshots without rewriting their evidence. */
export function useKnowledgeSpaceNames(artifacts: readonly ReportArtifact[]) {
  const [names, setNames] = useState<KnowledgeSpaceNames>({});
  const ids = [
    ...new Set(
      artifacts
        .filter(isKnowledgeReference)
        .map(knowledgeSpaceId)
        .filter(id => /^\d+$/.test(id)),
    ),
  ]
    .sort()
    .join(',');
  useEffect(() => {
    let alive = true;
    setNames({});
    if (!ids) return;
    void POST<{}, { id: string | number; name: string }[]>('/api/v1/knowledge/space/list', {})
      .then(response => {
        if (alive && response.data.success && Array.isArray(response.data.data)) {
          setNames(Object.fromEntries(response.data.data.map(space => [String(space.id), space.name])));
        }
      })
      .catch(() => {
        /* Keep the recorded identity visible when the space is unavailable. */
      });
    return () => {
      alive = false;
    };
  }, [ids]);
  return names;
}
