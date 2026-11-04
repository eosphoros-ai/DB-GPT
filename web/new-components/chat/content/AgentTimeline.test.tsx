import { buildActionDisplayText, publicAssistantText } from '@/utils/action-display';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import AgentTimeline, { stepsToTimelineBlocks } from './AgentTimeline';
import { isTerminalTool, terminalCommand } from './TerminalToolRow';

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock('@/new-components/common/MarkdownContext', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const query = (sql: string, value: number) => ({
  sql,
  columns: ['sales'],
  rows: [[value]],
  row_count: 1,
  db_name: 'Walmart_Sales',
});

const step = (id: string) => ({ id, title: 'sql_query', action: 'sql_query', status: 'done' });

describe('skill reading steps', () => {
  const binding = {
    skill: 'build-dashboard',
    documents: [
      { path: 'skills/build-dashboard/SKILL.md', status: 'loaded' },
      { path: 'skills/build-dashboard/references/evidence.md', status: 'loaded' },
    ],
  };

  it('shows recorded suite reads outside automatically folded tool phases', () => {
    const blocks = stepsToTimelineBlocks([step('q1'), step('q2'), step('q3')], {}, {}, binding);
    render(<AgentTimeline blocks={blocks} />);
    const read = screen.getByRole('button', { name: /timeline_read_skill.*build-dashboard/ });
    fireEvent.click(read);
    expect(screen.getByText(/File: skills\/build-dashboard\/SKILL.md/)).toBeTruthy();
    expect(screen.getByText(/File: skills\/build-dashboard\/references\/evidence.md/)).toBeTruthy();
    expect(screen.getByRole('button', { name: /timeline_phase_done/ }).getAttribute('aria-expanded')).toBe('false');
  });

  it('uses the full backend read step without duplicating the binding snapshot', () => {
    const blocks = stepsToTimelineBlocks(
      [
        {
          id: 'skill-read-suite',
          action: 'load_skill',
          title: '读取技能',
          status: 'done',
          actionInput: { skill_name: 'build-dashboard', file_path: binding.documents[0].path },
        },
      ],
      {},
      { 'skill-read-suite': [{ output_type: 'markdown', content: '# Actual skill instructions' }] },
      binding,
    );
    expect(blocks).toHaveLength(1);
    expect(blocks[0].output).toContain('Actual skill instructions');
  });

  it('does not present unread or failed skill bindings as reads', () => {
    expect(stepsToTimelineBlocks([], {}, {}, { ...binding, error: 'file missing' })).toEqual([]);
    expect(
      stepsToTimelineBlocks(
        [],
        {},
        {},
        {
          ...binding,
          documents: [{ path: 'SKILL.md', status: 'failed' }],
        },
      ),
    ).toEqual([]);
  });

  it('keeps ordinary skill calls and subsequent resource reads independently visible', () => {
    const blocks = stepsToTimelineBlocks(
      [
        { id: 'load', action: 'load_skill', status: 'done', actionInput: { skill_name: 'sql-data-analysis' } },
        {
          id: 'ref',
          action: 'get_skill_resource',
          status: 'done',
          actionInput: { skill_name: 'sql-data-analysis', resource_path: 'references/checks.md' },
        },
        step('q1'),
      ],
      {},
      {},
    );
    expect(blocks).toHaveLength(3);
    render(<AgentTimeline blocks={blocks} />);
    expect(screen.getByRole('button', { name: /timeline_read_skill sql-data-analysis/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /timeline_read_skill_resource sql-data-analysis/ })).toBeTruthy();
  });
});

describe('native multi-tool rounds', () => {
  const batch = {
    id: 'batch',
    action: 'semantic_search_metrics, sql_query',
    title: 'semantic_search_metrics, sql_query',
    status: 'done',
    actionInput: JSON.stringify([{ query: '业务指标', limit: 50 }, { sql: 'SELECT 77 AS sales' }]),
    startedAt: 0,
    endedAt: 1100,
  };
  const results = [
    {
      name: 'semantic_search_metrics',
      success: true,
      observation: JSON.stringify({
        source: 'semantic_center',
        items: [{ metric_name: 'GMV', formula: 'SUM(price)' }],
      }),
    },
    {
      name: 'sql_query',
      success: true,
      observation: JSON.stringify({ chunks: [{ output_type: 'query', content: query('SELECT 77 AS sales', 77) }] }),
    },
  ];

  it('shows independent calls with their own inputs and decoded result bodies', () => {
    const blocks = stepsToTimelineBlocks(
      [batch],
      {},
      {
        batch: [{ output_type: 'text', content: JSON.stringify(results) }],
      },
    );
    expect(blocks.map(block => block.tool)).toEqual(['semantic_search_metrics', 'sql_query']);
    expect(blocks[0].input).toContain('业务指标');
    expect(blocks[0].input).not.toContain('SELECT');
    expect(blocks[1].queryPayload?.sql).toBe('SELECT 77 AS sales');
    expect(blocks.every(block => block.durationMs === undefined)).toBe(true);
    render(<AgentTimeline blocks={blocks} />);
    fireEvent.click(screen.getByRole('button', { name: /semantic_search_metrics/ }));
    expect([...document.querySelectorAll('pre')].some(pre => pre.textContent?.includes('"metric_name": "GMV"'))).toBe(
      true,
    );
    expect(document.querySelector('table')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /sql_query/ }));
    expect(screen.getByRole('cell', { name: '77' })).toBeTruthy();
  });

  it('reassembles sliced SSE JSON and preserves independent success and failure states', () => {
    const text = JSON.stringify([results[0], { ...results[1], success: false, observation: 'SQL failed' }]);
    const blocks = stepsToTimelineBlocks(
      [{ ...batch, status: 'failed' }],
      {},
      {
        batch: [text.slice(0, 31), text.slice(31, 173), text.slice(173)].map(content => ({
          output_type: 'text',
          content,
        })),
      },
    );
    expect(blocks[0].status).toBe('success');
    expect(blocks[1].status).toBe('failed');
    expect(blocks[1].output).toBe('SQL failed');
  });

  it('keeps pending call identities stable while a batch result is streaming', () => {
    const initial = stepsToTimelineBlocks([{ ...batch, status: 'running' }], {}, {});
    const partial = stepsToTimelineBlocks(
      [{ ...batch, status: 'running' }],
      {},
      {
        batch: [{ output_type: 'text', content: '[{"name":' }],
      },
    );
    const complete = stepsToTimelineBlocks(
      [batch],
      {},
      {
        batch: [{ output_type: 'text', content: JSON.stringify(results) }],
      },
    );
    expect(initial.map(block => block.id)).toEqual(partial.map(block => block.id));
    expect(initial.map(block => block.id)).toEqual(complete.map(block => block.id));
    expect(partial.every(block => !block.output)).toBe(true);
  });

  it('does not assign mismatched legacy results to unrelated tool names', () => {
    const blocks = stepsToTimelineBlocks(
      [batch],
      {},
      {
        batch: [{ output_type: 'text', content: JSON.stringify([...results].reverse()) }],
      },
    );
    expect(blocks).toHaveLength(1);
    expect(blocks[0].tool).toBe(batch.action);
  });
});

describe('SQL execution timeline', () => {
  it('expands a query-only step to show SQL and results, then collapses it', () => {
    const blocks = stepsToTimelineBlocks(
      [step('q1')],
      {},
      {
        q1: [{ output_type: 'query', content: query('SELECT SUM(sales) FROM walmart_sales', 1234) }],
      },
    );
    render(<AgentTimeline blocks={blocks} />);
    const row = screen.getByRole('button', { name: /sql_query/ });
    expect(row.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(row);
    expect(row.getAttribute('aria-expanded')).toBe('true');
    expect(document.querySelector('pre')?.textContent).toContain('SELECT SUM(sales) FROM walmart_sales');
    expect(screen.getByRole('cell', { name: '1,234' })).toBeTruthy();
    fireEvent.click(row);
    expect(document.querySelector('table')).toBeNull();
  });

  it('keeps each query independently expandable inside consecutive query groups', () => {
    const blocks = stepsToTimelineBlocks(
      [step('q1'), step('q2')],
      {},
      {
        q1: [{ output_type: 'query', content: query('SELECT 111 AS sales', 111) }],
        q2: [{ output_type: 'query', content: query('SELECT 222 AS sales', 222) }],
      },
    );
    render(<AgentTimeline blocks={blocks} />);
    fireEvent.click(screen.getByRole('button', { name: /sql_query/ }));
    const rows = screen.getAllByRole('button', { name: /sql_query/ });
    expect(rows).toHaveLength(3);
    fireEvent.click(rows[1]);
    expect(screen.getByRole('cell', { name: '111' })).toBeTruthy();
    expect(screen.queryByRole('cell', { name: '222' })).toBeNull();
    fireEvent.click(rows[2]);
    expect(screen.getByRole('cell', { name: '222' })).toBeTruthy();
  });

  it('restores query payloads inside historical text envelopes', () => {
    const payload = query('SELECT 77 AS sales', 77);
    const blocks = stepsToTimelineBlocks(
      [step('history')],
      {},
      {
        history: [
          { output_type: 'text', content: JSON.stringify({ chunks: [{ output_type: 'query', content: payload }] }) },
        ],
      },
    );
    expect(blocks[0].queryPayload).toEqual(payload);
    render(<AgentTimeline blocks={blocks} />);
    fireEvent.keyDown(screen.getByRole('button', { name: /sql_query/ }), { key: 'Enter' });
    expect(screen.getByRole('cell', { name: '77' })).toBeTruthy();
  });

  it('preserves legacy markdown results when the structured result is absent', () => {
    const blocks = stepsToTimelineBlocks(
      [{ ...step('legacy'), actionInput: { sql: 'SELECT 1' } }],
      {},
      {
        legacy: [{ output_type: 'markdown', content: '| sales |\n| --- |\n| 1 |' }],
      },
    );
    expect(blocks[0].output).toContain('| sales |');
    render(<AgentTimeline blocks={blocks} />);
    fireEvent.click(screen.getByRole('button', { name: /sql_query/ }));
    expect(screen.getByText('Output')).toBeTruthy();
    expect(screen.getByText('| sales |', { exact: false })).toBeTruthy();
  });
});

describe('public progress and tool phases', () => {
  it.each([1, 2, 5, 17])('hides protocol fields split into %i-character chunks', chunkSize => {
    const text =
      'Thought: private reasoning\ncontinued reasoning\nAction Intention: 核对日期格式，再查询销售。\nAction: sql_query\nAction Input: {"sql":"SELECT 1"}';
    for (let end = chunkSize; end < text.length + chunkSize; end += chunkSize) {
      const content = publicAssistantText(text.slice(0, end), true);
      expect('核对日期格式，再查询销售。'.includes(content)).toBe(true);
    }
    expect(publicAssistantText(text)).toBe('核对日期格式，再查询销售。');
  });

  it('filters saved public text and intentions before rendering older conversations', () => {
    const raw = 'Thought: private reasoning\nAction Intention: 核对日期格式。\nAction: sql_query';
    const blocks = stepsToTimelineBlocks(
      [{ id: 'old-p1', action: '__progress__', progressContent: raw, status: 'done' }, step('q1')],
      {},
      {},
    );
    render(<AgentTimeline blocks={blocks} />);
    expect(screen.getByText('核对日期格式。')).toBeTruthy();
    expect(screen.queryByText(/Thought:|private reasoning|Action:/)).toBeNull();
    expect(buildActionDisplayText({ actionIntention: raw })).toBe('核对日期格式。');
  });

  it('drops protocol-only saved blocks while keeping the explicit tool intention', () => {
    const blocks = stepsToTimelineBlocks(
      [
        {
          id: 'old-p1',
          action: '__progress__',
          progressContent: 'Thought: private\nAction: sql_query',
          status: 'done',
        },
        { ...step('q1'), actionIntention: '查询销售。' },
      ],
      {},
      {},
    );
    expect(blocks.map(block => block.kind)).toEqual(['text', 'tool']);
    expect(blocks[0].content).toBe('查询销售。');
  });

  it('updates a streamed narration in place and removes the cursor on completion', () => {
    const live = { id: 'p1', action: '__progress__', progressContent: '先分析', status: 'running' };
    const { rerender } = render(<AgentTimeline blocks={stepsToTimelineBlocks([live], {}, {})} />);
    expect(screen.getByText('先分析')).toBeTruthy();
    expect(document.querySelector('.animate-pulse')).toBeTruthy();
    rerender(
      <AgentTimeline
        blocks={stepsToTimelineBlocks(
          [{ ...live, progressContent: '先分析数据，再比较趋势。', status: 'done' }],
          {},
          {},
        )}
      />,
    );
    expect(screen.getByText('先分析数据，再比较趋势。')).toBeTruthy();
    expect(document.querySelector('.animate-pulse')).toBeNull();
    expect(screen.queryByText('先分析', { exact: true })).toBeNull();
  });
  const progress = (id: string, content: string) => ({
    id,
    action: '__progress__',
    progressContent: content,
    status: 'done',
  });
  const tools = ['read', 'search', 'sql_query'].map((action, index) => ({
    id: `tool-${index}`,
    action,
    title: action,
    status: 'running',
  }));

  it('keeps narration between tool phases in persisted step order', () => {
    const blocks = stepsToTimelineBlocks(
      [
        progress('p1', '先确认口径，再查询数据。'),
        { ...step('q1'), actionIntention: '不应重复显示' },
        progress('p2', '口径已确认，接下来比较趋势。'),
        step('q2'),
      ],
      {},
      {},
    );
    expect(blocks.map(block => block.kind)).toEqual(['text', 'tool', 'text', 'tool']);
    expect(blocks.filter(block => block.kind === 'text').map(block => block.content)).toEqual([
      '先确认口径，再查询数据。',
      '口径已确认，接下来比较趋势。',
    ]);
  });

  it('auto-collapses a completed phase and preserves manual expansion on updates', () => {
    const { rerender } = render(<AgentTimeline blocks={stepsToTimelineBlocks(tools, {}, {})} />);
    expect(screen.getByRole('button', { name: /timeline_phase_running/ }).getAttribute('aria-expanded')).toBe('true');
    const done = stepsToTimelineBlocks(
      tools.map(tool => ({ ...tool, status: 'done' })),
      {},
      {},
    );
    rerender(<AgentTimeline blocks={done} />);
    const toggle = screen.getByRole('button', { name: /timeline_phase_done/ });
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(toggle);
    rerender(<AgentTimeline blocks={[...done]} />);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
  });

  it('keeps a manually opened phase open when its tools finish', () => {
    const { rerender } = render(<AgentTimeline blocks={stepsToTimelineBlocks(tools, {}, {})} />);
    const toggle = screen.getByRole('button', { name: /timeline_phase_running/ });
    fireEvent.click(toggle);
    fireEvent.click(toggle);
    rerender(
      <AgentTimeline
        blocks={stepsToTimelineBlocks(
          tools.map(tool => ({ ...tool, status: 'done' })),
          {},
          {},
        )}
      />,
    );
    expect(screen.getByRole('button', { name: /timeline_phase_done/ }).getAttribute('aria-expanded')).toBe('true');
  });

  it('restores legacy public intentions without exposing raw reasoning', () => {
    expect(buildActionDisplayText({ thought: 'private reasoning' })).toBeUndefined();
    const blocks = stepsToTimelineBlocks([{ ...step('legacy'), actionIntention: '查询月度销售额。' }], {}, {});
    expect(blocks[0].kind).toBe('text');
    expect(blocks[0].content).toBe('查询月度销售额。');
  });
});

describe('terminal tool presentation', () => {
  it.each(['code chunk', 'result envelope', 'streamed envelope'])(
    'recovers omitted command arguments from %s',
    source => {
      const command = 'head -n 3 Walmart_Sales.csv';
      const chunks = [
        { output_type: 'code', content: command },
        { output_type: 'text', content: 'Store,Date,Weekly_Sales' },
      ];
      const envelope = JSON.stringify({ chunks });
      const outputs =
        source === 'code chunk'
          ? chunks
          : source === 'streamed envelope'
            ? [envelope.slice(0, 65), envelope.slice(65)].map(content => ({ output_type: 'text', content }))
            : [{ output_type: 'text', content: envelope }];
      const blocks = stepsToTimelineBlocks(
        [{ id: 'old-bash', action: 'bash', status: 'done' }],
        {},
        { 'old-bash': outputs },
      );
      expect(blocks[0].input).toBe(command);
      render(<AgentTimeline blocks={blocks} />);
      const row = screen.getByRole('button', { name: /timeline_command_done.*head -n 3/ });
      expect(row.textContent).toContain(command);
      fireEvent.click(row);
      expect(document.querySelector('pre')?.textContent).toBe(command);
      expect(screen.getByRole('button', { name: 'timeline_command_copy' })).toBeTruthy();
    },
  );

  it('recognizes both engines and extracts commands without argument labels', () => {
    for (const name of ['bash', 'shell_interpreter', 'functions.exec_command']) {
      expect(isTerminalTool(name)).toBe(true);
    }
    expect(isTerminalTool('code_interpreter')).toBe(false);
    const command = "python3 - <<'EOF'\nprint('sales')\nEOF";
    expect(terminalCommand(JSON.stringify({ code: command, timeout: 30 }))).toBe(command);
    expect(terminalCommand(JSON.stringify({ command }))).toBe(command);
    expect(terminalCommand(command)).toBe(command);
  });

  it('shows a terminal icon, localized status, and bounded command/output transcript', () => {
    const command = Array.from({ length: 20 }, (_, index) => `echo ${index}`).join('\n');
    const blocks = stepsToTimelineBlocks(
      [{ id: 'bash-1', action: 'bash', actionInput: { code: command }, status: 'done' }],
      {},
      { 'bash-1': [{ output_type: 'text', content: '20 lines executed' }] },
    );
    render(<AgentTimeline blocks={blocks} />);
    expect(screen.getByRole('img', { name: 'terminal' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /timeline_command_done.*bash/ }));
    expect(screen.queryByText('Input')).toBeNull();
    expect(screen.queryByText('Output')).toBeNull();
    expect(document.querySelector('pre')?.textContent).toBe(command);
    expect(document.querySelector('pre')?.parentElement?.parentElement?.className).toContain('max-h-64');
    expect(screen.getByText('20 lines executed')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'timeline_command_more' }));
    expect(screen.getByRole('button', { name: 'timeline_command_less' }).getAttribute('aria-expanded')).toBe('true');
  });

  it('copies just the command and opens the complete transcript in a dialog', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { clipboard: { writeText } });
    try {
      render(
        <AgentTimeline
          blocks={stepsToTimelineBlocks(
            [{ id: 'shell-1', action: 'shell_interpreter', actionInput: { command: 'pwd' }, status: 'failed' }],
            {},
            { 'shell-1': [{ output_type: 'text', content: 'permission denied' }] },
          )}
        />,
      );
      fireEvent.click(screen.getByRole('button', { name: 'timeline_command_copy' }));
      await waitFor(() => expect(writeText).toHaveBeenCalledWith('pwd'));
      fireEvent.click(screen.getByRole('button', { name: 'timeline_command_expand' }));
      expect(screen.getByRole('dialog')).toBeTruthy();
      expect(screen.getByText('permission denied')).toBeTruthy();
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
