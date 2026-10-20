import { isFinancialReportReference } from './agent-artifact';
import type { EvidenceSelection, ReportData } from './types';

export interface FinancialCitation {
  runId: string;
  kind: 'fact' | 'calculation';
  refId: string;
}

export interface FinancialCitationTarget extends FinancialCitation {
  requestId: number;
}

/** Repair escaped Chinese in saved answers while retaining HTML escaping. */
export function cleanFinancialAnswerText(content: string): string {
  return content.replace(/&(?:amp;)?#(?:x([0-9a-f]+)|([0-9]+));/gi, (entity, hex, decimal) => {
    const point = Number.parseInt(hex || decimal, hex ? 16 : 10);
    return point >= 0x3400 && point <= 0x9fff ? String.fromCodePoint(point) : entity;
  });
}

export function parseFinancialCitation(href: unknown): FinancialCitation | null {
  if (typeof href !== 'string') return null;
  const match = /^#financial-report\/([a-f0-9-]{36})\/(fact|calculation)\/([A-Za-z0-9_-]{1,255})$/i.exec(href);
  if (!match || !['fact', 'calculation'].includes(match[2])) return null;
  return { runId: match[1], kind: match[2] as FinancialCitation['kind'], refId: match[3] };
}

/** Only an already-visible authenticated report may be opened from a citation. */
export function findFinancialCitationArtifact<T extends { content: unknown }>(
  artifacts: readonly T[],
  citation: FinancialCitation,
): T | undefined {
  return artifacts.find(
    artifact => isFinancialReportReference(artifact.content) && artifact.content.runId === citation.runId,
  );
}

export function resolveFinancialCitation(
  data: Pick<ReportData, 'report' | 'facts' | 'calculations'>,
  citation: FinancialCitation,
): EvidenceSelection | null {
  if (data.report.run.id !== citation.runId) return null;
  if (citation.kind === 'fact' && data.facts.some(item => item.id === citation.refId && item.normalizedValue != null)) {
    return { factId: citation.refId };
  }
  if (
    citation.kind === 'calculation' &&
    data.calculations.some(item => item.id === citation.refId && item.result != null)
  ) {
    return { calculationId: citation.refId };
  }
  return null;
}
