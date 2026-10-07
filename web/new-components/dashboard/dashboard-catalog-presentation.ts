import type { DashboardSchemaV1, DashboardThemeOverrides } from '@/types/dashboard';
import type { DashboardThemeTokens } from './dashboard-appearance';

const styles = [
  'skill_tree',
  'timeline',
  'dossier',
  'receipt',
  'story',
  'terminal',
  'executive',
  'monitor',
  'editorial',
  'brand',
  'marketing',
  'command',
  'clinical',
  'rural',
  'clinical_insight',
  'cardio_journal',
  'voice_observatory',
] as const;
export type CatalogPresentation = (typeof styles)[number];
export function catalogPresentation(schema: DashboardSchemaV1): CatalogPresentation | undefined {
  const entry = schema.metadata.compatibility?.catalog_presentation;
  if (!entry || typeof entry !== 'object' || !('style' in entry)) return undefined;
  return styles.find(style => style === entry.style);
}
export const presentationNames: Record<CatalogPresentation, string> = {
  skill_tree: 'PERFORMANCE MAP · 经营结构',
  timeline: 'QUARTERLY JOURNAL · 季度复盘',
  dossier: 'DATA BRIEF · 分析档案',
  receipt: 'SALES RECEIPT · 数据凭条',
  story: 'THE BUSINESS STORY · 经营观察',
  terminal: 'DATA TERMINAL / 数据终端',
  executive: 'EXECUTIVE SCOREBOARD · 经营总览',
  monitor: 'OPERATIONS / 运营观察',
  editorial: 'ANALYTICS JOURNAL · 数据观察',
  brand: 'BRAND PERFORMANCE · 品牌经营',
  marketing: 'IN-STORE MARKETING · 门店营销',
  command: 'BUSINESS OPERATIONS CENTER',
  clinical: 'CONNECTED HEALTHCARE · 服务运营',
  rural: 'INCLUSIVE FINANCE · 普惠服务',
  clinical_insight: 'CLINICAL DATA INSIGHTS · 研究总览',
  cardio_journal: 'DATA PULSE / RESEARCH JOURNAL',
  voice_observatory: 'VOICE INTELLIGENCE / TREND LAB',
};
/** Kept in one renderer path so preview, saved boards and shares stay identical. */
export function catalogTheme(
  theme: DashboardThemeTokens,
  style?: CatalogPresentation,
  overrides: DashboardThemeOverrides = {},
): DashboardThemeTokens {
  if (style === 'voice_observatory' && theme.mode === 'dark')
    return {
      ...theme,
      canvas: '#0A080E',
      card: '#17131D',
      cardMuted: '#201924',
      text: '#F5F0F6',
      muted: '#AFA4BA',
      border: '#342936',
      primary: overrides.primary_color ? theme.primary : '#FF388B',
      primarySoft: '#44152B',
      chartGrid: '#302735',
      gap: 16,
      radius: 5,
      chartPalette: overrides.chart_palette?.length ? theme.chartPalette : ['#FF388B', '#655D71', '#62D698', '#F1DB49'],
    };
  if ((style === 'clinical_insight' || style === 'cardio_journal') && theme.mode === 'light')
    return {
      ...theme,
      canvas: style === 'cardio_journal' ? '#FAFBFC' : '#F3F6FA',
      card: '#FFFFFF',
      cardMuted: '#EDF3FA',
      text: style === 'cardio_journal' ? '#18242E' : '#214265',
      muted: '#6B7D91',
      border: '#DCE5EF',
      primary: overrides.primary_color ? theme.primary : style === 'cardio_journal' ? '#137AD4' : '#345E8D',
      primarySoft: '#EAF3FC',
      chartGrid: '#E1E9F1',
      gap: 24,
      radius: 3,
      chartPalette: overrides.chart_palette?.length
        ? theme.chartPalette
        : ['#345E8D', '#88AACC', '#B94E59', '#D4B364', '#398274'],
    };
  if (style === 'marketing' && theme.mode === 'light')
    return {
      ...theme,
      canvas: '#FFF8ED',
      card: '#FFFEFB',
      cardMuted: '#FFF0DF',
      text: '#35251D',
      muted: '#846B5C',
      border: '#4A3529',
      primary: overrides.primary_color ? theme.primary : '#DC5425',
      primarySoft: '#FFEBDD',
      chartGrid: '#EBDDD0',
      chartPalette: overrides.chart_palette?.length
        ? theme.chartPalette
        : ['#ED6538', '#4D805C', '#CB9A45', '#758596', '#934B40'],
      gap: 20,
    };
  if (style && ['command', 'clinical', 'rural'].includes(style) && theme.mode === 'dark') {
    const rural = style === 'rural';
    const clinical = style === 'clinical';
    return {
      ...theme,
      canvas: rural ? '#081F22' : clinical ? '#0C1229' : '#061628',
      card: rural ? '#102C30' : clinical ? '#121F39' : '#0C233A',
      cardMuted: rural ? '#173B3D' : '#112C44',
      text: '#E8F5FF',
      muted: '#96B5CA',
      border: rural ? '#285453' : '#244560',
      primary: overrides.primary_color ? theme.primary : rural ? '#73D9B4' : '#65D8EF',
      primarySoft: rural ? '#174C42' : '#103C56',
      chartGrid: rural ? '#214542' : '#233C55',
      chartPalette: overrides.chart_palette?.length
        ? theme.chartPalette
        : rural
          ? ['#78DBC0', '#D8D979', '#6C9EDD', '#B8A3E2', '#EEBA6B']
          : clinical
            ? ['#76AAF0', '#74D6EA', '#C0A3E5', '#E7BA61', '#80CBBC']
            : ['#5DDCED', '#6D9FFA', '#F5C772', '#A594EC', '#6CD6AD'],
      gap: 10,
      radius: 3,
    };
  }
  if (style === 'terminal' && theme.id === 'graphite' && theme.mode === 'dark')
    return {
      ...theme,
      canvas: '#080E0B',
      card: '#0C1510',
      cardMuted: '#102017',
      text: '#E4F4E8',
      muted: '#A5BAAC',
      border: '#2D5039',
      primary: overrides.primary_color ? theme.primary : '#65E895',
      primarySoft: '#183D24',
      chartGrid: '#203628',
      chartPalette: overrides.chart_palette?.length
        ? theme.chartPalette
        : ['#65E895', '#F7C85D', '#75B6EA', '#C398E0', '#F59079', '#71D6CD'],
      gap: 8,
    };
  if ((style === 'executive' || style === 'brand') && theme.id === 'ocean' && theme.mode === 'light')
    return {
      ...theme,
      canvas: '#F1F4EC',
      card: '#FEFFFC',
      cardMuted: '#EAF0E2',
      text: '#233320',
      muted: '#5B6C55',
      border: '#D7DFCF',
      primary: overrides.primary_color ? theme.primary : '#406437',
      primarySoft: '#E2ECD9',
      chartGrid: '#E0E6D9',
      chartPalette: overrides.chart_palette?.length
        ? theme.chartPalette
        : ['#406437', '#A67519', '#3269AA', '#865096', '#AB4F5D', '#217D79'],
    };
  return theme;
}
