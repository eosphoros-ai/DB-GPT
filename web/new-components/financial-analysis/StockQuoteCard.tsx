import {
  CheckCircleFilled,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  HistoryOutlined,
  LinkOutlined,
  ReloadOutlined,
  StockOutlined,
} from '@ant-design/icons';
import React from 'react';
import {
  buildRefreshPrompt,
  changeTone,
  CLOSED_LIKE_PHASES,
  detailLabel,
  displayQuoteUrl,
  formatClock,
  formatNumber,
  formatSigned,
  formatTimestamp,
  formatTurnover,
  listingLabel,
  phaseLabel,
  reasonLabel,
  sectorUrl,
  type StockQuoteRow,
  type StockQuoteSnapshot,
  toFiniteNumber,
  toneStyle,
  unitLabel,
} from './stock-quote-types';

export interface StockQuoteCardProps {
  snapshot: StockQuoteSnapshot;
  language?: string;
  busy?: boolean;
  interactive?: boolean;
  onSelectCandidate?: (choice: string) => void;
  onRefresh?: (prompt: string) => void;
}

function isVerifiableStock(row: StockQuoteRow): boolean {
  const listing = row.quote?.listing;
  return !!listing && listing.asset_type === 'stock' && listing.market !== 'bj';
}

function formatRecallFieldValue(row: StockQuoteRow, detail: string, en: boolean): string | null {
  const q = row.quote;
  if (!q) return null;
  const unit = unitLabel(q.listing.currency, q.listing.asset_type, en);
  const turnoverCurrency = q.listing.currency || (q.listing.market === 'hk' ? 'HKD' : 'CNY');
  switch (detail) {
    case 'turnover':
      return formatTurnover(q.turnover, turnoverCurrency, en);
    case 'amplitude':
      return toFiniteNumber(q.amplitude) !== null ? `${formatNumber(q.amplitude, 2)}%` : '—';
    case 'last':
    case 'close':
    case 'previous':
    case 'opening':
    case 'high':
    case 'low': {
      const raw = detail === 'close' ? q.last : q[detail];
      const formatted = formatNumber(raw);
      return formatted === '—' ? '—' : `${formatted} ${unit}`;
    }
    default:
      return null;
  }
}

function IndexTile({ row, en }: { row: StockQuoteRow; en: boolean }) {
  const q = row.quote!;
  const tone = toneStyle(changeTone(q.percent), en);
  const stamp = formatTimestamp(q.as_of) || q.day;
  const turnoverCurrency = q.listing.currency || (q.listing.market === 'hk' ? 'HKD' : 'CNY');
  const turnoverText = toFiniteNumber(q.turnover) !== null ? formatTurnover(q.turnover, turnoverCurrency, en) : null;
  return (
    <div
      data-testid={`quote-index-${listingLabel(q.listing)}`}
      className='rounded-lg border border-gray-200/80 dark:border-gray-800 bg-gray-50/60 dark:bg-[#1a1b20] px-3 py-2.5 flex flex-col gap-1'
    >
      <div className='flex items-center justify-between gap-1.5 min-w-0'>
        <span className='text-xs font-semibold text-gray-900 dark:text-gray-100 truncate'>{q.listing.name}</span>
        <span className='text-[11px] font-mono text-gray-400 dark:text-gray-500 shrink-0'>
          {listingLabel(q.listing)}
        </span>
      </div>
      <div className='flex items-baseline justify-between gap-2 mt-0.5'>
        <span className={`text-base font-bold tabular-nums tracking-tight ${tone.text}`}>
          {formatNumber(q.last)}
        </span>
        <span className={`text-xs font-semibold tabular-nums px-1.5 py-0.5 rounded border ${tone.pill}`}>
          {formatSigned(q.percent, true)}
        </span>
      </div>
      <div className='flex items-center justify-between text-[11px] text-gray-500 dark:text-gray-400 tabular-nums'>
        <span className={tone.text}>{formatSigned(q.change)}</span>
        <a
          href={displayQuoteUrl(q.url, q.listing)}
          target='_blank'
          rel='noopener noreferrer'
          className='inline-flex items-center gap-0.5 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors'
        >
          <span>{q.source}</span>
          <LinkOutlined className='text-[10px]' />
        </a>
      </div>
      {turnoverText && (
        <div
          data-testid={`quote-index-turnover-${listingLabel(q.listing)}`}
          className='flex items-center justify-between gap-1.5 text-[11px] text-gray-500 dark:text-gray-400 tabular-nums'
        >
          <span>{en ? 'Turnover' : '成交额'}</span>
          <span className='font-medium text-gray-700 dark:text-gray-300'>{turnoverText}</span>
        </div>
      )}
      <div className='flex items-center justify-between gap-1.5 text-[10px] text-gray-400 dark:text-gray-500 tabular-nums pt-0.5 border-t border-gray-200/50 dark:border-gray-800/80'>
        <span className='truncate'>{phaseLabel(row.phase, en)}</span>
        <span className='shrink-0'>{stamp}</span>
      </div>
    </div>
  );
}

function ListingCard({ row, en }: { row: StockQuoteRow; en: boolean }) {
  const q = row.quote!;
  const v = row.verification;
  const tone = toneStyle(changeTone(q.percent), en);
  const label = listingLabel(q.listing);
  const unit = unitLabel(q.listing.currency, q.listing.asset_type, en);
  const isConfirmedClose = v?.status === 'confirmed';
  const isClosePending = !isConfirmedClose && isVerifiableStock(row) && CLOSED_LIKE_PHASES.has(row.phase || '');
  const turnoverCurrency = q.listing.currency || (q.listing.market === 'hk' ? 'HKD' : 'CNY');

  const metrics: Array<{ label: string; value: string }> = [
    { label: en ? 'Prev' : '前收', value: formatNumber(q.previous) },
    { label: en ? 'Open' : '今开', value: formatNumber(q.opening) },
    { label: en ? 'High' : '最高', value: formatNumber(q.high) },
    { label: en ? 'Low' : '最低', value: formatNumber(q.low) },
    {
      label: en ? 'Amp' : '振幅',
      value: toFiniteNumber(q.amplitude) !== null ? `${formatNumber(q.amplitude, 2)}%` : '—',
    },
    { label: en ? 'Turnover' : '成交额', value: formatTurnover(q.turnover, turnoverCurrency, en) },
  ];
  if (toFiniteNumber(q.turnover_rate) !== null) {
    metrics.push({ label: en ? 'Turn.' : '换手率', value: `${formatNumber(q.turnover_rate, 2)}%` });
  }
  if (toFiniteNumber(q.market_cap) !== null) {
    metrics.push({
      label: en ? 'Mkt Cap' : '总市值',
      value: en ? `${formatNumber(q.market_cap, 2)} × 100M CNY` : `${formatNumber(q.market_cap, 2)} 亿元`,
    });
  }
  if (toFiniteNumber(q.pe) !== null) {
    metrics.push({ label: 'PE', value: formatNumber(q.pe, 2) });
  }
  if (toFiniteNumber(q.pb) !== null) {
    metrics.push({ label: 'PB', value: formatNumber(q.pb, 2) });
  }

  const gapEntries = Object.entries(q.gaps || {});
  const hasChangeConflict = q.gaps?.change === 'reference_conflict';
  const missingFields = gapEntries
    .filter(([k, val]) => k !== 'change' && val === 'missing')
    .map(([k]) => detailLabel(k, en))
    .filter(Boolean);
  const showVerificationReason =
    !!v?.reason && !isConfirmedClose && v.reason !== 'close_pending';

  return (
    <div
      data-testid={`quote-listing-${label}`}
      className='rounded-lg border border-gray-200/80 dark:border-gray-800 bg-white dark:bg-[#1a1b20] p-3.5'
    >
      <div className='flex flex-wrap items-start justify-between gap-2'>
        <div className='min-w-0'>
          <div className='flex items-center gap-2 flex-wrap'>
            <span className='text-sm font-semibold text-gray-900 dark:text-gray-100'>{q.listing.name}</span>
            <span className='text-xs font-mono px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300'>
              {label}
            </span>
            {q.suspended && (
              <span className='text-[11px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800'>
                {en ? 'Suspended' : '停牌'}
              </span>
            )}
          </div>
          <div className='flex items-baseline gap-2.5 mt-1.5 flex-wrap'>
            <span className={`text-xl font-bold tabular-nums tracking-tight ${tone.text}`}>
              {formatNumber(q.last)}
            </span>
            <span className='text-xs text-gray-500 dark:text-gray-400'>{unit}</span>
            <span className={`text-xs font-medium tabular-nums ${tone.text}`}>{formatSigned(q.change)}</span>
            <span className={`text-xs font-semibold tabular-nums px-2 py-0.5 rounded-full border ${tone.pill}`}>
              {formatSigned(q.percent, true)}
            </span>
          </div>
        </div>

        <div className='flex flex-col items-end gap-1 shrink-0'>
          {isConfirmedClose ? (
            <span
              data-testid='quote-close-confirmed'
              className='inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/80 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800'
            >
              <CheckCircleFilled className='text-[10px]' />
              {en ? 'Confirmed close' : '收盘价已确认'}
            </span>
          ) : isClosePending ? (
            <span
              data-testid='quote-close-pending'
              className='inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200/80 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800'
            >
              <ClockCircleOutlined className='text-[10px]' />
              {phaseLabel(row.phase, en)} · {en ? 'Close pending' : '收盘价待确认'}
            </span>
          ) : (
            <span className='inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300'>
              {phaseLabel(row.phase, en)}
            </span>
          )}
          <span className='text-[11px] text-gray-400 dark:text-gray-500 tabular-nums'>
            {formatTimestamp(q.as_of) || q.day}
          </span>
        </div>
      </div>

      <div className='grid grid-cols-3 sm:grid-cols-6 gap-x-3 gap-y-1.5 mt-3 pt-2.5 border-t border-gray-100 dark:border-gray-800/80'>
        {metrics.map(item => (
          <div key={item.label} className='flex flex-col'>
            <span className='text-[11px] text-gray-400 dark:text-gray-500'>{item.label}</span>
            <span className='text-xs font-medium text-gray-700 dark:text-gray-200 tabular-nums'>{item.value}</span>
          </div>
        ))}
      </div>

      {(hasChangeConflict || missingFields.length > 0 || showVerificationReason) && (
        <div
          data-testid={`quote-warning-${label}`}
          className='flex flex-wrap items-center gap-x-3 gap-y-1 mt-2 pt-2 border-t border-gray-100 dark:border-gray-800/80 text-[11px] text-amber-600 dark:text-amber-400'
        >
          {hasChangeConflict && (
            <span>
              {en ? 'Change basis conflicts with source reference' : '涨跌与来源参考口径冲突'}
            </span>
          )}
          {showVerificationReason && <span>{reasonLabel(v?.reason, en)}</span>}
          {missingFields.length > 0 && (
            <span className='text-gray-500 dark:text-gray-400'>
              {en ? 'Source missing: ' : '来源缺项：'}
              {missingFields.join(en ? ', ' : '、')}
            </span>
          )}
        </div>
      )}

      <div className='flex flex-wrap items-center justify-between gap-2 mt-2.5 pt-2 border-t border-gray-100 dark:border-gray-800/80 text-[11px] text-gray-500 dark:text-gray-400'>
        <div className='flex items-center gap-2 flex-wrap'>
          <a
            href={displayQuoteUrl(q.url, q.listing)}
            target='_blank'
            rel='noopener noreferrer'
            className='inline-flex items-center gap-1 text-blue-600 dark:text-blue-400 hover:underline'
          >
            <LinkOutlined className='text-[10px]' />
            {q.source}
          </a>
          {v?.url && displayQuoteUrl(v.url, q.listing) !== displayQuoteUrl(q.url, q.listing) && (
            <a
              href={displayQuoteUrl(v.url, q.listing)}
              target='_blank'
              rel='noopener noreferrer'
              className='inline-flex items-center gap-1 text-blue-600 dark:text-blue-400 hover:underline'
            >
              <LinkOutlined className='text-[10px]' />
              {v.source}
              {en ? ' close' : '收盘复核'}
            </a>
          )}
        </div>
        {v?.other_price !== null && v?.other_price !== undefined && (
          <span className='text-amber-600 dark:text-amber-400 tabular-nums'>
            {v.other_url ? (
              <a
                href={displayQuoteUrl(v.other_url, q.listing)}
                target='_blank'
                rel='noopener noreferrer'
                className='hover:underline'
              >
                {v.other_source}
              </a>
            ) : (
              v.other_source
            )}
            : {formatNumber(v.other_price)}
            {v.other_as_of ? ` (${formatClock(v.other_as_of)})` : ''}
          </span>
        )}
      </div>
    </div>
  );
}

function SectorCard({
  row,
  en,
  focusDetail,
}: {
  row: StockQuoteRow;
  en: boolean;
  focusDetail?: string | null;
}) {
  const s = row.sector!;
  const q = row.sector_quote!;
  const tone = toneStyle(changeTone(q.percent), en);
  const upStyle = toneStyle('up', en);
  const downStyle = toneStyle('down', en);
  const up = q.rising ?? 0;
  const flat = q.flat ?? 0;
  const down = q.falling ?? 0;
  const breadthTotal = up + flat + down;
  const hasBreadth = q.rising !== null && q.rising !== undefined && breadthTotal > 0;
  const partialCoverage =
    q.ranked_members !== null &&
    q.ranked_members !== undefined &&
    q.total_members !== null &&
    q.total_members !== undefined &&
    q.ranked_members < q.total_members;

  const moverGroups = (
    [
      { key: 'gainers', title: en ? 'Top gainers' : '领涨个股', items: q.gainers, empty: en ? 'None' : '无上涨个股' },
      { key: 'losers', title: en ? 'Top decliners' : '领跌个股', items: q.losers, empty: en ? 'None' : '无下跌个股' },
    ] as const
  ).filter(g => !focusDetail || (focusDetail !== 'gainers' && focusDetail !== 'losers') || g.key === focusDetail);

  const hasAnyRanking = q.gainers !== null && q.gainers !== undefined || q.losers !== null && q.losers !== undefined;

  return (
    <div
      data-testid={`quote-sector-${s.code}`}
      className='rounded-lg border border-gray-200/80 dark:border-gray-800 bg-white dark:bg-[#1a1b20] p-3.5'
    >
      <div className='flex flex-wrap items-center justify-between gap-2'>
        <div className='flex items-center gap-2 flex-wrap'>
          <span className='text-sm font-semibold text-gray-900 dark:text-gray-100'>{s.name}</span>
          <span className='text-xs font-mono px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300'>
            {s.code}
          </span>
          <span className='text-[11px] text-gray-400 dark:text-gray-500'>
            {en ? 'A-share sector' : 'A 股板块指数'}
          </span>
        </div>
        <span className={`text-sm font-bold tabular-nums px-2.5 py-0.5 rounded-full border ${tone.pill}`}>
          {formatSigned(q.percent, true)}
        </span>
      </div>

      {hasBreadth && (
        <div className='mt-3'>
          <div className='h-1.5 w-full rounded-full overflow-hidden flex bg-gray-200 dark:bg-gray-700'>
            {up > 0 && <div className={upStyle.bar} style={{ width: `${(up / breadthTotal) * 100}%` }} />}
            {flat > 0 && <div className='bg-gray-400 dark:bg-gray-500' style={{ width: `${(flat / breadthTotal) * 100}%` }} />}
            {down > 0 && <div className={downStyle.bar} style={{ width: `${(down / breadthTotal) * 100}%` }} />}
          </div>
          <div className='flex flex-wrap items-center justify-between gap-2 mt-1.5 text-[11px] tabular-nums'>
            <div className='flex items-center gap-3'>
              <span className={`${upStyle.text} font-medium`}>{en ? `Up ${up}` : `上涨 ${up} 家`}</span>
              <span className='text-gray-500 dark:text-gray-400'>{en ? `Flat ${flat}` : `平盘 ${flat} 家`}</span>
              <span className={`${downStyle.text} font-medium`}>{en ? `Down ${down}` : `下跌 ${down} 家`}</span>
            </div>
            {partialCoverage && (
              <span className='text-gray-400 dark:text-gray-500'>
                {en
                  ? `Ranked ${q.ranked_members}/${q.total_members}`
                  : `有效报价覆盖 ${q.ranked_members}/${q.total_members} 家`}
              </span>
            )}
          </div>
        </div>
      )}

      {!hasBreadth && partialCoverage && (
        <div className='mt-2 text-[11px] text-gray-400 dark:text-gray-500 tabular-nums'>
          {en
            ? `Ranked ${q.ranked_members}/${q.total_members}`
            : `有效报价覆盖 ${q.ranked_members}/${q.total_members} 家`}
        </div>
      )}

      {hasAnyRanking ? (
        <div
          className={`grid grid-cols-1 ${moverGroups.length > 1 ? 'sm:grid-cols-2' : ''} gap-3 mt-3 pt-2.5 border-t border-gray-100 dark:border-gray-800/80`}
        >
          {moverGroups.map(group => (
            <div key={group.title} className='flex flex-col gap-1'>
              <span className='text-[11px] font-medium text-gray-500 dark:text-gray-400'>{group.title}</span>
              {group.items && group.items.length > 0 ? (
                group.items.map(mover => {
                  const moverTone = toneStyle(changeTone(mover.percent), en);
                  return (
                    <div
                      key={mover.code}
                      className='flex items-center justify-between gap-2 text-xs py-0.5 tabular-nums'
                    >
                      <span className='text-gray-800 dark:text-gray-200 truncate'>
                        {mover.name}{' '}
                        <span className='text-[11px] font-mono text-gray-400 dark:text-gray-500'>{mover.code}</span>
                      </span>
                      <span className='flex items-center gap-1.5 shrink-0'>
                        <span className={`font-semibold ${moverTone.text}`}>
                          {formatSigned(mover.percent, true)}
                        </span>
                        <span className='text-[10px] text-gray-400 dark:text-gray-500'>
                          {formatClock(mover.as_of)}
                        </span>
                      </span>
                    </div>
                  );
                })
              ) : (
                <span className='text-xs text-gray-400 dark:text-gray-500'>
                  {group.items ? group.empty : en ? 'Unavailable' : '排名数据不足'}
                </span>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className='mt-2.5 pt-2 border-t border-gray-100 dark:border-gray-800/80 text-[11px] text-gray-400 dark:text-gray-500'>
          {en ? 'Same-day constituent ranking unavailable' : '当日成分股排名数据不足'}
        </div>
      )}

      <div className='flex items-center justify-between gap-2 mt-2.5 pt-2 border-t border-gray-100 dark:border-gray-800/80 text-[11px] text-gray-500 dark:text-gray-400'>
        <a
          href={sectorUrl(s.code)}
          target='_blank'
          rel='noopener noreferrer'
          className='inline-flex items-center gap-1 text-blue-600 dark:text-blue-400 hover:underline'
        >
          <LinkOutlined className='text-[10px]' />
          {en ? 'Eastmoney' : '东方财富'}
        </a>
        <span className='tabular-nums'>{formatTimestamp(q.as_of) || q.day}</span>
      </div>
    </div>
  );
}

function CompactListingRow({
  row,
  en,
  detail,
}: {
  row: StockQuoteRow;
  en: boolean;
  detail?: string | null;
}) {
  const q = row.quote!;
  const label = listingLabel(q.listing);
  const tone = toneStyle(changeTone(q.percent), en);
  const unit = unitLabel(q.listing.currency, q.listing.asset_type, en);
  const focusValue = detail ? formatRecallFieldValue(row, detail, en) : null;
  const focusTitle = detail ? detailLabel(detail, en) : '';
  const isUnconfirmedClose = detail === 'close' && row.verification?.status !== 'confirmed';
  const unconfirmedCloseNote = isUnconfirmedClose
    ? row.verification?.reason
      ? reasonLabel(row.verification.reason, en)
      : en
        ? 'Close pending'
        : '收盘待确认'
    : '';

  return (
    <div
      data-testid={`quote-compact-${label}`}
      className='rounded-lg border border-gray-200/80 dark:border-gray-800 bg-white dark:bg-[#1a1b20] px-3 py-2 flex flex-wrap items-center justify-between gap-2'
    >
      <div className='flex items-center gap-2 min-w-0 flex-wrap'>
        <span className='text-xs font-semibold text-gray-900 dark:text-gray-100'>{q.listing.name}</span>
        <span className='text-[11px] font-mono px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300'>
          {label}
        </span>
        {focusValue !== null ? (
          <span className='inline-flex items-baseline gap-1.5 text-xs'>
            <span className='text-gray-500 dark:text-gray-400'>
              {isUnconfirmedClose
                ? en
                  ? `Latest (${unconfirmedCloseNote})`
                  : `最近报价（${unconfirmedCloseNote}）`
                : focusTitle}
            </span>
            <span className='font-bold text-gray-900 dark:text-gray-100 tabular-nums'>{focusValue}</span>
          </span>
        ) : (
          <span className='inline-flex items-baseline gap-1.5 tabular-nums'>
            <span className={`text-sm font-bold ${tone.text}`}>{formatNumber(q.last)}</span>
            <span className='text-[11px] text-gray-400'>{unit}</span>
            <span className={`text-[11px] font-semibold px-1.5 py-0.5 rounded border ${tone.pill}`}>
              {formatSigned(q.percent, true)}
            </span>
          </span>
        )}
      </div>
      <div className='flex items-center gap-2 text-[11px] text-gray-400 dark:text-gray-500 tabular-nums shrink-0'>
        <span>{formatTimestamp(q.as_of) || q.day}</span>
        <a
          href={displayQuoteUrl(q.url, q.listing)}
          target='_blank'
          rel='noopener noreferrer'
          className='inline-flex items-center gap-0.5 text-blue-600 dark:text-blue-400 hover:underline'
        >
          <span>{q.source}</span>
          <LinkOutlined className='text-[10px]' />
        </a>
      </div>
    </div>
  );
}

function CandidateRow({
  row,
  en,
  interactive,
  busy,
  onSelectCandidate,
}: {
  row: StockQuoteRow;
  en: boolean;
  interactive: boolean;
  busy: boolean;
  onSelectCandidate?: (choice: string) => void;
}) {
  const sectors = row.sector_candidates || [];
  const listings = row.candidates || [];
  const hasAction = !!onSelectCandidate;
  const canClick = interactive && !busy && hasAction;

  return (
    <div
      data-testid={`quote-choose-${row.requested}`}
      className='rounded-lg border border-blue-200/80 dark:border-blue-900/60 bg-blue-50/40 dark:bg-blue-950/20 p-3'
    >
      <div className='text-xs font-medium text-gray-800 dark:text-gray-200 mb-2'>
        {sectors.length > 0
          ? en
            ? hasAction
              ? `"${row.requested}" covers multiple A-share sectors — choose one:`
              : `"${row.requested}" candidate A-share sectors:`
            : hasAction
              ? `「${row.requested}」涵盖多个 A 股板块，请选择：`
              : `「${row.requested}」候选 A 股板块：`
          : en
            ? hasAction
              ? `"${row.requested}" matches multiple listings — choose one:`
              : `"${row.requested}" candidate listings:`
            : hasAction
              ? `「${row.requested}」匹配多个上市地，请选择：`
              : `「${row.requested}」候选上市地：`}
      </div>
      <div className='flex flex-wrap gap-2'>
        {sectors.map(item => {
          const choice = `${item.name}（${item.code}）`;
          if (!hasAction) {
            return (
              <span
                key={item.code}
                className='inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border border-blue-200/70 dark:border-blue-800/70 bg-white/80 dark:bg-[#1a1b20] text-gray-700 dark:text-gray-200'
              >
                <span>{item.name}</span>
                <span className='text-[11px] font-mono text-gray-400 dark:text-gray-500'>{item.code}</span>
              </span>
            );
          }
          return (
            <button
              key={item.code}
              type='button'
              disabled={!canClick}
              onClick={() => onSelectCandidate?.(choice)}
              className='inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border border-blue-200 dark:border-blue-800 bg-white dark:bg-[#1a1b20] text-blue-700 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-950/50 disabled:opacity-60 disabled:cursor-default transition-colors'
            >
              <span>{item.name}</span>
              <span className='text-[11px] font-mono text-gray-400 dark:text-gray-500'>{item.code}</span>
            </button>
          );
        })}
        {listings.map(item => {
          const code = listingLabel(item);
          const choice = `${item.name} ${code}`;
          if (!hasAction) {
            return (
              <span
                key={code}
                className='inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border border-blue-200/70 dark:border-blue-800/70 bg-white/80 dark:bg-[#1a1b20] text-gray-700 dark:text-gray-200'
              >
                <span>{item.name}</span>
                <span className='text-[11px] font-mono text-gray-500 dark:text-gray-400'>{code}</span>
                {item.currency && <span className='text-[10px] text-gray-400'>{item.currency}</span>}
              </span>
            );
          }
          return (
            <button
              key={code}
              type='button'
              disabled={!canClick}
              onClick={() => onSelectCandidate?.(choice)}
              className='inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border border-blue-200 dark:border-blue-800 bg-white dark:bg-[#1a1b20] text-blue-700 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-950/50 disabled:opacity-60 disabled:cursor-default transition-colors'
            >
              <span>{item.name}</span>
              <span className='text-[11px] font-mono text-gray-500 dark:text-gray-400'>{code}</span>
              {item.currency && <span className='text-[10px] text-gray-400'>{item.currency}</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function rowDedupKey(row: StockQuoteRow): string {
  if (row.quote) return `listing:${listingLabel(row.quote.listing)}`;
  if (row.sector) return `sector:${row.sector.code}`;
  if (row.sector_candidates?.length) {
    return `sector_choose:${row.sector_candidates.map(s => s.code).join(',')}`;
  }
  if (row.candidates?.length) {
    return `listing_choose:${row.candidates.map(listingLabel).join(',')}`;
  }
  return `raw:${row.outcome}:${row.requested.trim().toLowerCase()}`;
}

function dedupeQuoteRows(rows: StockQuoteRow[]): StockQuoteRow[] {
  const seen = new Set<string>();
  return rows.filter(row => {
    const key = rowDedupKey(row);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

const StockQuoteCard: React.FC<StockQuoteCardProps> = ({
  snapshot,
  language = 'zh',
  busy = false,
  interactive = false,
  onSelectCandidate,
  onRefresh,
}) => {
  const en = language.toLowerCase().startsWith('en');
  const isCompact = snapshot.display_mode === 'compact';
  const rawDisplayRows =
    isCompact && Array.isArray(snapshot.recall_indices) && snapshot.recall_indices.length > 0
      ? snapshot.recall_indices.map(idx => snapshot.rows[idx]).filter((r): r is StockQuoteRow => Boolean(r))
      : snapshot.rows;
  const rows = dedupeQuoteRows(rawDisplayRows);

  // Hide quote card completely when every row failed/unavailable.
  if (rows.length === 0 || rows.every(r => r.outcome === 'unavailable')) {
    return null;
  }

  const indexRows = rows.filter(r => r.outcome === 'quoted' && r.quote && r.kind === 'index');
  const stockRows = rows.filter(r => r.outcome === 'quoted' && r.quote && r.kind !== 'index');
  const sectorRows = rows.filter(r => r.outcome === 'quoted' && r.sector && r.sector_quote);
  const chooseRows = rows.filter(r => r.outcome === 'choose');
  const unavailableRows = rows.filter(r => r.outcome === 'unavailable');
  const hasQuoted = indexRows.length + stockRows.length + sectorRows.length > 0;
  const recallDetail = snapshot.recall_detail || null;

  if (isCompact) {
    const compactListings = [...indexRows, ...stockRows];
    return (
      <section
        data-testid='stock-quote-card'
        data-compact='true'
        aria-label={en ? 'Recalled quote snapshot' : '历史行情快照回看'}
        className='mt-3 mx-1 rounded-xl border border-gray-200/90 dark:border-gray-800 bg-[#fafafa] dark:bg-[#141519] overflow-hidden'
      >
        <div className='flex items-center justify-between gap-2 px-3 py-2 border-b border-gray-200/70 dark:border-gray-800 bg-white/80 dark:bg-[#18191e]'>
          <div className='flex items-center gap-2 min-w-0'>
            <HistoryOutlined className='text-blue-600 dark:text-blue-400 text-xs shrink-0' />
            <span className='text-xs font-semibold text-gray-800 dark:text-gray-100'>
              {en ? 'Recalled Snapshot' : '快照回看'}
            </span>
            {recallDetail && (
              <span className='text-[11px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300'>
                {detailLabel(recallDetail, en)}
              </span>
            )}
            <span className='text-[11px] text-gray-400 dark:text-gray-500 tabular-nums truncate'>
              {en ? 'Beijing ' : '北京时间 '}
              {formatTimestamp(snapshot.queried_at)}
            </span>
          </div>
          {interactive && onRefresh && hasQuoted && (
            <button
              type='button'
              disabled={busy}
              onClick={() => onRefresh(buildRefreshPrompt(snapshot, en, rows))}
              className='inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-50 transition-colors shrink-0'
            >
              <ReloadOutlined spin={busy} className='text-[11px]' />
              {en ? 'Refresh' : '刷新行情'}
            </button>
          )}
        </div>

        <div className='p-2.5 flex flex-col gap-2'>
          {compactListings.map((row, idx) => (
            <CompactListingRow
              key={`compact-${listingLabel(row.quote!.listing)}-${idx}`}
              row={row}
              en={en}
              detail={recallDetail}
            />
          ))}
          {sectorRows.map((row, idx) => (
            <SectorCard
              key={`compact-sector-${row.sector!.code}-${idx}`}
              row={row}
              en={en}
              focusDetail={recallDetail}
            />
          ))}
        </div>
      </section>
    );
  }

  return (
    <section
      data-testid='stock-quote-card'
      aria-label={en ? 'Market quote snapshot' : '实时行情快照'}
      className='mt-3 mx-1 rounded-xl border border-gray-200/90 dark:border-gray-800 bg-[#fafafa] dark:bg-[#141519] overflow-hidden'
    >
      <div className='flex items-center justify-between gap-2 px-3.5 py-2.5 border-b border-gray-200/70 dark:border-gray-800 bg-white/80 dark:bg-[#18191e]'>
        <div className='flex items-center gap-2 min-w-0'>
          <StockOutlined className='text-blue-600 dark:text-blue-400 text-sm shrink-0' />
          <span className='text-xs font-semibold text-gray-800 dark:text-gray-100'>
            {en ? 'Market Snapshot' : '行情快照'}
          </span>
          <span className='text-[11px] text-gray-400 dark:text-gray-500 tabular-nums truncate'>
            {en ? 'Beijing ' : '北京时间 '}
            {formatTimestamp(snapshot.queried_at)}
          </span>
        </div>
        {interactive && onRefresh && hasQuoted && (
          <button
            type='button'
            disabled={busy}
            onClick={() => onRefresh(buildRefreshPrompt(snapshot, en))}
            className='inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-50 transition-colors shrink-0'
          >
            <ReloadOutlined spin={busy} className='text-[11px]' />
            {en ? 'Refresh' : '刷新行情'}
          </button>
        )}
      </div>

      <div className='p-3 flex flex-col gap-2.5'>
        {indexRows.length > 0 && (
          <div className='grid grid-cols-1 sm:grid-cols-3 gap-2'>
            {indexRows.map((row, idx) => (
              <IndexTile key={`${row.requested}-${idx}`} row={row} en={en} />
            ))}
          </div>
        )}

        {sectorRows.map((row, idx) => (
          <SectorCard key={`${row.sector!.code}-${idx}`} row={row} en={en} />
        ))}

        {stockRows.map((row, idx) => (
          <ListingCard key={`${row.quote!.listing.code}-${idx}`} row={row} en={en} />
        ))}

        {chooseRows.map((row, idx) => (
          <CandidateRow
            key={`choose-${row.requested}-${idx}`}
            row={row}
            en={en}
            interactive={interactive}
            busy={busy}
            onSelectCandidate={onSelectCandidate}
          />
        ))}

        {unavailableRows.map((row, idx) => (
          <div
            key={`unavail-${row.requested}-${idx}`}
            className='flex items-center gap-2 rounded-lg border border-gray-200/80 dark:border-gray-800 bg-white/70 dark:bg-[#1a1b20] px-3 py-2 text-xs text-gray-500 dark:text-gray-400'
          >
            <ExclamationCircleOutlined className='text-amber-500 shrink-0' />
            <span className='font-medium text-gray-700 dark:text-gray-200'>{row.requested}</span>
            <span>·</span>
            <span>{reasonLabel(row.reason, en)}</span>
          </div>
        ))}
      </div>

      <div className='px-3.5 py-1.5 border-t border-gray-200/60 dark:border-gray-800/80 text-[10px] text-gray-400 dark:text-gray-500'>
        {en
          ? 'Public market feed snapshot for reference only; not investment advice.'
          : '数据来自公开行情接口，快照仅供参考，不构成投资建议。'}
      </div>
    </section>
  );
};

export default StockQuoteCard;
