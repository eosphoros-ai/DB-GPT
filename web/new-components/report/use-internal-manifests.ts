import { getReportSourceJson } from '@/client/api/report/standalone';
import type { ReportRun } from '@/types/report';
import { useEffect, useState } from 'react';

/** Hide legacy session-file manifests only when their contents prove their role. */
export function useInternalManifests(run?: ReportRun | null): Set<string> {
  const [internalManifests, setInternalManifests] = useState<Set<string>>(new Set());
  useEffect(() => {
    setInternalManifests(new Set());
    if (!run?.report_id || !run?.run_id) return;
    let active = true;
    const sources = run.document.artifacts.filter(a => a.type === 'reference' && a.reference_type === 'file');
    const paths = new Set(
      sources
        .map(a =>
          String(a.locator?.path || '')
            .replace(/\\/g, '/')
            .toLowerCase(),
        )
        .filter(Boolean),
    );
    const candidates = sources.filter(a => {
      const content = a.metadata?.content as { size?: number; media_type?: string } | undefined;
      return (
        a.execution?.action === 'execution.input' &&
        content?.media_type === 'application/json' &&
        typeof content.size === 'number' &&
        content.size <= 65536
      );
    });
    void Promise.all(
      candidates.map(async candidate => {
        try {
          const value = await getReportSourceJson(run.report_id, run.run_id, candidate.artifact_id);
          if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
          const entries = Object.entries(value);
          return entries.length > 0 &&
            entries.every(
              ([key, path]) =>
                /^sf_[0-9a-f]{32}$/i.test(key) &&
                typeof path === 'string' &&
                paths.has(path.replace(/\\/g, '/').toLowerCase()),
            )
            ? candidate.artifact_id
            : null;
        } catch {
          return null;
        }
      }),
    ).then(ids => {
      if (active) setInternalManifests(new Set(ids.filter((id): id is string => id !== null)));
    });
    return () => {
      active = false;
    };
  }, [run]);
  return internalManifests;
}
