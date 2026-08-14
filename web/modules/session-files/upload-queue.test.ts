import assert from 'node:assert/strict';
import test from 'node:test';

// @ts-expect-error Node's built-in TypeScript runner requires the extension.
import { MAX_UPLOAD_CONCURRENCY, UploadQueue } from './upload-queue.ts';

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (error: unknown) => void;
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const tick = () => new Promise(resolve => setImmediate(resolve));

test('exposes a max upload concurrency of 3', () => {
  assert.equal(MAX_UPLOAD_CONCURRENCY, 3);
});

test('peak concurrent executions never exceed the concurrency limit', async () => {
  const queue = new UploadQueue<number>({ concurrency: MAX_UPLOAD_CONCURRENCY });
  let active = 0;
  let peak = 0;
  const gates: Deferred<number>[] = [];
  const results: Promise<unknown>[] = [];

  for (let i = 0; i < 6; i += 1) {
    results.push(
      queue.enqueue(`id-${i}`, async () => {
        active += 1;
        peak = Math.max(peak, active);
        const gate = deferred<number>();
        gates.push(gate);
        const value = await gate.promise;
        active -= 1;
        return value;
      }),
    );
  }

  // Pump is synchronous: exactly 3 tasks are running before any release.
  assert.equal(peak, 3);
  assert.equal(gates.length, 3);
  assert.equal(queue.activeCount, 3);
  assert.equal(queue.pendingCount, 3);

  // Release the first wave; a macrotask tick lets the queue admit the rest.
  gates.slice().forEach((gate, i) => gate.resolve(i));
  await tick();
  assert.equal(gates.length, 6);

  gates.slice(3).forEach((gate, i) => gate.resolve(i + 3));
  await queue.drain();
  await Promise.all(results);

  assert.equal(peak, 3);
  assert.equal(queue.activeCount, 0);
});

test('starts tasks in stable FIFO order regardless of completion order', async () => {
  const queue = new UploadQueue<string>({ concurrency: 2 });
  const started: string[] = [];
  const gates = new Map<string, Deferred<string>>();

  for (const id of ['a', 'b', 'c', 'd']) {
    queue.enqueue(id, () => {
      started.push(id);
      const gate = deferred<string>();
      gates.set(id, gate);
      return gate.promise;
    });
  }
  assert.deepEqual(started, ['a', 'b']);

  gates.get('b')!.resolve('b');
  await tick();
  gates.get('a')!.resolve('a');
  await tick();
  gates.get('d')!.resolve('d');
  await tick();
  gates.get('c')!.resolve('c');
  await queue.drain();

  assert.deepEqual(started, ['a', 'b', 'c', 'd']);
});

test('a single failure does not affect sibling tasks', async () => {
  const queue = new UploadQueue<number>({ concurrency: 3 });

  const ok1 = queue.enqueue('ok1', async () => 1);
  const bad = queue.enqueue('bad', async () => {
    throw new Error('boom');
  });
  const ok2 = queue.enqueue('ok2', async () => 2);

  const [r1, r2, r3] = await Promise.all([ok1, bad, ok2]);
  assert.deepEqual(r1, { clientId: 'ok1', status: 'done', value: 1 });
  assert.deepEqual(r3, { clientId: 'ok2', status: 'done', value: 2 });
  assert.equal(r2.status, 'failed');
  assert.equal((r2.error as Error).message, 'boom');
});

test('drain resolves only after every queued task settles', async () => {
  const queue = new UploadQueue<number>({ concurrency: 1 });
  const gates: Deferred<number>[] = [];
  for (let i = 0; i < 3; i += 1) {
    queue.enqueue(`t${i}`, () => {
      const gate = deferred<number>();
      gates.push(gate);
      return gate.promise;
    });
  }

  let drained = false;
  const drainPromise = queue.drain().then(() => {
    drained = true;
  });

  await tick();
  assert.equal(drained, false);
  for (let i = 0; i < 3; i += 1) {
    // With concurrency 1 the next gate only exists after the previous
    // task settled; wait for it before releasing.
    while (gates.length <= i) {
      await tick();
    }
    gates[i].resolve(i);
  }
  await drainPromise;
  assert.equal(drained, true);
});

test('cancel drops a pending task without ever running it', async () => {
  const queue = new UploadQueue<number>({ concurrency: 1 });
  const blocker = deferred<number>();
  const started: string[] = [];

  queue.enqueue('first', () => {
    started.push('first');
    return blocker.promise;
  });
  const cancelledPromise = queue.enqueue('second', async () => {
    started.push('second');
    return 2;
  });

  assert.equal(queue.cancel('second'), true);
  blocker.resolve(1);
  const result = await cancelledPromise;
  await queue.drain();

  assert.deepEqual(result, { clientId: 'second', status: 'cancelled' });
  assert.deepEqual(started, ['first']);
});

test('aborting a running task marks it cancelled, never failed or retryable', async () => {
  const queue = new UploadQueue<number>({ concurrency: 1 });
  let observedSignal: AbortSignal | null = null;

  const promise = queue.enqueue('live', signal => {
    observedSignal = signal;
    return new Promise<number>((_, reject) => {
      signal.addEventListener('abort', () => reject(new DOMException('The operation was aborted.', 'AbortError')));
    });
  });

  assert.equal(queue.cancel('live'), true);
  const result = await promise;
  assert.equal(observedSignal!.aborted, true);
  assert.deepEqual(result, { clientId: 'live', status: 'cancelled' });
  assert.deepEqual(queue.result('live'), { clientId: 'live', status: 'cancelled' });

  // Cancelled tasks are explicitly excluded from failure retries.
  assert.deepEqual(queue.retryFailed(), []);
  assert.equal(queue.retry('live'), null);
});

test('retryFailed requeues only failed tasks preserving identity', async () => {
  const queue = new UploadQueue<number>({ concurrency: 3 });
  const attempts = new Map<string, number>();
  const gates = new Map<string, Deferred<number>[]>();

  const track = (id: string) => () => {
    attempts.set(id, (attempts.get(id) ?? 0) + 1);
    const list = gates.get(id) ?? [];
    const gate = deferred<number>();
    list.push(gate);
    gates.set(id, list);
    return gate.promise;
  };

  const okPromise = queue.enqueue('ok', track('ok'));
  const badPromise = queue.enqueue('bad', track('bad'));
  const nullPromise = queue.enqueue('nil', track('nil'));

  gates.get('ok')![0].resolve(1);
  gates.get('bad')![0].reject(new Error('nope'));
  queue.cancel('nil');
  gates.get('nil')![0].reject(new Error('aborted'));

  await Promise.all([okPromise, badPromise, nullPromise]);
  assert.equal(queue.result('bad')?.status, 'failed');
  assert.equal(queue.result('nil')?.status, 'cancelled');

  const retried = queue.retryFailed();
  assert.deepEqual(retried, ['bad']);
  assert.equal(attempts.get('bad'), 2);
  assert.equal(attempts.get('ok'), 1);
  assert.equal(attempts.get('nil'), 1);

  gates.get('bad')![1].resolve(42);
  const retryResult = await new Promise<unknown>(resolve => {
    // The requeued promise resolves once the second attempt settles.
    queue.drain().then(() => resolve(queue.result('bad')));
  });
  assert.deepEqual(retryResult, { clientId: 'bad', status: 'done', value: 42 });
});

test('enqueue after drain keeps working and default concurrency is applied', async () => {
  const queue = new UploadQueue<number>();
  let active = 0;
  let peak = 0;
  const gates: Deferred<number>[] = [];

  for (let i = 0; i < 5; i += 1) {
    queue.enqueue(`d${i}`, async () => {
      active += 1;
      peak = Math.max(peak, active);
      const gate = deferred<number>();
      gates.push(gate);
      await gate.promise;
      active -= 1;
      return i;
    });
  }
  assert.equal(peak, MAX_UPLOAD_CONCURRENCY);

  for (let i = 0; i < 5; i += 1) {
    // Later gates only appear once the queue admits the next tasks.
    while (gates.length <= i) {
      await tick();
    }
    gates[i].resolve(i);
  }
  await queue.drain();

  const again = queue.enqueue('solo', async () => 7);
  assert.deepEqual(await again, { clientId: 'solo', status: 'done', value: 7 });
});
