import { afterEach, describe, expect, it } from 'vitest';
import {
  clearDashboardAnnotationHandoff,
  readDashboardAnnotationHandoff,
  writeDashboardAnnotationHandoff,
} from './dashboard-annotation-handoff';

describe('dashboard annotation handoff', () => {
  afterEach(() => window.sessionStorage.clear());

  it('hands a persisted annotation to the source task once', () => {
    writeDashboardAnnotationHandoff({
      annotationId: 'annotation-1',
      dashboardId: 'dashboard-1',
      conversationId: 'conversation-1',
      modelPrompt: 'model prompt',
      visiblePrompt: 'visible prompt',
      createdAt: '2026-08-19T00:00:00Z',
    });
    expect(readDashboardAnnotationHandoff('annotation-1')?.dashboardId).toBe('dashboard-1');
    clearDashboardAnnotationHandoff('annotation-1');
    expect(readDashboardAnnotationHandoff('annotation-1')).toBeNull();
  });

  it('rejects malformed session data', () => {
    window.sessionStorage.setItem('dbgpt-dashboard-annotation-handoff:annotation-2', '{broken');
    expect(readDashboardAnnotationHandoff('annotation-2')).toBeNull();
  });
});
