import { describe, expect, it } from 'vitest';

import { buildQueryCsv } from './query-export';

describe('buildQueryCsv', () => {
  it('emits header + escaped rows with CRLF', () => {
    const csv = buildQueryCsv({
      columns: ['品类', '金额'],
      rows: [
        ['美妆,护肤', 'say "hi"'],
        [386.2, null],
      ],
    });
    // buildQueryCsv is BOM-free; downloadQueryCsv prepends the BOM.
    const lines = csv.split('\r\n');
    expect(lines[0]).toBe('品类,金额');
    expect(lines[1]).toBe('"美妆,护肤","say ""hi"""');
    expect(lines[2]).toBe('386.2,');
  });

  it('handles empty result sets', () => {
    const csv = buildQueryCsv({ columns: ['a'], rows: [] });
    expect(csv).toBe('a');
  });
});
