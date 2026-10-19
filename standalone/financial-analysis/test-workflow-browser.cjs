// Usage: node test-workflow-browser.cjs <playwright-core-module> <preview-runtime.html> <report.json> <output-dir>
// Build runtime using --export-runtime --workflow-preview. No API/model calls.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require(path.resolve(process.argv[2]));
const runtime = fs.readFileSync(process.argv[3], 'utf8');
const report = JSON.parse(fs.readFileSync(process.argv[4], 'utf8'));
assert.equal(report.mode, 'report');
assert.equal(report.workflow.topics.length, 6);
const output = path.resolve(process.argv[5]);
fs.mkdirSync(output, { recursive: true });
const file = path.join(output, 'workflow.html');
fs.writeFileSync(file, runtime.replace('<!--FINANCIAL_REPORT_JSON-->', JSON.stringify(report).replace(/</g, '\\u003c')));
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const errors = [], cases = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1500, height: 1050 }, reducedMotion: 'reduce' });
    page.on('pageerror', error => errors.push(error.message));
    for (const state of ['success', 'running', 'partial']) for (const embedded of [false, true]) {
      const name = `${state}${embedded ? '-embedded' : ''}`;
      await page.goto(pathToFileURL(file).href + `?state=${state}${embedded ? '&embedded=1' : ''}`);
      await page.getByRole('navigation', { name: '财务分析章节' }).waitFor();
      assert.equal(await page.getByLabel('报告状态', {exact:true}).innerText(), state === 'running' ? '分析中' : '报告已生成');
      assert.equal(await page.getByLabel('专题执行详情').count(), 0);
      assert.equal(await page.getByRole('button', { name: '重新分析此专题' }).count(), 0);
      const gap = await page.evaluate(() => {
        const nav = document.querySelector('[aria-label="财务分析章节"]');
        return nav.getBoundingClientRect().top - nav.previousElementSibling.getBoundingClientRect().bottom;
      });
      assert.ok(gap <= 10, `Extra block above section navigation: ${gap}`);
      await page.waitForTimeout(500); // Settle existing animation before visual QA.
      await page.screenshot({ path: path.join(output, `${name}.png`), fullPage: true });
      await page.getByRole('button', { name: /执行过程/ }).click();
      const topic = report.workflow.topics[0];
      await page.getByRole('navigation', { name: '执行步骤' }).getByRole('button', { name: new RegExp(topic.title) }).click();
      await page.getByLabel('专题执行详情').waitFor();
      const retry = page.getByRole('button', { name: '重新分析此专题' });
      if (state === 'running') assert.ok(await retry.isDisabled());
      else {
        await retry.click();
        assert.equal(await page.locator('html').getAttribute('data-retry-topic'), topic.id);
      }
      if (state === 'partial') {
        assert.ok((await page.getByLabel('校验错误').innerText()).includes('summary'));
        assert.ok((await page.getByLabel('专题执行详情').innerText()).includes('FINDING_VALIDATION_FAILED'));
      }
      await page.screenshot({ path: path.join(output, `${name}-execution.png`), fullPage: true });
      cases.push(name);
    }
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, 'result.json'), JSON.stringify({ passed: true, cases, errors }, null, 2));
    console.log('PASS real workflow browser layouts, execution details and retry guards:', cases.join(', '));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
