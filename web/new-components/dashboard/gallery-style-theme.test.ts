import { ADAPTED_SKILLS } from '@/new-components/skills/skill-catalog';
import { describe, expect, it } from 'vitest';
import { resolveDashboardTheme } from './dashboard-appearance';
import { galleryStyleTheme } from './dashboard-catalog-presentation';

describe('saved gallery style', () => {
  for (const name of ['learnhub-viz-design', 'brutal-viz-design', 'pawspa-viz-design', 'serenityspa-viz-design']) {
    it(`keeps ${name} colors when rendering a saved dashboard`, () => {
      const schema: Parameters<typeof galleryStyleTheme>[1] = {
        dashboard: { theme: { preset: 'warm', mode: 'light' } },
        metadata: { compatibility: { gallery_style: name } },
      };
      const theme = galleryStyleTheme(resolveDashboardTheme(schema.dashboard.theme), schema);
      expect(theme.canvas).toBe(ADAPTED_SKILLS[name].background);
      expect(theme.primary).toBe(ADAPTED_SKILLS[name].accent);
      expect(theme.text).toBe(ADAPTED_SKILLS[name].ink);
      expect(theme.radius).toBe(name === 'brutal-viz-design' ? 0 : 14);
    });
  }
  it('preserves explicit user changes to color and corner radius', () => {
    const schema: Parameters<typeof galleryStyleTheme>[1] = {
      dashboard: { theme: { preset: 'warm', mode: 'light', overrides: { primary_color: '#123456', card_radius: 8 } } },
      metadata: { compatibility: { gallery_style: 'pawspa-viz-design' } },
    };
    const theme = galleryStyleTheme(resolveDashboardTheme(schema.dashboard.theme), schema);
    expect(theme.primary).toBe('#123456');
    expect(theme.radius).toBe(8);
  });
});
