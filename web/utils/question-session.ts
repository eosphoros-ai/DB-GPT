/** Question identity and wire compatibility shared by every chat entry point. */
export interface QuestionOption {
  label: string;
  description: string;
}

export interface QuestionInfo {
  question: string;
  header: string;
  options: QuestionOption[];
  multiple?: boolean;
  custom?: boolean;
}

export interface PendingQuestion {
  request_id: string;
  conv_id: string;
  questions: unknown[];
  sequence?: number;
}

const record = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

/** Null slots are deliberate: removing one would shift every following answer. */
export function questionSlots(raw: unknown): Array<QuestionInfo | null> {
  if (!Array.isArray(raw)) return [];
  return raw.map(item => {
    const value = typeof item === 'string' ? { question: item } : item;
    if (!record(value) || typeof value.question !== 'string' || !value.question.trim()) return null;
    const options = Array.isArray(value.options)
      ? value.options.flatMap(option =>
          record(option) && typeof option.label === 'string' && option.label.trim()
            ? [{ label: option.label, description: typeof option.description === 'string' ? option.description : '' }]
            : [],
        )
      : [];
    return {
      question: value.question,
      header: typeof value.header === 'string' ? value.header : '',
      options,
      multiple: value.multiple === true,
      custom: value.custom !== false,
    };
  });
}

export function isQuestionEvent(event: unknown): event is Record<string, unknown> {
  return record(event) && ['question.asked', 'question.replied', 'question.rejected'].includes(String(event.type));
}

/** Retain closed/seen IDs so late replies AND replayed asks cannot resurrect A. */
export class QuestionSession {
  current: PendingQuestion | null = null;
  private seen = new Set<string>();
  private closed = new Set<string>();
  private latestSequence = new Map<string, number>();

  apply(event: unknown, conversationId?: string): PendingQuestion | null {
    if (!isQuestionEvent(event) || typeof event.request_id !== 'string' || !event.request_id) return this.current;
    if (conversationId && event.conv_id && event.conv_id !== conversationId) return this.current;
    if (event.type !== 'question.asked') {
      if (this.current?.request_id === event.request_id && event.conv_id && event.conv_id !== this.current.conv_id) {
        return this.current;
      }
      return this.resolve(event.request_id);
    }
    if (typeof event.conv_id !== 'string' || !event.conv_id) return this.current;
    if (this.closed.has(event.request_id) || this.seen.has(event.request_id)) return this.current;
    this.seen.add(event.request_id);
    const sequence =
      typeof event.sequence === 'number' && Number.isSafeInteger(event.sequence) ? event.sequence : undefined;
    if (sequence !== undefined) {
      if (sequence <= (this.latestSequence.get(event.conv_id) ?? -1)) return this.current;
      this.latestSequence.set(event.conv_id, sequence);
    }
    this.current = {
      request_id: event.request_id,
      conv_id: event.conv_id,
      questions: Array.isArray(event.questions) ? event.questions : [],
      sequence,
    };
    return this.current;
  }

  resolve(requestId: string): PendingQuestion | null {
    this.closed.add(requestId);
    if (this.current?.request_id === requestId) this.current = null;
    return this.current;
  }
}

export async function checkQuestionResponse(response: Response, requestId: string): Promise<void> {
  const body = await response.json().catch(() => null);
  if (!response.ok || body?.success !== true || body?.data?.success !== true || body?.data?.request_id !== requestId) {
    throw new Error('问题未提交成功，请重试或取消。');
  }
}
