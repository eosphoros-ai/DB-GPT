import { useId } from 'react';

export interface TemplatePreviewData {
  title: string;
  metric: string;
  unit: string;
  total: number;
  trend: { label: string; value: number }[];
  ranking: { label: string; value: number }[];
  segments: { label: string; value: number }[];
}
const number = (value: number) =>
  new Intl.NumberFormat('zh-CN', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
/** Tiny charts from the verified query result, not a screenshot of an empty editor. */
export default function DashboardTemplatePreview({ data }: { data: TemplatePreviewData }) {
  const gradientId = useId().replaceAll(':', '');
  const max = Math.max(1, ...data.trend.map(p => p.value));
  const points = data.trend
    .map((p, i) => `${227 + (i * 283) / Math.max(1, data.trend.length - 1)},${147 - (p.value / max) * 61}`)
    .join(' ');
  const ranking = data.ranking.slice(0, 5);
  const rankMax = Math.max(1, ...ranking.map(p => p.value));
  const segments = data.segments.slice(0, 4);
  const sum = Math.max(
    1,
    segments.reduce((total, p) => total + p.value, 0),
  );
  const colors = ['var(--app-accent)', 'var(--app-success)', 'var(--app-warning)', 'var(--app-muted)'];
  return (
    <svg
      viewBox='0 0 560 350'
      role='img'
      aria-label={`${data.title}，${data.metric} ${number(data.total)}${data.unit}，已验证数据预览`}
    >
      <defs>
        <linearGradient id={gradientId} x1='0' y1='0' x2='0' y2='1'>
          <stop offset='0' stopColor='var(--app-accent)' stopOpacity='.25' />
          <stop offset='1' stopColor='var(--app-accent)' stopOpacity='0' />
        </linearGradient>
      </defs>
      <rect width='560' height='350' rx='15' fill='var(--app-surface-muted)' />
      <circle cx='26' cy='25' r='5' fill='var(--app-accent)' />
      <text x='40' y='30' fontSize='14' fontWeight='600' fill='var(--app-text)'>
        {data.title}
      </text>
      <text x='536' y='29' fontSize='10' fill='var(--app-muted)' textAnchor='end'>
        DB-GPT / DATA
      </text>
      <rect x='20' y='51' width='173' height='114' rx='10' fill='var(--app-accent-soft)' />
      <text x='36' y='77' fontSize='12' fill='var(--app-muted)'>
        {data.metric}
      </text>
      <text x='36' y='117' fontSize='30' fontWeight='700' fill='var(--app-text)'>
        {number(data.total)}
      </text>
      <text x='36' y='145' fontSize='11' fill='var(--app-muted)'>
        {data.unit} · 全部年份
      </text>
      <rect x='206' y='51' width='334' height='114' rx='10' fill='var(--app-surface)' />
      <text x='223' y='77' fontSize='12' fill='var(--app-text)'>
        月度趋势
      </text>
      <path d={`M227 150 L${points} L510 150 Z`} fill={`url(#${gradientId})`} />
      <polyline points={points} fill='none' stroke='var(--app-accent)' strokeWidth='2.3' />
      <rect x='20' y='178' width='291' height='151' rx='10' fill='var(--app-surface)' />
      <text x='36' y='201' fontSize='12' fill='var(--app-text)'>
        贡献排行
      </text>
      {ranking.map((p, i) => (
        <g key={p.label}>
          <text x='36' y={221 + i * 21} fontSize='10' fill='var(--app-muted)'>
            {p.label.slice(0, 11)}
          </text>
          <rect
            x='119'
            y={213 + i * 21}
            width={Math.max(2, (p.value / rankMax) * 124)}
            height='8'
            rx='3'
            fill={colors[i % colors.length]}
          />
          <text x='295' y={221 + i * 21} textAnchor='end' fontSize='10' fill='var(--app-muted)'>
            {number(p.value)}
          </text>
        </g>
      ))}
      <rect x='324' y='178' width='216' height='151' rx='10' fill='var(--app-surface)' />
      <text x='340' y='201' fontSize='12' fill='var(--app-text)'>
        主要分类
      </text>
      {segments.map((p, i) => {
        const length = (p.value / sum) * 226;
        const offset = (segments.slice(0, i).reduce((total, segment) => total + segment.value, 0) / sum) * 226;
        return (
          <g key={p.label}>
            <circle
              cx='378'
              cy='265'
              r='36'
              fill='none'
              stroke={colors[i]}
              strokeWidth='11'
              strokeDasharray={`${length} ${226 - length}`}
              strokeDashoffset={-offset}
              transform='rotate(-90 378 265)'
            />
            <rect x='434' y={223 + i * 22} width='6' height='6' rx='2' fill={colors[i]} />
            <text x='447' y={230 + i * 22} fontSize='10' fill='var(--app-muted)'>
              {p.label.slice(0, 9)}
            </text>
          </g>
        );
      })}
      <text x='378' y='269' textAnchor='middle' fontSize='10' fill='var(--app-muted)'>
        前 {segments.length} 类
      </text>
    </svg>
  );
}
