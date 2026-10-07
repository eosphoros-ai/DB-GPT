import { DashboardSchemaV1 } from '@/types/dashboard';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  clearDashboardLocalDraft,
  readDashboardLocalDraft,
  writeDashboardLocalDraft,
} from './dashboard-draft-recovery';
import { dashboardHistoryReducer } from './dashboard-editor-history';

const schema = {
  schema_version: '1.2',
  dashboard: {
    id: 'dashboard-1',
    title: 'Original',
    description: '',
    data_source_id: 'sales',
    status: 'draft',
    theme: {},
  },
  metric_context: { grain: '', source_notes: [], metrics: [], dimensions: [] },
  filters: [],
  widgets: [],
  layouts: { columns: 12, desktop: [], mobile_strategy: 'stack' },
  metadata: { agent: { generated: false }, compatibility: {} },
} satisfies DashboardSchemaV1;

describe('dashboard editor history and recovery', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.restoreAllMocks());

  it('undoes and redoes schema changes without mutating the snapshots', () => {
    const initial = { past: [], present: schema, future: [] };
    const changed = dashboardHistoryReducer(initial, {
      type: 'set',
      update: current => ({ ...current, dashboard: { ...current.dashboard, title: 'Changed' } }),
    });
    const undone = dashboardHistoryReducer(changed, { type: 'undo' });
    const redone = dashboardHistoryReducer(undone, { type: 'redo' });

    expect(changed.present.dashboard.title).toBe('Changed');
    expect(undone.present.dashboard.title).toBe('Original');
    expect(redone.present.dashboard.title).toBe('Changed');
  });

  it('persists and clears one crash-recovery draft per dashboard', () => {
    writeDashboardLocalDraft('dashboard-1', 3, schema);
    expect(readDashboardLocalDraft('dashboard-1')).toMatchObject({
      dashboardId: 'dashboard-1',
      baseRevision: 3,
      schema: { dashboard: { title: 'Original' } },
    });

    clearDashboardLocalDraft('dashboard-1');
    expect(readDashboardLocalDraft('dashboard-1')).toBeNull();
  });

  it('keeps editing available when browser storage is unavailable', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('Quota exceeded', 'QuotaExceededError');
    });
    expect(() => writeDashboardLocalDraft('dashboard-1', 3, schema)).not.toThrow();

    vi.restoreAllMocks();
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new DOMException('Storage blocked', 'SecurityError');
    });
    expect(() => clearDashboardLocalDraft('dashboard-1')).not.toThrow();
  });
});
