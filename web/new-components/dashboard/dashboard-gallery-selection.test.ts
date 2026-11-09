import { ADAPTED_SKILLS } from '@/new-components/skills/skill-catalog';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { AVAILABLE_CATALOG, GALLERY_DESIGN_SKILL_IDS, TEMPLATE_GALLERY_ORDER } from './dashboard-catalog';
import definitions from './dashboard-template-definitions.json';
import { dashboardTemplateEntry } from './dashboard-template-entry';

const selected = [
  'design:brutal-viz-design',
  'design:serenityspa-viz-design',
  'catalog:voice-observatory',
  'catalog:store-marketing',
  'catalog:national-command',
  'catalog:brand-revenue',
  'catalog:northwind-revenue',
  'catalog:retail-overview',
];

describe('the eight selected gallery templates', () => {
  it('offers exactly the selected data templates and styles', () => {
    expect(TEMPLATE_GALLERY_ORDER.map(id => (id.startsWith('design:') ? id : `catalog:${id}`))).toEqual(selected);
    expect(
      [
        ...Array.from(GALLERY_DESIGN_SKILL_IDS, name => `design:${name}`),
        ...AVAILABLE_CATALOG.map(template => `catalog:${template.id}`),
      ].sort(),
    ).toEqual([...selected].sort());
  });

  it('does not restore removed templates through old creation links', () => {
    for (const { id } of definitions) {
      const entry = dashboardTemplateEntry({ creation_mode: 'dashboard', template: id });
      expect(entry?.selection ?? null).toBe(selected.includes(`catalog:${id}`) ? `catalog:${id}` : null);
    }
    for (const name of Object.keys(ADAPTED_SKILLS)) {
      const entry = dashboardTemplateEntry({ creation_mode: 'dashboard', skill: name });
      expect(entry?.selection ?? null).toBe(selected.includes(`design:${name}`) ? `design:${name}` : null);
    }
  });

  it('keeps the agent style index aligned with the visible gallery', () => {
    const referencesDir = path.resolve('../skills/dashboard-builder/internal/dashboard-design/references');
    const index = readFileSync(path.join(referencesDir, 'index.md'), 'utf8');
    const references = [...index.matchAll(/^- `([^`]+)` — \[[^\]]+\]\(([^)]+)\)/gm)];
    expect(references.map(match => match[1])).toEqual(selected);
    for (const match of references) expect(existsSync(path.join(referencesDir, match[2]))).toBe(true);
  });
});
