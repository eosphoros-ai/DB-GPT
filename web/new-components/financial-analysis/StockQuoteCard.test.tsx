import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import StockQuoteCard from './StockQuoteCard';
import { buildRefreshPrompt, isStockQuoteSnapshot, type StockQuoteSnapshot } from './stock-quote-types';

const sampleSnapshot: StockQuoteSnapshot = {
  version: 1,
  queried_at: '2026-11-24T16:52:43+08:00',
  rows: [
    {
      requested: '上证指数',
      kind: 'index',
      outcome: 'quoted',
      phase: 'closed',
      quote: {
        listing: { market: 'sh', code: '000001', name: '上证指数', currency: '', asset_type: 'index' },
        day: '2026-11-24',
        as_of: '2026-11-24T15:00:00+08:00',
        source: '腾讯财经',
        url: 'https://qt.gtimg.cn/q=sh000001',
        last: '3350.00',
        previous: '3320.00',
        change: '30.00',
        percent: '0.90',
      },
    },
    {
      requested: '半导体',
      kind: 'sector',
      outcome: 'quoted',
      sector: { code: 'BK1036', name: '半导体' },
      sector_quote: {
        day: '2026-11-24',
        as_of: '2026-11-24T15:39:57+08:00',
        percent: '1.08',
        rising: 125,
        falling: 59,
        flat: 4,
        ranked_members: 186,
        total_members: 188,
        gainers: [
          { code: '688230.SH', name: '芯导科技', percent: '10.74', as_of: '2026-11-24T15:00:00+08:00' },
        ],
        losers: [
          { code: '688798.SH', name: '艾为电子', percent: '-6.16', as_of: '2026-11-24T15:00:00+08:00' },
        ],
      },
    },
    {
      requested: '贵州茅台',
      kind: 'stock',
      outcome: 'quoted',
      phase: 'closed',
      verification: { status: 'pending', reason: 'close_pending' },
      quote: {
        listing: { market: 'sh', code: '600519', name: '贵州茅台', currency: 'CNY', asset_type: 'stock' },
        day: '2026-11-24',
        as_of: '2026-11-24T15:35:00+08:00',
        source: '腾讯财经',
        url: 'https://qt.gtimg.cn/q=sh600519',
        last: '1460.00',
        previous: '1439.00',
        opening: '1425.00',
        high: '1463.26',
        low: '1420.00',
        turnover: '6214000000',
        turnover_rate: '0.45',
        market_cap: '18340.50',
        pe: '21.80',
        pb: '7.90',
        change: '21.00',
        percent: '1.46',
        amplitude: '3.01',
      },
    },
    {
      requested: '腾讯控股',
      kind: 'stock',
      outcome: 'quoted',
      phase: 'closed',
      verification: {
        status: 'confirmed',
        source: '港交所',
        url: 'https://www.hkex.com.hk/eng/stat/smstat/dayquot/d261124e.htm',
      },
      quote: {
        listing: { market: 'hk', code: '00700', name: '腾讯控股', currency: 'HKD', asset_type: 'stock' },
        day: '2026-11-24',
        as_of: null,
        source: '港交所',
        url: 'https://www.hkex.com.hk/eng/stat/smstat/dayquot/d261124e.htm',
        last: '346.00',
        previous: '348.00',
        change: '-2.00',
        percent: '-0.57',
        turnover: '10111100000',
      },
    },
  ],
};

describe('StockQuoteCard', () => {
  it('validates snapshot payloads and renders index, sector, valuation metrics, and close badges', () => {
    expect(isStockQuoteSnapshot(sampleSnapshot)).toBe(true);
    expect(isStockQuoteSnapshot({ queried_at: 'now', rows: [] })).toBe(false);
    expect(isStockQuoteSnapshot(null)).toBe(false);

    render(<StockQuoteCard snapshot={sampleSnapshot} language='zh' />);

    expect(screen.getByTestId('quote-index-000001.SH').textContent).toContain('3350.00');
    const sectorText = screen.getByTestId('quote-sector-BK1036').textContent || '';
    expect(sectorText).toContain('半导体');
    expect(sectorText).toContain('有效报价覆盖 186/188 家');
    expect(sectorText).toContain('芯导科技');
    expect(sectorText).toContain('艾为电子');

    const moutaiText = screen.getByTestId('quote-listing-600519.SH').textContent || '';
    expect(moutaiText).toContain('1460.00');
    expect(moutaiText).toContain('21.80');
    expect(moutaiText).toContain('18340.50 亿');
    expect(screen.getByTestId('quote-close-pending').textContent).toContain('收盘价待确认');
    expect(screen.getByTestId('quote-close-confirmed').textContent).toContain('收盘价已确认');
  });

  it('invokes candidate selection and refresh callbacks when interactive', () => {
    const onSelect = vi.fn();
    const onRefresh = vi.fn();
    const chooseSnapshot: StockQuoteSnapshot = {
      queried_at: '2026-11-24T16:52:31+08:00',
      rows: [
        {
          requested: '科技股',
          kind: 'sector',
          outcome: 'choose',
          sector_candidates: [
            { code: 'BK1036', name: '半导体' },
            { code: 'BK0737', name: '软件开发' },
          ],
        },
        {
          requested: '美股某标的',
          kind: 'stock',
          outcome: 'unavailable',
          reason: 'unsupported',
        },
      ],
    };

    render(
      <StockQuoteCard
        snapshot={chooseSnapshot}
        language='zh'
        interactive
        onSelectCandidate={onSelect}
        onRefresh={onRefresh}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /半导体/ }));
    expect(onSelect).toHaveBeenCalledWith('半导体（BK1036）');

    fireEvent.click(screen.getByRole('button', { name: /刷新行情/ }));
    expect(onRefresh).toHaveBeenCalledWith(buildRefreshPrompt(chooseSnapshot, false));
    expect(screen.getByText('代码、市场或币种暂不支持')).toBeTruthy();
  });
});
