import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ArtifactRail, { type RailArtifact } from './ArtifactRail';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (_key: string, fallback?: string) => fallback || _key }),
}));
vi.mock('@/new-components/common/MarkdownContext', () => ({ default: () => null }));
vi.mock('@/new-components/dashboard/DashboardArtifactPreview', () => ({ default: () => null }));
vi.mock('next/dynamic', async () => {
  const { lazy, Suspense } = await import('react');
  return {
    default: (loader: Parameters<typeof lazy>[0]) => {
      const Component = lazy(loader);
      return (props: any) => (
        <Suspense fallback={null}>
          <Component {...props} />
        </Suspense>
      );
    },
  };
});
vi.mock('@/new-components/financial-analysis/FinancialReportArtifact', () => ({
  default: ({ reference }: any) => (
    <div data-testid='financial-report' data-revision={reference.revision}>
      {reference.title}
    </div>
  ),
  downloadFinancialReport: vi.fn(),
}));

const html = '<body data-dbgpt-er="1"><svg /></body>';
const items: RailArtifact[] = [
  { id: 'html', type: 'html', name: 'Report.html', content: html },
  { id: 'drawio', type: 'file', name: 'er-diagram.drawio', content: { content: '<mxfile />' } },
  { id: 'dbml', type: 'file', name: 'er-diagram.dbml', content: { content: 'Table orders {}' } },
  { id: 'script', type: 'code', name: 'code_131.py', content: 'print(1)' },
];
const bundle: RailArtifact = {
  id: 'bundle',
  type: 'artifact_bundle',
  name: 'ER 图',
  content: { primaryId: 'html', items },
};
const props = { artifacts: items, previewArtifact: bundle, onPreview: vi.fn(), onDebug: vi.fn(), onClose: vi.fn() };

describe('artifact bundle right panel', () => {
  it('opens the main render and allows selecting an editable format', () => {
    const { container } = render(<ArtifactRail {...props} />);
    expect(container.querySelector('iframe')?.getAttribute('srcdoc')).toBe(html);
    fireEvent.change(screen.getByLabelText('选择预览文件'), { target: { value: 'dbml' } });
    expect(container.querySelector('iframe')).toBeNull();
    expect(container.querySelector('pre')?.textContent).toBe('Table orders {}');
    expect(screen.getByText('下载')).toBeTruthy();
  });

  it('lists outputs with downloads and keeps code in collapsed process files', () => {
    const { container } = render(<ArtifactRail {...props} />);
    fireEvent.click(screen.getByText('文件'));
    expect(screen.getByText('Report.html')).toBeTruthy();
    expect(screen.getByText('er-diagram.drawio')).toBeTruthy();
    const details = container.querySelector('details');
    expect(details?.open).toBe(false);
    expect(details?.textContent).toContain('code_131.py');
    expect(container.querySelectorAll('button[title="下载"]')).toHaveLength(4);
    fireEvent.click(screen.getByText('er-diagram.dbml'));
    expect(container.querySelector('pre')?.textContent).toBe('Table orders {}');
  });

  it.each([false, true])(
    'loads a persisted financial report instead of an empty HTML frame (bundle=%s)',
    async bundled => {
      const reference = {
        kind: 'financial-report',
        sessionId: 'session',
        runId: '12345678-1234-4234-8234-123456789012',
        revision: 'published-v1',
        title: '海翔药业财报分析',
        published: true,
      };
      const report: RailArtifact = { id: 'financial', type: 'html', name: '财报分析.html', content: reference };
      const preview = bundled
        ? { id: 'financial-bundle', type: 'artifact_bundle', name: report.name, content: { items: [report] } }
        : report;
      const { container } = render(<ArtifactRail {...props} artifacts={[report]} previewArtifact={preview} />);
      expect((await screen.findByTestId('financial-report')).getAttribute('data-revision')).toBe('published-v1');
      expect(container.querySelector('iframe')).toBeNull();
      if (bundled) {
        fireEvent.click(screen.getByText('下载'));
        const { downloadFinancialReport } = await import('@/new-components/financial-analysis/FinancialReportArtifact');
        expect(downloadFinancialReport).toHaveBeenCalledWith(reference);
        fireEvent.click(screen.getByText('文件'));
        expect(screen.getByTitle('下载')).toBeTruthy();
      }
    },
  );
});
