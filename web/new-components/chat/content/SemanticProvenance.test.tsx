import { ChatEn } from '@/locales/en/chat';
import { SemanticProvenanceEn } from '@/locales/en/semanticProvenance';
import { ChatZh } from '@/locales/zh/chat';
import { SemanticProvenanceZh } from '@/locales/zh/semanticProvenance';
import {
  querySourcesFromExecution,
  semanticReadGapsFromExecution,
  semanticSourcesFromExecution,
} from '@/utils/semantic-provenance';
import { act, cleanup, fireEvent, render as renderUI, screen, waitFor } from '@testing-library/react';
import { createInstance } from 'i18next';
import type { ReactElement } from 'react';
import { I18nextProvider, initReactI18next } from 'react-i18next';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SemanticProvenance from './SemanticProvenance';

const i18n = createInstance();
i18n.use(initReactI18next).init({
  lng: 'zh',
  fallbackLng: 'en',
  initImmediate: false,
  resources: {
    en: { translation: { ...ChatEn, ...SemanticProvenanceEn } },
    zh: { translation: { ...ChatZh, ...SemanticProvenanceZh } },
  },
  interpolation: { escapeValue: false },
});

function render(ui: ReactElement, expandSources = true) {
  const result = renderUI(ui, {
    wrapper: ({ children }) => <I18nextProvider i18n={i18n}>{children}</I18nextProvider>,
  });
  if (expandSources) {
    const toggle = screen.queryByRole('button', { name: /展开引用来源|Expand sources/ });
    if (toggle) fireEvent.click(toggle);
  }
  return result;
}

const api = vi.hoisted(() => ({
  space: vi.fn(),
  entries: vi.fn(),
  tables: vi.fn(),
  columns: vi.fn(),
  relations: vi.fn(),
}));
vi.mock('@/client/api', () => ({ apiInterceptors: (value: unknown) => value }));
vi.mock('@/client/api/semantic', () => ({
  getSemanticSpace: api.space,
  getSemanticEntries: api.entries,
  getSemanticTables: api.tables,
  getSemanticColumns: api.columns,
  getSemanticRelations: api.relations,
}));
vi.mock('@/new-components/common/MarkdownContext', () => ({
  default: ({ children }: { children: string }) => <div>{children}</div>,
}));
vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: any) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

const sources = semanticSourcesFromExecution([{ id: 's', action: 'semantic_get_metric', status: 'done' }], {
  s: [
    {
      content: {
        source: 'semantic_center',
        status: 'ok',
        conn_id: 'commerce',
        ds_id: 3,
        metric: {
          id: 17,
          version: 1,
          status: 'published',
          metric_name: '净实收',
          citation: 'semantic::commerce/metric/17@v1',
          formula: 'published formula',
          metric_definition: { lineage: { sources: ['refunds.freight_cents'] } },
        },
      },
    },
  ],
});

const querySources = querySourcesFromExecution([{ id: 's', action: 'sql_query', status: 'done' }], {
  s: [
    {
      content: {
        sql: 'SELECT document FROM metric_definitions',
        columns: ['document'],
        rows: [['口径文档快照']],
        row_count: 1,
        db_name: 'commerce',
        execution: {
          status: 'succeeded',
          started_at: '2026-10-29T09:51:16Z',
          duration_ms: 16,
          tool: 'sql_query',
          artifact_id: 'sql-test-1',
        },
      },
    },
  ],
});
const readGaps = semanticReadGapsFromExecution([{ id: 's', action: 'semantic_search_metrics', status: 'done' }], {
  s: [{ content: { source: 'semantic_center', status: 'empty', ds_id: 3, conn_id: 'commerce', items: [] } }],
});

function setup() {
  api.space.mockResolvedValue([null, { conn_id: 'commerce' }]);
  api.tables.mockResolvedValue([null, [{ id: 7, table_name: 'refunds' }]]);
  api.columns.mockResolvedValue([null, [{ id: 71, column_name: 'freight_cents' }]]);
  api.entries.mockResolvedValue([
    null,
    [
      {
        id: 8,
        entry_type: 'column',
        target_id: 71,
        entry_name: '退运费',
        entry_comment: '退款中的运费部分',
        publish_version: 2,
      },
    ],
  ]);
  api.relations.mockResolvedValue([null, []]);
}
afterEach(cleanup);
beforeEach(async () => {
  await i18n.changeLanguage('zh');
});
describe('semantic citation interactions', () => {
  it('starts collapsed and keeps source details accessible after expanding in either language', async () => {
    setup();
    render(<SemanticProvenance content='' sources={sources} querySources={querySources} streaming />, false);
    const expand = screen.getByRole('button', { name: '展开引用来源' });
    expect(expand.getAttribute('aria-expanded')).toBe('false');
    expect(screen.queryByRole('button', { name: '查看引用 净实收 v1' })).toBeNull();
    fireEvent.click(expand);
    expect(screen.getByRole('button', { name: '收起引用来源' }).getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByRole('button', { name: '查看血缘 净实收 v1' })).toBeTruthy();
    await act(async () => {
      await i18n.changeLanguage('en');
    });
    fireEvent.click(screen.getByRole('button', { name: 'Collapse sources' }));
    expect(screen.queryByRole('button', { name: 'View source 净实收 v1' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Expand sources' }));
    fireEvent.click(screen.getByRole('button', { name: 'View source 净实收 v1' }));
    expect(await screen.findByText('published formula')).toBeTruthy();
  });
  it('shows metric definitions, business meanings, lineage and SQL together and opens lineage directly', async () => {
    setup();
    const businessSources = semanticSourcesFromExecution(
      [{ id: 's', action: 'semantic_search_business', status: 'done' }],
      {
        s: [
          {
            content: {
              source: 'semantic_center',
              status: 'ok',
              ds_id: 3,
              conn_id: 'commerce',
              items: [
                {
                  id: 8,
                  status: 'published',
                  entry_name: '退运费',
                  table_name: 'refunds',
                  column_name: 'freight_cents',
                },
              ],
            },
          },
        ],
      },
    );
    render(
      <SemanticProvenance content='回答' sources={[...sources, ...businessSources]} querySources={querySources} />,
    );
    expect(screen.getByRole('heading', { name: '指标与业务口径 · 1' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: '业务语义 · 1' })).toBeTruthy();
    expect(screen.queryByRole('heading', { name: '指标血缘 · 1' })).toBeNull();
    expect(screen.getByRole('button', { name: '查看口径' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '查看引用 退运费' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '查看 commerce 的SQL读取 1' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '查看血缘 净实收 v1' }));
    expect(screen.getByRole('tab', { name: '血缘与关联' }).getAttribute('aria-selected')).toBe('true');
    fireEvent.click(await screen.findByRole('button', { name: 'refunds.freight_cents' }));
    expect(await screen.findByText('退款中的运费部分')).toBeTruthy();
  });
  it('shows query evidence and missing-definition receipts without inventing published metric references', async () => {
    render(<SemanticProvenance content='回答' sources={[]} querySources={querySources} readGaps={readGaps} />);
    expect(screen.getByRole('region', { name: '引用来源' })).toBeTruthy();
    const gapSummary = screen.getByText('未命中的语义读取 · 1');
    expect(gapSummary.closest('details')?.open).toBe(false);
    fireEvent.click(gapSummary);
    expect(gapSummary.closest('details')?.open).toBe(true);
    expect(screen.getByText('无匹配的已发布定义或元数据', { exact: false })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '查看 commerce 的SQL读取 1' }));
    expect(await screen.findByText('口径文档快照')).toBeTruthy();
    expect(screen.getByText('sql-test-1')).toBeTruthy();
    expect(screen.queryByRole('tab', { name: '指标口径' })).toBeNull();
    expect(api.space).not.toHaveBeenCalled();
    await act(async () => {
      await i18n.changeLanguage('en');
    });
    expect(screen.getByRole('region', { name: 'Sources' })).toBeTruthy();
    expect(screen.getByText('SQL source evidence')).toBeTruthy();
    expect(screen.getByText('Execution record')).toBeTruthy();
    expect(screen.getByText('No matching published definitions or metadata', { exact: false })).toBeTruthy();
  });
  it('shows missing semantic evidence even when no SQL query was executed', () => {
    render(<SemanticProvenance content='需要澄清口径' sources={[]} readGaps={readGaps} />);
    expect(screen.getByRole('region', { name: '引用来源' })).toBeTruthy();
    expect(screen.getAllByRole('button')).toHaveLength(1);
    fireEvent.click(screen.getByText('未命中的语义读取 · 1'));
    expect(screen.getByRole('link', { name: '在语义中心查看' }).getAttribute('href')).toBe(
      '/construct/semantic?ds=3&tab=metrics',
    );
  });
  it('previews three SQL reads and expands the rest while keeping every record accessible', async () => {
    const queries = Array.from({ length: 5 }, (_, index) => ({
      ...querySources[0],
      key: `query-${index}`,
      payload: {
        ...querySources[0].payload,
        sql: `SELECT ${index}`,
        execution: {
          ...querySources[0].payload.execution,
          artifact_id: `sql-${index}`,
        },
      },
    }));
    render(<SemanticProvenance content='' sources={sources} querySources={queries} />);
    expect(screen.getByRole('button', { name: '查看血缘 净实收 v1' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: '查看 commerce 的SQL读取 4' })).toBeNull();
    const expand = screen.getByRole('button', { name: '展开其余 2 条 SQL 读取' });
    expect(expand.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(expand);
    expect(screen.getByRole('button', { name: '查看 commerce 的SQL读取 5' })).toBeTruthy();
    await act(async () => {
      await i18n.changeLanguage('en');
    });
    fireEvent.click(screen.getByRole('button', { name: 'Show fewer SQL reads' }));
    expect(screen.queryByRole('button', { name: 'View SQL read 4 from commerce' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Show 2 more SQL reads' }).getAttribute('aria-expanded')).toBe('false');
  });
  it('keeps sources clickable after artifacts, including while streaming or before text arrives', async () => {
    setup();
    const { rerender } = render(<SemanticProvenance content='' sources={sources} streaming />);
    fireEvent.click(screen.getByRole('button', { name: '查看引用 净实收 v1' }));
    expect(await screen.findByText('published formula')).toBeTruthy();
    rerender(
      <>
        <SemanticProvenance content='正在生成回答' sources={sources} streaming mode='answer' />
        <div>取数产物</div>
        <SemanticProvenance content='正在生成回答' sources={sources} streaming />
      </>,
    );
    const sourcePanel = screen.getByRole('region', { name: '引用来源' });
    expect(
      screen.getByText('正在生成回答').compareDocumentPosition(screen.getByText('取数产物')) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      screen.getByText('取数产物').compareDocumentPosition(sourcePanel) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });
  it('updates the source panel and open drawer when switching languages', async () => {
    setup();
    render(<SemanticProvenance content={'## 引用溯源\n指标 17@v1\n证据缺口：无调度任务'} sources={sources} />);
    fireEvent.click(screen.getByRole('button', { name: '查看引用 净实收 v1' }));
    expect(await screen.findByText('published formula')).toBeTruthy();
    await act(async () => {
      await i18n.changeLanguage('en');
    });
    expect(screen.getByRole('region', { name: 'Sources' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'View source 净实收 v1' })).toBeTruthy();
    expect(screen.getByText('Additional notes and evidence gaps')).toBeTruthy();
    expect(screen.getByRole('tab', { name: 'Metric definition' })).toBeTruthy();
    expect(screen.getByText('Cited version v1')).toBeTruthy();
    fireEvent.click(screen.getByRole('tab', { name: 'Lineage and relationships' }));
    expect(await screen.findByText('No recorded relationships')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'refunds.freight_cents' }));
    expect(await screen.findByText('退款中的运费部分')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Open business semantics in Semantic Center' })).toBeTruthy();
    await act(async () => {
      await i18n.changeLanguage('zh');
    });
    expect(screen.getByRole('region', { name: '引用来源' })).toBeTruthy();
    expect(screen.getByRole('tab', { name: '业务语义' })).toBeTruthy();
  });
  it('opens the cited snapshot and follows a field dependency to published business meaning', async () => {
    setup();
    render(<SemanticProvenance content='回答' sources={sources} />);
    fireEvent.click(screen.getByRole('button', { name: '查看引用 净实收 v1' }));
    expect(await screen.findByText('published formula')).toBeTruthy();
    fireEvent.click(screen.getByRole('tab', { name: '血缘与关联' }));
    fireEvent.click(await screen.findByRole('button', { name: 'refunds.freight_cents' }));
    expect(await screen.findByText('退款中的运费部分')).toBeTruthy();
    expect(screen.getByRole('link', { name: '在语义中心查看业务语义' }).getAttribute('href')).toBe(
      '/construct/semantic?ds=3&tab=entries',
    );
    expect(api.entries).toHaveBeenCalledWith(3, 'published');
  });
  it('retains the snapshot and shows a retry state if the space identity no longer matches', async () => {
    setup();
    api.space.mockResolvedValue([null, { conn_id: 'other' }]);
    render(<SemanticProvenance content='回答' sources={sources} />);
    fireEvent.click(screen.getByRole('button', { name: '查看引用 净实收 v1' }));
    fireEvent.click(screen.getByRole('tab', { name: '业务语义' }));
    await waitFor(() => expect(screen.getByText('关联信息加载失败，请重试；引用快照仍可查看。')).toBeTruthy());
    expect(await screen.findByRole('button', { name: '重试' })).toBeTruthy();
    expect(api.entries).not.toHaveBeenCalled();
  });
});
