import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/financial-e2e',
  testMatch: '**/*.spec.cjs',
  outputDir: './node_modules/.cache/financial-comparison/playwright',
  workers: 1,
  timeout: 60000,
  expect: { timeout: 15000 },
  use: {
    ...devices['Desktop Chrome'],
    channel: process.env.FINANCIAL_E2E_BROWSER_CHANNEL || 'chrome',
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
});
