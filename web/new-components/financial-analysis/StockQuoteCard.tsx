import {
  CheckCircleFilled,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  LinkOutlined,
  ReloadOutlined,
  StockOutlined,
} from '@ant-design/icons';
import React from 'react';
import {
  buildRefreshPrompt,
  changeTone,
  CLOSED_LIKE_PHASES,
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

const TONE_TEXT = {
  up: 'text-[#dc2626] dark:text-[#f87171]',
  down: 'text-[#16a34a] dark:text-[#4ade80]',
  flat: 'text-gray-600 dark:text-gray-400',
};

const TONE_PILL = {
  up: 'bg-red-50 text-[#dc2626] border-red-200/80 dark:bg-red-950/40 dark:text-[#f87171] dark:border-red-900/60',
  down: 'bg-emerald-50 text-[#16a34a] border-emerald-200/80 dark:bg-emerald-950/40 dark:text-[#4ade80] dark:border-emerald-900/60',
  flat: 'bg-gray-100 text-gray-600 border-gray-200 dark:bg-gray-800/70 dark:text-gray-300 dark:border-gray-700',
};

function IndexTile({ row, en }: { row: StockQuoteRow; en: boolean }) {
  const q = row.quote!;
  const tone = changeTone(q.percent);
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
        <span className={`text-base font-bold tabular-nums tracking-tight ${TONE_TEXT[tone]}`}>
          {formatNumber(q.last)}
        </span>
        <span className={`text-xs font-semibold tabular-nums px-1.5 py-0.5 rounded border ${TONE_PILL[tone]}`}>
          {formatSigned(q.percent, true)}
        </span>
      </div>
      <div className='flex items-center justify-between text-[11px] text-gray-500 dark:text-gray-400 tabular-nums'>
        <span className={TONE_TEXT[tone]}>{formatSigned(q.change)}</span>
        <a
          href={q.url}
          target='_blank'
          rel='noopener noreferrer'
          className='inline-flex items-center gap-0.5 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors'
        >
          <span>{q.source}</span>
          <LinkOutlined className='text-[10px]' />
        </a>
      </div>
    </div>
  );
}

function ListingCard({ row, en }: { row: StockQuoteRow; en: boolean }) {
  const q = row.quote!;
  const v = row.verification;
  const tone = changeTone(q.percent);
  const label = listingLabel(q.listing);
  const unit = unitLabel(q.listing.currency, q.listing.asset_type, en);
  const isConfirmedClose = v?.status === 'confirmed';
  const isClosePending = !isConfirmedClose && q.listing.asset_type !== 'index' && CLOSED_LIKE_PHASES.has(row.phase || '');
  const turnoverCurrency = q.listing.currency || (q.listing.market === 'hk' ? 'HKD' : 'CNY');

  const metrics: Array<{ label: string; value: string }> = [
    { label: en ? 'Prev' : '前收', value: formatNumber(q.previous) },
    { label: en ? 'Open' : '今开', value: formatNumber(q.opening) },
    { label: en ? 'High' : '最高', value: formatNumber(q.high) },
    { label: en ? 'Low' : '最低', value: formatNumber(q.low) },
    { label: en ? 'Amp' : '振幅', value: toFiniteNumber(q.amplitude) !== null ? `${formatNumber(q.amplitude)}%` : '—' },
    { label: en ? 'Turnover' : '成交额', value: formatTurnover(q.turnover, turnoverCurrency, en) },
  ];
  if (toFiniteNumber(q.turnover_rate) !== null) {
    metrics.push({ label: en ? 'Turn.' : '换手率', value: `${formatNumber(q.turnover_rate)}%` });
  }
  if (toFiniteNumber(q.market_cap) !== null) {
    metrics.push({
      label: en ? 'Mkt Cap' : '总市值',
      value: en ? `${formatNumber(q.market_cap)} × 100M` : `${formatNumber(q.market_cap)} 亿`,
    });
  }
  if (toFiniteNumber(q.pe) !== null) {
    metrics.push({ label: 'PE', value: formatNumber(q.pe) });
  }
  if (toFiniteNumber(q.pb) !== null) {
    metrics.push({ label: 'PB', value: formatNumber(q.pb) });
  }

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
            <span className={`text-xl font-bold tabular-nums tracking-tight ${TONE_TEXT[tone]}`}>
              {formatNumber(q.last)}
            </span>
            <span className='text-xs text-gray-500 dark:text-gray-400'>{unit}</span>
            <span className={`text-xs font-medium tabular-nums ${TONE_TEXT[tone]}`}>{formatSigned(q.change)}</span>
            <span className={`text-xs font-semibold tabular-nums px-2 py-0.5 rounded-full border ${TONE_PILL[tone]}`}>
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

      <div className='flex flex-wrap items-center justify-between gap-2 mt-2.5 pt-2 border-t border-gray-100 dark:border-gray-800/80 text-[11px] text-gray-500 dark:text-gray-400'>
        <div className='flex items-center gap-2 flex-wrap'>
          <a
            href={q.url}
            target='_blank'
            rel='noopener noreferrer'
            className='inline-flex items-center gap-1 text-blue-600 dark:text-blue-400 hover:underline'
          >
            <LinkOutlined className='text-[10px]' />
            {q.source}
          </a>
          {v?.url && v.url !== q.url && (
            <a
              href={v.url}
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
          <span className='text-amber-600 dark:text-amber-400'>
            {v.other_source}: {formatNumber(v.other_price)}
          </span>
        )}
      </div>
    </div>
  );
}

function SectorCard({ row, en }: { row: StockQuoteRow; en: boolean }) {
  const s = row.sector!;
  const q = row.sector_quote!;
  const tone = changeTone(q.percent);
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
        <span className={`text-sm font-bold tabular-nums px-2.5 py-0.5 rounded-full border ${TONE_PILL[tone]}`}>
          {formatSigned(q.percent, true)}
        </span>
      </div>

      {hasBreadth && (
        <div className='mt-3'>
          <div className='h-1.5 w-full rounded-full overflow-hidden flex bg-gray-200 dark:bg-gray-700'>
            {up > 0 && <div className='bg-[#dc2626] dark:bg-[#f87171]' style={{ width: `${(up / breadthTotal) * 100}%` }} />}
            {flat > 0 && <div className='bg-gray-400 dark:bg-gray-500' style={{ width: `${(flat / breadthTotal) * 100}%` }} />}
            {down > 0 && (
              <div className='bg-[#16a34a] dark:bg-[#4ade80]' style={{ width: `${(down / breadthTotal) * 100}%` }} />
            )}
          </div>
          <div className='flex flex-wrap items-center justify-between gap-2 mt-1.5 text-[11px] tabular-nums'>
            <div className='flex items-center gap-3'>
              <span className='text-[#dc2626] dark:text-[#f87171] font-medium'>
                {en ? `Up ${up}` : `上涨 ${up} 家`}
              </span>
              <span className='text-gray-500 dark:text-gray-400'>{en ? `Flat ${flat}` : `平盘 ${flat} 家`}</span>
              <span className='text-[#16a34a] dark:text-[#4ade80] font-medium'>
                {en ? `Down ${down}` : `下跌 ${down} 家`}
              </span>
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

      {(q.gainers || q.losers) && (
        <div className='grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3 pt-2.5 border-t border-gray-100 dark:border-gray-800/80'>
          {(
            [
              { title: en ? 'Top gainers' : '领涨个股', items: q.gainers, empty: en ? 'None' : '无上涨个股' },
              { title: en ? 'Top decliners' : '领跌个股', items: q.losers, empty: en ? 'None' : '无下跌个股' },
            ] as const
          ).map(group => (
            <div key={group.title} className='flex flex-col gap-1'>
              <span className='text-[11px] font-medium text-gray-500 dark:text-gray-400'>{group.title}</span>
              {group.items && group.items.length > 0 ? (
                group.items.map(mover => {
                  const moverTone = changeTone(mover.percent);
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
                        <span className={`font-semibold ${TONE_TEXT[moverTone]}`}>
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
  const canClick = interactive && !busy && !!onSelectCandidate;

  return (
    <div
      data-testid={`quote-choose-${row.requested}`}
      className='rounded-lg border border-blue-200/80 dark:border-blue-900/60 bg-blue-50/40 dark:bg-blue-950/20 p-3'
    >
      <div className='text-xs font-medium text-gray-800 dark:text-gray-200 mb-2'>
        {sectors.length > 0
          ? en
            ? `"${row.requested}" covers multiple A-share sectors — choose one:`
            : `「${row.requested}」涵盖多个 A 股板块，请选择：`
          : en
            ? `"${row.requested}" matches multiple listings — choose one:`
            : `「${row.requested}」匹配多个上市地，请选择：`}
      </div>
      <div className='flex flex-wrap gap-2'>
        {sectors.map(item => {
          const choice = `${item.name}（${item.code}）`;
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

const StockQuoteCard: React.FC<StockQuoteCardProps> = ({
  snapshot,
  language = 'zh',
  busy = false,
  interactive = false,
  onSelectCandidate,
  onRefresh,
}) => {
  const en = language.toLowerCase().startsWith('en');
  const indexRows = snapshot.rows.filter(r => r.outcome === 'quoted' && r.quote && r.kind === 'index');
  const stockRows = snapshot.rows.filter(r => r.outcome === 'quoted' && r.quote && r.kind !== 'index');
  const sectorRows = snapshot.rows.filter(r => r.outcome === 'quoted' && r.sector && r.sector_quote);
  const chooseRows = snapshot.rows.filter(r => r.outcome === 'choose');
  const unavailableRows = snapshot.rows.filter(r => r.outcome === 'unavailable');

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
        {interactive && onRefresh && (
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
