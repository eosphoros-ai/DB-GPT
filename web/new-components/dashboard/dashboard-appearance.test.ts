import { describe, expect, it } from 'vitest';
import {
  DASHBOARD_PALETTES,
  DASHBOARD_THEME_PRESETS,
  type DashboardThemeId,
  auditDashboardTheme,
  dashboardContrastRatio,
  detectDashboardPalette,
  replacePaletteColor,
  resolveDashboardTheme,
} from './dashboard-appearance';

describe('dashboard appearance', () => {
  it('uses clarity for missing and historical theme ids', () => {
    expect(resolveDashboardTheme(undefined).id).toBe('clarity');
    expect(resolveDashboardTheme({ preset: 'clean' }).id).toBe('clarity');
    expect(resolveDashboardTheme({ preset: 'business_blue' }).id).toBe('clarity');
    expect(resolveDashboardTheme({ preset: 'graphite' }).mode).toBe('dark');
    expect(resolveDashboardTheme({ preset: 'graphite' }).card).toBe('#1B1E24');
  });

  it('keeps every initial preset and mode above the contrast and color-vision thresholds', () => {
    for (const preset of Object.keys(DASHBOARD_THEME_PRESETS)) {
      for (const mode of ['light', 'dark'] as const) {
        expect(auditDashboardTheme({ preset: preset as DashboardThemeId, mode }), `${preset}/${mode}`).toEqual([]);
      }
    }
  });

  it('layers custom values over the selected preset without mutating its defaults', () => {
    const base = resolveDashboardTheme({ preset: 'clarity', mode: 'light' });
    const customized = resolveDashboardTheme({
      preset: 'clarity',
      mode: 'light',
      overrides: {
        primary_color: '#7B4BA8',
        font_scale: 'large',
        density: 'spacious',
        card_radius: 24,
        card_shadow: 'none',
        kpi_style: 'solid',
        table_style: 'striped',
      },
    });
    expect(customized.primary).toBe('#7B4BA8');
    expect(customized.kpiSize).toBeGreaterThan(base.kpiSize);
    expect(customized.gap).toBeGreaterThan(base.gap);
    expect(customized.radius).toBe(24);
    expect(customized.shadow).toBe('none');
    expect(customized.kpiStyle).toBe('solid');
    expect(customized.tableStyle).toBe('striped');
    expect(resolveDashboardTheme({ preset: 'clarity', mode: 'light' }).primary).toBe(base.primary);
  });

  it('detects invalid custom contrast and duplicate palette colors', () => {
    const issues = auditDashboardTheme({
      preset: 'clarity',
      mode: 'light',
      overrides: { chart_palette: ['#FDFDFD', '#1D5FD1', '#1D5FD1'] },
    });
    expect(issues.map(issue => issue.code)).toEqual(expect.arrayContaining(['palette_contrast', 'palette_duplicate']));
    expect(dashboardContrastRatio('#172033', '#FFFFFF')).toBeGreaterThanOrEqual(4.5);
  });

  it('detects presets and preserves custom color edits', () => {
    expect(detectDashboardPalette([...DASHBOARD_PALETTES.tealOrange.colors])).toBe('tealOrange');
    expect(detectDashboardPalette(['#123456'])).toBe('custom');
    expect(replacePaletteColor([], 0, '#abcdef')[0]).toBe('#ABCDEF');
  });
});
