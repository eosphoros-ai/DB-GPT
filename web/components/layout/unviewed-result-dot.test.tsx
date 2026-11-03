import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import UnviewedResultDot from './unviewed-result-dot';

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (_key: string, fallback: string) => fallback }) }));

describe('unviewed result dot', () => {
  it('labels the blue dot for screen readers', () => {
    render(<UnviewedResultDot visible />);
    expect(screen.getByRole('status').getAttribute('aria-label')).toBe('已完成，未查看');
  });
  it('disappears when there is no unviewed result', () => {
    const { container } = render(<UnviewedResultDot visible={false} />);
    expect(container.textContent).toBe('');
    expect(container.querySelector('[role="status"]')).toBeNull();
  });
});
