import type { SuiteItem } from '@/types/suite';
import { describe, expect, it } from 'vitest';
import { getSuiteCommandGroups, getSuiteCommandQuery } from './suite-commands';

const financial: SuiteItem = {
  id: 1,
  name: 'financial-report',
  display: '财报分析',
  status: 'enabled',
  version: '1.0.0',
  source: 'official',
  manifest_snapshot: {
    display_en: 'Financial Reports',
    commands: [
      {
        name: '/读年报',
        display_en: '/annual-report',
        aliases: ['/annual'],
        description: '上传年报 PDF，查看营收、利润和现金流',
        description_en: 'Upload an annual report PDF to analyze revenue and cash flow',
      },
      { name: '/对比财报', description: '比较多家公司或多个报告期' },
    ],
  },
};

describe('getSuiteCommandQuery', () => {
  it.each([
    ['/', ''],
    [' /读', '读'],
    ['/annual', 'annual'],
    ['请分析 /读年报', null],
    ['https://example.com', null],
    ['/tmp/report.pdf', null],
    ['C:\\reports\\annual.pdf', null],
    ['/读年报 分析现金流', null],
    ['', null],
  ])('recognizes a leading command token in %j', (value, expected) => {
    expect(getSuiteCommandQuery(value)).toBe(expected);
  });

  it('uses the caret when editing a command before existing arguments', () => {
    expect(getSuiteCommandQuery('/读年报 分析现金流', 2)).toBe('读');
    expect(getSuiteCommandQuery('/读年报', 0)).toBeNull();
    expect(getSuiteCommandQuery('/读年报', 10)).toBeNull();
    expect(getSuiteCommandQuery('/tmp/report.pdf', 3)).toBeNull();
    expect(getSuiteCommandQuery('/读年报 /tmp/report.pdf', 2)).toBe('读');
  });
});

describe('getSuiteCommandGroups', () => {
  it('includes only enabled suites with commands and preserves their order', () => {
    const groups = getSuiteCommandGroups([
      { ...financial, name: 'disabled', status: 'disabled' },
      { ...financial, name: 'installed', status: 'installed' },
      { ...financial, name: 'empty', manifest_snapshot: {} },
      financial,
    ]);
    expect(groups.map(group => group.suite.name)).toEqual(['financial-report']);
    expect(groups[0].options.map(option => option.command.name)).toEqual(['/读年报', '/对比财报']);
  });

  it('filters by aliases, purpose, and suite name across languages', () => {
    expect(getSuiteCommandGroups([financial], '/ANNUAL')[0].options[0].command.name).toBe('/读年报');
    expect(getSuiteCommandGroups([financial], '财报 现金流')[0].options[0].command.name).toBe('/读年报');
    expect(getSuiteCommandGroups([financial], 'Financial Reports')[0].options).toHaveLength(2);
    expect(getSuiteCommandGroups([financial], '不存在')).toEqual([]);
  });

  it('finds an alias from a later matching snapshot without duplicating its command', () => {
    const updated = {
      ...financial,
      manifest_snapshot: {
        ...financial.manifest_snapshot,
        commands: [{ ...financial.manifest_snapshot!.commands![0], aliases: ['/new-alias'] }],
      },
    };
    const groups = getSuiteCommandGroups([financial, updated, updated], 'new-alias');
    expect(groups.flatMap(group => group.options).map(option => option.command.name)).toEqual(['/读年报']);
  });

  it('localizes labels while preserving the original execution identity', () => {
    const option = getSuiteCommandGroups([financial], '', 'en-US')[0].options[0];
    expect(option.suiteLabel).toBe('Financial Reports');
    expect(option.label).toBe('/annual-report');
    expect(option.description).toContain('Upload an annual report');
    expect(option.suite).toBe(financial);
    expect(option.command).toBe(financial.manifest_snapshot?.commands?.[0]);
    expect(option.command.name).toBe('/读年报');
  });

  it('keeps identical commands in different suites distinct and deduplicates repeated entries', () => {
    const otherSuite = { ...financial, name: 'another-suite', id: 2 };
    const groups = getSuiteCommandGroups([financial, otherSuite, financial], '读年报');
    expect(groups).toHaveLength(2);
    expect(groups[0].options[0].key).not.toBe(groups[1].options[0].key);
    const keys = groups.flatMap(group => group.options.map(option => option.key));
    expect(new Set(keys).size).toBe(keys.length);
  });
});
