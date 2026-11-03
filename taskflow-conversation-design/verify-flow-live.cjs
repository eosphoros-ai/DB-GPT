/* Current editor + real backend/model probe. No saved/published workflows. */
const { chromium } = require('../web/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');

function probe(data) {
  return new Promise(resolve => {
    let sse = '';
    let httpStatus;
    let finished = false;
    const done = timeout => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      resolve({ sse, httpStatus, timeout });
    };
    const req = http.request('http://127.0.0.1:5670/api/v2/serve/awel/flow/debug', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
    }, response => {
      httpStatus = response.statusCode;
      response.on('data', chunk => {
        sse += chunk.toString();
        if (sse.includes('[SERVER_ERROR]')) { done(false); req.destroy(); }
      });
      response.on('end', () => done(false));
    });
    req.on('error', error => { if (!finished) { sse += error.message; done(false); } });
    const timer = setTimeout(() => { done(true); req.destroy(); }, 30000);
    req.end(JSON.stringify(data));
  });
}

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const evidencePath = path.join(__dirname, 'semantic-flow-live-evidence.json');
  const evidence = fs.existsSync(evidencePath)
    ? JSON.parse(fs.readFileSync(evidencePath))
    : { errors: [], probes: [] };
  page.on('pageerror', error => evidence.errors.push(error.message));
  try {
    await page.goto('http://localhost:3000/taskflow/editor', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('workflow-conversation').waitFor({ timeout: 30000 });
    evidence.editor = { url: page.url(), conversationPanel: true };
    const options = await page.request.get('http://127.0.0.1:5670/api/v2/serve/awel/taskflow/agent-options');
    const manifest = (await options.json()).data;
    evidence.options = { tools: manifest.tools.map(t => t.id), skills: manifest.skills.map(s => s.name) };
    for (const [file, model, question] of [
      ['taskflow-db-fetch-template.json', 'deepseek-v4-flash', '只返回 Walmart_Sales 前3行，禁止做全表聚合。'],
    ]) {
      const flow = JSON.parse(fs.readFileSync(path.join(__dirname, '../packages/dbgpt-serve/src/dbgpt_serve/flow/templates/zh', file))).flow;
      for (const node of flow.taskflow_source.nodes) if (node.kind === 'agent') node.config.model = model;
      const began = Date.now();
      const response = await probe({
          flow,
          request: { model, messages: question, stream: true, incremental: false, conv_uid: `semantic_flow_audit_${Date.now()}` },
      });
      const text = response.sse;
      const failures = text.split('\n').filter(line => line.includes('[SERVER_ERROR]'));
      const result = { file, model, httpStatus: response.httpStatus, elapsedMs: Date.now() - began, serverErrors: failures, success: response.httpStatus === 200 && !response.timeout && failures.length === 0, timeout: response.timeout, sse: text };
      evidence.probes.push(result);
      console.log(JSON.stringify(result));
    }
  } catch (error) {
    evidence.failure = error.message;
    console.log(error.message);
    process.exitCode = 1;
  } finally {
    fs.writeFileSync(path.join(__dirname, 'semantic-flow-live-evidence.json'), JSON.stringify(evidence, null, 2));
    await browser.close();
  }
})();
