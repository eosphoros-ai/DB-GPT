import { getDashboardAxisConfig } from '@/new-components/charts/AdvancedCharts';
import { act, render, screen } from '@testing-library/react';
import { useRef } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { useWidgetContentSize } from './use-widget-content-size';

describe('dashboard chart content-box sizing', () => {
  it('keeps horizontal category names level and reserves readable label width', () => {
    const config = getDashboardAxisConfig({
      chartType: 'bar',
      dashboardSurface: true,
      width: 360,
      data: Array.from({ length: 10 }, (_, i) => ({ category: `长分类名称 ${i}`, value: i })),
      xField: 'category',
      yField: 'value',
    });
    expect(config.axis.x.labelTransform).toBeUndefined();
    expect(config.axis.x.labelWordWrap).toBe(true);
    expect(config.axis.x.labelWordWrapWidth).toBeGreaterThan(80);
  });
  it('tracks the actual body after headings, evidence and footer change size', () => {
    let callback: ResizeObserverCallback;
    const disconnect = vi.fn();
    vi.stubGlobal(
      'ResizeObserver',
      class {
        constructor(cb: ResizeObserverCallback) {
          callback = cb;
        }
        observe() {}
        disconnect = disconnect;
      },
    );
    function Body() {
      const ref = useRef<HTMLDivElement>(null);
      const size = useWidgetContentSize(ref);
      return (
        <div ref={ref} data-testid='body'>
          {size.width} × {size.height}
        </div>
      );
    }
    const { unmount } = render(<Body />);
    const target = screen.getByTestId('body');
    for (const height of [268, 211, 136, 302]) {
      act(() =>
        callback(
          [
            {
              target,
              contentRect: new DOMRect(0, 0, 510, height),
              borderBoxSize: [],
              contentBoxSize: [],
              devicePixelContentBoxSize: [],
            },
          ],
          {} as ResizeObserver,
        ),
      );
      expect(target.textContent).toBe(`510 × ${height}`);
    }
    unmount();
    expect(disconnect).toHaveBeenCalledOnce();
    vi.unstubAllGlobals();
  });

  it.each([3, 33, 45])('keeps every category tick at %i categories', count => {
    const config = getDashboardAxisConfig({
      chartType: 'column',
      dashboardSurface: true,
      width: 500,
      data: Array.from({ length: count }, (_, index) => ({ year: `year-${index}`, value: index })),
      xField: 'year',
      yField: 'value',
    });
    expect(config.axis.x.label).toBe(true);
    expect(config.axis.x.labelAutoHide).toBe(false);
    expect(config.axis.x.labelAutoEllipsis).toBe(false);
    expect(config.axis.x.tickFilter()).toBe(true);
    expect(config.axis.x.labelFormatter(2024)).toBe('2024');
    expect(config.axis.y.tick).toBe(true);
    expect(config.axis.y.label).toBe(true);
  });

  it('spaces long time-series labels while retaining both endpoints and every data point', () => {
    const dates = Array.from({ length: 143 }, (_, i) =>
      new Date(Date.UTC(2023, 0, 1 + i * 7)).toISOString().slice(0, 10),
    );
    const data = dates.flatMap(date => [
      { date, series: 'A', value: 1 },
      { date, series: 'B', value: 2 },
    ]);
    const axesAt = (width: number) =>
      getDashboardAxisConfig({
        chartType: 'line',
        dashboardSurface: true,
        width,
        data,
        xField: 'date',
        yField: 'value',
        seriesField: 'series',
      }).axis.x;
    const narrow = axesAt(500);
    const ticks = dates.filter(narrow.tickFilter);
    expect(ticks.length).toBeGreaterThanOrEqual(2);
    expect(ticks.length).toBeLessThanOrEqual(5);
    expect(ticks[0]).toBe(dates[0]);
    expect(ticks.at(-1)).toBe(dates.at(-1));
    expect(dates.filter(axesAt(1000).tickFilter).length).toBeGreaterThan(ticks.length);
    expect(narrow.labelTransform).toBeUndefined();
    expect(narrow.labelFormatter(dates[0])).toBe(dates[0]);
    expect(data).toHaveLength(286);
  });
});
