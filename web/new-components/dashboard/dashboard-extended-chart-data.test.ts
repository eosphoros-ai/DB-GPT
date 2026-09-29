import { describe, expect, it } from 'vitest';
import { mapCountryData, numericChartData, treemapBoxes, waterfallSteps, waterfallSeries } from './dashboard-extended-chart-data';
const rows = (values: number[]) => values.map((value, i) => ({ label: String(i), value, source: {} }));
describe('extended chart calculations', () => {
  it('reconciles a legacy explicit final total without doubling revenue', () => {
    const result = waterfallSeries([...rows([100, -20, 30]), { label: '合计', value: 110, source: {} }]);
    expect(result.map(row => row.value)).toEqual([100, -20, 30, 110]);
    expect(result.filter(row => row.isTotal)).toHaveLength(1);
    expect(result.at(-1)?.end).toBe(110);
  });
  it('preserves an ordinary or nonterminal category even when named total', () => {
    expect(waterfallSeries([{ label: '合计', value: 20, source: {} }, ...rows([20, 10])]).at(-1)?.end).toBe(50);
    expect(waterfallSeries([...rows([20]), { label: '合计', value: 10, source: {} }]).at(-1)?.end).toBe(30);
  });
  it('accepts a reconciled total marker and still handles zero and negative totals', () => {
    const result = waterfallSeries([...rows([10, -30]), { label: '余额', value: -20, source: { is_total: true } }]);
    expect(result.map(row => [row.start, row.end])).toEqual([[0, 10], [10, -20], [0, -20]]);
    expect(waterfallSeries(rows([10, -10])).at(-1)?.value).toBe(0);
  });
  it('keeps zero and negatives but distinguishes missing and invalid values', () => {
    expect(
      numericChartData(
        [0, -3, null, '', 'bad', true, '12'].map(v => ({ name: 'A', v })),
        'name',
        'v',
      ).map(item => item.value),
    ).toEqual([0, -3, 12]);
  });
  it('preserves waterfall stage order and negative cumulative balances', () => {
    expect(waterfallSteps(rows([10, -30, 5])).map(item => [item.start, item.end])).toEqual([
      [0, 10],
      [10, -20],
      [-20, -15],
    ]);
  });
  it('allocates treemap area proportionately without overlap or leaving the bounds', () => {
    const boxes = treemapBoxes(rows([60, 25, 10, 5]), 0, 0, 100, 100);
    boxes.forEach(box => {
      expect(box.width * box.height).toBeCloseTo(box.value * 100);
      expect(box.x + box.width).toBeLessThanOrEqual(100);
      expect(box.y + box.height).toBeLessThanOrEqual(100);
    });
    for (let i = 0; i < boxes.length; i++)
      for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i],
          b = boxes[j];
        expect(a.x + a.width <= b.x || b.x + b.width <= a.x || a.y + a.height <= b.y || b.y + b.height <= a.y).toBe(
          true,
        );
      }
  });
  it('matches country aliases and exposes names it cannot place on a map', () => {
    const result = mapCountryData(
      ['USA', '美国', 'UK', 'Germany', '未知市场'].map((label, i) => ({ label, value: i + 1, source: {} })),
    );
    expect(result.matched.find(item => item.country.id === 'USA')?.value).toBe(3);
    expect(result.matched.map(item => item.country.id)).toEqual(['USA', 'GBR', 'DEU']);
    expect(result.unmatched.map(item => item.label)).toEqual(['未知市场']);
  });
});
