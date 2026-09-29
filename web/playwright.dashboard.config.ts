import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/dashboard-e2e',
  outputDir: '../output/playwright/test-results',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  use: {
    actionTimeout: 30_000,
    baseURL: process.env.DASHBOARD_E2E_BASE_URL || 'http://localhost:5670',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: process.env.DASHBOARD_E2E_DISABLE_VIDEO ? 'off' : 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        channel: process.env.DASHBOARD_E2E_BROWSER_CHANNEL || undefined,
      },
    },
  ],
  webServer:
    process.env.DASHBOARD_E2E_START_SERVER === '1'
      ? {
          command: 'npm run start -- -p 5670',
          url: 'http://127.0.0.1:5670/dashboards/',
          reuseExistingServer: false,
          timeout: 180_000,
        }
      : undefined,
});
