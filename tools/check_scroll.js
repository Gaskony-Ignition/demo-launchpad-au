// Measure whether the OEE overview can actually reach its clipped content.
// A static screenshot cannot answer this: headless Chromium draws overlay
// scrollbars that are invisible unless a scroll is in progress.
const path = require('path');
const { chromium } = require('./lib/toolkit').playwright('check_scroll');

const URL = process.argv[2] || 'http://localhost:8088/data/perspective/client/OEE/';
const W = parseInt(process.argv[3] || '1366', 10);
const H = parseInt(process.argv[4] || '720', 10);
const SHOT = process.argv[5];

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  await page.goto(URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(14000);

  const report = await page.evaluate(() => {
    const out = { scrollable: [], overflowing: [] };
    document.querySelectorAll('*').forEach((el) => {
      const over = el.scrollHeight - el.clientHeight;
      if (over <= 2 || el.clientHeight < 40) return;
      const cs = getComputedStyle(el);
      const id = (el.getAttribute('data-component-path') || el.className || el.tagName)
        .toString().slice(0, 90);
      const rec = { id, clientH: el.clientHeight, scrollH: el.scrollHeight, hidden: over,
                    overflowY: cs.overflowY };
      if (cs.overflowY === 'auto' || cs.overflowY === 'scroll') out.scrollable.push(rec);
      else out.overflowing.push(rec);
    });
    out.bodyScroll = { clientH: document.documentElement.clientHeight,
                       scrollH: document.documentElement.scrollHeight };
    return out;
  });

  console.log('--- containers that CAN scroll to their hidden content ---');
  report.scrollable.slice(0, 12).forEach((r) =>
    console.log(`  ${r.hidden}px hidden  overflowY=${r.overflowY}  ${r.id}`));
  console.log('--- containers CLIPPING content with no scroll ---');
  report.overflowing.slice(0, 12).forEach((r) =>
    console.log(`  ${r.hidden}px UNREACHABLE  overflowY=${r.overflowY}  ${r.id}`));
  console.log('page:', JSON.stringify(report.bodyScroll));

  if (SHOT) {
    // scroll every scrollable pane to the bottom, then capture
    await page.evaluate(() => {
      document.querySelectorAll('*').forEach((el) => {
        if (el.scrollHeight - el.clientHeight > 2) {
          const cs = getComputedStyle(el);
          if (cs.overflowY === 'auto' || cs.overflowY === 'scroll') el.scrollTop = el.scrollHeight;
        }
      });
    });
    await page.waitForTimeout(2500);
    await page.screenshot({ path: SHOT });
    console.log('PNG :', SHOT);
  }
  await browser.close();
})();
