export interface ActionDisplayFields {
  actionIntention?: unknown;
  actionReason?: unknown;
  thought?: unknown;
}

const normalizeDisplayField = (value: unknown): string | undefined => {
  if (typeof value !== 'string') return undefined;
  const normalized = value.trim();
  return normalized || undefined;
};

export const buildActionDisplayText = ({
  actionIntention,
  actionReason,
  thought,
}: ActionDisplayFields): string | undefined => {
  const intention = normalizeDisplayField(actionIntention);
  const reason = normalizeDisplayField(actionReason);
  // derisk-style: `thought` now carries a user-facing narration ("thoughts to
  // the user") which is short and safe to surface. Use it as the primary line,
  // fall back to intention when absent, and append reason only when it adds
  // information beyond the primary.
  const thoughtText = normalizeDisplayField(thought);
  const primary = thoughtText || intention;
  const parts: string[] = primary ? [primary] : [];
  if (reason && reason !== primary) {
    parts.push(reason);
  }
  return parts.length > 0 ? parts.join('\n') : undefined;
};
