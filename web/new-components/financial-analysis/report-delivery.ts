import { isFinancialReportReference, type FinancialReportReference } from './agent-artifact';

interface ArtifactIdentity {
  type: string;
  name: string;
  content: unknown;
  messageId?: string;
}

export function artifactIdentity(artifact: ArtifactIdentity): string {
  const reference = artifact.content;
  return isFinancialReportReference(reference)
    ? `${artifact.messageId || ''}:financial:${reference.sessionId}:${reference.runId}`
    : `${artifact.messageId || ''}:${artifact.type}:${artifact.name}`;
}

/** Live delivery and history use the same report identity, regardless of title or tool call. */
export function mergeArtifacts<T extends ArtifactIdentity>(artifacts: T[]): T[] {
  const merged = new Map<string, T>();
  for (const artifact of artifacts) {
    const key = artifactIdentity(artifact);
    merged.delete(key);
    merged.set(key, artifact);
  }
  return [...merged.values()];
}

export function financialArtifact(reference: FinancialReportReference, messageId: string, stepId?: string) {
  return {
    id: `${messageId}-financial-${reference.sessionId}-${reference.runId}`,
    type: 'html' as const,
    name: `${reference.title}.html`,
    content: reference,
    createdAt: Date.now(),
    messageId,
    stepId,
    downloadable: true,
  };
}

/** Receipt is independent of final-answer delivery, and navigation happens at most once per turn. */
export class FinancialReportDelivery {
  private received = new Map<string, FinancialReportReference>();
  private published = new Set<string>();

  receive(content: unknown, sessionId: string, responseId: string, canNavigate: boolean, stepId?: string) {
    if (!isFinancialReportReference(content) || content.sessionId !== sessionId) return null;
    this.received.set(responseId, content);
    const open = content.published === true && !this.published.has(responseId) && canNavigate;
    if (content.published === true) this.published.add(responseId);
    return { artifact: financialArtifact(content, responseId, stepId), open };
  }

  hasReport(responseId: string) {
    return this.received.has(responseId);
  }

  hasPublished(responseId: string) {
    return this.received.get(responseId)?.published === true;
  }
}
