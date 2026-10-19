import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/report-e2e',
  testMatch: '**/*.spec.cjs',
  outputDir: './node_modules/.cache/report-e2e/results',
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  use: {
    ...devices['Desktop Chrome'],
    channel: process.env.REPORT_E2E_BROWSER_CHANNEL || 'chrome',
    headless: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
});
