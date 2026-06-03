import { useRouter } from 'next/router';
import { useCallback, useMemo } from 'react';

/** Query params for Pages Router (replaces `useSearchParams` from `next/navigation`). */
export function usePageQuery() {
  const router = useRouter();

  const get = useCallback(
    (key: string): string | null => {
      if (!router.isReady) return null;
      const value = router.query[key];
      if (value === undefined) return null;
      return Array.isArray(value) ? value[0] ?? null : String(value);
    },
    [router.isReady, router.query],
  );

  return useMemo(
    () => ({
      get,
      isReady: router.isReady,
      query: router.query,
    }),
    [get, router.isReady, router.query],
  );
}
