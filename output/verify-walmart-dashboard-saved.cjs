const { chromium } = require('../web/node_modules/@playwright/test');
const fs = require('fs');
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.addInitScript(() => localStorage.setItem('__db_gpt_lng_key', 'zh'));
  await page.goto('http://localhost:3000/dashboards/a6951ffa997c47fe87918f365258ac46');
  await page.waitForTimeout(5000);
  console.log(await page.getByRole('button').allTextContents());
  await page.getByRole('button', { name: '保存看板', exact: true }).waitFor({ timeout: 60000 });
  await page.getByRole('button', { name: '保存看板', exact: true }).click();
  await page.waitForTimeout(2000);
  await page.getByText('预览', { exact: true }).click();
  await page.waitForTimeout(4000);
  await page.screenshot({ path: 'output/walmart-dashboard-preview.png', fullPage: true });
  fs.writeFileSync('/tmp/walmart-preview.txt', await page.locator('body').innerText());
  await page.goto('http://localhost:3000/?id=122456fb-e4bd-46aa-99d8-fad27266b486');
  await page.getByTestId('chat-dashboard-card').getByRole('button', { name: '查看看板', exact: true }).waitFor({ timeout: 60000 });
  console.log(JSON.stringify({
    restoredCards: await page.getByTestId('chat-dashboard-card').count(),
    staleConfirmations: await page.getByRole('button', { name: '确认并生成看板', exact: true }).count(),
  }));
  await page.screenshot({ path: 'output/walmart-dashboard-restored.png', fullPage: true });
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
