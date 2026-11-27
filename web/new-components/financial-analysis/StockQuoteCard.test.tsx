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
        turnover: '929777000000',
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

    const idxTile = screen.getByTestId('quote-index-000001.SH');
    expect(idxTile.textContent).toContain('3350.00');
    expect(idxTile.textContent).toContain('2026-11-24 15:00:00');
    expect(idxTile.textContent).toContain('已收市');

    const sectorText = screen.getByTestId('quote-sector-BK1036').textContent || '';
    expect(sectorText).toContain('半导体');
    expect(sectorText).toContain('有效报价覆盖 186/188 家');
    expect(sectorText).toContain('芯导科技');
    expect(sectorText).toContain('艾为电子');

    const moutaiText = screen.getByTestId('quote-listing-600519.SH').textContent || '';
    expect(moutaiText).toContain('1460.00');
    expect(moutaiText).toContain('21.80');
    expect(moutaiText).toContain('18340.50 亿元');
    expect(screen.getByTestId('quote-close-pending').textContent).toContain('收盘价待确认');
    expect(screen.getByTestId('quote-close-confirmed').textContent).toContain('收盘价已确认');

    // Legacy qt.gtimg.cn and HKEX raw bulletin URLs upgrade to readable web pages.
    const moutaiLink = screen
      .getByTestId('quote-listing-600519.SH')
      .querySelector('a')
      ?.getAttribute('href');
    expect(moutaiLink).toBe('https://gu.qq.com/sh600519');
    const tencentLink = screen
      .getByTestId('quote-listing-00700.HK')
      .querySelector('a')
      ?.getAttribute('href');
    expect(tencentLink).toBe(
      'https://www.hkex.com.hk/Market-Data/Securities-Prices/Equities/Equities-Quote?sym=700&sc_lang=zh-HK',
    );
  });

  it('switches gain/loss color conventions by language (ZH red-up vs EN green-up)', () => {
    const { rerender } = render(<StockQuoteCard snapshot={sampleSnapshot} language='zh' />);
    const zhIndexHtml = screen.getByTestId('quote-index-000001.SH').innerHTML;
    expect(zhIndexHtml).toContain('text-[#dc2626]');

    rerender(<StockQuoteCard snapshot={sampleSnapshot} language='en' />);
    const enIndexHtml = screen.getByTestId('quote-index-000001.SH').innerHTML;
    expect(enIndexHtml).toContain('text-[#16a34a]');
    const enTencentHtml = screen.getByTestId('quote-listing-00700.HK').innerHTML;
    expect(enTencentHtml).toContain('text-[#dc2626]');
  });

  it('hides card for all-unavailable snapshots and hides refresh when no rows are quoted', () => {
    const failedOnly: StockQuoteSnapshot = {
      queried_at: '2026-11-24T16:52:31+08:00',
      rows: [
        {
          requested: '美股某标的',
          kind: 'stock',
          outcome: 'unavailable',
          reason: 'unsupported',
        },
      ],
    };
    const { container } = render(<StockQuoteCard snapshot={failedOnly} language='zh' interactive />);
    expect(container.firstChild).toBeNull();

    const onSelect = vi.fn();
    const onRefresh = vi.fn();
    const chooseOnly: StockQuoteSnapshot = {
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

    const { rerender } = render(
      <StockQuoteCard
        snapshot={chooseOnly}
        language='zh'
        interactive
        onSelectCandidate={onSelect}
        onRefresh={onRefresh}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /半导体/ }));
    expect(onSelect).toHaveBeenCalledWith('半导体（BK1036）');
    expect(screen.queryByRole('button', { name: /刷新行情/ })).toBeNull();
    expect(screen.getByText('代码、市场或币种暂不支持')).toBeTruthy();

    // Without onSelectCandidate (single-turn QuestionDock mode), candidates render as read-only tags.
    rerender(<StockQuoteCard snapshot={chooseOnly} language='zh' interactive onRefresh={onRefresh} />);
    expect(screen.queryByRole('button', { name: /半导体/ })).toBeNull();
    expect(screen.getByText('半导体')).toBeTruthy();
  });

  it('refreshes all rows when mixed snapshot contains quoted rows', () => {
    const onRefresh = vi.fn();
    const mixed: StockQuoteSnapshot = {
      queried_at: '2026-11-24T16:52:31+08:00',
      rows: [
        {
          requested: '科技股',
          kind: 'sector',
          outcome: 'choose',
          sector_candidates: [{ code: 'BK1036', name: '半导体' }],
        },
        sampleSnapshot.rows[2],
      ],
    };

    render(<StockQuoteCard snapshot={mixed} language='zh' interactive onRefresh={onRefresh} />);
    fireEvent.click(screen.getByRole('button', { name: /刷新行情/ }));
    expect(onRefresh).toHaveBeenCalledWith(buildRefreshPrompt(mixed, false));
  });

  it('preserves 3-decimal ETF prices, avoids close-pending on ETF/BJ, and shows data warnings', () => {
    const edgeSnapshot: StockQuoteSnapshot = {
      queried_at: '2026-11-24T16:52:43+08:00',
      rows: [
        {
          requested: '510300.SH',
          kind: 'etf',
          outcome: 'quoted',
          phase: 'closed',
          quote: {
            listing: { market: 'sh', code: '510300', name: '沪深300ETF', currency: 'CNY', asset_type: 'etf' },
            day: '2026-11-24',
            as_of: '2026-11-24T15:00:00+08:00',
            source: '腾讯财经',
            url: 'https://gu.qq.com/sh510300',
            last: '4.125',
            previous: '4.121',
            change: '0.004',
            percent: '0.10',
          },
        },
        {
          requested: '920157.BJ',
          kind: 'stock',
          outcome: 'quoted',
          phase: 'closed',
          quote: {
            listing: { market: 'bj', code: '920157', name: '宇特光电', currency: 'CNY', asset_type: 'stock' },
            day: '2026-11-24',
            as_of: '2026-11-24T15:00:00+08:00',
            source: '腾讯财经',
            url: 'https://gu.qq.com/bj920157',
            last: '25.00',
            previous: '22.50',
            change: null,
            percent: null,
            gaps: { change: 'reference_conflict' },
          },
          verification: { status: 'pending', reason: 'different_close' },
        },
      ],
    };

    render(<StockQuoteCard snapshot={edgeSnapshot} language='zh' />);
    const etfText = screen.getByTestId('quote-listing-510300.SH').textContent || '';
    expect(etfText).toContain('4.125');
    expect(etfText).toContain('+0.004');
    expect(screen.queryByTestId('quote-close-pending')).toBeNull();
    const warning = screen.getByTestId('quote-warning-920157.BJ').textContent || '';
    expect(warning).toContain('涨跌与来源参考口径冲突');
    expect(warning).toContain('交易所快照与日线收盘价不一致');
  });

  it('renders a compact recall card focused on recalled rows and detail field', () => {
    const compactSnapshot: StockQuoteSnapshot = {
      ...sampleSnapshot,
      display_mode: 'compact',
      recall_detail: 'turnover',
      recall_indices: [2],
    };

    render(<StockQuoteCard snapshot={compactSnapshot} language='zh' />);
    const card = screen.getByTestId('stock-quote-card');
    expect(card.getAttribute('data-compact')).toBe('true');
    expect(card.textContent).toContain('快照回看');
    expect(card.textContent).toContain('成交额');
    expect(card.textContent).toContain('62.14 亿元');
    expect(screen.getByTestId('quote-compact-600519.SH')).toBeTruthy();
    expect(screen.queryByTestId('quote-compact-00700.HK')).toBeNull();
  });

  it('deduplicates repeated index, sector, and stock rows in legacy snapshots', () => {
    const duplicated: StockQuoteSnapshot = {
      ...sampleSnapshot,
      rows: [...sampleSnapshot.rows, ...sampleSnapshot.rows],
    };

    render(<StockQuoteCard snapshot={duplicated} language='zh' />);

    expect(screen.getAllByTestId('quote-index-000001.SH')).toHaveLength(1);
    expect(screen.getAllByTestId('quote-sector-BK1036')).toHaveLength(1);
    expect(screen.getAllByTestId('quote-listing-600519.SH')).toHaveLength(1);
    expect(screen.getAllByTestId('quote-listing-00700.HK')).toHaveLength(1);
  });

  it('shows index turnover on IndexTile and accurate close-reason on compact recall', () => {
    const { rerender } = render(<StockQuoteCard snapshot={sampleSnapshot} language='zh' />);
    const turnoverRow = screen.getByTestId('quote-index-turnover-000001.SH').textContent || '';
    expect(turnoverRow).toContain('成交额');
    expect(turnoverRow).toContain('9297.77 亿元');

    const compactClose: StockQuoteSnapshot = {
      queried_at: '2026-11-24T10:30:00+08:00',
      display_mode: 'compact',
      recall_detail: 'close',
      recall_indices: [0],
      rows: [
        {
          requested: '510300.SH',
          kind: 'etf',
          outcome: 'quoted',
          phase: 'closed',
          quote: {
            listing: { market: 'sh', code: '510300', name: '沪深300ETF', currency: 'CNY', asset_type: 'etf' },
            day: '2026-11-24',
            as_of: '2026-11-24T15:00:00+08:00',
            source: '腾讯财经',
            url: 'https://gu.qq.com/sh510300',
            last: '4.125',
            previous: '4.121',
            change: '0.004',
            percent: '0.10',
          },
          verification: { status: 'pending', reason: 'close_unsupported' },
        },
      ],
    };

    rerender(<StockQuoteCard snapshot={compactClose} language='zh' />);
    const compactText = screen.getByTestId('quote-compact-510300.SH').textContent || '';
    expect(compactText).toContain('该品种无交易所收盘复核，展示最新报价');
    expect(compactText).not.toContain('收盘待确认');
  });
});
