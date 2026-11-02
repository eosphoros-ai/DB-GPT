import { expect, it } from 'vitest';
import { offlineCitationLabels } from './offline-citations';

it('keeps financial evidence labels readable without exposing application link syntax offline', () => {
  const text =
    '**Revenue** [Evidence](#financial-report/12345678-1234-4234-8234-123456789012/fact/revenue?revision=saved)';
  expect(offlineCitationLabels(text)).toBe('**Revenue** Evidence');
  expect(offlineCitationLabels('[Evidence](https://example.com)')).toBe('[Evidence](https://example.com)');
});
