import type { DashboardAnnotationRecord, DashboardRecord, DashboardSchemaV1 } from '@/types/dashboard';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const state = vi.hoisted(() => ({
  onRemoteRecord: undefined as undefined | ((record: DashboardRecord) => void),
  save: vi.fn(),
  apply: vi.fn(),
  deferRemoteRecord: vi.fn(),
  applyBatch: vi.fn(),
  annotations: vi.fn(),
  refresh: vi.fn(),
  info: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
  getDashboard: vi.fn(),
  validate: vi.fn(),
  publish: vi.fn(),
}));
vi.mock('@/client/api', () => ({
  getDashboard: state.getDashboard,
  validateDashboard: state.validate,
  publishDashboard: state.publish,
  applyDashboardAnnotation: state.apply,
  listDashboardAnnotations: state.annotations,
  refreshDashboard: state.refresh,
  getDashboardJsonSchema: () => Promise.reject(new Error('No schema endpoint in fixture')),
}));
vi.mock('@/client/api/dashboard', () => ({ applyDashboardAnnotationBatch: state.applyBatch }));
vi.mock('./dashboard-collaboration', () => ({
  useDashboardCollaboration: ({ onRemoteRecord }: { onRemoteRecord: (record: DashboardRecord) => void }) => {
    state.onRemoteRecord = onRemoteRecord;
    return { save: state.save, deferRemoteRecord: state.deferRemoteRecord, status: 'online', participants: [] };
  },
}));
vi.mock('antd', async importOriginal => {
  const actual = await importOriginal<typeof import('antd')>();
  return {
    ...actual,
    Select: () => null,
    App: {
      ...actual.App,
      useApp: () => ({
        message: { info: state.info, success: state.success, warning: state.warning, error: state.error },
        modal: { confirm: vi.fn(), error: vi.fn() },
      }),
    },
  };
});
vi.mock('@/hooks/use-question-session', () => ({ useQuestionSession: () => ({ pendingQuestion: null }) }));
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
        annotationIds: ['annotation-1'],
      });
      return { session, setSession };
    },
  };
});
vi.mock('./DashboardRenderer', () => ({
  default: ({
    schema,
    onLayoutChange,
    onOpenWidgetQueryEditor,
  }: {
    schema: DashboardSchemaV1;
    onLayoutChange: (layout: DashboardSchemaV1['layouts']['desktop']) => void;
    onOpenWidgetQueryEditor: (id: string) => void;
  }) => (
    <div>
      <output data-testid='current-schema'>{JSON.stringify(schema)}</output>
      <button onClick={() => onLayoutChange([{ ...schema.layouts.desktop[0], x: 3 }])}>Move widget</button>
      <button onClick={() => onOpenWidgetQueryEditor('sales')}>Edit SQL</button>
    </div>
  ),
}));
vi.mock('./DashboardAnnotationOverlay', () => ({
  default: ({
    annotations,
    onApply,
  }: {
    annotations: DashboardAnnotationRecord[];
    onApply: (annotation: DashboardAnnotationRecord) => void;
  }) => (
    <button disabled={!annotations.length} onClick={() => onApply(annotations[0])}>
      Apply single
    </button>
  ),
}));
vi.mock('./DashboardAssistantConversation', () => ({
  default: ({ onApplyBatch }: { onApplyBatch: () => void }) => <button onClick={onApplyBatch}>Apply batch</button>,
}));
vi.mock('./DashboardAccessPanel', () => ({ default: () => null }));
vi.mock('./DashboardAnnotationTray', () => ({ default: () => null }));
vi.mock('./DashboardAnomalyRuleEditor', () => ({ default: () => null }));
vi.mock('./DashboardArtifactPanel', () => ({ default: () => null }));
vi.mock('./DashboardCoverCapture', () => ({ default: () => null }));
vi.mock('./DashboardFilters', () => ({ default: () => null }));
vi.mock('./DashboardLifecyclePanel', () => ({ default: () => null }));
vi.mock('./DashboardPublishDialog', () => ({
  default: ({ onPublish }: { onPublish: (mode: 'snapshot') => void }) => (
    <button onClick={() => onPublish('snapshot')}>Confirm publish</button>
  ),
}));
vi.mock('./DashboardQueryLogicPanel', () => ({ default: () => null }));
vi.mock('./DashboardThemePanel', () => ({ default: () => null }));
vi.mock('@/new-components/chat/content/QuestionDock', () => ({ default: () => null }));
vi.mock('@/new-components/scheduled-task/SaveAsScheduledTaskDrawer', () => ({ default: () => null }));

import DashboardEditor from './DashboardEditor';
import { readDashboardLocalDraft } from './dashboard-draft-recovery';
import { makeUnconfiguredWidget } from './dashboard-editor-model';

const initial: DashboardRecord = {
  id: 'dashboard-1',
  owner_id: 'owner',
  origin: 'manual',
  asset_state: 'saved',
  current_revision: 3,
  status: 'draft',
  created_at: '',
  updated_at: '',
  schema: {
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
    widgets: [makeUnconfiguredWidget('table', 'sales', 'sales')],
    layouts: { columns: 12, desktop: [{ widget_id: 'sales', x: 0, y: 0, w: 6, h: 4 }], mobile_strategy: 'stack' },
    metadata: { agent: { generated: false }, compatibility: {} },
  },
};
const annotation = { id: 'annotation-1', status: 'proposed', base_revision: 3 } as DashboardAnnotationRecord;
const response = <T,>(data: T) => ({ data: { success: true, data } });
const currentSchema = () => JSON.parse(screen.getByTestId('current-schema').textContent!) as DashboardSchemaV1;
const title = (value: string) =>
  fireEvent.change(screen.getByRole('textbox', { name: '看板标题' }), { target: { value } });
const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => {
    resolve = done;
  });
  return { promise, resolve };
};

beforeEach(() => {
  vi.resetAllMocks();
  localStorage.clear();
  state.annotations.mockResolvedValue(response([annotation]));
  state.refresh.mockResolvedValue(response({ widgets: {}, filters: {} }));
  Element.prototype.scrollIntoView = vi.fn();
});

async function openEditor(record = initial) {
  render(<DashboardEditor initialRecord={structuredClone(record)} />);
  await waitFor(() => expect((screen.getByText('Apply single') as HTMLButtonElement).disabled).toBe(false));
}

describe('DashboardEditor persistence races', () => {
  it('preserves edit made during generated promotion instead of overwriting with latest', async () => {
    const generated = structuredClone(initial);
    generated.asset_state = 'generated';
    generated.schema.widgets[0].query.sql = 'SELECT amount FROM sales';
    const request = deferred<DashboardRecord>();
    state.save.mockReturnValue(request.promise);
    state.getDashboard.mockResolvedValue(response({ ...generated, asset_state: 'saved', current_revision: 5 }));
    state.validate.mockResolvedValue(response({ issues: [] }));
    state.publish.mockResolvedValue(response({ share_path: '/share/fixture' }));
    await openEditor(generated);
    fireEvent.click(screen.getByRole('button', { name: '发布看板' }));
    fireEvent.click(screen.getByText('Confirm publish'));
    expect(state.save).toHaveBeenCalledOnce();
    title('New while promoting');
    const edited = currentSchema();
    await act(async () => request.resolve({ ...generated, asset_state: 'saved', current_revision: 4 }));
    expect(currentSchema()).toEqual(edited);
    await waitFor(() => expect(readDashboardLocalDraft(initial.id)).toMatchObject({ baseRevision: 4, schema: edited }));
    expect(state.deferRemoteRecord).toHaveBeenCalledWith(expect.objectContaining({ current_revision: 5 }));
  });

  it('preserves edit made while clean-publish latest lookup is in flight', async () => {
    const configured = structuredClone(initial);
    configured.schema.widgets[0].query.sql = 'SELECT amount FROM sales';
    const request = deferred<ReturnType<typeof response>>();
    state.getDashboard.mockReturnValue(request.promise);
    state.validate.mockResolvedValue(response({ issues: [] }));
    state.publish.mockResolvedValue(response({ share_path: '/share/fixture' }));
    await openEditor(configured);
    fireEvent.click(screen.getByRole('button', { name: '发布看板' }));
    fireEvent.click(screen.getByText('Confirm publish'));
    await waitFor(() => expect(state.getDashboard).toHaveBeenCalledOnce());
    title('New while fetching latest');
    const edited = currentSchema();
    await act(async () => request.resolve(response({ ...configured, current_revision: 4 })));
    expect(currentSchema()).toEqual(edited);
    await waitFor(() => expect(readDashboardLocalDraft(initial.id)).toMatchObject({ baseRevision: 3, schema: edited }));
    expect(state.deferRemoteRecord).toHaveBeenCalledWith(expect.objectContaining({ current_revision: 4 }));
  });

  it('preserves Redo when edit then Undo returns to submitted save snapshot', async () => {
    const request = deferred<DashboardRecord>();
    state.save.mockReturnValue(request.promise);
    await openEditor();
    title('Submitted');
    fireEvent.click(screen.getByRole('button', { name: '保存看板' }));
    const submitted = state.save.mock.calls[0][0] as DashboardSchemaV1;
    title('I may want to redo this');
    fireEvent.click(screen.getByRole('button', { name: '撤销' }));
    expect((screen.getByRole('button', { name: '重做' }) as HTMLButtonElement).disabled).toBe(false);
    await act(async () => request.resolve({ ...initial, current_revision: 4, schema: submitted }));
    expect((screen.getByRole('button', { name: '重做' }) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: '重做' }));
    expect(currentSchema().dashboard.title).toBe('I may want to redo this');
    await waitFor(() =>
      expect(readDashboardLocalDraft(initial.id)).toMatchObject({
        baseRevision: 4,
        schema: { dashboard: { title: 'I may want to redo this' } },
      }),
    );
  });

  it('does not roll back a newer collaboration revision when old promotion save returns', async () => {
    const generated = structuredClone(initial);
    generated.asset_state = 'generated';
    const request = deferred<DashboardRecord>();
    state.save.mockReturnValue(request.promise);
    await openEditor(generated);
    fireEvent.click(screen.getByRole('button', { name: '保存看板' }));
    expect(state.save).toHaveBeenCalledOnce();
    act(() => state.onRemoteRecord?.({ ...generated, asset_state: 'saved', current_revision: 5 }));
    expect(screen.getByText('修订 5')).toBeTruthy();
    await act(async () => request.resolve({ ...generated, asset_state: 'saved', current_revision: 4 }));
    expect(screen.getByText('修订 5')).toBeTruthy();
  });

  it('does not roll back a newer collaboration revision when old annotation response returns', async () => {
    const request = deferred<ReturnType<typeof response>>();
    state.apply.mockReturnValue(request.promise);
    await openEditor();
    fireEvent.click(screen.getByText('Apply single'));
    act(() => state.onRemoteRecord?.({ ...initial, current_revision: 5 }));
    expect(screen.getByText('修订 5')).toBeTruthy();
    await act(async () =>
      request.resolve(response({ operation: { dashboard: { ...initial, current_revision: 4 } }, annotation })),
    );
    expect(screen.getByText('修订 5')).toBeTruthy();
  });

  it('preserves newer annotation edits delivered in same React batch as response', async () => {
    const request = deferred<ReturnType<typeof response>>();
    state.apply.mockReturnValue(request.promise);
    await openEditor();
    fireEvent.click(screen.getByText('Apply single'));
    await act(async () => {
      title('Same batch edit');
      request.resolve(response({ operation: { dashboard: { ...initial, current_revision: 4 } }, annotation }));
    });
    expect(currentSchema().dashboard.title).toBe('Same batch edit');
  });

  it('keeps normal in-flight annotation edits with old base and defers remote record intentionally', async () => {
    const request = deferred<ReturnType<typeof response>>();
    state.apply.mockReturnValue(request.promise);
    await openEditor();
    fireEvent.click(screen.getByText('Apply single'));
    title('Normal newer edit');
    const next = { ...initial, current_revision: 4 };
    await act(async () => request.resolve(response({ operation: { dashboard: next }, annotation })));
    expect(currentSchema().dashboard.title).toBe('Normal newer edit');
    expect(screen.getByText('修订 3')).toBeTruthy();
    expect(state.deferRemoteRecord).toHaveBeenCalledWith(next);
    await waitFor(() => expect(readDashboardLocalDraft(initial.id)).toMatchObject({ baseRevision: 3 }));
  });

  it.each(['save', 'annotation'] as const)(
    'keeps a newer collaboration record in the same React batch as an old %s response',
    async mutation => {
      const generated = { ...structuredClone(initial), asset_state: 'generated' as const };
      const request = deferred<DashboardRecord | ReturnType<typeof response>>();
      (mutation === 'save' ? state.save : state.apply).mockReturnValue(request.promise);
      await openEditor(generated);
      fireEvent.click(
        mutation === 'save' ? screen.getByRole('button', { name: '保存看板' }) : screen.getByText('Apply single'),
      );
      const remote = structuredClone(generated);
      remote.current_revision = 5;
      remote.schema.dashboard.title = 'Newer remote revision';
      await act(async () => {
        state.onRemoteRecord?.(remote);
        const old = { ...generated, current_revision: 4 };
        request.resolve(mutation === 'save' ? old : response({ operation: { dashboard: old }, annotation }));
      });
      expect(screen.getByText('修订 5')).toBeTruthy();
      expect(currentSchema().dashboard.title).toBe('Newer remote revision');
      expect(state.deferRemoteRecord).not.toHaveBeenCalled();
    },
  );

  it('accepts latest publication data when the editor has stayed clean', async () => {
    const configured = structuredClone(initial);
    configured.schema.widgets[0].query.sql = 'SELECT amount FROM sales';
    const latest = structuredClone(configured);
    latest.current_revision = 4;
    latest.schema.dashboard.title = 'Latest server title';
    state.getDashboard.mockResolvedValue(response(latest));
    state.validate.mockResolvedValue(response({ issues: [] }));
    state.publish.mockResolvedValue(response({ share_path: '/share/fixture' }));
    await openEditor(configured);
    fireEvent.click(screen.getByRole('button', { name: '发布看板' }));
    fireEvent.click(screen.getByText('Confirm publish'));
    await waitFor(() => expect(state.publish).toHaveBeenCalledWith(initial.id, 4, {}, false));
    expect(currentSchema().dashboard.title).toBe('Latest server title');
    expect(screen.getByText('修订 4')).toBeTruthy();
    expect(state.deferRemoteRecord).not.toHaveBeenCalled();
    expect(readDashboardLocalDraft(initial.id)).toBeNull();
  });

  it('keeps a newer collaboration revision when publication completion is late', async () => {
    const configured = structuredClone(initial);
    configured.schema.widgets[0].query.sql = 'SELECT amount FROM sales';
    const request = deferred<ReturnType<typeof response>>();
    state.getDashboard.mockResolvedValue(response(configured));
    state.validate.mockResolvedValue(response({ issues: [] }));
    state.publish.mockReturnValue(request.promise);
    await openEditor(configured);
    fireEvent.click(screen.getByRole('button', { name: '发布看板' }));
    fireEvent.click(screen.getByText('Confirm publish'));
    await waitFor(() => expect(state.publish).toHaveBeenCalledOnce());
    const remote = structuredClone(configured);
    remote.current_revision = 5;
    remote.schema.dashboard.title = 'Newer published revision';
    await act(async () => {
      state.onRemoteRecord?.(remote);
      request.resolve(response({ share_path: '/share/fixture' }));
    });
    expect(screen.getByText('修订 5')).toBeTruthy();
    expect(currentSchema().dashboard.title).toBe('Newer published revision');
  });
});
