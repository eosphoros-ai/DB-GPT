/**
 * In-process upload command queue.
 *
 * - Bounded concurrency (default MAX_UPLOAD_CONCURRENCY).
 * - Stable FIFO start order; task results always resolve (never reject),
 *   so one failure can never take down its siblings.
 * - Aborted tasks report 'cancelled' and are never treated as retryable
 *   network errors; retry requeues failed tasks only.
 */

export const MAX_UPLOAD_CONCURRENCY = 3;

export type QueueSettledStatus = 'done' | 'failed' | 'cancelled';

export interface QueueTaskResult<T> {
  clientId: string;
  status: QueueSettledStatus;
  value?: T;
  error?: unknown;
}

export interface UploadQueueOptions {
  concurrency?: number;
}

type TaskStatus = 'pending' | 'running' | QueueSettledStatus;

interface QueueTask<T> {
  clientId: string;
  run: (signal: AbortSignal) => Promise<T>;
  controller: AbortController;
  status: TaskStatus;
  aborted: boolean;
  result?: QueueTaskResult<T>;
  promise: Promise<QueueTaskResult<T>>;
  resolve: (result: QueueTaskResult<T>) => void;
}

function makeTask<T>(clientId: string, run: (signal: AbortSignal) => Promise<T>): QueueTask<T> {
  const task: Partial<QueueTask<T>> = {
    clientId,
    run,
    controller: new AbortController(),
    status: 'pending',
    aborted: false,
    result: undefined,
  };
  task.promise = new Promise<QueueTaskResult<T>>(resolve => {
    task.resolve = resolve;
  });
  return task as QueueTask<T>;
}

export class UploadQueue<T = unknown> {
  private readonly concurrency: number;
  private readonly pending: QueueTask<T>[] = [];
  private readonly running = new Set<QueueTask<T>>();
  private readonly tasks = new Map<string, QueueTask<T>>();

  constructor(options: UploadQueueOptions = {}) {
    const concurrency = options.concurrency ?? MAX_UPLOAD_CONCURRENCY;
    this.concurrency = Math.max(1, Math.floor(concurrency));
  }

  get activeCount(): number {
    return this.running.size;
  }

  get pendingCount(): number {
    return this.pending.length;
  }

  result(clientId: string): QueueTaskResult<T> | undefined {
    return this.tasks.get(clientId)?.result;
  }

  /** Enqueue a task; the returned promise always resolves (never rejects). */
  enqueue(clientId: string, run: (signal: AbortSignal) => Promise<T>): Promise<QueueTaskResult<T>> {
    const task = makeTask(clientId, run);
    this.tasks.set(clientId, task);
    this.pending.push(task);
    this.pump();
    return task.promise;
  }

  private pump(): void {
    while (this.running.size < this.concurrency && this.pending.length > 0) {
      const task = this.pending.shift()!;
      this.running.add(task);
      task.status = 'running';
      void this.execute(task);
    }
  }

  private async execute(task: QueueTask<T>): Promise<void> {
    try {
      const value = await task.run(task.controller.signal);
      this.finish(task, { clientId: task.clientId, status: task.aborted ? 'cancelled' : 'done', value });
    } catch (error) {
      // An abort is never reported as a retryable failure, whatever the
      // underlying run() rejected with.
      this.finish(
        task,
        task.aborted
          ? { clientId: task.clientId, status: 'cancelled' }
          : { clientId: task.clientId, status: 'failed', error },
      );
    }
  }

  private finish(task: QueueTask<T>, result: QueueTaskResult<T>): void {
    task.status = result.status;
    task.result = result;
    this.running.delete(task);
    task.resolve(result);
    this.pump();
  }

  /**
   * Cancel a pending or running task. Pending tasks never run; running
   * tasks get an aborted signal and settle as 'cancelled' (never 'failed').
   * Returns false when the clientId is unknown.
   */
  cancel(clientId: string): boolean {
    const pendingIndex = this.pending.findIndex(task => task.clientId === clientId);
    if (pendingIndex >= 0) {
      const [task] = this.pending.splice(pendingIndex, 1);
      task.aborted = true;
      task.controller.abort();
      this.finish(task, { clientId, status: 'cancelled' });
      return true;
    }
    for (const task of this.running) {
      if (task.clientId !== clientId) continue;
      task.aborted = true;
      task.controller.abort();
      return true;
    }
    return false;
  }

  /** Cancel everything pending or running (e.g. on turn cleanup). */
  cancelAll(): void {
    for (const task of [...this.pending, ...this.running]) {
      this.cancel(task.clientId);
    }
  }

  /**
   * Requeue one failed task with a fresh controller and promise.
   * Returns null when the task is unknown or not in 'failed' state —
   * cancelled tasks are explicitly not retryable.
   */
  retry(clientId: string): Promise<QueueTaskResult<T>> | null {
    const task = this.tasks.get(clientId);
    if (!task || task.result?.status !== 'failed') return null;
    task.controller = new AbortController();
    task.aborted = false;
    task.status = 'pending';
    task.result = undefined;
    task.promise = new Promise<QueueTaskResult<T>>(resolve => {
      task.resolve = resolve;
    });
    this.pending.push(task);
    this.pump();
    return task.promise;
  }

  /** Requeue all failed tasks, preserving FIFO order. Returns their clientIds. */
  retryFailed(): string[] {
    const retried: string[] = [];
    for (const task of this.tasks.values()) {
      if (task.result?.status !== 'failed') continue;
      if (this.retry(task.clientId)) retried.push(task.clientId);
    }
    return retried;
  }

  /** Resolve once every queued task has settled (failures included). */
  async drain(): Promise<void> {
    while (this.pending.length > 0 || this.running.size > 0) {
      await Promise.allSettled([...this.pending, ...this.running].map(task => task.promise));
    }
  }
}
