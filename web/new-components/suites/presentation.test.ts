import type { SuiteItem } from '@/types/suite';
import { describe, expect, it } from 'vitest';
import { artifactPresentation, getBuiltinPresentation, getSuiteCategory, matchesSuiteSource } from './presentation';

function suite(overrides: Partial<SuiteItem> = {}): SuiteItem {
  return { id: 1, name: 'db-query', version: '1.1.0', source: 'official', status: 'enabled', ...overrides };
}

describe('Plugin directory filters', () => {
  it('renders real structured artifact declarations and preserves unknown IDs', () => {
    expect(artifactPresentation({ type: 'html', name: '架构报告', name_en: 'Architecture report' }, 'en')).toEqual({
      label: 'Architecture report',
    });
    expect(artifactPresentation({ type: 'html', name: '架构报告' }, 'zh-CN')).toEqual({ label: '架构报告' });
    expect(artifactPresentation('sql_card', 'en').translationKey).toBe('plugins_artifact_sql');
    expect(artifactPresentation('custom_output', 'en').label).toBe('custom_output');
  });
  it('keeps installed and disabled plugins discoverable without including uninstalled rows', () => {
    for (const status of ['installed', 'enabled', 'disabled']) {
      expect(matchesSuiteSource(suite({ status }), 'installed')).toBe(true);
    }
    expect(matchesSuiteSource(suite({ status: 'uninstalled' }), 'installed')).toBe(false);
  });

  it('uses registered marketplace sources instead of manufacturing an empty market', () => {
    expect(matchesSuiteSource(suite({ source: 'market' }), 'market')).toBe(true);
    expect(matchesSuiteSource(suite(), 'market')).toBe(false);
  });

  it('distinguishes metadata and SQL experts despite their shared expert scenario', () => {
    expect(getSuiteCategory(suite({ name: 'metadata-architecture-expert', scenario_id: 'expert' }))).toBe('metadata');
    expect(getSuiteCategory(suite({ name: 'sql-optimization-expert', scenario_id: 'expert' }))).toBe('ops');
    expect(getSuiteCategory(suite({ name: 'team-expert', source: 'enterprise', scenario_id: 'expert' }))).toBe('other');
  });

  it('preserves third-party identity and uses its declared scenario for filters', () => {
    const imported = suite({ source: 'enterprise', display: 'Team Query', scenario_id: 'query' });
    expect(getBuiltinPresentation(imported)).toBeUndefined();
    expect(getSuiteCategory(imported)).toBe('query');
    expect(imported.name).toBe('db-query');
  });
});
