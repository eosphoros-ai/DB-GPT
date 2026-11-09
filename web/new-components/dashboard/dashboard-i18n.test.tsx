import DashboardEn from '@/locales/en/dashboard';
import DashboardZh from '@/locales/zh/dashboard';
import { ADAPTED_SKILLS } from '@/new-components/skills/skill-catalog';
import type { DashboardSchemaV1 } from '@/types/dashboard';
import { act, fireEvent, render, screen } from '@testing-library/react';
import i18next from 'i18next';
import { useState } from 'react';
import { initReactI18next } from 'react-i18next';
import { afterEach, beforeAll, describe, expect, it } from 'vitest';
import DashboardAnomalyRuleEditor from './DashboardAnomalyRuleEditor';
import DashboardDataFreshness from './DashboardDataFreshness';
import DashboardExtendedChart from './DashboardExtendedChart';
import DashboardGenerationCard from './DashboardGenerationCard';
import { GALLERY_DESIGN_SKILL_IDS } from './dashboard-catalog';
import { dashboardDateLocale, dashboardText, useDashboardTranslation } from './dashboard-i18n';
import { dashboardTemplateEntry, dashboardTemplatePrompt } from './dashboard-template-entry';

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

  it('separates English labels and rule fragments from their values', async () => {
    const refreshedAt = '2026-10-21T10:00:00Z';
    render(
      <>
        <DashboardDataFreshness
          schema={{ widgets: [] } as unknown as DashboardSchemaV1}
          snapshot={{ dashboard_id: 'spacing', refreshed_at: refreshedAt, filters: {}, widgets: {} }}
        />
        <DashboardAnomalyRuleEditor
          fields={[{ value: 'sales', label: 'Sales' }]}
          rules={[
            {
              id: 'sales-drop',
              label: 'My sales rule',
              baseline: 'previous_period',
              value_field: 'sales',
              direction: 'below',
              threshold: { mode: 'relative_change', value: 0.2 },
              rolling_window: 3,
              min_samples: 2,
              enabled: true,
            },
          ]}
          onChange={() => undefined}
        />
      </>,
    );
    expect(screen.getByText(/^查询时间：/).textContent).toBe(
      `查询时间：${new Date(refreshedAt).toLocaleString('zh-CN')}`,
    );
    await act(async () => {
      await i18next.changeLanguage('en');
    });
    expect(screen.getByText(/^Query time:/).textContent).toBe(
      `Query time: ${new Date(refreshedAt).toLocaleString('en-US')}`,
    );
    expect(screen.getByText(/^Data through/).textContent).toBe(
      'Data through (current results): No date field provided',
    );
    expect(screen.getByLabelText('Rule meaning').textContent).toBe(
      'When Sales compared with Previous period Decrease of at least 20%, flag an anomaly.',
    );
  });

  it('localizes template requests while preserving their selection and custom text', async () => {
    for (const language of ['en', 'zh']) {
      await act(async () => {
        await i18next.changeLanguage(language);
      });
      for (const name of GALLERY_DESIGN_SKILL_IDS) {
        const design = ADAPTED_SKILLS[name];
        const prompt = dashboardTemplatePrompt(name);
        expect(dashboardTemplateEntry({ creation_mode: 'dashboard', skill: name })?.selection).toBe(`design:${name}`);
        expect(prompt).not.toContain('dashboard-builder');
        if (language === 'en') {
          expect(prompt).not.toMatch(/[\u4e00-\u9fff]/);
          expect(prompt).toContain('Adapt metrics to the actual fields');
        } else {
          expect(prompt.startsWith(design.prompt)).toBe(true);
        }
        expect(dashboardTemplateEntry({ creation_mode: 'dashboard', skill: name })?.prompt).toBe(prompt);
        expect(
          dashboardTemplateEntry({ creation_mode: 'dashboard', skill: name, skill_prompt: 'Revenue 需求保持原样' })
            ?.prompt,
        ).toBe('Revenue 需求保持原样');
      }
    }
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
