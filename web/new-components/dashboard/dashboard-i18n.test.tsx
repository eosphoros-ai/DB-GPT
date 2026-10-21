import DashboardEn from '@/locales/en/dashboard';
import DashboardZh from '@/locales/zh/dashboard';
import { act, fireEvent, render, screen } from '@testing-library/react';
import i18next from 'i18next';
import { useState } from 'react';
import { initReactI18next } from 'react-i18next';
import { afterEach, beforeAll, describe, expect, it } from 'vitest';
import DashboardExtendedChart from './DashboardExtendedChart';
import DashboardGenerationCard from './DashboardGenerationCard';
import { dashboardDateLocale, dashboardText, useDashboardTranslation } from './dashboard-i18n';

beforeAll(async () => {
  await i18next.use(initReactI18next).init({
    lng: 'zh',
    resources: { en: { dashboard: DashboardEn }, zh: { dashboard: DashboardZh } },
    interpolation: { escapeValue: false },
  });
});
afterEach(async () => {
  await act(async () => {
    await i18next.changeLanguage('zh');
  });
});

function Draft() {
  useDashboardTranslation();
  const [title, setTitle] = useState('我的业务看板');
  return (
    <label>
      {dashboardText('看板标题')}
      <input aria-label={dashboardText('看板标题')} value={title} onChange={event => setTitle(event.target.value)} />
      <button>{dashboardText('保存')}</button>
    </label>
  );
}

describe('Dashboard locale integration', () => {
  it('switches both ways without remounting or translating user content', async () => {
    render(<Draft />);
    const input = screen.getByRole('textbox', { name: '看板标题' });
    fireEvent.change(input, { target: { value: '业务名称保持原样' } });
    await act(async () => {
      await i18next.changeLanguage('en');
    });
    expect(screen.getByRole('button', { name: 'Save' })).toBeTruthy();
    expect(screen.getByRole('textbox', { name: 'Dashboard title' })).toBe(input);
    expect((input as HTMLInputElement).value).toBe('业务名称保持原样');
    expect(dashboardDateLocale()).toBe('en-US');
    await act(async () => {
      await i18next.changeLanguage('zh');
    });
    expect(screen.getByRole('button', { name: '保存' })).toBeTruthy();
    expect((screen.getByRole('textbox', { name: '看板标题' }) as HTMLInputElement).value).toBe('业务名称保持原样');
  });

  it('updates an existing generation card while retaining its business title', async () => {
    render(
      <DashboardGenerationCard
        onOpen={() => undefined}
        state={{
          dashboardId: 'draft-1',
          title: '销售计划',
          status: 'awaiting_confirmation',
          totalWidgets: 1,
          validatedWidgets: 0,
          failedWidgets: 0,
          widgetStates: {},
        }}
      />,
    );
    await act(async () => {
      await i18next.changeLanguage('en');
    });
    expect(screen.getByText('销售计划')).toBeTruthy();
    expect(screen.getByText(/SQL has not been generated/)).toBeTruthy();
  });

  it('switches nested chart notices while preserving data labels and counts', async () => {
    render(
      <>
        <DashboardExtendedChart
          visualization='geo_map'
          data={[{ label: '自定义地区', value: 5 }]}
          categoryField='label'
          valueField='value'
          format={String}
        />
        <DashboardExtendedChart
          visualization='radar'
          data={Array.from({ length: 13 }, (_, index) => ({ label: `Dimension ${index}`, value: index + 1 }))}
          categoryField='label'
          valueField='value'
          format={String}
        />
      </>,
    );
    expect(screen.getByText(/未匹配 1 项：自定义地区。/)).toBeTruthy();
    expect(screen.getByText(/显示前 12 \/ 13 个维度。/)).toBeTruthy();
    await act(async () => {
      await i18next.changeLanguage('en');
    });
    expect(screen.getByText(/1 unmatched items: 自定义地区\./)).toBeTruthy();
    expect(screen.getByText(/Showing the first 12 of 13 dimensions\./)).toBeTruthy();
  });

  it('preserves interpolation fields in every English message', () => {
    for (const [source, translated] of Object.entries(DashboardEn)) {
      expect((translated.match(/\{\{\w+\}\}/g) || []).sort(), source).toEqual(
        (source.match(/\{\{\w+\}\}/g) || []).sort(),
      );
    }
    expect(dashboardText('共 {{n}} 行', { n: 12 })).toBe('共 12 行');
  });
});
