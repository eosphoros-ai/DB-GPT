export interface ActionDisplayFields {
  actionIntention?: unknown;
  actionReason?: unknown;
  thought?: unknown;
}

const reactFields = ['Thought', 'Action Intention', 'Action Reason', 'Action Input', 'Action', 'Observation', 'Phase'];

/** Defence for saved conversations and older backends, including split labels. */
export const publicAssistantText = (text: string, streaming = false): string => {
  if (streaming) {
    const lastLine = text.split('\n').pop() || '';
    const candidate = lastLine
      .replace(/^[ \t]*(?:[-*][ \t]+)?(?:\*\*)?/, '')
      .trim()
      .toLowerCase();
    if (
      ['*', '**'].includes(lastLine.trim()) ||
      (candidate &&
        reactFields.some(
          field => field.toLowerCase().startsWith(candidate) || candidate === `${field.toLowerCase()}**`,
        ))
    ) {
      text = text.slice(0, text.length - lastLine.length);
    }
  }
  const pattern = new RegExp(
    `^[ \\t]*(?:[-*][ \\t]+)?(?:\\*\\*)?(${reactFields.join('|')})(?:\\*\\*)?[ \\t]*[:：][ \\t]*\\*{0,2}[ \\t]*`,
    'gim',
  );
  const fields = [...text.matchAll(pattern)];
  if (!fields.length) return text;
  const parts = [text.slice(0, fields[0].index).trimEnd()];
  fields.forEach((field, index) => {
    if (field[1].toLowerCase() !== 'action intention') return;
    const end = fields[index + 1]?.index ?? text.length;
    const intention = text
      .slice(field.index! + field[0].length, end)
      .split('\n')[0]
      .replace(/\r$/, '');
    if (intention.trim()) parts.push(intention);
  });
  return parts.filter(Boolean).join('\n');
};

const normalizeDisplayField = (value: unknown): string | undefined => {
  if (typeof value !== 'string') return undefined;
  const normalized = publicAssistantText(value).trim();
  return normalized || undefined;
};

export const buildActionDisplayText = ({ actionIntention, actionReason }: ActionDisplayFields): string | undefined => {
  const intention = normalizeDisplayField(actionIntention);
  const reason = normalizeDisplayField(actionReason);
  // Only explicitly public action fields belong in the status line.
  const primary = intention;
  const parts: string[] = primary ? [primary] : [];
  if (reason && reason !== primary) {
    parts.push(reason);
  }
  return parts.length > 0 ? parts.join('\n') : undefined;
};
