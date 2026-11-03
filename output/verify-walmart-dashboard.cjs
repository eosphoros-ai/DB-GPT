const { chromium } = require('../web/node_modules/@playwright/test');
const fs = require('fs');
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.addInitScript(() => {
    localStorage.setItem('__db_gpt_lng_key', 'zh');
    localStorage.setItem('dbgpt-selected-model', 'deepseek-v4-flash');
  });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('http://localhost:3000/?id=122456fb-e4bd-46aa-99d8-fad27266b486');
  await page.getByRole('textbox').first().waitFor({ timeout: 90000 });
  await page.waitForTimeout(5000);
  await page.locator('.ant-select-selector').click();
  await page.locator('.ant-select-item-option').filter({ hasText: /^deepseek-v4-flash$/ }).click();
  page.on('response', async response => {
    if (response.url().endsWith('/api/v1/chat/react-agent')) {
      try { fs.writeFileSync('/tmp/walmart-generation.sse', await response.text()); } catch {}
    }
  });
  fs.writeFileSync('/tmp/walmart-page.txt', await page.locator('body').innerText());
  console.log(JSON.stringify({ cards: await page.getByTestId('chat-dashboard-card').count(), errors }));
  await page.screenshot({ path: 'output/walmart-dashboard-before.png', fullPage: true });
  const confirm = page.getByRole('button', { name: '确认并生成看板', exact: true });
  if (await confirm.count()) {
    await confirm.last().click();
    await page.getByRole('button', { name: '查看看板', exact: true }).last().waitFor({ timeout: 300000 });
    await page.screenshot({ path: 'output/walmart-dashboard-generated.png', fullPage: true });
    await page.getByRole('button', { name: '查看看板', exact: true }).last().click();
    await page.waitForTimeout(8000);
    fs.writeFileSync('/tmp/walmart-editor.txt', await page.locator('body').innerText());
    await page.screenshot({ path: 'output/walmart-dashboard-editor.png', fullPage: true });
    console.log(JSON.stringify({ url: page.url(), errors }));
  }
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
