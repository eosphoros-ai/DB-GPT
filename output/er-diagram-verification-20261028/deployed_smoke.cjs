const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('../../web/node_modules/@playwright/test');
(async () => {
  const browser = await chromium.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true,
  });
  const page = await browser.newPage();
  const response = await page.goto('http://127.0.0.1:5670/', { waitUntil: 'networkidle' });
  if (response.status() !== 200) throw new Error('Home unavailable');
  await page.getByText('元数据与架构专家', { exact: true }).first().waitFor();
  await page.screenshot({ path: path.join(__dirname, 'deployed-home.png') });
  console.log('Deployed frontend: homepage and official metadata suite visible');
  await browser.close();
})().catch(error => { console.error(error); process.exitCode = 1; });
