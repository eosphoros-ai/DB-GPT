import type { DashboardWidget } from '@/types/dashboard';
import type { CSSProperties } from 'react';
import type { DashboardThemeTokens } from './dashboard-appearance';
import styles from './DashboardCohortMatrix.module.css';

export default function DashboardCohortMatrix({
  widget,
  data,
  theme,
}: {
  widget: DashboardWidget;
  data: Record<string, unknown>[];
  theme?: DashboardThemeTokens;
}) {
  const {
    row = 'cohort',
    column = 'age',
    value = 'retained',
    target = 'cohort_size',
    color = 'observed',
  } = widget.encoding;
  const cohorts = [...new Set(data.map(item => String(item[row!])))].sort();
  const ages = [...new Set(data.map(item => Number(item[column!])))].filter(Number.isFinite).sort((a, b) => a - b);
  const lookup = new Map(data.map(item => [`${item[row!]}:${item[column!]}`, item]));
  const unit = widget.presentation?.unit === '周' ? '周' : '月';
  return (
    <div
      className={styles.root}
      style={
        {
          '--cohort-accent': theme?.primary,
          '--cohort-card': theme?.card,
          '--cohort-text': theme?.text,
          '--cohort-muted': theme?.muted,
        } as CSSProperties
      }
    >
      <div className={styles.scroll} tabIndex={0} aria-label='留存矩阵，可横向查看后续周期'>
        <table className={styles.table} aria-label='客户首购与复购留存矩阵'>
          <thead>
            <tr>
              <th scope='col'>首次购买</th>
              <th scope='col'>客户数</th>
              {ages.map(age => (
                <th key={age} scope='col'>
                  第 {age} {unit}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cohorts.map(cohort => {
              const first = ages.map(age => lookup.get(`${cohort}:${age}`)).find(Boolean);
              return (
                <tr key={cohort}>
                  <th scope='row'>{cohort}</th>
                  <td className={styles.size}>{Number(first?.[target!] || 0).toLocaleString('zh-CN')}</td>
                  {ages.map(age => {
                    const datum = lookup.get(`${cohort}:${age}`);
                    const observed = datum && Number(datum[color!]) === 1;
                    const numerator = Number(datum?.[value!]);
                    const denominator = Number(datum?.[target!]);
                    const valid =
                      observed &&
                      denominator > 0 &&
                      Number.isFinite(numerator) &&
                      numerator >= 0 &&
                      numerator <= denominator;
                    const rate = valid ? (numerator / denominator) * 100 : 0;
                    return (
                      <td
                        key={age}
                        className={styles.cell}
                        data-observed={observed ? 'true' : 'false'}
                        style={
                          valid
                            ? {
                                backgroundColor: `color-mix(in srgb, var(--cohort-accent, var(--app-accent)) ${Math.round(8 + rate * 0.28)}%, var(--cohort-card, var(--app-surface)))`,
                              }
                            : undefined
                        }
                        title={
                          !datum
                            ? '缺少此周期数据'
                            : !observed
                              ? '源数据尚未覆盖此周期，不能视为 0% 留存'
                              : valid
                                ? `${numerator} / ${denominator} 位客户在第 ${age} ${unit}购买`
                                : '人数或分母无效'
                        }
                      >
                        {valid ? (
                          <>
                            <strong>{rate.toFixed(1)}%</strong>
                            <span>{numerator.toLocaleString('zh-CN')} 人</span>
                          </>
                        ) : (
                          <span>{datum && !observed ? '未到期' : '无数据'}</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className={styles.note}>
        留存率 = 当期购买客户数 ÷ 首购客户数。按客户去重；未到期不计为 0%。最近一个周期可能尚未结束。
      </p>
    </div>
  );
}
