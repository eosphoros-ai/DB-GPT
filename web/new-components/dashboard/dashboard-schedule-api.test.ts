import { GET, runDashboardSchedule } from '@/client/api';
import { afterEach, expect, it, vi } from 'vitest';

const transport = vi.hoisted(() => ({ responseAfter: 0 }));
vi.mock('@/utils', () => ({ getUserId: () => 'test-user' }));
vi.mock('axios', async importOriginal => {
  const actual = await importOriginal<typeof import('axios')>();
  const create = actual.default.create.bind(actual.default);
  return {
    ...actual,
    default: {
      ...actual.default,
      create: (...args: Parameters<typeof create>) => {
        const instance = create(...args);
        // Exercise the real request interceptor and per-call config with a timed transport.
        instance.defaults.adapter = config =>
          new Promise((resolve, reject) => {
            const response = setTimeout(() => {
              clearTimeout(timeout);
              resolve({ config, status: 200, statusText: 'OK', headers: {}, data: { success: true } });
            }, transport.responseAfter);
            const timeout = setTimeout(() => {
              clearTimeout(response);
              reject(new actual.AxiosError('timeout', 'ECONNABORTED', config));
            }, config.timeout);
          });
        return instance;
      },
    },
  };
});

afterEach(() => vi.useRealTimers());

it.each([
  { budget: undefined, duration: 361_000 },
  { budget: { timeout_seconds: 600, max_attempts: 5 }, duration: 3_015_000 },
])('waits past 100 seconds for the configured execution budget: $duration ms', async ({ budget, duration }) => {
  vi.useFakeTimers();
  transport.responseAfter = duration;
  let settled = false;
  const request = runDashboardSchedule('dashboard', 'schedule', budget).then(response => {
    settled = true;
    return response;
  });
  await vi.advanceTimersByTimeAsync(100_001);
  expect(settled).toBe(false);
  await vi.advanceTimersByTimeAsync(duration - 100_001);
  expect((await request).data.success).toBe(true);
});

it('keeps the shared 100-second timeout for unrelated requests', async () => {
  vi.useFakeTimers();
  transport.responseAfter = 101_000;
  const result = expect(GET('/unrelated')).rejects.toMatchObject({ code: 'ECONNABORTED' });
  await vi.advanceTimersByTimeAsync(100_000);
  await result;
});
