const fs = require('node:fs');
const path = require('node:path');
const { Parser } = require('./tooling/node_modules/@dbml/core');
const { chromium } = require('../../web/node_modules/@playwright/test');

(async () => {
  const browser = await chromium.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true,
  });
  const page = await browser.newPage({ acceptDownloads: true });
  const { default: mermaid } = await import('./tooling/node_modules/mermaid/dist/mermaid.esm.mjs');
  mermaid.initialize({ startOnLoad: false });
  for (const name of ['olist', 'composite-declared', 'composite-inferred']) {
    const dir = path.join(__dirname, name);
    const db = new Parser().parse(fs.readFileSync(path.join(dir, 'er-diagram.dbml'), 'utf8'), 'dbml');
    await mermaid.parse(fs.readFileSync(path.join(dir, 'er-diagram.mmd'), 'utf8'));
    const html = fs.readFileSync(path.join(dir, 'er-diagram.html'), 'utf8');
    // Same opaque-origin sandbox used by ArtifactCards and the preview rail.
    await page.setContent('<iframe title="ER" sandbox="allow-scripts allow-downloads" style="width:100%;height:700px"></iframe>');
    await page.locator('iframe').evaluate((frame, text) => { frame.srcdoc = text; }, html);
    const frame = page.frameLocator('iframe');
    await frame.locator('svg').waitFor();
    const width = Number(await frame.locator('svg').getAttribute('width'));
    await frame.locator('#bigger').click();
    if (Number(await frame.locator('svg').getAttribute('width')) !== width * 1.25) throw new Error('Zoom failed');
    await frame.locator('#reset').click();
    for (const ext of ['drawio', 'dbml', 'mmd', 'svg', 'json']) {
      const downloaded = page.waitForEvent('download');
      await frame.locator(`a[download="er-diagram.${ext}"]`).click();
      const download = await downloaded;
      const target = path.join(dir, `downloaded.${ext}`);
      await download.saveAs(target);
      if (!fs.readFileSync(target).equals(fs.readFileSync(path.join(dir, `er-diagram.${ext}`)))) {
        throw new Error(`Downloaded ${ext} mismatch`);
      }
    }
    await page.screenshot({ path: path.join(dir, 'inline-render.png') });
    console.log(JSON.stringify({ name, dbmlSchemas: db.schemas.length, mermaid: 'parsed', sandboxZoom: 'passed', downloads: 5 }));
  }
  await browser.close();
})().catch(error => { console.error(error); process.exitCode = 1; });
