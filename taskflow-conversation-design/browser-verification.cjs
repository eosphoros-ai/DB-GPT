/* Run against the real editor/backend/model; no mocked API or generated DSL. */
const { chromium } = require('../web/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = 'http://127.0.0.1:5670/api/v2/serve/awel/taskflow/generation-sessions';
const resumeSid = process.env.TASKFLOW_TEST_RESUME_SESSION;
const evidence = resumeSid
  ? JSON.parse(fs.readFileSync(path.join(__dirname, 'browser-verification.json'), 'utf8')).filter(item => item.name !== 'FAILED')
  : [];
const record = (name, detail) => {
  evidence.push({ name, detail, time: new Date().toISOString() });
  fs.writeFileSync(path.join(__dirname, 'browser-verification.json'), JSON.stringify(evidence, null, 2));
  console.log(name, detail ?? '');
};

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  });
  const page = await browser.newPage({ viewport: { width: 1680, height: 1050 } });
  const errors = [];
  page.on('pageerror', err => errors.push(err.message));
  try {
    await page.goto('http://localhost:3000/taskflow/editor', { waitUntil: 'domcontentloaded' });
    await page.evaluate(async () => {
      const deadline = Date.now() + 180000;
      while (Date.now() < deadline) {
        try {
          const response = await fetch('http://127.0.0.1:5670/api/v1/model/types');
          if (response.ok && (await response.json()).data.includes('glm-5.3-flash')) return;
        } catch {}
        await new Promise(resolve => setTimeout(resolve, 800));
      }
      throw new Error('Backend did not start');
    });
    if (resumeSid) await page.evaluate(sid => localStorage.setItem('taskflow-session:new', sid), resumeSid);
    await page.reload({ waitUntil: 'domcontentloaded' });
    const panel = page.getByTestId('workflow-conversation');
    await panel.waitFor();
    await page.waitForFunction(() => !!localStorage.getItem('taskflow-session:new'));
    const sid = await page.evaluate(() => localStorage.getItem('taskflow-session:new'));
    const state = async () => {
      const response = await page.request.get(`${base}/${sid}`);
      assert(response.ok());
      return (await response.json()).data;
    };
    const persist = async publish => {
      const responsePromise = page.waitForResponse(response =>
        response.url().endsWith(`/${sid}/save`) && response.request().method() === 'POST');
      await page.getByRole('button', { name: publish ? /发\s*布/ : /^保\s*存$/ }).click();
      const response = await responsePromise;
      const body = await response.json();
      assert(response.ok() && body.success, body.err_msg || JSON.stringify(body));
    };
    const wait = async (predicate, params = null) => {
      await page.evaluate(async ({ url, predicateText, params }) => {
        const deadline = Date.now() + 190000;
        while (Date.now() < deadline) {
          const { data } = await (await fetch(url)).json();
          if (new Function('state', 'params', `return (${predicateText})(state, params)`)(data, params)) return;
          await new Promise(resolve => setTimeout(resolve, 600));
        }
        throw new Error('Timed out waiting for server state');
      }, { url: `${base}/${sid}`, predicateText: predicate.toString(), params });
    };
    await panel.locator('.ant-select').first().click();
    await page.locator('.ant-select-item-option[title="glm-5.3-flash"]').click();
    const input = panel.getByRole('textbox', { name: '描述工作流需求' });
    const send = async text => {
      const previousCount = Object.keys((await state()).requests).length;
      await input.fill(text);
      await panel.getByRole('button', { name: /^(发\s*送|回答并继续|替换候选)$/ }).click();
      await page.evaluate(async ({ url, count }) => {
        const deadline = Date.now() + 190000;
        while (Date.now() < deadline) {
          const { data } = await (await fetch(url)).json();
          if (Object.keys(data.requests).length > count
            && !Object.values(data.requests).some(r => r.status === 'running')) return;
          await new Promise(resolve => setTimeout(resolve, 600));
        }
        throw new Error('Timed out waiting for generation');
      }, { url: `${base}/${sid}`, count: previousCount });
      const result = await state();
      const last = Object.values(result.requests).at(-1);
      assert.equal(last.status, 'succeeded', last.error || JSON.stringify(last));
      return result;
    };

    let result;
    if (resumeSid) {
      result = await state();
      assert([1, 3, 4].includes(result.draft_revision), 'Resume a verified browser checkpoint');
      record('重新打开浏览器恢复编辑会话', sid);
    } else {
      result = await send('分析销售情况');
      assert(result.questions.length > 0, 'Ambiguous request must produce clarification');
      assert.equal(result.snapshot.dsl.nodes.length, 2, 'Clarification must keep the empty canvas');
      record('真实模型澄清', result.questions.map(q => q.text));
      await page.screenshot({ path: path.join(__dirname, 'editor-clarification.png'), fullPage: true });

      result = await send('分析同比趋势。用户会在输入中提供今年和去年销售额，不连接数据库，不使用任何工具。用两个 Agent：第一个计算同比并说明计算过程，第二个汇总中文结论与风险提示。');
      assert.equal(result.candidate.status, 'applied');
      assert.equal(result.snapshot.dsl.nodes.filter(n => n.kind === 'agent').length, 2);
      await panel.getByTestId('generation-preview').getByText('已应用', { exact: true }).waitFor();
      record('首次生成自动应用', result.snapshot.dsl.nodes.map(n => [n.id, n.label || n.kind]));
      await page.screenshot({ path: path.join(__dirname, 'editor-generated.png'), fullPage: true });
    }

    const original = structuredClone(result.snapshot.dsl);
    if (result.draft_revision < 4) {
    const agent = original.nodes.filter(n => n.kind === 'agent').at(-1);
    await page.locator(`.react-flow__node[data-id="${agent.id}"]`).click({ noWaitAfter: true });
    await panel.locator('.ant-select').nth(1).click();
    await page.locator('.ant-select-item-option[title="选中节点"]').click();
    if (!(resumeSid && result.draft_revision === 3 && result.candidate.status === 'pending')) {
    result = await send('只修改这个 Agent 的目标：最终结论还必须列出两条行动建议。其余配置、名称、节点ID和连线不变。');
    assert.equal(result.candidate.status, 'pending');
    assert.deepEqual(result.snapshot.dsl, original, 'Preview must not modify canvas');
    for (const node of original.nodes.filter(n => n.id !== agent.id)) {
      assert.deepEqual(result.candidate.candidate_dsl.nodes.find(n => n.id === node.id), node);
    }
    record('局部修改预览保留其他节点', result.candidate.change_summary);
    await panel.getByRole('button', { name: '应用修改', exact: true }).click();
    await wait(s => s.candidate.status === 'applied' && s.draft_revision === 2);
    result = await state();
    assert.match(result.snapshot.dsl.nodes.find(n => n.id === agent.id).config.goal, /行动建议/);
    await panel.getByRole('button', { name: '撤销最近一次应用' }).click();
    await wait(s => s.draft_revision === 3 && !s.undo);
    result = await state();
    assert.deepEqual(result.snapshot.dsl, original);
    record('应用与撤销', { revision: result.draft_revision, restored: true });

    result = await send('这个 Agent 的目标补充：结论控制在 150 字以内。其他不变。');
    assert.equal(result.candidate.status, 'pending');
    }
    await panel.getByRole('button', { name: /^放\s*弃$/ }).click();
    await wait(s => s.candidate.status === 'discarded');
    assert.deepEqual((await state()).snapshot.dsl, original);
    record('放弃候选保留画布', true);

    result = await send('这个 Agent 的目标补充：结论控制在 100 字以内。其他不变。');
    assert.equal(result.candidate.status, 'pending');
    await page.locator('input[placeholder="未命名任务流程"]').count().then(async count => {
      if (count) await page.locator('input[placeholder="未命名任务流程"]').fill('对话工作流浏览器验证');
      else await page.locator('input.ant-input-borderless').first().fill('对话工作流浏览器验证');
    });
    await wait(s => s.candidate.status === 'stale');
    assert.equal(await panel.getByRole('button', { name: '应用修改', exact: true }).count(), 0);
    record('手工编辑使候选过期', (await state()).draft_revision);

    await input.fill('继续调整这个 Agent：增加一段详细的同比趋势背景解释。');
    await panel.getByRole('button', { name: /发\s*送/ }).click();
    await panel.getByRole('button', { name: '取消生成', exact: true }).click();
    await wait(s => Object.values(s.requests).at(-1).status === 'cancelled');
    record('取消真实生成请求', true);
    }

    await page.getByRole('button', { name: /发\s*布/ }).click();
    await page.getByText('请先对当前版本成功试运行，再发布', { exact: true }).waitFor();
    record('未试运行发布被服务端拦截', true);

    await page.getByRole('button', { name: /试运行/ }).click();
    const drawer = page.locator('.ant-drawer-content');
    await drawer.getByRole('textbox').fill('今年销售额为120万元，去年为100万元。请分析同比趋势。');
    const previousRunId = (await state()).run?.run_id;
    await drawer.getByRole('button', { name: /运\s*行/, exact: false }).click();
    await wait((s, previous) => s.run && s.run.run_id !== previous && s.run.status !== 'running', previousRunId);
    result = await state();
    assert.equal(result.run.status, 'success');
    await page.waitForFunction(() => !document.querySelector('.ant-drawer-content .ant-btn-loading'));
    assert.match(await drawer.innerText(), /20(?:\.0+)?\s*[%％]/, 'Render the actual 20% year-on-year result');
    record('真实 Agent 工作流试运行成功', result.run);
    await page.screenshot({ path: path.join(__dirname, 'editor-debug-success.png'), fullPage: true });
    await drawer.locator('button.ant-drawer-close').click();

    await persist(false);
    await wait(s => !!s.snapshot.meta.uid && !s.dirty);
    const saved = (await state()).snapshot;
    await page.reload({ waitUntil: 'domcontentloaded' });
    await panel.getByTestId('generation-preview').waitFor();
    assert.deepEqual((await state()).snapshot.dsl, original);
    record('保存及刷新恢复对话与画布', saved.meta.uid);
    await persist(true);
    await wait(s => s.snapshot.meta.state === 'deployed');
    const publishedResponse = await page.request.get(`http://127.0.0.1:5670/api/v2/serve/awel/flows/${saved.meta.uid}`);
    const published = (await publishedResponse.json()).data;
    assert.deepEqual(published.taskflow_source, original);
    record('当前验证版本发布成功', saved.meta.uid);
    await page.locator('input.ant-input-borderless').first().fill('已发布流程的新草稿标题');
    await persist(false);
    await wait(s => !s.dirty && s.snapshot.meta.label === '已发布流程的新草稿标题');
    const liveResponse = await page.request.get(`http://127.0.0.1:5670/api/v2/serve/awel/flows/${saved.meta.uid}`);
    const live = (await liveResponse.json()).data;
    assert.equal(live.label, published.label, 'Saving draft must preserve published metadata');
    assert.deepEqual(live.taskflow_source, published.taskflow_source);
    assert.equal(live.state, 'running');
    record('保存新草稿保持已发布定义和运行 DAG', true);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => document.querySelector('input.ant-input-borderless')?.value === '已发布流程的新草稿标题');
    record('浏览器异常', errors);
    assert.equal(errors.length, 0);
    await page.screenshot({ path: path.join(__dirname, 'editor-final.png'), fullPage: true });
    const deleted = await page.request.delete(`http://127.0.0.1:5670/api/v2/serve/awel/flows/${saved.meta.uid}`);
    assert(deleted.ok());
    assert.equal((await deleted.json()).success, true);
    record('清理本次测试流程', saved.meta.uid);
  } catch (err) {
    record('FAILED', err.stack);
    await page.screenshot({ path: path.join(__dirname, 'editor-failure.png'), fullPage: true });
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
