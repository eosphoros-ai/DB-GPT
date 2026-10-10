const path = require("node:path");
const { defineConfig } = require("@playwright/test");
const output = path.join(
  process.env.REGRESSION_OUTPUT || path.join(__dirname, "results"),
  process.env.REGRESSION_MODE || "production",
);
module.exports = defineConfig({
  testDir: __dirname,
  testMatch: [
    "toolchain.spec.cjs",
    "copilot-auth.spec.cjs",
    "home-examples.spec.cjs",
  ],
  timeout: 180000,
  expect: { timeout: 15000 },
  workers: 1,
  retries: 0,
  reporter: [
    ["list"],
    ["json", { outputFile: path.join(output, "results.json") }],
  ],
  outputDir: path.join(output, "artifacts"),
  use: {
    baseURL: process.env.REGRESSION_URL || "http://127.0.0.1:3000",
    browserName: process.env.REGRESSION_BROWSER || "chromium",
    headless: true,
    viewport: { width: 1440, height: 1000 },
    locale: "zh-CN",
    serviceWorkers: "block",
    navigationTimeout: Number(
      process.env.REGRESSION_NAVIGATION_TIMEOUT || 120000,
    ),
    actionTimeout: 15000,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
