import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ContextUsageBar from './ContextUsageBar';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ i18n: { language: 'zh' } }),
}));

afterEach(cleanup);

describe('ContextUsageBar', () => {
  it('separates estimated input usage, total window and output reservation', () => {
    render(
      <ContextUsageBar
        used={13500}
        budget={1032192}
        ratio={0.0131}
        state='OK'
        contextWindow={1048576}
        reservedTokens={16384}
        windowSource='deployment_config'
        variant='compact'
      />,
    );
    expect(screen.getByRole('button').getAttribute('aria-label')).toContain('输入预算');
    expect(screen.getByRole('tooltip').textContent).toContain('约 13.5K / 1.03M');
    expect(screen.getByRole('tooltip').textContent).toContain('窗口 1.05M');
    expect(screen.getByRole('tooltip').textContent).toContain('输出预留 16.4K');
    expect(screen.getByRole('tooltip').textContent).toContain('模型部署配置');
  });

  it('labels an unresolved model limit as a fallback', () => {
    render(
      <ContextUsageBar used={10} budget={120000} ratio={0.001} state='OK' variant='compact' windowSource='fallback' />,
    );
    expect(screen.getByRole('tooltip').textContent).toContain('模型上限未知');
  });
});
