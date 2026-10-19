/* Real Chrome, full HtmlReportEvidence, actual AutoChart/G2 and export code.
 * The HTTP fixture only controls report metadata arrival; no DOM/chart mocks.
 * Usage: npm run test:e2e:report
 * DBGPT_BROWSER_BASELINE=1 runs exactly the same assertions on the audited iframe.
 */
const fs = require('fs');
const path = require('path');
const http = require('http');
const assert = require('node:assert/strict');
const { test } = require('@playwright/test');
const ROOT = path.resolve(__dirname, '../../..');
const WEB = path.join(ROOT, 'web');
const webpack = require(path.join(WEB, 'node_modules/webpack'));
const OUT = path.join(WEB, 'node_modules/.cache/report-e2e/bundle');
fs.mkdirSync(OUT, { recursive: true });

async function build() {
  return new Promise((resolve, reject) =>
    webpack(
      {
        mode: 'development',
        context: ROOT,
        devtool: false,
        entry: path.join(__dirname, 'browser-entry.tsx'),
        output: { path: OUT, filename: 'browser.js' },
        resolve: {
          extensions: ['.tsx', '.ts', '.js', '.jsx', '.json'],
          modules: ['node_modules', path.join(WEB, 'node_modules')],
          alias: {
            '@': WEB,
            '@babel/runtime': path.join(WEB, 'node_modules/next/dist/compiled/@babel/runtime'),
            '@berryv/g2-react$': path.join(WEB, 'node_modules/@berryv/g2-react/es/index.js'),
            '@antv/gpt-vis$': path.join(WEB, 'node_modules/@antv/gpt-vis/dist/esm/index.js'),
          },
          fallback: { fs: false },
        },
        module: {
          rules: [
            { test: /\.m?js$/, resolve: { fullySpecified: false } },
            { test: /\.tsx?$/, exclude: /node_modules/, use: path.join(__dirname, 'browser-ts-loader.cjs') },
            { test: /\.(css|less)$/, type: 'asset/source' },
            { test: /\.(svg|png|jpg|woff2?)$/, type: 'asset/inline' },
          ],
        },
        plugins: [new webpack.DefinePlugin({ 'process.env.API_BASE_URL': JSON.stringify('') })],
        performance: { hints: false },
      },
      (error, stats) =>
        error
          ? reject(error)
          : stats.hasErrors()
            ? reject(new Error(stats.toString({ all: false, errors: true })))
            : resolve(),
    ),
  );
}

const canary = `<!doctype html><html><body><h1>Real iframe transition</h1>
<figure data-dbgpt-artifacts="chart-1" style="width:640px;height:360px"></figure>
<script>try{parent.__parentCanary='changed'}catch(e){window.__parentDenied=true}window.__scriptRan=true;</script>
</body></html>`;
const chart = {
  artifact_id: 'chart-1',
  type: 'chart',
  name: 'Actual G2 chart',
  status: 'succeeded',
  metadata: {},
  input_artifact_ids: [],
  execution: { action: 'chart_action.render', conv_uid: 'browser', step_id: 'chart-step' },
  spec: {
    renderer: 'vis-db-chart',
    type: 'response_bar_chart',
    data: [
      { bucket: 'A', total: 3 },
      { bucket: 'B', total: 4 },
    ],
  },
};

let server,
  pending,
  current,
  released = false,
  observations = [];

test.beforeAll(async () => {
  await build();
  server = http.createServer((req, res) => {
    if (req.url === '/browser.js') {
      res.setHeader('Content-Type', 'application/javascript');
      fs.createReadStream(path.join(OUT, 'browser.js')).pipe(res);
      return;
    }
    if (req.url.includes('/render-observations')) {
      let body = '';
      req.on('data', c => (body += c));
      req.on('end', () => {
        if (req.method === 'POST') observations.push(JSON.parse(body));
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify({ success: true, data: req.method === 'POST' ? JSON.parse(body) : [] }));
      });
      return;
    }
    if (req.url.startsWith('/api/v1/reports/')) {
      const respond = () => {
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify({ success: true, data: current }));
      };
      if (released) respond();
      else pending = respond;
      return;
    }
    res.setHeader('Content-Type', 'text/html');
    res.end(
      '<!doctype html><html><head><style>iframe{width:100%;border:0;display:block}</style></head><body><div id="root"></div><script>window.process={env:{NODE_ENV:"development",API_BASE_URL:""},browser:true};</script><script src="/browser.js"></script></body></html>',
    );
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
});

test.afterAll(async () => {
  if (server) await new Promise(resolve => server.close(resolve));
});

for (const { title, trusted } of [
  { title: 'opaque-to-trusted', trusted: true },
  { title: 'empty-to-untrusted', trusted: false },
  { title: 'empty-to-missing-trust', trusted: undefined },
]) {
  test(title, async ({ page, browser }, testInfo) => {
    released = false;
    pending = undefined;
    observations = [];
    current = {
      report_id: 'browser-regression',
      run_id: 'run-1',
      document: {
        schema_version: 3,
        report_id: 'browser-regression',
        title: 'Browser regression',
        conv_uid: 'browser',
        created_at: new Date().toISOString(),
        artifacts: trusted ? [chart] : [],
        sections: [],
        metadata: { presentation: { format: 'html', content: canary, trusted_template_scripts: trusted } },
      },
    };
    const errors = [];
    page.on('pageerror', e => {
      errors.push(String(e));
      console.error('BROWSER ERROR:', String(e));
    });
    await page.goto(`http://127.0.0.1:${server.address().port}`);
    await page.waitForFunction(() => window.probeLoaded);
    await page.evaluate(
      html => {
        window.__parentCanary = null;
        window.mountReport(html);
      },
      trusted ? canary : '',
    );
    await page.waitForTimeout(400);
    const firstFrame = await page.locator('iframe').elementHandle();
    assert.ok(pending, 'actual metadata fetch has not reached the HTTP server');
    released = true;
    pending();
    await page.waitForTimeout(1400);
    if (trusted) {
      await page.frameLocator('iframe').locator('canvas').waitFor({ timeout: 30000 });
      for (let i = 0; i < 100 && !observations.length; i++) await new Promise(resolve => setTimeout(resolve, 100));
      assert.ok(
        observations.some(o => o.renderer === 'g2' && o.state === 'rendered'),
        JSON.stringify(observations),
      );
      assert.ok(!observations.some(o => o.state === 'failed'), JSON.stringify(observations));
    }
    const state = await page.evaluate(async () => {
      const iframe = document.querySelector('iframe');
      const html = await window.exportReport();
      return {
        sandbox: iframe.getAttribute('sandbox'),
        readable: !!iframe.contentDocument,
        parentCanary: window.__parentCanary,
        exported: html,
        portals: iframe.contentDocument?.querySelectorAll('[data-dbgpt-native-chart-host]').length || 0,
        canvases: iframe.contentDocument?.querySelectorAll('canvas').length || 0,
      };
    });
    state.remounted = await firstFrame.evaluate(node => !node.isConnected);
    const direction = trusted
      ? 'opaque-to-trusted'
      : trusted === false
        ? 'empty-to-untrusted'
        : 'empty-to-missing-trust';
    const { exported, ...measured } = state;
    const resultPath = testInfo.outputPath('browser-results.json');
    fs.mkdirSync(path.dirname(resultPath), { recursive: true });
    fs.writeFileSync(
      resultPath,
      JSON.stringify(
        {
          browser: browser.version(),
          baseline: process.env.DBGPT_BROWSER_BASELINE === '1',
          direction,
          ...measured,
          observations,
        },
        null,
        2,
      ),
    );
    await testInfo.attach('browser-results', { path: resultPath, contentType: 'application/json' });
    console.log(direction, JSON.stringify(measured));
    assert.equal(state.readable, trusted === true);
    assert.equal(state.sandbox.includes('allow-same-origin'), trusted === true);
    if (trusted) {
      assert.equal(state.portals, 1);
      assert.ok(state.canvases > 0, 'actual AutoChart/G2 canvas absent');
      assert.match(state.exported, /data:image\/png;base64,/);
    } else {
      assert.equal(state.parentCanary, null, 'untrusted script modified the parent');
      const frame = page.frames().find(f => f.parentFrame());
      assert.equal(await frame.evaluate(() => window.__scriptRan), true);
      assert.equal(await frame.evaluate(() => window.__parentDenied), true);
    }
    assert.ok(state.exported.includes('Real iframe transition'));
    assert.ok(!state.exported.includes('<script'));
    assert.deepEqual(errors, []);
    fs.writeFileSync(testInfo.outputPath('report.html'), state.exported);
    await page.screenshot({ path: testInfo.outputPath('report.png') });
    // Chromium's real PDF path exercises the serialized chart presentation.
    const printPage = await browser.newPage();
    await printPage.setContent(state.exported);
    await printPage.pdf({ path: testInfo.outputPath('report.pdf'), format: 'A4', printBackground: true });
    await printPage.close();
  });
}
