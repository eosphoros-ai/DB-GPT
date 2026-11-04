/** A persisted agent artifact points to an authenticated report, never to HTML. */
export interface FinancialReportReference {
  kind: 'financial-report';
  runId: string;
  sessionId: string;
  revision: string;
  title: string;
  mode?: 'report' | 'comparison';
  published?: boolean;
}

export function isFinancialReportReference(value: unknown): value is FinancialReportReference {
  if (!value || typeof value !== 'object') return false;
  const ref = value as Record<string, unknown>;
  return (
    ref.kind === 'financial-report' &&
    typeof ref.runId === 'string' &&
    /^[a-f0-9-]{36}$/i.test(ref.runId) &&
    typeof ref.sessionId === 'string' &&
    /^[A-Za-z0-9_-]{1,255}$/.test(ref.sessionId) &&
    typeof ref.revision === 'string' &&
    ref.revision.length > 0 &&
    ref.revision.length <= 255 &&
    typeof ref.title === 'string' &&
    ref.title.length <= 500 &&
    (ref.mode === undefined || ref.mode === 'report' || ref.mode === 'comparison') &&
    (ref.published === undefined || typeof ref.published === 'boolean')
  );
}

export function reportArtifactContent(content: unknown): unknown {
  if (isFinancialReportReference(content)) return content;
  if (typeof content === 'string') return content;
  if (content && typeof content === 'object') {
    if ('content' in content && typeof content.content === 'string') return content.content;
    if ('html' in content && typeof content.html === 'string') return content.html;
  }
  return String(content);
}
