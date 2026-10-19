import type { DashboardVisualization } from '@/types/dashboard';
import { Empty } from 'antd';
import { useState, type CSSProperties, type SVGProps } from 'react';
import type { DashboardThemeTokens } from './dashboard-appearance';
import {
  countries,
  mapCountryData,
  numericChartData,
  treemapBoxes,
  waterfallSeries,
  type ChartDatum,
} from './dashboard-extended-chart-data';
import DashboardChinaMap from './DashboardChinaMap';
import styles from './DashboardExtendedChart.module.css';

export default function DashboardExtendedChart({
  visualization,
  mapRegion,
  data,
  categoryField,
  valueField,
  format,
  colors,
  theme,
  onSelect,
}: {
  visualization: DashboardVisualization;
  mapRegion?: 'china';
  data: Record<string, unknown>[];
  categoryField: string;
  valueField: string;
  format: (value: unknown) => string;
  colors?: string[];
  theme?: DashboardThemeTokens;
  onSelect?: (datum: Record<string, unknown>) => void;
}) {
  const [hover, setHover] = useState('');
  const rows = numericChartData(data, categoryField, valueField);
  const palette = colors?.length
    ? colors
    : theme?.chartPalette || ['#406437', '#BB983F', '#6E9B89', '#5C78A7', '#AF745E'];
  const color = (index: number) => palette[index % palette.length];
  const label = (item: ChartDatum) => `${item.label} · ${format(item.value)}`;
  const interactive = (item: ChartDatum): SVGProps<SVGGElement> => ({
    tabIndex: 0,
    role: onSelect ? 'button' : 'img',
    'aria-label': label(item),
    onMouseEnter: () => setHover(label(item)),
    onMouseLeave: () => setHover(''),
    onFocus: () => setHover(label(item)),
    onBlur: () => setHover(''),
    onClick: event => {
      event.stopPropagation();
      onSelect?.(item.source);
    },
    onKeyDown: event => {
      if (onSelect && ['Enter', ' '].includes(event.key)) {
        event.preventDefault();
        onSelect(item.source);
      }
    },
  });
  if (!rows.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description='没有有效数值，请检查数值字段' />;
  if (visualization !== 'waterfall' && rows.some(item => item.value < 0))
    return <p className={styles.explanation}>此图需要非负数值。存在负值时可选择瀑布图或条形图。</p>;
  if (visualization === 'geo_map' && mapRegion === 'china')
    return <DashboardChinaMap rows={rows} format={format} onSelect={onSelect} />;
  const max = Math.max(...rows.map(item => item.value), 1);
  let plot;
  let note = rows.length < data.length ? `已略过 ${data.length - rows.length} 条空值或无效数值。` : '';
  if (visualization === 'geo_map') {
    const { matched, unmatched } = mapCountryData(rows);
    const countryValues = new Map(matched.map(item => [item.country.id, item]));
    const largest = Math.max(...matched.map(item => item.value), 1);
    note += `气泡面积表示数值，位置为国家标记点。${unmatched.length ? `未匹配 ${unmatched.length} 项：${unmatched.map(item => item.label).join('、')}。` : ''}`;
    plot = (
      <svg viewBox='0 0 800 420' className={styles.map} aria-label='国家地理分布'>
        {countries.map(country => {
          const item = countryValues.get(country.id);
          return (
            <path
              key={country.id}
              d={country.path}
              fill={item ? color(0) : 'var(--plot-land)'}
              stroke='var(--plot-card)'
              strokeWidth='.8'
            >
              <title>
                {country.name}
                {item ? ` · ${format(item.value)}` : ' · 无数据'}
              </title>
            </path>
          );
        })}
        {[...matched]
          .sort((a, b) => b.value - a.value)
          .map(item => (
            <g key={item.country.id} {...interactive(item)}>
              <circle
                cx={item.country.center[0]}
                cy={item.country.center[1]}
                r={Math.sqrt(item.value / largest) * 24}
                fill={color(1)}
                fillOpacity='.8'
                stroke='var(--plot-card)'
                strokeWidth='1.5'
              />
              <title>{label(item)}</title>
            </g>
          ))}
      </svg>
    );
  } else if (visualization === 'treemap') {
    const boxes = treemapBoxes(rows.filter(item => item.value > 0).sort((a, b) => b.value - a.value));
    if (!boxes.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description='数值均为 0，无法分配面积' />;
    plot = (
      <svg viewBox='0 0 560 320' aria-label='按数值面积分配的矩形树图'>
        {boxes.map((item, index) => (
          <g key={index} {...interactive(item)}>
            <rect
              x={item.x + 1}
              y={item.y + 1}
              width={Math.max(0, item.width - 2)}
              height={Math.max(0, item.height - 2)}
              rx='4'
              fill={color(index)}
              fillOpacity='.18'
            />
            {item.width > 50 && item.height > 40 && (
              <>
                <text x={item.x + 9} y={item.y + 23} fontSize='13'>
                  {item.label.slice(0, Math.max(2, Math.floor(item.width / 12) - 2))}
                </text>
                {item.height > 65 && item.width > format(item.value).length * 7 + 18 && (
                  <text x={item.x + 9} y={item.y + 44} fontSize='12'>
                    {format(item.value)}
                  </text>
                )}
              </>
            )}
            <title>{label(item)}</title>
          </g>
        ))}
      </svg>
    );
    note += '面积表示数值占比；悬停或聚焦查看完整名称与数值。';
  } else if (visualization === 'funnel') {
    const height = Math.max(280, rows.length * 47);
    plot = (
      <svg viewBox={`0 0 560 ${height}`} style={{ minHeight: height }} aria-label='按查询阶段顺序排列的漏斗图'>
        {rows.map((item, index) => {
          const w = (item.value / max) * 310;
          const next = ((rows[index + 1]?.value ?? item.value) / max) * 310;
          const top = index * (height / rows.length) + 4,
            bottom = (index + 1) * (height / rows.length) - 4;
          return (
            <g key={index} {...interactive(item)}>
              <path
                d={`M ${195 - w / 2} ${top} H ${195 + w / 2} L ${195 + next / 2} ${bottom} H ${195 - next / 2} Z`}
                fill={color(index)}
                fillOpacity='.8'
              />
              <text x='370' y={(top + bottom) / 2 - 3} fontSize='13'>
                {item.label.slice(0, 18)}
              </text>
              <text x='370' y={(top + bottom) / 2 + 16} fontSize='12'>
                {format(item.value)}
              </text>
              <title>{label(item)}</title>
            </g>
          );
        })}
      </svg>
    );
    note += '按查询返回的阶段顺序显示，宽度表示各阶段数值。';
  } else if (visualization === 'radar') {
    const dimensions = rows.slice(0, 12),
      count = dimensions.length;
    if (count < 3) return <p className={styles.explanation}>雷达图至少需要 3 个同单位维度；当前有 {count} 个。</p>;
    const point = (index: number, radius: number) => [
      280 + Math.sin((index * 2 * Math.PI) / count) * radius,
      160 - Math.cos((index * 2 * Math.PI) / count) * radius,
    ];
    const polygon = (radius: number) => dimensions.map((_, index) => point(index, radius).join(',')).join(' ');
    plot = (
      <svg viewBox='0 0 560 340' aria-label='从零开始、统一量程的雷达图'>
        {[0.25, 0.5, 0.75, 1].map(ratio => (
          <polygon key={ratio} points={polygon(112 * ratio)} fill='none' stroke='var(--plot-border)' />
        ))}
        {dimensions.map((item, index) => {
          const [x, y] = point(index, 134);
          const [endX, endY] = point(index, 112);
          return (
            <g key={index}>
              <line x1='280' y1='160' x2={endX} y2={endY} stroke='var(--plot-border)' />
              <text x={x} y={y} textAnchor={x < 270 ? 'end' : x > 290 ? 'start' : 'middle'} fontSize='12'>
                {item.label.slice(0, 12)}
              </text>
            </g>
          );
        })}
        <polygon
          points={dimensions.map((item, index) => point(index, (112 * item.value) / max).join(',')).join(' ')}
          fill={color(0)}
          fillOpacity='.2'
          stroke={color(0)}
          strokeWidth='2'
        />
        {dimensions.map((item, index) => {
          const [x, y] = point(index, (112 * item.value) / max);
          return (
            <g key={index} {...interactive(item)}>
              <circle cx={x} cy={y} r='5' fill={color(0)} />
              <title>{label(item)}</title>
            </g>
          );
        })}
        <text x='280' y='326' textAnchor='middle' fontSize='11'>
          量程 0 — {format(max)}
        </text>
      </svg>
    );
    note += `各维度使用相同单位与量程。${rows.length > 12 ? `显示前 12 / ${rows.length} 个维度。` : ''}`;
  } else {
    const steps = waterfallSeries(rows);
    const lo = Math.min(0, ...steps.flatMap(item => [item.start, item.end]));
    const hi = Math.max(1, ...steps.flatMap(item => [item.start, item.end]));
    const y = (value: number) => 250 - ((value - lo) / (hi - lo)) * 210;
    const width = Math.max(560, steps.length * 75 + 75),
      stepWidth = (width - 75) / steps.length;
    plot = (
      <svg viewBox={`0 0 ${width} 320`} style={{ minWidth: width }} aria-label='各项增减及累计总额瀑布图'>
        {[lo, (hi + lo) / 2, hi].map((value, index) => (
          <g key={index}>
            <line x1='65' y1={y(value)} x2={width - 5} y2={y(value)} stroke='var(--plot-border)' />
            <text x='60' y={y(value) + 4} textAnchor='end' fontSize='11'>
              {format(value)}
            </text>
          </g>
        ))}
        {steps.map((item, index) => {
          const x = 70 + index * stepWidth,
            top = y(Math.max(item.start, item.end));
          return (
            <g key={index} {...(!item.isTotal ? interactive(item) : {})}>
              <rect
                x={x}
                y={top}
                width={stepWidth * 0.7}
                height={Math.max(1, Math.abs(y(item.start) - y(item.end)))}
                rx='2'
                fill={item.isTotal ? color(0) : item.value < 0 ? '#B55B4A' : '#518565'}
              />
              {index < steps.length - 1 && (
                <line
                  x1={x + stepWidth * 0.7}
                  x2={x + stepWidth}
                  y1={y(item.end)}
                  y2={y(item.end)}
                  stroke='var(--plot-muted)'
                  strokeDasharray='3 3'
                />
              )}
              <text x={x + stepWidth * 0.35} y={top - 8} textAnchor='middle' fontSize='11'>
                {format(item.value)}
              </text>
              <text x={x + stepWidth * 0.35} y='278' textAnchor='middle' fontSize='11'>
                {item.label.slice(0, 9)}
              </text>
              <title>
                {label(item)}；累计 {format(item.end)}
              </title>
            </g>
          );
        })}
      </svg>
    );
    note += '最后一列为累计合计。已核对一致的末尾合计不会重复累加。';
  }
  return (
    <div
      className={styles.chart}
      data-extended-chart={visualization}
      style={
        {
          '--plot-card': theme?.card || '#fff',
          '--plot-border': theme?.border || '#d6dbd4',
          '--plot-muted': theme?.muted || '#6c7568',
          '--plot-land': theme?.cardMuted || '#e5eae2',
          color: theme?.text,
        } as CSSProperties
      }
    >
      <div className={styles.plot}>{plot}</div>
      <div className={styles.hover} aria-live='polite'>
        {hover || '\u00a0'}
      </div>
      <p className={styles.note}>{note}</p>
    </div>
  );
}
