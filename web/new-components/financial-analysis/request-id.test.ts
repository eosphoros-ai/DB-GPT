import { describe, expect, it, vi } from 'vitest';
import { createRequestId } from './request-id';

describe('financial request IDs on HTTP origins', () => {
  it('creates distinct UUID v4 IDs without the secure-context randomUUID API', () => {
    vi.stubGlobal('crypto', { getRandomValues: globalThis.crypto.getRandomValues.bind(globalThis.crypto) });
    try {
      const ids = new Set(Array.from({ length: 100 }, () => createRequestId()));
      expect(ids.size).toBe(100);
      for (const id of ids) expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
