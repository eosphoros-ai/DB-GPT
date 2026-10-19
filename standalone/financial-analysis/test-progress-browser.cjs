// node test-progress-browser.cjs <playwright-core> <progress-preview.html> <output-dir> <fixture.json>
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require(path.resolve(process.argv[2]));
const output = path.resolve(process.argv[4]);
const fixture = JSON.parse(fs.readFileSync(process.argv[5], 'utf8'));
fs.mkdirSync(output, { recursive: true });
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const errors = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1500, height: 900 } });
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(pathToFileURL(path.resolve(process.argv[3])).href);
    await page.waitForFunction(() => !!window.pushExecution);
    const push = (events) => page.evaluate(events => events.forEach(event => window.pushExecution(event)), events);
    const plan = (tasks, running = true) => page.evaluate(({tasks,running}) => window.pushProgress(tasks,running), {tasks,running});
    const right = page.getByTestId('right-panel');
    const left = page.getByTestId('left-plan');
    const execution = right.getByTestId('execution-output-scroll');
    for (const phase of ['read', 'analysis', 'validated', 'checking', 'published']) {
      if (phase === 'published') await push(fixture.events.reviewing);
      await push(fixture.events[phase]);
      await plan(fixture.tasks[phase], phase !== 'published');
      await execution.waitFor();
      assert.equal(await left.getByTestId('financial-progress').locator('li').count(), 4);
      assert.equal(await right.getByTestId('financial-progress').count(), 0);
      assert.doesNotMatch(await left.innerText(), /INTERNAL_THOUGHT_SENTINEL/);
      assert.doesNotMatch(await right.innerText(), /Thought\/Action\/Observation|正在执行\.\.\.|共 4 个阶段/);
      if (phase === 'analysis') {
        assert.match(await right.innerText(), /Action: prepare_financial_report/);
        assert.match(await execution.innerText(), /营业收入、净利润/);
        assert.match(await execution.innerText(), /等待模型返回/);
        await push(fixture.events.waiting);
        assert.match(await execution.innerText(), /\[00:26\].*仍在等待/);
        await page.screenshot({path: path.join(output, 'running.png'), fullPage: true});
      }
      if (phase === 'validated') {
        assert.match(await execution.innerText(), /收入与利润变化方向一致/);
        assert.match(await execution.innerText(), /现金流对利润的支撑/);
        await page.screenshot({path: path.join(output, 'validation.png'), fullPage: true});
      }
    }
    assert.match(await right.innerText(), /Action: review_financial_report/);
    assert.match(await execution.innerText(), /报告已生成/);
    // The original tool selection remains available below the four-stage plan.
    await left.getByText('工具调用详情', {exact:true}).click();
    await left.getByText('prepare_financial_report', {exact:true}).click();
    assert.match(await execution.innerText(), /收入与利润变化方向一致/);
    assert.match(await right.innerText(), /Action: prepare_financial_report/);
    assert.doesNotMatch(await execution.innerText(), /报告已生成/);
    await left.getByText('review_financial_report', {exact:true}).click();
    assert.match(await execution.innerText(), /报告已生成/);
    // Reload production-format history, then switch steps again.
    await page.evaluate(history => window.restoreExecution(history), fixture.history);
    await page.waitForFunction(() => document.querySelector('[data-testid="right-panel"]').textContent.includes('Action: prepare_financial_report'));
    assert.match(await execution.innerText(), /\[00:26\].*仍在等待/);
    assert.match(await execution.innerText(), /现金流对利润的支撑/);
    assert.doesNotMatch(await left.innerText(), /本阶段已用|仍在等待处理/);
    await page.screenshot({path: path.join(output, 'history.png'), fullPage: true});
    // A normal conversation/tool uses exactly the same output renderer.
    await plan([], true);
    await push([
      {type:'step.start',id:'sql',title:'sql_query',detail:'Action: sql_query'},
      {type:'step.meta',id:'sql',action:'sql_query',action_input:{sql:'SELECT 1'},title:'sql_query'},
      {type:'step.chunk',id:'sql',output_type:'text',content:'普通对话工具输出'},
      {type:'step.done',id:'sql',status:'done'},
    ]);
    assert.match(await execution.innerText(), /普通对话工具输出/);
    assert.doesNotMatch(await execution.innerText(), /已校验的分析发现/);
    assert.equal(await right.getByTestId('financial-progress').count(), 0);
    // New output follows the end while the user is there; reading older output keeps its position.
    await push([
      {type:'step.start',id:'long',title:'prepare_financial_report',detail:'Action: prepare_financial_report'},
      {type:'step.meta',id:'long',action:'prepare_financial_report',action_input:{},title:'prepare_financial_report'},
      {type:'step.chunk',id:'long',output_type:'text',content:Array.from({length:50},(_,i) => `执行进展 ${i}`).join('\n')},
    ]);
    assert.ok(await execution.evaluate(el => el.scrollHeight - el.scrollTop - el.clientHeight < 48));
    await execution.evaluate(el => {el.scrollTop = 0; el.dispatchEvent(new Event('scroll', {bubbles:true}));});
    await push([{type:'step.chunk',id:'long',output_type:'text',content:'最新处理结果'}]);
    assert.equal(await execution.evaluate(el => el.scrollTop), 0);
    assert.deepEqual(errors, []);
    console.log('PASS: four stages on left; real tool input/live output/wait feedback on right; step selection, durable history, normal-tool isolation');
    fs.writeFileSync(path.join(output, 'result.json'), JSON.stringify({passed:true, errors}, null, 2));
  } finally { await browser.close(); }
})().catch(e => {console.error(e); process.exitCode = 1;});
