import { useState } from 'react';
import type { ChartDatum } from './dashboard-extended-chart-data';
import styles from './DashboardShowcase.module.css';
import provinces from './geo/china-provinces.json';

const normalize = (name: string) =>
  name.trim().replace(/特别行政区|壮族自治区|回族自治区|维吾尔自治区|自治区|省|市/g, '');

export default function DashboardChinaMap({
  rows,
  format,
  onSelect,
}: {
  rows: ChartDatum[];
  format: (value: unknown) => string;
  onSelect?: (datum: Record<string, unknown>) => void;
}) {
  const [hover, setHover] = useState('');
  const known = new Set(provinces.map(p => normalize(p.name)));
  const unmatched = rows.filter(row => !known.has(normalize(row.label)));
  const values = new Map<string, ChartDatum>();
  rows.forEach(row => {
    const key = normalize(row.label),
      previous = values.get(key);
    values.set(key, previous ? { ...previous, value: previous.value + row.value } : row);
  });
  const max = Math.max(1, ...rows.map(r => r.value));
  const top = new Set(
    [...values.entries()]
      .sort((a, b) => b[1].value - a[1].value)
      .slice(0, 5)
      .map(([key]) => key),
  );
  return (
    <div className={styles.chinaMap}>
      <svg viewBox='0 0 800 485' role='img' aria-label='中国省区业务分布，气泡面积表示数值'>
        <g className={styles.mapGrid} aria-hidden='true'>
          {[100, 200, 300, 400].map(y => (
            <path key={y} d={`M 10 ${y} H 780`} />
          ))}
          {[100, 200, 300, 400, 500, 600, 700].map(x => (
            <path key={x} d={`M ${x} 15 V 470`} />
          ))}
        </g>
        {provinces.map(province => {
          const datum = values.get(normalize(province.name));
          return (
            <path key={province.id} d={province.path} className={styles.province} data-has-value={!!datum}>
              <title>
                {province.name} · {datum ? format(datum.value) : '无数据'}
              </title>
            </path>
          );
        })}
        <g aria-hidden='true' className={styles.mapInset}>
          <rect x='678' y='380' width='96' height='92' rx='2' />
          <text x='687' y='397'>
            南海诸岛
          </text>
        </g>
        {provinces.map(province => {
          const datum = values.get(normalize(province.name));
          if (!datum) return null;
          const [x, y] = province.center,
            r = Math.max(3, Math.sqrt(Math.max(0, datum.value) / max) * 16);
          const label = `${province.name} · ${format(datum.value)}`;
          return (
            <g
              key={province.id}
              className={styles.mapPoint}
              tabIndex={0}
              role={onSelect ? 'button' : 'img'}
              aria-label={label}
              onMouseEnter={() => setHover(label)}
              onMouseLeave={() => setHover('')}
              onFocus={() => setHover(label)}
              onBlur={() => setHover('')}
              onClick={e => {
                e.stopPropagation();
                onSelect?.(datum.source);
              }}
              onKeyDown={e => {
                if (onSelect && ['Enter', ' '].includes(e.key)) {
                  e.preventDefault();
                  e.stopPropagation();
                  onSelect(datum.source);
                }
              }}
            >
              <circle cx={x} cy={y} r={r + 7} className={styles.mapHalo} />
              <circle cx={x} cy={y} r={r} className={styles.mapBubble} />
              {top.has(normalize(province.name)) && (
                <text x={x + 15} y={y - 14}>
                  {normalize(province.name)}
                </text>
              )}
              <title>{label}</title>
            </g>
          );
        })}
      </svg>
      <div className={styles.mapLegend}>
        <span>{hover || '气泡面积表示数值 · 省级标记点'}</span>
        <small>
          {unmatched.length
            ? `未匹配 ${unmatched.length} 项：${unmatched.map(r => r.label).join('、')}`
            : onSelect
              ? '点击省区联动筛选'
              : '悬停或聚焦查看数值'}
        </small>
      </div>
    </div>
  );
}
