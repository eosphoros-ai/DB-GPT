import {
  DashboardThemeDensity,
  DashboardThemeFontScale,
  DashboardThemeKpiStyle,
  DashboardThemeMode,
  DashboardThemeOverrides,
  DashboardThemeShadow,
  DashboardThemeTableStyle,
  DashboardVisualTheme,
} from '@/types/dashboard';
import { BgColorsOutlined, DownOutlined, ReloadOutlined, UpOutlined } from '@ant-design/icons';
import { Alert, Button, InputNumber, Segmented, Select } from 'antd';
import { useMemo, useState } from 'react';
import styles from './DashboardWorkspace.module.css';
import {
  DASHBOARD_THEME_PRESETS,
  DashboardThemeId,
  auditDashboardTheme,
  resolveDashboardTheme,
} from './dashboard-appearance';

interface DashboardThemePanelProps {
  theme?: DashboardVisualTheme;
  onChange: (theme: DashboardVisualTheme) => void;
}

const sameValue = (left: unknown, right: unknown) => JSON.stringify(left) === JSON.stringify(right);

export default function DashboardThemePanel({ theme, onChange }: DashboardThemePanelProps) {
  const [customizing, setCustomizing] = useState(false);
  const resolved = useMemo(() => resolveDashboardTheme(theme), [theme]);
  const base = useMemo(
    () => resolveDashboardTheme({ preset: resolved.id, mode: resolved.mode, overrides: {} }),
    [resolved.id, resolved.mode],
  );
  const issues = useMemo(() => auditDashboardTheme(theme), [theme]);
  const overrides = theme?.overrides || {};
  const overrideCount = Object.values(overrides).filter(value => value != null).length;

  const emit = (nextOverrides: DashboardThemeOverrides, preset = resolved.id, mode = resolved.mode) =>
    onChange({ preset, mode, overrides: nextOverrides });

  const setOverride = <Key extends keyof DashboardThemeOverrides>(
    key: Key,
    value: NonNullable<DashboardThemeOverrides[Key]>,
    baseValue: unknown,
  ) => {
    const next = { ...overrides };
    if (sameValue(value, baseValue)) delete next[key];
    else next[key] = value;
    emit(next);
  };

  return (
    <section className={styles.themePanel} aria-labelledby='dashboard-visual-theme-title'>
      <div className={styles.themePanelHeading}>
        <div>
          <h3 id='dashboard-visual-theme-title' className={styles.sectionTitle}>
            视觉主题
          </h3>
          <p className={styles.themePanelHint}>只改变看板内容与发布页</p>
        </div>
        <BgColorsOutlined aria-hidden='true' />
      </div>
      <div className={styles.themePresetGrid}>
        {(Object.keys(DASHBOARD_THEME_PRESETS) as DashboardThemeId[]).map(id => {
          const definition = DASHBOARD_THEME_PRESETS[id];
          const preview = definition.modes[resolved.mode];
          const selected = resolved.id === id;
          return (
            <button
              key={id}
              type='button'
              aria-label={`选择${definition.label}主题`}
              aria-pressed={selected}
              data-testid={`dashboard-theme-${id}`}
              className={`${styles.themePresetCard} ${selected ? styles.themePresetCardSelected : ''}`}
              style={{ backgroundColor: preview.card, borderColor: selected ? preview.primary : preview.border }}
              onClick={() => emit(overrides, id, resolved.mode)}
            >
              <span className={styles.themePresetPreview} style={{ backgroundColor: preview.canvas }}>
                <span style={{ backgroundColor: preview.primary }} />
                <span style={{ backgroundColor: preview.chartPalette[1] }} />
                <span style={{ backgroundColor: preview.chartPalette[2] }} />
              </span>
              <span style={{ color: preview.text }}>{definition.label}</span>
            </button>
          );
        })}
      </div>
      <Segmented
        block
        size='small'
        aria-label='主题明暗模式'
        value={resolved.mode}
        options={[
          { label: '浅色', value: 'light' },
          { label: '深色', value: 'dark' },
        ]}
        onChange={value => emit(overrides, resolved.id, value as DashboardThemeMode)}
      />
      <Button
        type='text'
        size='small'
        className={styles.themeCustomizeToggle}
        aria-label={customizing ? '收起二次创作' : '展开二次创作'}
        aria-expanded={customizing}
        onClick={() => setCustomizing(current => !current)}
        icon={customizing ? <UpOutlined /> : <DownOutlined />}
      >
        二次创作{overrideCount ? `（${overrideCount} 项）` : ''}
      </Button>
      {customizing && (
        <div className={styles.themeOverrideGrid} data-testid='dashboard-theme-overrides'>
          <label className={styles.themeField}>
            <span>主色</span>
            <span className={styles.themeColorControl}>
              <input
                aria-label='主题主色'
                type='color'
                value={resolved.primary}
                onChange={event => setOverride('primary_color', event.target.value.toUpperCase(), base.primary)}
              />
              <code>{resolved.primary}</code>
            </span>
          </label>
          <label className={styles.themeField}>
            <span>字号档位</span>
            <Select
              aria-label='主题字号档位'
              size='small'
              value={resolved.fontScale}
              options={[
                { value: 'compact', label: '紧凑' },
                { value: 'standard', label: '标准' },
                { value: 'large', label: '放大' },
              ]}
              onChange={(value: DashboardThemeFontScale) => setOverride('font_scale', value, base.fontScale)}
            />
          </label>
          <label className={styles.themeField}>
            <span>留白密度</span>
            <Select
              aria-label='主题留白密度'
              size='small'
              value={resolved.density}
              options={[
                { value: 'compact', label: '紧凑' },
                { value: 'comfortable', label: '舒适' },
                { value: 'spacious', label: '宽松' },
              ]}
              onChange={(value: DashboardThemeDensity) => setOverride('density', value, base.density)}
            />
          </label>
          <label className={styles.themeField}>
            <span>卡片圆角</span>
            <InputNumber
              aria-label='主题卡片圆角'
              size='small'
              min={0}
              max={28}
              value={resolved.radius}
              addonAfter='px'
              onChange={value => setOverride('card_radius', Number(value ?? base.radius), base.radius)}
            />
          </label>
          <label className={styles.themeField}>
            <span>卡片阴影</span>
            <Select
              aria-label='主题卡片阴影'
              size='small'
              value={overrides.card_shadow || 'soft'}
              options={[
                { value: 'none', label: '无' },
                { value: 'soft', label: '柔和' },
                { value: 'elevated', label: '悬浮' },
              ]}
              onChange={(value: DashboardThemeShadow) => setOverride('card_shadow', value, 'soft')}
            />
          </label>
          <label className={styles.themeField}>
            <span>KPI 样式</span>
            <Select
              aria-label='主题 KPI 样式'
              size='small'
              value={resolved.kpiStyle}
              options={[
                { value: 'quiet', label: '克制' },
                { value: 'accent', label: '强调' },
                { value: 'solid', label: '色块' },
              ]}
              onChange={(value: DashboardThemeKpiStyle) => setOverride('kpi_style', value, base.kpiStyle)}
            />
          </label>
          <label className={styles.themeField}>
            <span>表格样式</span>
            <Select
              aria-label='主题表格样式'
              size='small'
              value={resolved.tableStyle}
              options={[
                { value: 'plain', label: '纯净' },
                { value: 'striped', label: '斑马纹' },
                { value: 'divided', label: '分隔线' },
              ]}
              onChange={(value: DashboardThemeTableStyle) => setOverride('table_style', value, base.tableStyle)}
            />
          </label>
          <div className={styles.themeFieldWide}>
            <span>图表色板</span>
            <div className={styles.themePaletteEditor}>
              {resolved.chartPalette.map((color, index) => (
                <input
                  key={`${index}-${color}`}
                  aria-label={`图表色板颜色 ${index + 1}`}
                  type='color'
                  value={color}
                  onChange={event => {
                    const next = [...resolved.chartPalette];
                    next[index] = event.target.value.toUpperCase();
                    setOverride('chart_palette', next, base.chartPalette);
                  }}
                />
              ))}
            </div>
          </div>
          {!!issues.length && (
            <Alert className={styles.themeAuditAlert} type='error' showIcon message={issues[0].message} />
          )}
          <Button
            className={styles.themeResetButton}
            size='small'
            icon={<ReloadOutlined />}
            aria-label='恢复主题默认'
            disabled={!overrideCount}
            onClick={() => emit({})}
          >
            恢复主题默认
          </Button>
        </div>
      )}
    </section>
  );
}
