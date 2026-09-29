import { resolveDashboardTheme, type DashboardThemeTokens } from '@/new-components/dashboard/dashboard-appearance';
import type { DashboardThemeMode, DashboardThemePreset } from '@/types/dashboard';
import type { CSSProperties } from 'react';

export const INTERFACE_THEME_KEY = 'dbgpt.interface.theme';

/** Complete semantic mapping for nested editors and body-mounted AntD portals. */
export function dashboardAntdTokens(tokens: DashboardThemeTokens) {
  return {
    colorPrimary: tokens.primary,
    colorPrimaryHover: tokens.primary,
    colorPrimaryActive: tokens.primary,
    colorLink: tokens.primary,
    colorLinkHover: tokens.primary,
    colorLinkActive: tokens.primary,
    colorBgBase: tokens.canvas,
    colorBgContainer: tokens.card,
    colorBgElevated: tokens.card,
    colorText: tokens.text,
    colorTextSecondary: tokens.muted,
    colorTextTertiary: tokens.muted,
    colorTextQuaternary: tokens.muted,
    colorTextDisabled: tokens.muted,
    colorTextPlaceholder: tokens.muted,
    colorBorder: tokens.border,
    colorBorderSecondary: tokens.border,
    colorFillAlter: tokens.cardMuted,
    colorBgContainerDisabled: tokens.cardMuted,
    colorSuccess: tokens.success,
    colorWarning: tokens.warning,
    colorError: tokens.danger,
    colorTextLightSolid: tokens.mode === 'dark' ? tokens.canvas : tokens.card,
  };
}

export function statusTagStyle(kind: 'accent' | 'success' | 'warning' | 'danger' | 'muted'): CSSProperties {
  return {
    color: `var(--app-${kind})`,
    background: kind === 'muted' ? 'var(--app-surface-muted)' : `var(--app-${kind}-soft)`,
    borderColor: 'transparent',
  };
}

export function interfaceThemeTokens(preset: DashboardThemePreset, mode: DashboardThemeMode): DashboardThemeTokens {
  const tokens = resolveDashboardTheme({ preset, mode, overrides: {} });
  if (preset !== 'clarity' || mode !== 'light') return tokens;
  return {
    ...tokens,
    canvas: '#F7F8FA',
    card: '#FFFFFF',
    text: '#202431',
    muted: '#687080',
    border: '#E6E8ED',
    primary: '#5865F2',
    primarySoft: '#EEEFFD',
  };
}

export function interfaceThemeVariables(tokens: DashboardThemeTokens): CSSProperties {
  return {
    colorScheme: tokens.mode,
    '--app-background': tokens.canvas,
    '--app-surface': tokens.card,
    '--app-surface-muted': tokens.cardMuted,
    '--app-text': tokens.text,
    '--app-muted': tokens.muted,
    '--app-border': tokens.border,
    '--app-border-strong': tokens.borderStrong,
    '--app-accent': tokens.primary,
    '--antd-primary-color': tokens.primary,
    '--app-accent-soft': tokens.primarySoft,
    '--app-on-accent': tokens.card,
    '--app-success': tokens.success,
    '--app-warning': tokens.warning,
    '--app-danger': tokens.danger,
    '--app-success-soft': `color-mix(in srgb, ${tokens.success} 9%, ${tokens.card})`,
    '--app-warning-soft': `color-mix(in srgb, ${tokens.warning} 9%, ${tokens.card})`,
    '--app-danger-soft': `color-mix(in srgb, ${tokens.danger} 9%, ${tokens.card})`,
    '--app-shadow': tokens.shadow,
    '--app-overlay': `color-mix(in srgb, ${tokens.text} 35%, transparent)`,
    '--app-rail-width': '56px',
  } as CSSProperties;
}
