const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('../../web/node_modules/@playwright/test');
(async () => {
  const browser = await chromium.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true,
  });
  const page = await browser.newPage({ ignoreHTTPSErrors: true });
  page.on('requestfailed', request => console.log('Request failed:', new URL(request.url()).hostname, request.failure()?.errorText));
  const xml = fs.readFileSync(path.join(__dirname, 'composite-declared/er-diagram.drawio'), 'utf8');
  await page.setContent('<html><body></body></html>');
  const result = await page.evaluate(xml => new Promise((resolve, reject) => {
    const frame = document.createElement('iframe');
    frame.style = 'width:1200px;height:800px';
    const timer = setTimeout(() => reject(new Error('diagrams.net import timed out')), 45000);
    window.addEventListener('message', event => {
      if (event.source !== frame.contentWindow) return;
      let message;
      try { message = JSON.parse(event.data); } catch { return; }
      if (message.event === 'init') {
        frame.contentWindow.postMessage(JSON.stringify({ action: 'load', xml, title: 'Composite ER import test' }), '*');
        setTimeout(() => {
          frame.contentWindow.postMessage(JSON.stringify({ action: 'export', format: 'xml' }), '*');
        }, 1500);
      } else if (message.event === 'load') {
        frame.contentWindow.postMessage(JSON.stringify({ action: 'export', format: 'xml' }), '*');
      } else if (message.event === 'export') {
        clearTimeout(timer);
        resolve({ event: message.event, format: message.format, xml: message.xml, data: message.data });
      }
    });
    frame.src = 'https://embed.diagrams.net/?embed=1&proto=json&spin=1&libraries=1';
    document.body.appendChild(frame);
  }), xml);
  fs.writeFileSync(path.join(__dirname, 'drawio-import-result.json'), JSON.stringify(result, null, 2));
  await page.screenshot({ path: path.join(__dirname, 'drawio-import.png') });
  console.log(JSON.stringify({ drawio: 'loaded and exported by diagrams.net', format: result.format }));
  await browser.close();
})().catch(error => { console.error(error); process.exitCode = 1; });
