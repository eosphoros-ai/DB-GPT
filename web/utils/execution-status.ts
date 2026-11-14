type Step = { action?: string; status: string };
type Task = { status: string };

export type ExecutionStatus = 'running' | 'done' | 'partial' | 'failed' | 'incomplete';

/** Ending the stream does not imply that its tools or planned stages succeeded. */
export function executionStatus(
  steps: Step[],
  thinking = false,
  tasks: Task[] = [],
  recordedStatus?: string,
): ExecutionStatus {
  if (thinking || (!recordedStatus && steps.some(step => step.status === 'running'))) return 'running';
  if (recordedStatus === 'failed' || recordedStatus === 'report_failed') return 'failed';
  if (recordedStatus && !['done', 'completed'].includes(recordedStatus)) return 'incomplete';
  const failed = steps.some(step => step.status === 'failed') || tasks.some(task => task.status === 'error');
  if (failed) {
    const completed =
      steps.some(step => step.action !== '__progress__' && step.status === 'done') ||
      tasks.some(task => task.status === 'completed');
    return completed ? 'partial' : 'failed';
  }
  if (tasks.some(task => task.status !== 'completed') || steps.some(step => step.status !== 'done'))
    return 'incomplete';
  return 'done';
}
