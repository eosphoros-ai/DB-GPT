import type { DashboardVisualization } from '@/types/dashboard';
import { useState } from 'react';
import styles from './DashboardShowcase.module.css';

/** Wall displays need legible plots even in 180px panels. Numeric scales start
 * at zero; sparse labels never remove data points. Full values remain focusable. */
export default function DashboardWallChart({
  kind,
  data,
  xField,
  yField,
  seriesField,
  format,
  colors,
  width,
  height,
  onSelect,
}: {
  kind: DashboardVisualization;
  data: Record<string, unknown>[];
  xField: string;
  yField: string;
  seriesField?: string | null;
  format: (value: unknown) => string;
  colors: string[];
  width: number;
  height: number;
  onSelect?: (datum: Record<string, unknown>) => void;
}) {
  const [hover, setHover] = useState('');
  const w = Math.max(180, width),
    h = Math.max(64, height - 18);
  const values = data.map(d => Number(d[yField]));
  const maximum = Math.max(1, ...values);
  const color = (i: number) => colors[i % colors.length];
  const categories = [...new Set(data.map(d => String(d[xField] ?? '')))];
  const series = seriesField ? [...new Set(data.map(d => String(d[seriesField] ?? '')))] : [''];
  const title = (datum: Record<string, unknown>) =>
    `${String(datum[xField] ?? '')}${seriesField ? ' · ' + datum[seriesField] : ''}：${format(datum[yField])}`;
  const events = (datum: Record<string, unknown>) => ({
    tabIndex: 0,
    role: onSelect ? 'button' : 'img',
    'aria-label': title(datum),
    onMouseEnter: () => setHover(title(datum)),
    onMouseLeave: () => setHover(''),
    onFocus: () => setHover(title(datum)),
    onBlur: () => setHover(''),
    onClick: (e: React.MouseEvent) => {
      e.stopPropagation();
      onSelect?.(datum);
    },
    onKeyDown: (e: React.KeyboardEvent) => {
      if (onSelect && ['Enter', ' '].includes(e.key)) {
        e.preventDefault();
        e.stopPropagation();
        onSelect(datum);
      }
    },
  });
  let plot;
  if (kind === 'gauge') {
    const current = Number(data[0]?.[yField]);
    const radius = Math.min(w * 0.32, h * 0.37),
      cx = w / 2,
      cy = h * 0.46;
    const circumference = 2 * Math.PI * radius;
    plot = (
      <>
        <circle cx={cx} cy={cy} r={radius} fill='none' stroke='var(--dashboard-theme-border)' strokeWidth='9' />
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill='none'
          stroke={color(0)}
          strokeWidth='9'
          strokeLinecap='round'
          strokeDasharray={`${Math.min(1, Math.max(0, current / 100)) * circumference} ${circumference}`}
          transform={`rotate(-90 ${cx} ${cy})`}
        />
        <text x={cx} y={cy + 6} textAnchor='middle' fontSize='24' fontWeight='600' fill='var(--dashboard-theme-text)'>
          {format(current)}
        </text>
        <text x={cx} y={h - 6} textAnchor='middle' fontSize='10' fill='var(--dashboard-theme-muted)'>
          当前比例 · 百分比刻度 0–100
        </text>
      </>
    );
  } else if (kind === 'donut' || kind === 'pie') {
    const total = values.reduce((a, b) => a + b, 0),
      r = Math.min(w * 0.22, h * 0.33),
      cx = w * 0.32,
      cy = h * 0.49;
    const point = (a: number) => [cx + Math.cos(a) * r, cy + Math.sin(a) * r];
    plot = (
      <>
        {data.map((d, i) => {
          const fraction = total > 0 ? Number(d[yField]) / total : 0;
          const angle =
            -Math.PI / 2 + (total > 0 ? values.slice(0, i).reduce((a, b) => a + b, 0) / total : 0) * Math.PI * 2;
          const start = point(angle);
          const end = point(angle + fraction * Math.PI * 2);
          return (
            <g key={i} {...events(d)}>
              {fraction >= 0.99999 ? (
                <circle cx={cx} cy={cy} r={r} fill={color(i)} />
              ) : (
                <path
                  d={`M ${cx} ${cy} L ${start} A ${r} ${r} 0 ${fraction > 0.5 ? 1 : 0} 1 ${end} Z`}
                  fill={color(i)}
                  stroke='var(--dashboard-theme-card)'
                  strokeWidth='2'
                />
              )}
              <title>{title(d)}</title>
            </g>
          );
        })}
        {kind === 'donut' && <circle cx={cx} cy={cy} r={r * 0.68} fill='var(--dashboard-theme-card)' />}
        {data.map((d, i) => (
          <g key={i} {...events(d)}>
            <rect
              x={w * 0.59}
              y={h * 0.5 + (i - (data.length - 1) / 2) * 25 - 7}
              width='6'
              height='6'
              rx='1'
              fill={color(i)}
            />
            <text
              x={w * 0.59 + 12}
              y={h * 0.5 + (i - (data.length - 1) / 2) * 25}
              fill='var(--dashboard-theme-text)'
              fontSize='10'
            >
              {String(d[xField]).slice(0, 8)}{' '}
              <tspan fill='var(--dashboard-theme-muted)'>
                {total ? ((Number(d[yField]) / total) * 100).toFixed(0) : '0'}%
              </tspan>
            </text>
            <title>{title(d)}</title>
          </g>
        ))}
      </>
    );
  } else if (kind === 'bar') {
    const left = Math.min(86, w * 0.28),
      right = 65,
      inner = w - left - right;
    const step = (h - 20) / Math.max(1, data.length),
      bar = Math.max(3, Math.min(18, step * 0.58));
    plot = (
      <>
        {data.map((d, i) => (
          <g key={i} {...events(d)}>
            <text
              x={left - 8}
              y={12 + i * step + bar * 0.75}
              textAnchor='end'
              fontSize='10'
              fill='var(--dashboard-theme-muted)'
            >
              {String(d[xField]).slice(0, 7)}
            </text>
            <rect
              x={left}
              y={10 + i * step}
              width={inner}
              height={bar}
              rx='2'
              fill='var(--dashboard-theme-border)'
              fillOpacity='.45'
            />
            <rect
              x={left}
              y={10 + i * step}
              width={Math.max(0, Number(d[yField]) / maximum) * inner}
              height={bar}
              rx='2'
              fill={color(0)}
            />
            <text
              x={w - 3}
              y={12 + i * step + bar * 0.75}
              textAnchor='end'
              fontSize='9'
              fill='var(--dashboard-theme-text)'
            >
              {format(d[yField])}
            </text>
            <title>{title(d)}</title>
          </g>
        ))}
      </>
    );
  } else {
    const left = Math.min(94, Math.max(48, format(maximum).length * 6 + 8)),
      right = 20,
      top = series.length > 1 ? 26 : 12,
      bottom = 25;
    const iw = Math.max(30, w - left - right),
      ih = Math.max(25, h - top - bottom);
    const column = kind === 'column',
      step = iw / Math.max(1, categories.length);
    const x = (index: number) =>
      left + (column ? (index + 0.5) * step : (index * iw) / Math.max(1, categories.length - 1));
    const y = (value: number) => top + ih - (value / maximum) * ih;
    const stride = Math.max(1, Math.ceil(categories.length / (iw / 55)));
    plot = (
      <>
        {[0, 0.5, 1].map(t => (
          <g key={t}>
            <path
              d={`M ${left} ${y(maximum * t)} H ${w - right}`}
              stroke='var(--dashboard-theme-border)'
              strokeDasharray='3 4'
            />
            <text x={left - 6} y={y(maximum * t) + 3} textAnchor='end' fontSize='9' fill='var(--dashboard-theme-muted)'>
              {format(maximum * t)}
            </text>
          </g>
        ))}
        {categories.map((c, i) =>
          i % stride === 0 || i === categories.length - 1 ? (
            <text key={c} x={x(i)} y={h - 5} textAnchor='middle' fontSize='9' fill='var(--dashboard-theme-muted)'>
              {/^\d{4}-\d{2}$/.test(c) ? c.slice(2) : c.slice(0, 6)}
            </text>
          ) : null,
        )}
        {series.map((name, index) => {
          const points = data.filter(d => !seriesField || String(d[seriesField]) === name);
          const line = points
            .map(d => `${x(categories.indexOf(String(d[xField])))} ${y(Number(d[yField]))}`)
            .join(' L ');
          return (
            <g key={name}>
              {series.length > 1 && (
                <>
                  <circle cx={left + index * (iw / series.length)} cy='7' r='3' fill={color(index)} />
                  <text
                    x={left + 7 + index * (iw / series.length)}
                    y='10'
                    fill='var(--dashboard-theme-muted)'
                    fontSize='10'
                  >
                    {name}
                  </text>
                </>
              )}
              {kind === 'area' && points.length > 0 && (
                <path
                  d={`M ${x(0)} ${y(0)} L ${line} L ${x(categories.length - 1)} ${y(0)} Z`}
                  fill={color(index)}
                  fillOpacity='.13'
                />
              )}
              {!column && <path d={'M ' + line} fill='none' stroke={color(index)} strokeWidth='1.7' />}
              {points.map((d, i) => (
                <g key={i} {...events(d)}>
                  {column ? (
                    <rect
                      x={x(i) - step * 0.3}
                      y={y(Number(d[yField]))}
                      width={step * 0.6}
                      height={Math.max(0, y(0) - y(Number(d[yField])))}
                      rx='2'
                      fill={color(index)}
                    />
                  ) : (
                    <>
                      <circle
                        cx={x(categories.indexOf(String(d[xField])))}
                        cy={y(Number(d[yField]))}
                        r='7'
                        fill='transparent'
                      />
                      <circle
                        cx={x(categories.indexOf(String(d[xField])))}
                        cy={y(Number(d[yField]))}
                        r='2.3'
                        fill={color(index)}
                      />
                    </>
                  )}
                  <title>{title(d)}</title>
                </g>
              ))}
            </g>
          );
        })}
      </>
    );
  }
  return (
    <div className={styles.wallChart}>
      <svg width='100%' height={h} viewBox={`0 0 ${w} ${h}`} role='img' aria-label='数据图表'>
        {plot}
      </svg>
      <div className={styles.plotTooltip} aria-live='polite'>
        {hover || '\u00a0'}
      </div>
    </div>
  );
}
