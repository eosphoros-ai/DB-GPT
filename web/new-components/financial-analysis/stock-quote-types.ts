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

/** A-share market convention: red for positive gains, green for declines. */
export function changeTone(value: string | number | null | undefined): 'up' | 'down' | 'flat' {
  const n = toFiniteNumber(value);
  if (n === null || n === 0) return 'flat';
  return n > 0 ? 'up' : 'down';
}

export function formatNumber(value: string | number | null | undefined, digits = 2): string {
  const n = toFiniteNumber(value);
  if (n === null) return '—';
  return n.toFixed(digits);
}

export function formatSigned(value: string | number | null | undefined, percent = false): string {
  const n = toFiniteNumber(value);
  if (n === null) return '—';
  const sign = n < 0 ? '−' : n > 0 ? '+' : '';
  return `${sign}${Math.abs(n).toFixed(2)}${percent ? '%' : ''}`;
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
};

export function reasonLabel(reason: string | undefined, en: boolean): string {
  const pair = REASON_MAP[reason || 'missing_quote'] || REASON_MAP.missing_quote;
  return en ? pair[1] : pair[0];
}

export function buildRefreshPrompt(snapshot: StockQuoteSnapshot, en: boolean): string {
  const subjects = snapshot.rows
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
