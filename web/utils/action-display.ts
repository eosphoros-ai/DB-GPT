export interface ActionDisplayFields {
  actionIntention?: unknown;
  actionReason?: unknown;
  thought?: unknown;
}

/** Older ReAct streams included answer drafts among the execution steps. */
export function chatDisplaySteps<
  T extends { action?: string; title?: string; detail?: string; toolConfirmed?: boolean },
>(steps: T[], executionStatus?: string): T[] {
  const keepUnfinishedProgress = !!executionStatus && !['completed', 'done'].includes(executionStatus);
  const visible: T[] = [];
  let toolFollows = false;
  for (let index = steps.length - 1; index >= 0; index--) {
    const step = steps[index];
    if (step.action === '__progress__') {
      if (step.toolConfirmed || toolFollows || keepUnfinishedProgress) visible.push(step);
      toolFollows = false;
      continue;
    }
    // Older servers opened this provisional step for ordinary text as well
    // as reasoning. A real tool subsequently updates the same step with its action.
    if (
      !step.action &&
      step.detail === 'Thought/Action/Observation' &&
      (step.title === 'Thinking' || step.title === '思考中')
    ) {
      continue;
    }
    visible.push(step);
    if (step.action) toolFollows = true;
  }
  return visible.reverse();
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
