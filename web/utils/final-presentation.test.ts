import assert from 'node:assert/strict';
import test from 'node:test';

import {
  SUMMARY_HOLD_MS,
  SUMMARY_REVEAL_MAX_MS,
  SUMMARY_REVEAL_MIN_MS,
  calculateSummaryRevealDuration,
  createSummaryPresentation,
  type PresentationScheduler,
} from './final-presentation';

class FakeScheduler implements PresentationScheduler {
  private currentTime = 0;
  private nextId = 1;
  private tasks = new Map<number, { callback: () => void; runAt: number }>();
  requestedFrameCount = 0;

  now(): number {
    return this.currentTime;
  }

  setTimeout(callback: () => void, delayMs: number): number {
    const id = this.nextId++;
    this.tasks.set(id, { callback, runAt: this.currentTime + delayMs });
    return id;
  }

  clearTimeout(id: unknown): void {
    this.tasks.delete(id as number);
  }

  requestFrame(callback: () => void): number {
    this.requestedFrameCount += 1;
    return this.schedule(callback, 16);
  }

  cancelFrame(id: unknown): void {
    this.tasks.delete(id as number);
  }

  advanceBy(delayMs: number): void {
    const targetTime = this.currentTime + delayMs;
    while (this.tasks.size > 0) {
      const nextTask = [...this.tasks.entries()]
        .filter(([, task]) => task.runAt <= targetTime)
        .sort((left, right) => left[1].runAt - right[1].runAt || left[0] - right[0])[0];
      if (!nextTask) break;

      const [id, task] = nextTask;
      this.tasks.delete(id);
      this.currentTime = task.runAt;
      task.callback();
    }
    this.currentTime = targetTime;
  }

  private schedule(callback: () => void, delayMs: number): number {
    const id = this.nextId++;
    this.tasks.set(id, { callback, runAt: this.currentTime + delayMs });
    return id;
  }
}

test('bounds summary reveal time independently of content length', () => {
  assert.equal(calculateSummaryRevealDuration('短摘要'), SUMMARY_REVEAL_MIN_MS);
  assert.equal(calculateSummaryRevealDuration('x'.repeat(100_000)), SUMMARY_REVEAL_MAX_MS);
});

test('reveals the summary before completing the automatic preview transition', () => {
  const scheduler = new FakeScheduler();
  const summary = '销售分析完成，网页报告已经生成。'.repeat(30);
  const updates: Array<{ complete: boolean; content: string }> = [];
  let previewCount = 0;
  const presentation = createSummaryPresentation({
    scheduler,
    summary,
    onSummaryUpdate: (content, complete) => updates.push({ content, complete }),
    onPreviewReady: () => {
      previewCount += 1;
    },
  });

  presentation.start();
  assert.deepEqual(updates[0], { content: Array.from(summary)[0], complete: false });
  assert.equal(previewCount, 0);

  scheduler.advanceBy(calculateSummaryRevealDuration(summary));
  assert.equal(updates[updates.length - 1]?.content, summary);
  assert.equal(updates[updates.length - 1]?.complete, true);
  assert.equal(previewCount, 0);

  scheduler.advanceBy(SUMMARY_HOLD_MS - 1);
  assert.equal(previewCount, 0);
  scheduler.advanceBy(1);
  assert.equal(previewCount, 1);
});

test('updates a long summary on animation frames instead of coarse timer ticks', () => {
  const scheduler = new FakeScheduler();
  const updateTimes: number[] = [];
  const presentation = createSummaryPresentation({
    scheduler,
    summary: '流畅输出'.repeat(250),
    onSummaryUpdate: () => updateTimes.push(scheduler.now()),
    onPreviewReady: () => undefined,
  });

  presentation.start();
  scheduler.advanceBy(100);

  assert.ok(scheduler.requestedFrameCount >= 6);
  assert.ok(updateTimes.length >= 7);
  assert.ok(updateTimes.slice(1).every((time, index) => time - updateTimes[index] <= 17));
});

test('caps even a very large clean summary at the maximum transition time', () => {
  const scheduler = new FakeScheduler();
  const summary = 'x'.repeat(100_000);
  let finalSummary = '';
  let previewCount = 0;
  const presentation = createSummaryPresentation({
    scheduler,
    summary,
    onSummaryUpdate: content => {
      finalSummary = content;
    },
    onPreviewReady: () => {
      previewCount += 1;
    },
  });

  presentation.start();
  scheduler.advanceBy(SUMMARY_REVEAL_MAX_MS + SUMMARY_HOLD_MS);

  assert.equal(finalSummary, summary);
  assert.equal(previewCount, 1);
});

test('cancels pending reveal and preview callbacks', () => {
  const scheduler = new FakeScheduler();
  const updates: string[] = [];
  let previewCount = 0;
  const presentation = createSummaryPresentation({
    scheduler,
    summary: '需要展示但不应自动抢回的摘要'.repeat(20),
    onSummaryUpdate: content => updates.push(content),
    onPreviewReady: () => {
      previewCount += 1;
    },
  });

  presentation.start();
  scheduler.advanceBy(200);
  presentation.cancel();
  const updateCountAfterCancel = updates.length;
  scheduler.advanceBy(10_000);

  assert.equal(updates.length, updateCountAfterCancel);
  assert.equal(previewCount, 0);
});

test('can cancel automatic preview during the completed-summary hold', () => {
  const scheduler = new FakeScheduler();
  const summary = '摘要已经完整显示';
  let previewCount = 0;
  const presentation = createSummaryPresentation({
    scheduler,
    summary,
    onSummaryUpdate: () => undefined,
    onPreviewReady: () => {
      previewCount += 1;
    },
  });

  presentation.start();
  scheduler.advanceBy(calculateSummaryRevealDuration(summary));
  presentation.cancel();
  scheduler.advanceBy(SUMMARY_HOLD_MS);

  assert.equal(previewCount, 0);
});

test('skips presentation and completes immediately when the summary is empty', () => {
  const scheduler = new FakeScheduler();
  const updates: Array<{ complete: boolean; content: string }> = [];
  let previewCount = 0;
  const presentation = createSummaryPresentation({
    scheduler,
    summary: '',
    onSummaryUpdate: (content, complete) => updates.push({ content, complete }),
    onPreviewReady: () => {
      previewCount += 1;
    },
  });

  presentation.start();

  assert.deepEqual(updates, [{ content: '', complete: true }]);
  assert.equal(previewCount, 1);
});
