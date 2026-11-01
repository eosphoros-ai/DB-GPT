import type { DashboardAnnotationRecord, DashboardRecord } from '@/types/dashboard';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { App } from 'antd';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from '../../tests/dashboard-e2e/fixtures/walmart/record.json';
import DashboardEditor from './DashboardEditor';
import { readDashboardLocalDraft } from './dashboard-draft-recovery';

const mocks = vi.hoisted(() => ({
  save: vi.fn(),
  apply: vi.fn(),
  deferRemoteRecord: vi.fn(),
  refresh: vi.fn(),
  annotations: vi.fn(),
}));

vi.mock('@/client/api', () => ({
  getDashboardJsonSchema: vi.fn().mockResolvedValue({ data: { data: { type: 'object' } } }),
  listDashboardAnnotations: mocks.annotations,
  applyDashboardAnnotation: mocks.apply,
  refreshDashboard: mocks.refresh,
  getLatestDashboardSnapshot: vi.fn(),
  getDashboard: vi.fn(),
  createDashboardAnnotation: vi.fn(),
  generateDashboardAnnotationProposal: vi.fn(),
  previewDashboardWidget: vi.fn(),
  publishDashboard: vi.fn(),
  rejectDashboardAnnotation: vi.fn(),
  resolveDashboardAnnotationIntents: vi.fn(),
  resolveDashboardTarget: vi.fn(),
  validateDashboard: vi.fn(),
}));
vi.mock('@/client/api/dashboard', () => ({
  applyDashboardAnnotationBatch: vi.fn(),
  createDashboardLiveShare: vi.fn(),
}));
vi.mock('./dashboard-collaboration', () => ({
  useDashboardCollaboration: () => ({
    clientId: 'test-editor',
    status: 'online',
    participants: [],
    pendingRemote: null,
    save: mocks.save,
    deferRemoteRecord: mocks.deferRemoteRecord,
  }),
}));
vi.mock('@/hooks/use-question-session', () => ({
  useQuestionSession: () => ({ pendingQuestion: null, clearQuestions: vi.fn() }),
}));
vi.mock('./DashboardRenderer', () => ({ default: () => null }));
vi.mock('./DashboardCoverCapture', () => ({ default: () => null }));
vi.mock('./DashboardThemePanel', () => ({ default: () => null }));
vi.mock('./DashboardAccessPanel', () => ({ default: () => null }));
vi.mock('./DashboardArtifactPanel', () => ({ default: () => null }));
vi.mock('./DashboardLifecyclePanel', () => ({ default: () => null }));
vi.mock('./DashboardQueryLogicPanel', () => ({ default: () => null }));
vi.mock('./DashboardAnomalyRuleEditor', () => ({ default: () => null }));
vi.mock('./DashboardAssistantConversation', () => ({ default: () => null }));
vi.mock('./DashboardAnnotationTray', () => ({ default: () => null }));
vi.mock('./DashboardFilters', () => ({ default: () => null }));
vi.mock('./DashboardPublishDialog', () => ({ default: () => null }));
vi.mock('./DashboardLayoutTemplates', () => ({ DashboardLayoutTemplatePicker: () => null }));
vi.mock('./dashboard-assistant-stream', () => ({ runDashboardAssistant: vi.fn() }));
vi.mock('./dashboard-assistant-session', async () => {
  const { useState } = await import('react');
  return {
    sendableAnnotations: () => [],
    useDashboardAssistantSession: () => {
      const [session, setSession] = useState({
        drafts: [],
        saved: [],
        messages: [],
        pending: [],
        clarification: [],
        annotationIds: [],
      });
      return { session, setSession };
    },
  };
});
vi.mock('@/new-components/chat/content/QuestionDock', () => ({ default: () => null }));
vi.mock('@/new-components/scheduled-task/SaveAsScheduledTaskDrawer', () => ({ default: () => null }));
vi.mock('./DashboardAnnotationOverlay', () => ({
  default: ({
    annotations,
    applyingId,
    onApply,
  }: {
    annotations: DashboardAnnotationRecord[];
    applyingId: string | null;
    onApply: (annotation: DashboardAnnotationRecord) => Promise<void>;
  }) => (
    <button disabled={!annotations.length || Boolean(applyingId)} onClick={() => void onApply(annotations[0])}>
      应用测试批注
    </button>
  ),
}));

/** Create a minimal editable record while retaining the real fixture contract. */
function record(title = 'Original', revision = 1): DashboardRecord {
  const result = structuredClone(fixture) as unknown as DashboardRecord;
  result.current_revision = revision;
  result.status = 'draft';
  result.schema.dashboard.title = title;
  result.schema.widgets = [];
  result.schema.filters = [];
  result.schema.layouts.desktop = [];
  return result;
}

/** Control response delivery without changing the production timeout. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((onResolve, onReject) => {
    resolve = onResolve;
    reject = onReject;
  });
  return { promise, resolve, reject };
}

const proposal = { id: 'proposal-1', status: 'proposed', base_revision: 1 } as DashboardAnnotationRecord;
const applied = (next: DashboardRecord) => ({
  data: { success: true, data: { operation: { dashboard: next }, annotation: { ...proposal, status: 'applied' } } },
});

async function openEditor() {
  const onRecordChange = vi.fn();
  render(
    <App>
      <DashboardEditor initialRecord={record()} onRecordChange={onRecordChange} />
    </App>,
  );
  await waitFor(() => expect(screen.getByText('应用测试批注').hasAttribute('disabled')).toBe(false));
  return onRecordChange;
}

const titleInput = () => screen.getByLabelText('看板标题') as HTMLInputElement;
const changeTitle = (title: string) => fireEvent.change(titleInput(), { target: { value: title } });
const save = () => fireEvent.click(screen.getByLabelText('保存看板'));
const apply = () => fireEvent.click(screen.getByText('应用测试批注'));

describe('DashboardEditor pending mutations', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    mocks.save.mockReset();
    mocks.apply.mockReset();
    mocks.deferRemoteRecord.mockReset();
    mocks.annotations.mockResolvedValue({ data: { data: [proposal] } });
    mocks.refresh.mockResolvedValue({ data: { success: true, data: { widgets: {}, filters: {} } } });
  });

  it('keeps edits made after a save was submitted and saves them using the acknowledged revision', async () => {
    const pending = deferred<DashboardRecord>();
    mocks.save.mockReturnValueOnce(pending.promise).mockResolvedValueOnce(record('Newer edit', 3));
    await openEditor();
    changeTitle('Submitted');
    save();
    await waitFor(() => expect(mocks.save).toHaveBeenCalledTimes(1));
    changeTitle('Newer edit');
    await act(async () => pending.resolve(record('Submitted', 2)));
    expect(titleInput().value).toBe('Newer edit');
    expect(screen.getByText('未保存')).toBeTruthy();
    await waitFor(() =>
      expect(readDashboardLocalDraft(record().id)).toMatchObject({
        baseRevision: 2,
        schema: { dashboard: { title: 'Newer edit' } },
      }),
    );
    save();
    await waitFor(() => expect(mocks.save).toHaveBeenCalledTimes(2));
    expect(mocks.save.mock.calls[1]).toEqual([
      expect.objectContaining({ dashboard: expect.objectContaining({ title: 'Newer edit' }) }),
      2,
      true,
    ]);
    await waitFor(() => expect(screen.queryByText('未保存')).toBeNull());
  });

  it('accepts server normalization and clears recovery only when there are no newer edits', async () => {
    const pending = deferred<DashboardRecord>();
    mocks.save.mockReturnValueOnce(pending.promise);
    await openEditor();
    changeTitle('Submitted');
    save();
    await waitFor(() => expect(mocks.save).toHaveBeenCalledTimes(1));
    await act(async () => pending.resolve(record('Server normalized', 2)));
    expect(titleInput().value).toBe('Server normalized');
    expect(screen.queryByText('未保存')).toBeNull();
    await waitFor(() => expect(readDashboardLocalDraft(record().id)).toBeNull());
  });

  it('keeps the draft and revision when saving fails', async () => {
    const pending = deferred<DashboardRecord>();
    mocks.save.mockReturnValueOnce(pending.promise);
    const changed = await openEditor();
    changeTitle('Unsent work');
    save();
    await waitFor(() => expect(mocks.save).toHaveBeenCalledTimes(1));
    await act(async () => pending.reject(new Error('save failed')));
    expect(titleInput().value).toBe('Unsent work');
    expect(changed.mock.lastCall?.[0].current_revision).toBe(1);
    expect(screen.getByText('未保存')).toBeTruthy();
  });

  it('does not submit a single annotation while manual edits are unsaved', async () => {
    await openEditor();
    changeTitle('Keep my title');
    apply();
    expect(mocks.apply).not.toHaveBeenCalled();
    expect(titleInput().value).toBe('Keep my title');
    expect(await screen.findByText('请先保存当前手动修改，再应用 AI 方案')).toBeTruthy();
  });

  it('applies a proposal to a clean editor and refreshes its data', async () => {
    mocks.apply.mockResolvedValueOnce(applied(record('Agent title', 2)));
    const changed = await openEditor();
    apply();
    await waitFor(() => expect(titleInput().value).toBe('Agent title'));
    expect(changed.mock.lastCall?.[0].current_revision).toBe(2);
    expect(mocks.deferRemoteRecord).not.toHaveBeenCalled();
    expect(mocks.refresh).toHaveBeenCalledWith(record().id, {});
  });

  it('keeps edits made during annotation application and requires explicit remote reconciliation', async () => {
    const pending = deferred<ReturnType<typeof applied>>();
    mocks.apply.mockReturnValueOnce(pending.promise);
    const changed = await openEditor();
    apply();
    await waitFor(() => expect(mocks.apply).toHaveBeenCalledTimes(1));
    changeTitle('Typed during request');
    await act(async () => pending.resolve(applied(record('Agent title', 2))));
    expect(titleInput().value).toBe('Typed during request');
    // Keep the old base revision so a subsequent save cannot silently undo the applied proposal.
    expect(changed.mock.lastCall?.[0].current_revision).toBe(1);
    expect(mocks.deferRemoteRecord).toHaveBeenCalledWith(record('Agent title', 2));
    expect(mocks.refresh).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(readDashboardLocalDraft(record().id)).toMatchObject({
        baseRevision: 1,
        schema: { dashboard: { title: 'Typed during request' } },
      }),
    );
  });

  it('leaves the current draft intact when annotation application fails', async () => {
    mocks.apply.mockRejectedValueOnce(new Error('annotation failed'));
    const changed = await openEditor();
    apply();
    await waitFor(() => expect(mocks.apply).toHaveBeenCalledTimes(1));
    expect(titleInput().value).toBe('Original');
    expect(changed.mock.lastCall?.[0].current_revision).toBe(1);
    expect(mocks.deferRemoteRecord).not.toHaveBeenCalled();
  });
});
