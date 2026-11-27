/**
 * Structured stock, index, ETF, and A-share sector quote snapshot types
 * matching ``dbgpt_serve.financial_analysis.quotes.models.Snapshot``.
 */

export interface StockListing {
  market: 'sh' | 'sz' | 'bj' | 'hk';
  code: string;
  name: string;
  currency?: string;
  asset_type?: 'stock' | 'index' | 'etf';
}

export interface StockQuoteData {
  listing: StockListing;
  day: string;
  as_of?: string | null;
  source: string;
  url: string;
  last?: string | number | null;
  previous?: string | number | null;
  opening?: string | number | null;
  high?: string | number | null;
  low?: string | number | null;
  turnover?: string | number | null;
  pe?: string | number | null;
  pb?: string | number | null;
  market_cap?: string | number | null;
  turnover_rate?: string | number | null;
  suspended?: boolean;
  change?: string | number | null;
  percent?: string | number | null;
  amplitude?: string | number | null;
  gaps?: Record<string, string>;
}

export interface StockVerification {
  status?: 'pending' | 'confirmed';
  source?: string | null;
  url?: string | null;
  day?: string | null;
  fields?: string[];
  reason?: string;
  other_price?: string | number | null;
  other_source?: string | null;
  other_url?: string | null;
  other_as_of?: string | null;
}

export interface SectorInfo {
  code: string;
  name: string;
}

export interface SectorMover {
  code: string;
  name: string;
  percent: string | number;
  as_of: string;
}

export interface SectorQuoteData {
  day: string;
  as_of?: string | null;
  percent?: string | number | null;
  rising?: number | null;
  falling?: number | null;
  flat?: number | null;
  gainers?: SectorMover[] | null;
  losers?: SectorMover[] | null;
  ranked_members?: number | null;
  total_members?: number | null;
}

export interface StockQuoteRow {
  requested: string;
  kind?: 'stock' | 'index' | 'etf' | 'sector';
  outcome: 'quoted' | 'choose' | 'unavailable';
  candidates?: StockListing[];
  quote?: StockQuoteData | null;
  sector_candidates?: SectorInfo[];
  sector?: SectorInfo | null;
  sector_quote?: SectorQuoteData | null;
  phase?: string;
  verification?: StockVerification | null;
  reason?: string;
}

export interface StockQuoteSnapshot {
  version?: number;
  queried_at: string;
  rows: StockQuoteRow[];
  display_mode?: 'full' | 'compact';
  recall_detail?: string | null;
  recall_indices?: number[] | null;
}

export function isStockQuoteSnapshot(value: unknown): value is StockQuoteSnapshot {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Record<string, unknown>;
  return typeof candidate.queried_at === 'string' && Array.isArray(candidate.rows) && candidate.rows.length > 0;
}

export function toFiniteNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === '') return null;
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

export type QuoteTone = 'up' | 'down' | 'flat';

export function changeTone(value: string | number | null | undefined): QuoteTone {
  const n = toFiniteNumber(value);
  if (n === null || n === 0) return 'flat';
  return n > 0 ? 'up' : 'down';
}

const RED_STYLE = {
  text: 'text-[#dc2626] dark:text-[#f87171]',
  pill: 'bg-red-50 text-[#dc2626] border-red-200/80 dark:bg-red-950/40 dark:text-[#f87171] dark:border-red-900/60',
  bar: 'bg-[#dc2626] dark:bg-[#f87171]',
};

const GREEN_STYLE = {
  text: 'text-[#16a34a] dark:text-[#4ade80]',
  pill: 'bg-emerald-50 text-[#16a34a] border-emerald-200/80 dark:bg-emerald-950/40 dark:text-[#4ade80] dark:border-emerald-900/60',
  bar: 'bg-[#16a34a] dark:bg-[#4ade80]',
};

const FLAT_STYLE = {
  text: 'text-gray-600 dark:text-gray-400',
  pill: 'bg-gray-100 text-gray-600 border-gray-200 dark:bg-gray-800/70 dark:text-gray-300 dark:border-gray-700',
  bar: 'bg-gray-400 dark:bg-gray-500',
};

/** Locale-aware market convention: ZH uses red-up/green-down; EN uses green-up/red-down. */
export function toneStyle(tone: QuoteTone, en: boolean) {
  if (tone === 'flat') return FLAT_STYLE;
  if (en) return tone === 'up' ? GREEN_STYLE : RED_STYLE;
  return tone === 'up' ? RED_STYLE : GREEN_STYLE;
}

function needsThreeDecimals(n: number): boolean {
  return Math.abs(Math.round(n * 100) - n * 100) > 1e-6;
}

export function formatNumber(value: string | number | null | undefined, digits?: number): string {
  const n = toFiniteNumber(value);
  if (n === null) return '—';
  const precision = digits ?? (needsThreeDecimals(n) ? 3 : 2);
  return n.toFixed(precision);
}

export function formatSigned(value: string | number | null | undefined, percent = false): string {
  const n = toFiniteNumber(value);
  if (n === null) return '—';
  const precision = percent ? 2 : needsThreeDecimals(n) ? 3 : 2;
  const rounded = Number(n.toFixed(precision));
  const sign = rounded < 0 ? '−' : rounded > 0 ? '+' : '';
  return `${sign}${Math.abs(rounded).toFixed(precision)}${percent ? '%' : ''}`;
}

export function formatTurnover(value: string | number | null | undefined, currency: string, en: boolean): string {
  const n = toFiniteNumber(value);
  if (n === null) return '—';
  const yi = n / 1e8;
  if (en) return `${yi.toFixed(2)} × 100M ${currency}`;
  const unit = currency === 'HKD' ? '亿港元' : currency === 'USD' ? '亿美元' : '亿元';
  return `${yi.toFixed(2)} ${unit}`;
}

export function formatTimestamp(raw: string | null | undefined): string {
  if (!raw) return '';
  const match = raw.match(/(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})/);
  return match ? `${match[1]} ${match[2]}` : raw;
}

export function formatClock(raw: string | null | undefined): string {
  if (!raw) return '';
  const match = raw.match(/(\d{2}:\d{2}:\d{2})/);
  return match ? match[1] : raw;
}

export function listingLabel(listing: StockListing): string {
  return `${listing.code}.${listing.market.toUpperCase()}`;
}

export function sectorUrl(code: string): string {
  return `https://quote.eastmoney.com/bk/90.${code}.html`;
}

/** Upgrade legacy raw API URLs (e.g. qt.gtimg.cn) to human-readable quote pages. */
export function displayQuoteUrl(url: string | null | undefined, listing?: StockListing): string {
  const raw = (url || '').trim();
  const tencentApi = raw.match(/^https?:\/\/qt\.gtimg\.cn\/q=([a-z]{2}[A-Za-z0-9]+)/i);
  if (tencentApi) {
    return `https://gu.qq.com/${tencentApi[1]}`;
  }
  if (/^https?:\/\/yunhq\.sse\.com\.cn/i.test(raw) && listing?.code) {
    return listing.asset_type === 'etf'
      ? `https://www.sse.com.cn/assortment/fund/list/etfinfo/basic/index.shtml?FUNDID=${listing.code}`
      : `https://www.sse.com.cn/assortment/stock/list/info/company/index.shtml?COMPANY_CODE=${listing.code}`;
  }
  if (/^https?:\/\/www\.szse\.cn\/api\/market\/ssjjhq/i.test(raw) && listing?.code) {
    return `https://www.szse.cn/market/trend/index.html?code=${listing.code}`;
  }
  if (/^https?:\/\/www\.hkex\.com\.hk\/eng\/stat\/smstat\/dayquot\//i.test(raw) && listing?.code && /^\d+$/.test(listing.code)) {
    return `https://www.hkex.com.hk/Market-Data/Securities-Prices/Equities/Equities-Quote?sym=${Number(listing.code)}&sc_lang=zh-HK`;
  }
  return raw;
}

export function unitLabel(currency: string | undefined, assetType: string | undefined, en: boolean): string {
  if (assetType === 'index' || !currency) return en ? 'pts' : '点';
  if (en) return currency;
  return currency === 'HKD' ? '港元' : currency === 'CNY' ? '元' : currency;
}

const PHASE_MAP: Record<string, [string, string]> = {
  preopen: ['开盘前', 'Pre-open'],
  opening_auction: ['开市竞价', 'Opening auction'],
  trading: ['交易中', 'Trading'],
  lunch: ['午休', 'Lunch'],
  closing_auction: ['收市竞价', 'Closing auction'],
  random_close: ['随机收市', 'Random close'],
  auction_ended: ['收盘竞价结束', 'Auction ended'],
  after_hours: ['盘后交易', 'After-hours'],
  closed: ['已收市', 'Closed'],
  holiday: ['休市日', 'Holiday'],
  unknown: ['时段待核实', 'Unverified'],
};

export const CLOSED_LIKE_PHASES = new Set([
  'closed',
  'holiday',
  'after_hours',
  'auction_ended',
  'closing_auction',
  'random_close',
]);

export function phaseLabel(phase: string | undefined, en: boolean): string {
  const pair = PHASE_MAP[phase || 'unknown'] || PHASE_MAP.unknown;
  return en ? pair[1] : pair[0];
}

const REASON_MAP: Record<string, [string, string]> = {
  unsupported: ['代码、市场或币种暂不支持', 'Unsupported symbol or market'],
  not_found: ['未匹配到个股、指数或 A 股板块', 'No matching stock, index, or sector'],
  sector_not_found: ['未匹配到 A 股板块，请输入具体行业或概念名称', 'No matching A-share sector'],
  sector_market: ['板块行情目前仅覆盖 A 股行业和概念', 'Sector quotes cover A-share boards only'],
  sector_lookup_failed: ['板块名称检索暂不可用', 'Sector lookup unavailable'],
  sector_unavailable: ['暂未取得带交易日期的板块行情', 'No dated sector quote available'],
  lookup_failed: ['名称检索源暂不可用', 'Symbol lookup unavailable'],
  timeout: ['查询超时', 'Request timed out'],
  missing_quote: ['行情源未返回有效报价', 'No valid quote returned'],
  daily_unavailable: ['当日港交所主板日报未发布或未覆盖', 'HKEX daily bulletin unavailable'],
  different_close: ['交易所快照与日线收盘价不一致', 'Exchange snapshot and daily close differ'],
  close_pending: ['交易所收盘记录待核对', 'Exchange close pending'],
  close_unsupported: ['该品种无交易所收盘复核，展示最新报价', 'No exchange close check; showing latest quote'],
  market_open: ['当前尚未收盘，展示盘中最新报价', 'Market open; showing latest quote'],
};

export function reasonLabel(reason: string | undefined, en: boolean): string {
  const pair = REASON_MAP[reason || 'missing_quote'] || REASON_MAP.missing_quote;
  return en ? pair[1] : pair[0];
}

const DETAIL_MAP: Record<string, [string, string]> = {
  last: ['最新价', 'Last'],
  close: ['收盘价', 'Close'],
  previous: ['前收', 'Prev close'],
  opening: ['今开', 'Open'],
  high: ['最高', 'High'],
  low: ['最低', 'Low'],
  turnover: ['成交额', 'Turnover'],
  amplitude: ['振幅', 'Amplitude'],
  gainers: ['领涨个股', 'Top gainers'],
  losers: ['领跌个股', 'Top decliners'],
};

export function detailLabel(detail: string | null | undefined, en: boolean): string {
  if (!detail) return '';
  const pair = DETAIL_MAP[detail];
  return pair ? (en ? pair[1] : pair[0]) : detail;
}

export function buildRefreshPrompt(
  snapshot: StockQuoteSnapshot,
  en: boolean,
  targetRows?: StockQuoteRow[],
): string {
  const sourceRows = targetRows && targetRows.length > 0 ? targetRows : snapshot.rows;
  const subjects = sourceRows
    .map(row => {
      if (row.sector) return `${row.sector.name}（${row.sector.code}）`;
      if (row.quote) return `${row.quote.listing.name}（${listingLabel(row.quote.listing)}）`;
      return row.requested;
    })
    .filter(Boolean);
  const unique = Array.from(new Set(subjects));
  if (!unique.length) return en ? 'Refresh the latest quotes.' : '刷新最新行情';
  return en ? `Refresh latest quotes for ${unique.join(', ')}.` : `刷新 ${unique.join('、')} 的最新行情`;
}
