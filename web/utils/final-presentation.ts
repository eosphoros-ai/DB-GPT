/** Timing policy for presenting a completed agent summary before its preview. */

export const SUMMARY_REVEAL_MIN_MS = 600;
export const SUMMARY_REVEAL_MAX_MS = 1500;
export const SUMMARY_HOLD_MS = 500;

const SUMMARY_REVEAL_MS_PER_CHARACTER = 4;
const FALLBACK_ANIMATION_FRAME_MS = 16;

export interface PresentationScheduler {
  now(): number;
  setTimeout(callback: () => void, delayMs: number): unknown;
  clearTimeout(id: unknown): void;
  requestFrame(callback: () => void): unknown;
  cancelFrame(id: unknown): void;
}

export interface SummaryPresentation {
  start(): void;
  cancel(): void;
}

interface SummaryPresentationOptions {
  summary: string;
  onSummaryUpdate(content: string, complete: boolean): void;
  onPreviewReady(): void;
  reducedMotion?: boolean;
  scheduler?: PresentationScheduler;
}

const defaultScheduler: PresentationScheduler = {
  now: () => globalThis.performance?.now() ?? Date.now(),
  setTimeout: (callback, delayMs) => globalThis.setTimeout(callback, delayMs),
  clearTimeout: id => globalThis.clearTimeout(id as ReturnType<typeof setTimeout>),
  requestFrame: callback => {
    if (typeof globalThis.requestAnimationFrame === 'function') {
      return globalThis.requestAnimationFrame(() => callback());
    }
    return globalThis.setTimeout(callback, FALLBACK_ANIMATION_FRAME_MS);
  },
  cancelFrame: id => {
    if (typeof globalThis.cancelAnimationFrame === 'function' && typeof id === 'number') {
      globalThis.cancelAnimationFrame(id);
      return;
    }
    globalThis.clearTimeout(id as ReturnType<typeof setTimeout>);
  },
};

export function calculateSummaryRevealDuration(summary: string): number {
  const characterCount = Array.from(summary).length;
  return Math.min(
    SUMMARY_REVEAL_MAX_MS,
    Math.max(SUMMARY_REVEAL_MIN_MS, characterCount * SUMMARY_REVEAL_MS_PER_CHARACTER),
  );
}

/**
 * Present a complete, already-normalized summary with bounded visual streaming.
 *
 * Artifact creation deliberately stays outside this module. The caller may prepare
 * a preview immediately while this controller owns only the visible transition.
 */
export function createSummaryPresentation({
  summary,
  onSummaryUpdate,
  onPreviewReady,
  reducedMotion = false,
  scheduler = defaultScheduler,
}: SummaryPresentationOptions): SummaryPresentation {
  const characters = Array.from(summary);
  let frameId: unknown;
  let revealDeadlineTimerId: unknown;
  let holdTimerId: unknown;
  let cancelled = false;

  const clearScheduledWork = () => {
    if (frameId !== undefined) {
      scheduler.cancelFrame(frameId);
      frameId = undefined;
    }
    if (revealDeadlineTimerId !== undefined) {
      scheduler.clearTimeout(revealDeadlineTimerId);
      revealDeadlineTimerId = undefined;
    }
    if (holdTimerId !== undefined) {
      scheduler.clearTimeout(holdTimerId);
      holdTimerId = undefined;
    }
  };

  const finishAfterHold = () => {
    if (cancelled) return;
    holdTimerId = scheduler.setTimeout(() => {
      holdTimerId = undefined;
      if (!cancelled) onPreviewReady();
    }, SUMMARY_HOLD_MS);
  };

  const start = () => {
    clearScheduledWork();
    cancelled = false;

    if (characters.length === 0) {
      onSummaryUpdate('', true);
      onPreviewReady();
      return;
    }

    if (reducedMotion) {
      onSummaryUpdate(summary, true);
      finishAfterHold();
      return;
    }

    const revealDuration = calculateSummaryRevealDuration(summary);
    const startedAt = scheduler.now();
    let lastVisibleCharacterCount = 1;
    let revealFinished = false;
    // Keep the summary tab renderable from the first paint. An empty string
    // would make controlled tab content fall back to the full saved message.
    onSummaryUpdate(characters[0], false);

    const completeReveal = () => {
      if (cancelled || revealFinished) return;
      revealFinished = true;

      if (frameId !== undefined) {
        scheduler.cancelFrame(frameId);
        frameId = undefined;
      }
      if (revealDeadlineTimerId !== undefined) {
        scheduler.clearTimeout(revealDeadlineTimerId);
        revealDeadlineTimerId = undefined;
      }

      lastVisibleCharacterCount = characters.length;
      onSummaryUpdate(summary, true);
      finishAfterHold();
    };

    const revealNextChunk = () => {
      frameId = undefined;
      if (cancelled || revealFinished) return;

      const elapsed = Math.max(0, scheduler.now() - startedAt);
      const progress = Math.min(1, elapsed / revealDuration);
      const visibleCharacterCount = Math.max(1, Math.ceil(characters.length * progress));
      if (progress >= 1) {
        completeReveal();
        return;
      }

      if (visibleCharacterCount !== lastVisibleCharacterCount) {
        lastVisibleCharacterCount = visibleCharacterCount;
        onSummaryUpdate(characters.slice(0, visibleCharacterCount).join(''), false);
      }

      frameId = scheduler.requestFrame(revealNextChunk);
    };

    // rAF keeps intermediate paints smooth, while this deadline preserves the
    // bounded transition contract even when a frame is delayed or throttled.
    revealDeadlineTimerId = scheduler.setTimeout(() => {
      revealDeadlineTimerId = undefined;
      completeReveal();
    }, revealDuration);
    frameId = scheduler.requestFrame(revealNextChunk);
  };

  return {
    start,
    cancel: () => {
      cancelled = true;
      clearScheduledWork();
    },
  };
}
