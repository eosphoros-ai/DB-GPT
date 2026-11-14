import type { SuiteItem } from '@/types/suite';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

let language = 'zh';
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key, i18n: { language } }),
}));

import ComposerContextMenu from './ComposerContextMenu';

const suites: SuiteItem[] = [
  {
    id: 1,
    name: 'analysis',
    display: '智能分析',
    status: 'enabled',
    version: '1',
    source: 'official',
    manifest_snapshot: { display_en: 'Data Analysis', description: '分析业务', description_en: 'Analyze business' },
  },
  { id: 2, name: 'disabled', display: 'Disabled', status: 'disabled', version: '1', source: 'official' },
];

function mount(availableSuites = suites) {
  const onSelectSuite = vi.fn();
  const onManageSuites = vi.fn();
  render(
    <ComposerContextMenu
      suites={availableSuites}
      selectedSuite='analysis'
      onSelectSuite={onSelectSuite}
      onManageSuites={onManageSuites}
      uploadProps={{}}
      skillItems={[]}
      onViewSkills={vi.fn()}
      onSelectDatabase={vi.fn()}
      onSelectKnowledge={vi.fn()}
      onSelectConnector={vi.fn()}
      flowItems={[]}
    />,
  );
  fireEvent.click(screen.getByTestId('composer-context-trigger'));
  return { onSelectSuite, onManageSuites };
}

async function openSuites() {
  fireEvent.mouseEnter(await screen.findByText('suite_reference_label'));
  await waitFor(() => expect(screen.getByText('composer_view_suites')).toBeTruthy());
}

describe('composer expert suite picker', () => {
  it('shows enabled suites, marks the selection and selects the actual suite', async () => {
    language = 'zh';
    const { onSelectSuite } = mount();
    await openSuites();
    expect(screen.queryByText('Disabled')).toBeNull();
    const option = screen.getByTestId('composer-suite-analysis');
    expect(option.textContent).toContain('智能分析');
    expect(option.textContent).toContain('分析业务');
    expect(option.querySelector('[data-icon="check"]')).toBeTruthy();
    fireEvent.click(option);
    expect(onSelectSuite).toHaveBeenCalledWith(suites[0]);
  });

  it('localizes the name and description and opens suite management', async () => {
    language = 'en';
    const { onManageSuites } = mount();
    await openSuites();
    expect(screen.getByTestId('composer-suite-analysis').textContent).toContain('Data AnalysisAnalyze business');
    fireEvent.click(screen.getByText('composer_view_suites'));
    expect(onManageSuites).toHaveBeenCalledOnce();
  });

  it('keeps management accessible when no suite is enabled', async () => {
    const { onManageSuites } = mount([suites[1]]);
    await openSuites();
    expect(screen.getByText('composer_suites_empty').closest('li')?.getAttribute('aria-disabled')).toBe('true');
    fireEvent.click(screen.getByText('composer_view_suites'));
    expect(onManageSuites).toHaveBeenCalledOnce();
  });
});
