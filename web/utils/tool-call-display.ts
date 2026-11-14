/** Preserve the identity of each tool in DB-GPT's native multi-call rounds. */
export interface ToolDisplayOutput {
  output_type?: string;
  content?: unknown;
}

interface ToolDisplayStep {
  id: string;
  action?: string;
  title?: string;
  actionInput?: unknown;
  status?: string;
  startedAt?: number;
  endedAt?: number;
}

interface BatchToolResult {
  name: string;
  success: boolean;
  content?: unknown;
  observation?: unknown;
}

function parseJson(value: unknown): unknown {
  if (typeof value !== 'string') return value;
  try {
    return JSON.parse(value);
  } catch {
    return undefined;
  }
}

function resultOutputs(value: unknown): ToolDisplayOutput[] {
  const decoded = parseJson(value);
  if (decoded && typeof decoded === 'object' && !Array.isArray(decoded)) {
    const chunks = (decoded as { chunks?: unknown }).chunks;
    if (Array.isArray(chunks)) {
      return chunks.filter((chunk): chunk is ToolDisplayOutput => Boolean(chunk && typeof chunk === 'object'));
    }
  }
  return [
    {
      output_type: 'text',
      content:
        decoded !== undefined
          ? typeof decoded === 'string'
            ? decoded
            : JSON.stringify(decoded, null, 2)
          : typeof value === 'string'
            ? value
            : JSON.stringify(value, null, 2),
    },
  ];
}

export function expandToolCallSteps<T extends ToolDisplayStep>(
  steps: T[],
  outputsByStep: Record<string, ToolDisplayOutput[]>,
): { steps: T[]; outputs: Record<string, ToolDisplayOutput[]> } {
  const outputs = { ...outputsByStep };
  const expanded = steps.flatMap(step => {
    const names = (step.action || '').split(',').map(name => name.trim());
    if (names.length < 2 || names.some(name => !name)) return [step];
    const input = parseJson(step.actionInput);
    const inputs = Array.isArray(input) && input.length === names.length ? input : undefined;
    const rawOutputs = outputsByStep[step.id] || [];
    const fragments = rawOutputs.filter(o => o.output_type === 'text').map(o => String(o.content ?? ''));
    // SSE text chunks are slices, not lines. Joining with newlines can corrupt
    // JSON strings; history normally stores the same array in one text output.
    const parsed = parseJson(fragments.join('')) ?? parseJson(fragments.join('\n'));
    const results =
      Array.isArray(parsed) &&
      parsed.length === names.length &&
      parsed.every((result, index) => result && result.name === names[index] && typeof result.success === 'boolean')
        ? (parsed as BatchToolResult[])
        : undefined;
    // Never guess which tool owns an unstructured or truncated result.
    // During streaming we can already show the confirmed individual inputs.
    if (!results && (!inputs || (rawOutputs.length > 0 && step.status !== 'running' && step.status !== 'pending')))
      return [step];
    return names.map((name, index) => {
      const id = `${step.id}:tool:${index}`;
      const result = results?.[index];
      outputs[id] = result ? resultOutputs(result.observation ?? result.content) : [];
      return {
        ...step,
        id,
        title: name,
        action: name,
        actionInput: inputs?.[index],
        status: result ? (result.success ? 'done' : 'failed') : step.status,
        // The round duration is not an individual tool duration.
        startedAt: undefined,
        endedAt: undefined,
      } as T;
    });
  });
  return { steps: expanded, outputs };
}
