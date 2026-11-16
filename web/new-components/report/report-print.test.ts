import { afterEach, describe, expect, it, vi } from 'vitest';
import { waitForReportPaint } from './report-print';

const createSource = (visibilityState: DocumentVisibilityState) => {
  const source = document.implementation.createHTMLDocument('report');
  const requestAnimationFrame = vi.fn();
  const cancelAnimationFrame = vi.fn();
  Object.defineProperties(source, {
    visibilityState: { value: visibilityState },
    defaultView: { value: { requestAnimationFrame, cancelAnimationFrame } },
  });
  return { source, requestAnimationFrame };
};

afterEach(() => {
  vi.useRealTimers();
});

describe('waitForReportPaint', () => {
  it('does not wait for animation frames in a hidden document', async () => {
    const { source, requestAnimationFrame } = createSource('hidden');

    await expect(waitForReportPaint(source)).resolves.toBeUndefined();
    expect(requestAnimationFrame).not.toHaveBeenCalled();
  });

  it('falls back when a visible document stops producing animation frames', async () => {
    vi.useFakeTimers();
    const { source } = createSource('visible');
    let settled = false;
    const painted = waitForReportPaint(source).then(() => {
      settled = true;
    });

    await vi.runAllTimersAsync();

    expect(settled).toBe(true);
    await painted;
  });
});
