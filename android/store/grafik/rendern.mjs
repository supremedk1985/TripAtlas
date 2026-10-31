import { chromium } from 'playwright-core';
const b = await chromium.launch();
for (const [f, w, h, out] of [['symbol.html', 512, 512, 'symbol-512.png'], ['titel-de.html', 1024, 500, 'titelgrafik-de.png'], ['titel-en.html', 1024, 500, 'titelgrafik-en.png']]) {
  const p = await b.newPage({ viewport: { width: w, height: h } });
  await p.goto('file:///g/' + f); await p.waitForTimeout(500);
  await p.screenshot({ path: '/g/' + out }); await p.close();
}
await b.close();
