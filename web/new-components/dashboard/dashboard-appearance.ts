import {
  DashboardThemeDensity,
  DashboardThemeFontScale,
  DashboardThemeKpiStyle,
  DashboardThemeMode,
  DashboardThemeShadow,
  DashboardThemeTableStyle,
  DashboardVisualTheme,
} from '@/types/dashboard';
import type { CSSProperties } from 'react';

export const DASHBOARD_PALETTES = {
  businessBlue: {
    label: '商务蓝',
    colors: ['#315EFB', '#4E83FD', '#67C9C3', '#F6BD5A', '#F08A5D', '#7C6FE8'],
  },
  deepNavy: {
    label: '深海蓝',
    colors: ['#233B6E', '#3D5A98', '#5B7CBA', '#75AADB', '#85C7D5', '#A8DADC'],
  },
  tealOrange: {
    label: '青橙对比',
    colors: ['#087E8B', '#4FB3BF', '#F4A261', '#E76F51', '#264653', '#E9C46A'],
  },
  violet: {
    label: '紫罗兰',
    colors: ['#5B4BDB', '#7B6DE5', '#A78BFA', '#D8B4FE', '#EC4899', '#F59E0B'],
  },
  executive: {
    label: '经营仪表盘',
    colors: ['#274C77', '#6096BA', '#A3CEF1', '#E7C66B', '#C96F53', '#6B8E74'],
  },
  monochrome: {
    label: '高级灰',
    colors: ['#111827', '#374151', '#6B7280', '#9CA3AF', '#D1D5DB', '#E5E7EB'],
  },
} as const;

export type DashboardPaletteId = keyof typeof DASHBOARD_PALETTES;

interface DashboardThemeModeDefinition {
  canvas: string;
  card: string;
  cardMuted: string;
  border: string;
  borderStrong: string;
  text: string;
  muted: string;
  primary: string;
  primarySoft: string;
  success: string;
  warning: string;
  danger: string;
  chartPalette: readonly string[];
  chartGrid: string;
  radius: number;
  shadow: string;
  fontScale: DashboardThemeFontScale;
  density: DashboardThemeDensity;
  kpiStyle: DashboardThemeKpiStyle;
  tableStyle: DashboardThemeTableStyle;
}

interface DashboardThemeDefinition {
  label: string;
  description: string;
  modes: Record<DashboardThemeMode, DashboardThemeModeDefinition>;
}

export const DASHBOARD_THEME_PRESETS = {
  clarity: {
    label: '澄明',
    description: '清晰留白与克制蓝色，适合日常经营看板。',
    modes: {
      light: {
        canvas: '#F4F7FB',
        card: '#FFFFFF',
        cardMuted: '#F7F9FC',
        border: '#D5DEE9',
        borderStrong: '#B9C6D6',
        text: '#172033',
        muted: '#5F6F85',
        primary: '#1D5FD1',
        primarySoft: '#E8F0FD',
        success: '#087A72',
        warning: '#8A6500',
        danger: '#B02E62',
        chartPalette: ['#1D5FD1', '#087A72', '#7B4BA8', '#A64B2A', '#7A6500', '#B02E62'],
        chartGrid: '#E7EDF5',
        radius: 14,
        shadow: '0 8px 24px rgba(31, 45, 61, 0.07)',
        fontScale: 'standard',
        density: 'comfortable',
        kpiStyle: 'accent',
        tableStyle: 'divided',
      },
      dark: {
        canvas: '#0E1623',
        card: '#152235',
        cardMuted: '#1A2A40',
        border: '#34465D',
        borderStrong: '#506784',
        text: '#F4F7FB',
        muted: '#AAB8CC',
        primary: '#78A9FF',
        primarySoft: '#203C63',
        success: '#45C8BE',
        warning: '#E8CD57',
        danger: '#FF9BBA',
        chartPalette: ['#78A9FF', '#45C8BE', '#D8A0F0', '#FF9B7A', '#E8CD57', '#83C95B'],
        chartGrid: '#2A3C53',
        radius: 14,
        shadow: '0 12px 32px rgba(0, 0, 0, 0.3)',
        fontScale: 'standard',
        density: 'comfortable',
        kpiStyle: 'accent',
        tableStyle: 'divided',
      },
    },
  },
  ocean: {
    label: '海境',
    description: '蓝青层次与更开阔的留白，适合趋势和运营监控。',
    modes: {
      light: {
        canvas: '#EEF7FA',
        card: '#FFFFFF',
        cardMuted: '#F1F8FA',
        border: '#C9DEE6',
        borderStrong: '#9DBFCB',
        text: '#12303A',
        muted: '#526D77',
        primary: '#0068A8',
        primarySoft: '#DCEFF8',
        success: '#007A77',
        warning: '#7C6900',
        danger: '#B5385D',
        chartPalette: ['#0068A8', '#007A77', '#7251A3', '#A65300', '#7C6900', '#B5385D'],
        chartGrid: '#DDECEF',
        radius: 18,
        shadow: '0 10px 30px rgba(17, 83, 105, 0.1)',
        fontScale: 'standard',
        density: 'spacious',
        kpiStyle: 'accent',
        tableStyle: 'plain',
      },
      dark: {
        canvas: '#081C26',
        card: '#102735',
        cardMuted: '#183443',
        border: '#31515F',
        borderStrong: '#517382',
        text: '#EDF8FB',
        muted: '#A8C1CA',
        primary: '#67B8E8',
        primarySoft: '#173E56',
        success: '#43C6C1',
        warning: '#D7CE64',
        danger: '#F18BAA',
        chartPalette: ['#67B8E8', '#43C6C1', '#BDA5E8', '#F2A466', '#D7CE64', '#F18BAA'],
        chartGrid: '#294652',
        radius: 18,
        shadow: '0 14px 38px rgba(0, 0, 0, 0.34)',
        fontScale: 'standard',
        density: 'spacious',
        kpiStyle: 'accent',
        tableStyle: 'plain',
      },
    },
  },
  warm: {
    label: '暖叙',
    description: '温暖纸感与稳重强调，适合经营复盘和叙事型汇报。',
    modes: {
      light: {
        canvas: '#FAF4ED',
        card: '#FFFCF8',
        cardMuted: '#F8EEE4',
        border: '#E5D2C0',
        borderStrong: '#CDB09A',
        text: '#3B2A22',
        muted: '#6F5B50',
        primary: '#9F4F2F',
        primarySoft: '#F5E3D8',
        success: '#34745B',
        warning: '#8A6512',
        danger: '#AD3D60',
        chartPalette: ['#9F4F2F', '#126E82', '#744FA1', '#8A6512', '#AD3D60', '#34745B'],
        chartGrid: '#EEE1D5',
        radius: 12,
        shadow: '0 8px 24px rgba(96, 70, 50, 0.1)',
        fontScale: 'large',
        density: 'comfortable',
        kpiStyle: 'solid',
        tableStyle: 'divided',
      },
      dark: {
        canvas: '#201814',
        card: '#2B211C',
        cardMuted: '#352821',
        border: '#57453A',
        borderStrong: '#765E4F',
        text: '#FFF4EA',
        muted: '#CDB9AA',
        primary: '#F0A17C',
        primarySoft: '#503124',
        success: '#77C4A0',
        warning: '#E9C46A',
        danger: '#F08CAB',
        chartPalette: ['#F0A17C', '#65C0D0', '#C3A6E8', '#E9C46A', '#F08CAB', '#77C4A0'],
        chartGrid: '#49382F',
        radius: 12,
        shadow: '0 12px 34px rgba(0, 0, 0, 0.38)',
        fontScale: 'large',
        density: 'comfortable',
        kpiStyle: 'solid',
        tableStyle: 'divided',
      },
    },
  },
  graphite: {
    label: '石墨',
    description: '中性高对比界面，适合密集分析与管理汇报。',
    modes: {
      light: {
        canvas: '#F2F3F5',
        card: '#FCFCFD',
        cardMuted: '#F3F4F6',
        border: '#D2D5DA',
        borderStrong: '#AEB4BD',
        text: '#1D2229',
        muted: '#5D6673',
        primary: '#4056B4',
        primarySoft: '#E9EBF8',
        success: '#00777E',
        warning: '#7A6500',
        danger: '#9C3E67',
        chartPalette: ['#4056B4', '#00777E', '#8B4678', '#9A5700', '#637000', '#6C4A96'],
        chartGrid: '#E1E3E7',
        radius: 10,
        shadow: '0 5px 16px rgba(22, 27, 34, 0.08)',
        fontScale: 'compact',
        density: 'compact',
        kpiStyle: 'quiet',
        tableStyle: 'striped',
      },
      dark: {
        canvas: '#111317',
        card: '#1B1E24',
        cardMuted: '#23272F',
        border: '#393F49',
        borderStrong: '#59616E',
        text: '#F4F5F7',
        muted: '#B2B8C2',
        primary: '#91A0FF',
        primarySoft: '#303755',
        success: '#46C7BE',
        warning: '#C9D66B',
        danger: '#E59BC8',
        chartPalette: ['#91A0FF', '#46C7BE', '#E59BC8', '#F5A45D', '#C9D66B', '#B39DDB'],
        chartGrid: '#30353E',
        radius: 10,
        shadow: '0 10px 28px rgba(0, 0, 0, 0.36)',
        fontScale: 'compact',
        density: 'compact',
        kpiStyle: 'quiet',
        tableStyle: 'striped',
      },
    },
  },
} as const satisfies Record<string, DashboardThemeDefinition>;

export type DashboardThemeId = keyof typeof DASHBOARD_THEME_PRESETS;

const LEGACY_THEME_ALIASES: Record<string, DashboardThemeId> = { clean: 'clarity', business_blue: 'clarity' };
const FONT_SCALES: Record<DashboardThemeFontScale, { body: number; title: number; kpi: number }> = {
  compact: { body: 11, title: 12, kpi: 30 },
  standard: { body: 12, title: 13, kpi: 36 },
  large: { body: 14, title: 15, kpi: 42 },
};
const DENSITIES: Record<DashboardThemeDensity, { gap: number; bodyPadding: number; headerPadding: string }> = {
  compact: { gap: 10, bodyPadding: 8, headerPadding: '8px 11px 7px' },
  comfortable: { gap: 12, bodyPadding: 10, headerPadding: '10px 13px 9px' },
  spacious: { gap: 16, bodyPadding: 14, headerPadding: '13px 16px 11px' },
};
const SHADOWS: Record<DashboardThemeMode, Record<DashboardThemeShadow, string>> = {
  light: { none: 'none', soft: '0 8px 24px rgba(31, 45, 61, 0.07)', elevated: '0 16px 38px rgba(31, 45, 61, 0.16)' },
  dark: { none: 'none', soft: '0 10px 28px rgba(0, 0, 0, 0.28)', elevated: '0 18px 44px rgba(0, 0, 0, 0.48)' },
};

export const DASHBOARD_SERIES_DASHES = [[], [6, 3], [2, 3], [8, 3, 2, 3], [10, 4], [3, 2, 1, 2]] as const;
export const DASHBOARD_SERIES_SHAPES = ['circle', 'square', 'triangle', 'diamond', 'bowtie', 'hexagon'] as const;

export interface DashboardThemeTokens extends DashboardThemeModeDefinition {
  id: DashboardThemeId;
  mode: DashboardThemeMode;
  label: string;
  description: string;
  chartPalette: string[];
  fontSize: number;
  titleSize: number;
  kpiSize: number;
  gap: number;
  bodyPadding: number;
  headerPadding: string;
  seriesDashes: typeof DASHBOARD_SERIES_DASHES;
  seriesShapes: typeof DASHBOARD_SERIES_SHAPES;
}

const isHexColor = (value: unknown): value is string => typeof value === 'string' && /^#[0-9A-Fa-f]{6}$/.test(value);

export const canonicalDashboardThemeId = (preset: unknown): DashboardThemeId => {
  if (typeof preset === 'string' && preset in DASHBOARD_THEME_PRESETS) return preset as DashboardThemeId;
  if (typeof preset === 'string' && LEGACY_THEME_ALIASES[preset]) return LEGACY_THEME_ALIASES[preset];
  return 'clarity';
};

export const resolveDashboardTheme = (theme: DashboardVisualTheme | undefined): DashboardThemeTokens => {
  const id = canonicalDashboardThemeId(theme?.preset);
  const requestedMode = theme?.mode;
  const mode: DashboardThemeMode =
    requestedMode === 'light' || requestedMode === 'dark'
      ? requestedMode
      : theme?.preset === 'graphite'
        ? 'dark'
        : 'light';
  const definition = DASHBOARD_THEME_PRESETS[id];
  const base = definition.modes[mode];
  const overrides = theme?.overrides || {};
  const fontScale = overrides.font_scale || base.fontScale;
  const density = overrides.density || base.density;
  const fontTokens = FONT_SCALES[fontScale];
  const densityTokens = DENSITIES[density];
  const primary = isHexColor(overrides.primary_color) ? overrides.primary_color.toUpperCase() : base.primary;
  const customPalette = overrides.chart_palette?.filter(isHexColor).map(color => color.toUpperCase());
  const chartPalette =
    customPalette && customPalette.length >= 3 ? customPalette : [primary, ...base.chartPalette.slice(1)];
  const cardShadow = overrides.card_shadow;
  return {
    id,
    mode,
    label: definition.label,
    description: definition.description,
    ...base,
    primary,
    chartPalette,
    radius: overrides.card_radius ?? base.radius,
    shadow: cardShadow ? SHADOWS[mode][cardShadow] : base.shadow,
    fontScale,
    density,
    kpiStyle: overrides.kpi_style || base.kpiStyle,
    tableStyle: overrides.table_style || base.tableStyle,
    fontSize: fontTokens.body,
    titleSize: fontTokens.title,
    kpiSize: fontTokens.kpi,
    gap: densityTokens.gap,
    bodyPadding: densityTokens.bodyPadding,
    headerPadding: densityTokens.headerPadding,
    seriesDashes: DASHBOARD_SERIES_DASHES,
    seriesShapes: DASHBOARD_SERIES_SHAPES,
  };
};

export const dashboardThemeCssVariables = (theme: DashboardThemeTokens): CSSProperties =>
  ({
    colorScheme: theme.mode,
    '--dashboard-theme-canvas': theme.canvas,
    '--dashboard-theme-card': theme.card,
    '--dashboard-theme-card-muted': theme.cardMuted,
    '--dashboard-theme-border': theme.border,
    '--dashboard-theme-border-strong': theme.borderStrong,
    '--dashboard-theme-text': theme.text,
    '--dashboard-theme-muted': theme.muted,
    '--dashboard-theme-primary': theme.primary,
    '--dashboard-theme-primary-soft': theme.primarySoft,
    '--dashboard-theme-success': theme.success,
    '--dashboard-theme-warning': theme.warning,
    '--dashboard-theme-danger': theme.danger,
    '--dashboard-theme-chart-grid': theme.chartGrid,
    '--dashboard-theme-radius': `${theme.radius}px`,
    '--dashboard-theme-shadow': theme.shadow,
    '--dashboard-theme-gap': `${theme.gap}px`,
    '--dashboard-theme-body-padding': `${theme.bodyPadding}px`,
    '--dashboard-theme-header-padding': theme.headerPadding,
    '--dashboard-theme-font-size': `${theme.fontSize}px`,
    '--dashboard-theme-title-size': `${theme.titleSize}px`,
    '--dashboard-theme-kpi-size': `${theme.kpiSize}px`,
  }) as CSSProperties;

const rgb = (value: string): [number, number, number] =>
  [1, 3, 5].map(index => Number.parseInt(value.slice(index, index + 2), 16) / 255) as [number, number, number];
const relativeLuminance = (value: string) => {
  const channels = rgb(value).map(channel =>
    channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4,
  );
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
};
export const dashboardContrastRatio = (left: string, right: string) => {
  const values = [relativeLuminance(left), relativeLuminance(right)].sort((a, b) => b - a);
  return (values[0] + 0.05) / (values[1] + 0.05);
};
const COLOR_VISION_MATRICES = [
  [
    [0.56667, 0.43333, 0],
    [0.55833, 0.44167, 0],
    [0, 0.24167, 0.75833],
  ],
  [
    [0.625, 0.375, 0],
    [0.7, 0.3, 0],
    [0, 0.3, 0.7],
  ],
] as const;
const simulatedDistance = (left: string, right: string, matrix: (typeof COLOR_VISION_MATRICES)[number]) => {
  const simulate = (value: string) => {
    const channels = rgb(value);
    return matrix.map(row => row.reduce<number>((sum, coefficient, index) => sum + coefficient * channels[index], 0));
  };
  const leftChannels = simulate(left);
  const rightChannels = simulate(right);
  return (
    Math.sqrt(leftChannels.reduce<number>((sum, value, index) => sum + (value - rightChannels[index]) ** 2, 0)) * 255
  );
};

export interface DashboardThemeAuditIssue {
  code: string;
  level: 'error' | 'warning';
  message: string;
}

export const auditDashboardTheme = (theme: DashboardVisualTheme | undefined): DashboardThemeAuditIssue[] => {
  const resolved = resolveDashboardTheme(theme);
  const issues: DashboardThemeAuditIssue[] = [];
  if (dashboardContrastRatio(resolved.text, resolved.card) < 4.5)
    issues.push({ code: 'text_contrast', level: 'error', message: '正文与卡片背景的对比度低于 4.5:1。' });
  if (dashboardContrastRatio(resolved.muted, resolved.card) < 3)
    issues.push({ code: 'muted_contrast', level: 'error', message: '辅助文字与卡片背景的对比度低于 3:1。' });
  const lowContrast = resolved.chartPalette
    .map((color, index) => ({ color, index }))
    .filter(({ color }) => dashboardContrastRatio(color, resolved.card) < 3)
    .map(({ index }) => index + 1);
  if (lowContrast.length)
    issues.push({
      code: 'palette_contrast',
      level: 'error',
      message: `图表色板第 ${lowContrast.join('、')} 个颜色与卡片背景的对比度低于 3:1。`,
    });
  if (new Set(resolved.chartPalette).size !== resolved.chartPalette.length)
    issues.push({ code: 'palette_duplicate', level: 'error', message: '图表色板存在重复颜色。' });
  const collisions: string[] = [];
  resolved.chartPalette.forEach((left, leftIndex) =>
    resolved.chartPalette.slice(leftIndex + 1).forEach((right, offset) => {
      if (COLOR_VISION_MATRICES.some(matrix => simulatedDistance(left, right, matrix) < 8))
        collisions.push(`${leftIndex + 1}/${leftIndex + offset + 2}`);
    }),
  );
  if (collisions.length)
    issues.push({
      code: 'palette_colorblind_collision',
      level: 'error',
      message: `色觉模拟下存在难以区分的颜色组合：${collisions.join('、')}。`,
    });
  return issues;
};

export const detectDashboardPalette = (colors: string[] | undefined): DashboardPaletteId | 'custom' => {
  if (!colors?.length) return 'businessBlue';
  const serialized = JSON.stringify(colors.map(color => color.toUpperCase()));
  const match = (Object.keys(DASHBOARD_PALETTES) as DashboardPaletteId[]).find(
    id => JSON.stringify([...DASHBOARD_PALETTES[id].colors].map(color => color.toUpperCase())) === serialized,
  );
  return match || 'custom';
};

export const replacePaletteColor = (colors: string[] | undefined, index: number, color: string): string[] => {
  const next = colors?.length ? [...colors] : [...DASHBOARD_PALETTES.businessBlue.colors];
  while (next.length <= index) next.push(DASHBOARD_PALETTES.businessBlue.colors[next.length % 6]);
  next[index] = color.toUpperCase();
  return next.slice(0, 20);
};
