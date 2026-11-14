import type { ITaskflowAgentStep } from '@/types/taskflow';
import { useMemo } from 'react';
import AgentTimeline, { stepsToTimelineBlocks, type TimelineSourceStep } from './AgentTimeline';

/** Adapt workflow rounds to the same tool timeline used by homepage Agents. */
export function taskflowTraceBlocks(steps: ITaskflowAgentStep[], running: boolean, nodeId: string) {
  const source: TimelineSourceStep[] = [];
  const outputs: Record<string, { output_type: string; content: unknown }[]> = {};
  const thoughts: Record<string, string> = {};
  steps.forEach((step, index) => {
    const id = `${nodeId}:round:${step.round ?? 0}:${index}`;
    if (step.kind === 'thinking' && step.detail?.trim()) {
      source.push({ id, title: '思考中', status: 'done' });
      thoughts[id] = step.detail;
    }
    if (step.kind !== 'action') return;
    // Stop at the next action: a later round's observation cannot complete
    // this call. Old traces only have title/detail; keep that fallback.
    let observation: ITaskflowAgentStep | undefined;
    for (const next of steps.slice(index + 1)) {
      if (next.kind === 'action' || next.kind === 'thinking') break;
      if (next.kind === 'observation') {
        observation = next;
        break;
      }
    }
    const result = observation?.output ?? observation?.detail;
    let succeeded = observation?.success ?? step.success;
    if (succeeded == null && typeof result === 'string') {
      try {
        const parsed = JSON.parse(result);
        if (typeof parsed?.is_exe_success === 'boolean') succeeded = parsed.is_exe_success;
        else if (typeof parsed?.success === 'boolean') succeeded = parsed.success;
      } catch {
        // Legacy plain-text failures still have a meaningful display.
        if (/execute failed|was called with no arguments|missing \d+ required|error:|执行失败/i.test(result))
          succeeded = false;
      }
    }
    source.push({
      id,
      title: step.title,
      action: step.title,
      actionInput: step.action_input ?? step.detail,
      status:
        succeeded === false ? 'failed' : observation || succeeded === true ? 'done' : running ? 'running' : 'failed',
    });
    outputs[id] =
      result != null
        ? [{ output_type: 'text', content: typeof result === 'string' ? result : JSON.stringify(result) }]
        : running
          ? []
          : [{ output_type: 'text', content: '未收到工具执行结果' }];
  });
  return stepsToTimelineBlocks(source, thoughts, outputs);
}

export default function TaskflowAgentTrace({
  steps,
  running,
  nodeId,
}: {
  steps: ITaskflowAgentStep[];
  running: boolean;
  nodeId: string;
}) {
  const blocks = useMemo(() => taskflowTraceBlocks(steps, running, nodeId), [steps, running, nodeId]);
  return (
    <div data-testid='taskflow-agent-trace' className='min-w-0'>
      <AgentTimeline blocks={blocks} isRunning={running} />
    </div>
  );
}
