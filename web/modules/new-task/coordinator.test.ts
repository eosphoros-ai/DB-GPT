import assert from 'node:assert/strict';
import test from 'node:test';

// @ts-expect-error Node's built-in TypeScript runner requires the extension.
import * as newTaskModule from './coordinator.ts';

const { createNewTaskCoordinator } = newTaskModule;

test('begin resets the mounted task even when the page is already canonical home', async () => {
  const calls: string[] = [];
  const coordinator = createNewTaskCoordinator({
    isCanonicalHome: () => true,
    goCanonicalHome: async () => {
      calls.push('navigate');
    },
  });

  coordinator.attach(() => {
    calls.push('reset');
  });

  await coordinator.begin();

  assert.deepEqual(calls, ['reset']);
});

test('begin resets the mounted task before canonicalizing a history URL', async () => {
  const calls: string[] = [];
  const coordinator = createNewTaskCoordinator({
    isCanonicalHome: () => false,
    goCanonicalHome: async () => {
      calls.push('navigate');
    },
  });

  coordinator.attach(() => {
    calls.push('reset');
  });

  await coordinator.begin();

  assert.deepEqual(calls, ['reset', 'navigate']);
});

test('begin navigates to canonical home when no task target is mounted', async () => {
  const calls: string[] = [];
  const coordinator = createNewTaskCoordinator({
    isCanonicalHome: () => false,
    goCanonicalHome: async () => {
      calls.push('navigate');
    },
  });

  await coordinator.begin();

  assert.deepEqual(calls, ['navigate']);
});

test('a command issued before the task owner mounts is consumed on attach', async () => {
  const calls: string[] = [];
  const coordinator = createNewTaskCoordinator({
    isCanonicalHome: () => true,
    goCanonicalHome: async () => {
      calls.push('navigate');
    },
  });

  await coordinator.begin();
  coordinator.attach(() => {
    calls.push('reset');
  });

  assert.deepEqual(calls, ['reset']);
});

test('concurrent begin calls share one reset and one navigation', async () => {
  let finishNavigation!: () => void;
  const navigation = new Promise<void>(resolve => {
    finishNavigation = resolve;
  });
  const calls: string[] = [];
  const coordinator = createNewTaskCoordinator({
    isCanonicalHome: () => false,
    goCanonicalHome: async () => {
      calls.push('navigate');
      await navigation;
    },
  });
  coordinator.attach(() => {
    calls.push('reset');
  });

  const first = coordinator.begin();
  const second = coordinator.begin();
  assert.deepEqual(calls, ['reset', 'navigate']);

  finishNavigation();
  await Promise.all([first, second]);
  assert.deepEqual(calls, ['reset', 'navigate']);
});

test('a failed navigation releases the command for an idempotent retry', async () => {
  const calls: string[] = [];
  let navigationAttempts = 0;
  const coordinator = createNewTaskCoordinator({
    isCanonicalHome: () => false,
    goCanonicalHome: async () => {
      calls.push('navigate');
      navigationAttempts += 1;
      if (navigationAttempts === 1) throw new Error('navigation failed');
    },
  });
  coordinator.attach(() => {
    calls.push('reset');
  });

  await assert.rejects(coordinator.begin(), /navigation failed/);
  await coordinator.begin();

  assert.deepEqual(calls, ['reset', 'navigate', 'reset', 'navigate']);
});

test('a broken owner is surfaced as a rejected command instead of a synchronous throw', async () => {
  const coordinator = createNewTaskCoordinator({
    isCanonicalHome: () => true,
    goCanonicalHome: async () => undefined,
  });
  coordinator.attach(() => {
    throw new Error('reset failed');
  });

  const command = coordinator.begin();

  await assert.rejects(command, /reset failed/);
});

test('a rejecting guard cancels the command before any reset or navigation', async () => {
  const calls: string[] = [];
  const coordinator = createNewTaskCoordinator({
    isCanonicalHome: () => false,
    goCanonicalHome: async () => {
      calls.push('navigate');
    },
  });
  coordinator.attachGuard(() => false);
  coordinator.attach(() => {
    calls.push('reset');
  });

  await coordinator.begin();

  assert.deepEqual(calls, []);
});

test('an approving guard still runs the reset before the navigation', async () => {
  const calls: string[] = [];
  const coordinator = createNewTaskCoordinator({
    isCanonicalHome: () => false,
    goCanonicalHome: async () => {
      calls.push('navigate');
    },
  });
  coordinator.attachGuard(async () => true);
  coordinator.attach(() => {
    calls.push('reset');
  });

  await coordinator.begin();

  assert.deepEqual(calls, ['reset', 'navigate']);
});

test('a guard-cancelled command is consumed and never fires on a later attach', async () => {
  const calls: string[] = [];
  const coordinator = createNewTaskCoordinator({
    isCanonicalHome: () => true,
    goCanonicalHome: async () => {
      calls.push('navigate');
    },
  });
  coordinator.attachGuard(() => false);

  await coordinator.begin();
  coordinator.attach(() => {
    calls.push('reset');
  });

  assert.deepEqual(calls, []);
});

test('concurrent begin calls share one guard decision', async () => {
  const calls: string[] = [];
  let guardCalls = 0;
  let releaseGuard!: (allowed: boolean) => void;
  const gate = new Promise<boolean>(resolve => {
    releaseGuard = resolve;
  });
  const coordinator = createNewTaskCoordinator({
    isCanonicalHome: () => true,
    goCanonicalHome: async () => {
      calls.push('navigate');
    },
  });
  coordinator.attachGuard(() => {
    guardCalls += 1;
    return gate;
  });
  coordinator.attach(() => {
    calls.push('reset');
  });

  const first = coordinator.begin();
  const second = coordinator.begin();
  releaseGuard(true);
  await Promise.all([first, second]);

  assert.equal(guardCalls, 1);
  assert.deepEqual(calls, ['reset']);
});

test('a detached guard no longer gates the command', async () => {
  const calls: string[] = [];
  const coordinator = createNewTaskCoordinator({
    isCanonicalHome: () => true,
    goCanonicalHome: async () => {
      calls.push('navigate');
    },
  });
  const detachGuard = coordinator.attachGuard(() => false);
  coordinator.attach(() => {
    calls.push('reset');
  });

  detachGuard();
  await coordinator.begin();

  assert.deepEqual(calls, ['reset']);
});
