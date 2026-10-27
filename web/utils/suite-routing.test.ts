import { describe, expect, it } from 'vitest';

import { SuiteItem } from '@/types/suite';
import { resolveSuiteQuestionDatabase, scoreSuites, suiteDisplayName } from './suite-routing';

const makeSuite = (name: string, keywords: string[], specificity = 0.8, display = name): SuiteItem =>
  ({
    id: 1,
    name,
    display,
    version: '1.0.0',
    source: 'official',
    status: 'enabled',
    manifest_snapshot: {
      display,
      display_en: name,
      routing: { keywords, specificity },
      recommended_questions: [{ text: 'q', hint: 'h' }],
    },
  }) as SuiteItem;

// Specificity mirrors the real manifests (db-query 0.8 / db-analysis 0.85 /
// db-ops 0.9): on keyword overlap the higher-specificity suite wins, which is
// how "生产库健康巡检出报告" (hits 巡检 + 报告) resolves to db-ops.
const query = makeSuite('db-query', ['查', '统计', '导出', 'gmv', '客单价', 'top', '环比', '明细'], 0.8, '智能取数');
const analysis = makeSuite('db-analysis', ['分析', '归因', '报告', '趋势', '对比', '复盘'], 0.85, '智能分析');
const ops = makeSuite('db-ops', ['慢查询', '巡检', '排障', '根因', 'profile', '治理'], 0.9, '智能运维');
const suites = [query, analysis, ops];

describe('resolveSuiteQuestionDatabase', () => {
  const olist = { db_name: 'Olist_Ecommerce', db_type: 'sqlite' };
  const walmart = { db_name: 'Walmart_Sales', db_type: 'sqlite' };

  it('binds a named example to its database even when another database is selected', () => {
    expect(
      resolveSuiteQuestionDatabase({ text: '生成 Walmart 销售分析报告', database_name: 'Walmart_Sales' }, olist, [
        olist,
        walmart,
      ]),
    ).toBe(walmart);
  });

  it('does not send a named example against a different database when its source is missing', () => {
    expect(
      resolveSuiteQuestionDatabase({ text: '生成 Walmart 销售分析报告', database_name: 'Walmart_Sales' }, olist, [
        olist,
      ]),
    ).toBeNull();
  });

  it('uses the session database for generic questions and requires selection when absent', () => {
    expect(resolveSuiteQuestionDatabase({ text: '统计客户 GMV' }, olist, [olist])).toBe(olist);
    expect(resolveSuiteQuestionDatabase({ text: '统计客户 GMV' }, null, [olist])).toBeNull();
  });
});

describe('scoreSuites', () => {
  it('returns null for empty query or no suites', () => {
    expect(scoreSuites('', suites)).toBeNull();
    expect(scoreSuites('查一下', [])).toBeNull();
  });

  it('routes a data-query question to db-query', () => {
    expect(scoreSuites('上个月华东区的有效GMV是多少', suites)?.slug).toBe('db-query');
    expect(scoreSuites('统计 Top10 客户 GMV 及环比', suites)?.slug).toBe('db-query');
  });

  it('routes an ops question to db-ops', () => {
    expect(scoreSuites('订单库昨晚慢查询根因', suites)?.slug).toBe('db-ops');
    expect(scoreSuites('生产库健康巡检出报告', suites)?.slug).toBe('db-ops');
  });

  it('routes an analysis question to db-analysis', () => {
    expect(scoreSuites('分析本月销售下滑归因', suites)?.slug).toBe('db-analysis');
  });

  it('prefers the higher-specificity suite on keyword overlap', () => {
    const hot = makeSuite('hot', ['分析'], 0.95);
    expect(scoreSuites('分析', [...suites, hot])?.slug).toBe('hot');
  });

  it('returns null when no keyword matches', () => {
    expect(scoreSuites('今天天气怎么样', suites)).toBeNull();
  });
});

describe('suiteDisplayName', () => {
  it('prefers display_en under EN locale', () => {
    expect(suiteDisplayName(query, 'en-US')).toBe('db-query');
    expect(suiteDisplayName(query, 'zh-CN')).toBe('智能取数');
  });

  it('falls back to slug when no display', () => {
    expect(suiteDisplayName({ name: 'x' } as SuiteItem, 'zh')).toBe('x');
  });
});
