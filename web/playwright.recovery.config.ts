import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/recovery-e2e',
  outputDir: './node_modules/.cache/recovery-e2e',
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: 'http://127.0.0.1:5688',
    browserName: 'chromium',
    channel: 'chrome',
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  // API traffic is intercepted in these tests. No real model or daily server.
  webServer: {
    command: 'node --max-old-space-size=16384 node_modules/next/dist/bin/next dev --webpack -p 5688',
    url: 'http://127.0.0.1:5688',
    timeout: 180_000,
    reuseExistingServer: false,
  },
});
