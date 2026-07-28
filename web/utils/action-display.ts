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

export const buildActionDisplayText = ({ actionIntention, actionReason }: ActionDisplayFields): string | undefined => {
  const intention = normalizeDisplayField(actionIntention);
  const reason = normalizeDisplayField(actionReason);

  if (intention) {
    return reason ? `${intention}\n${reason}` : intention;
  }

  // Raw Thought is internal model reasoning and must never be used as
  // user-facing timeline copy. Action Reason is already constrained by the
  // ReAct prompt to be concise and is the safe fallback when intention is absent.
  return reason;
};
