import { describe, expect, it } from 'vitest';

import { SuiteItem } from '@/types/suite';
import { localizeSuite, resolveSuiteQuestionDatabase, scoreSuites, suiteDisplayName } from './suite-routing';

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

describe('localizeSuite', () => {
  const bilingual: SuiteItem = {
    ...query,
    readme: '原文',
    readme_locales: { en: 'English overview' },
    manifest_snapshot: {
      display_en: 'Data Query',
      description: '中文简介',
      description_en: 'English description',
      skill_details: [
        { name: 'doctor', display: 'SQL 体检', display_en: 'SQL Doctor', description_en: 'Diagnose SQL' },
      ],
      commands: [
        {
          name: '/SQL 体检',
          display_en: '/SQL Doctor',
          aliases: ['/SQL Doctor'],
          skill: 'doctor',
          description: '检查 SQL',
          description_en: 'Review SQL',
          prefill: '输入 SQL',
          prefill_en: 'Enter SQL',
        },
      ],
      recommended_questions: [
        {
          text: '生成销售报告',
          text_en: 'Generate a sales report',
          hint: '只读',
          hint_en: 'Read only',
          database_name: 'Walmart_Sales',
          command: '/SQL 体检',
        },
      ],
    },
  };

  it('translates the full presentation while preserving execution and database bindings', () => {
    const en = localizeSuite(bilingual, 'en-US');
    expect(en.display).toBe('Data Query');
    expect(en.readme).toBe('English overview');
    expect(en.manifest_snapshot?.description).toBe('English description');
    expect(en.skill_details?.[0].display).toBe('SQL Doctor');
    expect(en.manifest_snapshot?.commands?.[0]).toMatchObject({
      name: '/SQL 体检',
      display: '/SQL Doctor',
      skill: 'doctor',
      description: 'Review SQL',
      prefill: 'Enter SQL',
    });
    expect(en.manifest_snapshot?.recommended_questions?.[0]).toMatchObject({
      text: 'Generate a sales report',
      hint: 'Read only',
      database_name: 'Walmart_Sales',
      command: '/SQL 体检',
    });
  });

  it('can switch back to Chinese without mutating the source package', () => {
    localizeSuite(bilingual, 'en');
    const zh = localizeSuite(bilingual, 'zh-CN');
    expect(zh.display).toBe('智能取数');
    expect(zh.readme).toBe('原文');
    expect(zh.manifest_snapshot?.commands?.[0].display).toBe('/SQL 体检');
    expect(bilingual.manifest_snapshot?.description).toBe('中文简介');
    expect(bilingual.manifest_snapshot?.commands?.[0].display).toBeUndefined();
  });

  it('falls back to original content for packages without translations', () => {
    const en = localizeSuite(query, 'en');
    expect(en.manifest_snapshot?.recommended_questions?.[0].text).toBe('q');
    expect(en.readme).toBeUndefined();
  });
});
