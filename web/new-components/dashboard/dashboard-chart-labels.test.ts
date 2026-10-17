import {
  dashboardBarLabel,
  hideUnfittingDashboardLabels,
  settledDashboardBounds,
} from '@/new-components/charts/dashboard-chart-labels';
import { describe, expect, it, vi } from 'vitest';
import { dashboardContrastRatio, resolveDashboardTheme } from './dashboard-appearance';

const node = (x: number, y: number, width: number, height = 12) => ({
  style: { visibility: 'visible' },
  getBounds: () => ({ min: [x, y], max: [x + width, y + height] }),
});

describe('outside bar labels', () => {
  it('checks a resizing bar at its final bounds without moving the live element', () => {
    const destroy = vi.fn();
    const clone = { ...node(10, 30, 30, 50), attr: vi.fn(), destroy };
    const bar = {
      ...node(10, 5, 30, 75),
      getAnimations: () => [{ effect: { getKeyframes: () => [{ y: 5 }, { y: 30 }] } }],
      cloneNode: () => clone,
      parentNode: { appendChild: vi.fn() },
    };
    const label = { ...node(10, 10, 30), __data__: { dependentElement: bar } };
    hideUnfittingDashboardLabels([label], 100, 100);
    expect(label.style.visibility).toBe('visible');
    expect(clone.attr).toHaveBeenCalledWith({ y: 30 });
    expect(bar.getBounds().min[1]).toBe(5);
    expect(destroy).toHaveBeenCalledOnce();
  });
  it('still hides labels that overlap the final bar after the animation completes', () => {
    const clone = { ...node(10, 5, 30, 75), attr: vi.fn(), destroy: vi.fn() };
    const bar = {
      ...node(10, 30, 30, 50),
      getAnimations: () => [{ effect: { getKeyframes: () => [{ y: 30 }, { y: 5 }] } }],
      cloneNode: () => clone,
      parentNode: { appendChild: vi.fn() },
    };
    const label = { ...node(10, 10, 30), __data__: { dependentElement: bar } };
    hideUnfittingDashboardLabels([label], 100, 100);
    expect(label.style.visibility).toBe('hidden');
    expect(settledDashboardBounds(node(1, 2, 3)).min).toEqual([1, 2]);
  });
  it('keeps positive labels above the bar and negative labels below', () => {
    const config = dashboardBarLabel({ chartType: 'column', yField: 'sales' });
    expect(config.position({ sales: 10 })).toBe('top');
    expect(config.textBaseline({ sales: 10 })).toBe('bottom');
    expect(config.dy({ sales: 10 })).toBeLessThan(0);
    expect(config.position({ sales: -10 })).toBe('bottom');
    expect(config.textBaseline({ sales: -10 })).toBe('top');
  });
  it('keeps horizontal labels beyond the value endpoint', () => {
    const config = dashboardBarLabel({ chartType: 'bar', yField: 'sales' });
    expect(config.position({ sales: 10 })).toBe('right');
    expect(config.textAlign({ sales: 10 })).toBe('start');
    expect(config.dx({ sales: 10 })).toBeGreaterThan(0);
  });
  it('hides whole overflowing labels and thins overlapping adjacent labels', () => {
    const labels = [node(5, 5, 30), node(15, 5, 30), node(55, 5, 30), node(90, 5, 30)];
    hideUnfittingDashboardLabels(labels, 100, 100);
    expect(labels.map(label => label.style.visibility)).toEqual(['visible', 'hidden', 'visible', 'hidden']);
    expect(labels[3].getBounds().max[0]).toBe(120); // Not shortened to fit.
  });
  it('never overlaps a bar, axis label or legend text', () => {
    const label = { ...node(10, 10, 30), __data__: { dependentElement: node(10, 10, 30, 50) } };
    hideUnfittingDashboardLabels([label], 100, 100);
    expect(label.style.visibility).toBe('hidden');
    const axisOverlap = node(10, 75, 30);
    hideUnfittingDashboardLabels([axisOverlap], 100, 100, [node(0, 80, 100).getBounds()]);
    expect(axisOverlap.style.visibility).toBe('hidden');
  });
  for (const preset of ['clarity', 'graphite', 'ocean', 'warm'] as const) {
    for (const mode of ['light', 'dark'] as const) {
      it(`uses the foreground token with >=4.5 contrast for ${preset}/${mode}`, () => {
        const theme = resolveDashboardTheme({ preset, mode, overrides: {} });
        const label = dashboardBarLabel({ chartType: 'column', visualTheme: theme });
        expect(label.fill).toBe(theme.text);
        expect(dashboardContrastRatio(label.fill, theme.card)).toBeGreaterThanOrEqual(4.5);
      });
    }
  }
});
