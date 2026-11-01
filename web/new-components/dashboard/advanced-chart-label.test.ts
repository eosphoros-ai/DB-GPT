import {
  buildDualAxesChildren,
  makePieLabelFormatter,
  resolveAreaGradient,
} from '@/new-components/charts/AdvancedCharts';
import { describe, expect, it } from 'vitest';

describe('advanced chart pie labels', () => {
  it('formats category percentages without expression-template syntax', () => {
    const format = makePieLabelFormatter(
      [
        { kind: 'Holiday', sales: 20 },
        { kind: 'Regular', sales: 80 },
      ],
      'kind',
      'sales',
    );

    expect(format({ kind: 'Holiday', sales: 20 })).toBe('Holiday: 20.0%');
    expect(format({ kind: 'Regular', sales: 80 })).toBe('Regular: 80.0%');
  });

  it('uses the user-selected primary color in area gradients', () => {
    expect(resolveAreaGradient(['#087E8B', '#F4A261'])).toContain('#087E8B');
    expect(resolveAreaGradient()).toContain('#3B82F6');
  });

  it('builds current Plot 2.x dual-axis child layers with themed non-color cues', () => {
    const children = buildDualAxesChildren({
      chartType: 'dual-axes',
      data: [{ month: '2026-01', revenue: 12, orders: 4 }],
      xField: 'month',
      yFields: ['revenue', 'orders'],
      colors: ['#1D5FD1', '#A45410'],
      visualTheme: {
        mode: 'light',
        text: '#172033',
        muted: '#5F6C7B',
        grid: '#DDE5EF',
        card: '#FFFFFF',
        border: '#D7E0EB',
        primary: '#1D5FD1',
        seriesDashes: [[], [6, 3]],
      },
    });

    expect(children).toHaveLength(2);
    expect(children.map(child => child.type)).toEqual(['interval', 'line']);
    expect(children.map(child => child.yField)).toEqual(['revenue', 'orders']);
    expect(children[0].style.fill).toBe('#1D5FD1');
    expect(children[1].style.stroke).toBe('#A45410');
    expect(children[1].style.lineDash).toEqual([6, 3]);
  });
});
