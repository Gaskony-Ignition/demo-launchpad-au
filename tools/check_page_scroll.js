// Fail if a project page SCROLLS AS A PAGE at the smallest window we support.
//
//   node tools/check_page_scroll.js http://localhost:8988 KPI / /trending /alarming
//
// A page scrollbar is a defect here, not a preference (Nigel, standing rule):
// on an operations screen the thing you need is as likely to be below the fold
// as above it, and nothing on the page says there is a below-the-fold. Cards
// and tables scroll INSIDE themselves; the page does not.
//
// The trap this exists for: Perspective does not scroll the document. It
// scrolls a wrapper element inside it, so `document.documentElement.scrollHeight`
// reads clean on a page that is visibly scrolling, and every headless check
// written against the document passes. The KPI Overview shipped in 3.3.0
// hiding 844px that way.
//
// It measures at 1366x768 by default, which is the floor the layouts are built
// to. Widen it with --size WxH; the page is expected to be correct at anything
// larger, so the floor is the only size worth gating.
//
// RUN IT AGAINST THE STANDARD GATEWAY. Not because Edge is exempt, but because
// Edge's Perspective session cap is one at a time and it does not release a
// slot when the browser closes, so a multi-page run there measures error pages
// however patiently it is paced. It does not need to: the Edge zip differs from
// the standard zip ONLY in the provider substitutions, so the layout under test
// is the same file. Prove that rather than assume it -
//
//   diff <(unzip -p dist/KPI_Edge.zip <view> | sed 's/\[edge\]/[Launchpad]/g') \
//        <(unzip -p dist/KPI.zip <view>)
//
// - and check Edge's own behaviour, the parts that really do differ, one page
// at a time with tools/shoot-page.js.
const { chromium } = require('./lib/toolkit').playwright('check_page_scroll');

function arg(n, d) { const i = process.argv.indexOf('--' + n); return i > -1 ? process.argv[i + 1] : d; }
const SIZE = arg('size', '1366x768');
// Closing the browser context does not free an Ignition Edge Perspective
// session immediately - the gateway holds it for a while, and the next page
// gets "Sessions Exceeded" instead of a page. Edge's cap is small enough that
// even a strictly sequential run trips it, so leave a gap between pages there:
//   --gap 45   (seconds; 0 is fine on a standard gateway)
const GAP = Number(arg('gap', '0')) * 1000;
const [W, H] = SIZE.split('x').map(Number);
// Strip every --flag and its value, whatever the flag, so the positional
// arguments stay positional. Filtering on one known flag name silently ate the
// wrong tokens the moment a second flag was added.
const rest = [];
for (let i = 2; i < process.argv.length; i++) {
  if (process.argv[i].startsWith('--')) { i++; continue; }
  rest.push(process.argv[i]);
}
const BASE = (rest[0] || 'http://localhost:8988').replace(/\/+$/, '');
const PROJECT = rest[1] || 'KPI';
const PAGES = rest.slice(2).length ? rest.slice(2) : ['/'];

(async () => {
  const browser = await chromium.launch();
  const bad = [];
  for (const path of PAGES) {
    // ONE page per context: Edge caps concurrent Perspective sessions and a
    // run that opens several at once fails on all of them.
    const ctx = await browser.newContext({ viewport: { width: W, height: H } });
    const page = await ctx.newPage();
    // domcontentloaded, not networkidle: a Perspective session holds a websocket
    // open, so "network idle" is not guaranteed to arrive and the run dies on a
    // timeout that has nothing to do with the page. Wait for the shell to mount
    // instead - a fixed sleep alone reports a slow page as an empty one.
    await page.goto(`${BASE}/data/perspective/client/${PROJECT}${path}`,
                    { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForFunction(() => document.querySelectorAll('*').length > 300,
                               { timeout: 60000 }).catch(() => {});
    // The page paints before its websocket is up and wears a "No Connection to
    // Gateway" banner until it is, so measure only once that has gone. Match
    // the VISIBLE banner: the element stays in the DOM afterwards, so innerText
    // still carries the words on a page that is rendering perfectly.
    const banner = page.locator('text=No Connection to Gateway').first();
    for (let i = 0; i < 30; i++) {
      if (!(await banner.isVisible().catch(() => false))) break;
      await page.waitForTimeout(1000);
    }
    await page.waitForTimeout(9000);

    // A page that never rendered does not scroll, so without this the check
    // reports a clean pass on a gateway error page. Ignition Edge caps
    // concurrent Perspective sessions and answers the surplus with a full-page
    // "Sessions Exceeded" - which is how this check first passed four Edge
    // pages that a browser could not open at all. Run it against Edge on its
    // own; one page at a time is the whole reason shoot-page.js exists.
    // Two signals, both unambiguous. The "No Connection to Gateway" banner is
    // NOT one of them: the element stays laid out after the websocket connects,
    // so both a getBoundingClientRect test and Playwright's isVisible() report
    // it on a page that is rendering perfectly - it is fine to WAIT on, as
    // shoot-page.js does, and useless to assert on. Asserting on it failed all
    // five KPI pages that the same run had just measured correctly.
    const exceeded = await page.locator('text=Sessions Exceeded').first()
      .isVisible().catch(() => false);
    const nodes = await page.evaluate(() => document.querySelectorAll('*').length);
    if (nodes < 150 || exceeded) {
      bad.push(`${PROJECT}${path}: the page did not render (${nodes} nodes` +
               `${exceeded ? ', Sessions Exceeded' : ''})`);
      console.log(`  FAIL ${PROJECT}${path}  did not render`);
      await ctx.close();
      continue;
    }

    const worst = await page.evaluate(() => {
      // The page-level scroller is whatever wraps the view: it is the outermost
      // element that can scroll and is as tall as the viewport.
      let worst = null;
      const vh = document.documentElement.clientHeight;
      document.querySelectorAll('*').forEach((el) => {
        const over = el.scrollHeight - el.clientHeight;
        if (over <= 2) return;
        if (el.clientHeight < vh - 120) return;   // an inner card, not the page
        const cs = getComputedStyle(el);
        if (cs.overflowY === 'visible') return;   // clipping is a different check
        if (!worst || over > worst.hidden) {
          worst = { hidden: over, id: el.getAttribute('data-component-path') || el.className || el.tagName };
        }
      });
      const doc = document.documentElement.scrollHeight - document.documentElement.clientHeight;
      if (doc > 2 && (!worst || doc > worst.hidden)) worst = { hidden: doc, id: 'document' };
      return worst;
    });
    if (worst) {
      bad.push(`${PROJECT}${path}: ${worst.hidden}px below the fold (${worst.id})`);
      console.log(`  FAIL ${PROJECT}${path}  ${worst.hidden}px hidden`);
    } else {
      console.log(`  ok   ${PROJECT}${path}`);
    }
    await ctx.close();
    if (GAP && path !== PAGES[PAGES.length - 1]) {
      console.log(`       (waiting ${GAP / 1000}s for the session to be released)`);
      await new Promise((r) => setTimeout(r, GAP));
    }
  }
  await browser.close();
  if (bad.length) {
    console.error(`\npage-scroll check FAILED at ${SIZE}:`);
    bad.forEach((b) => console.error('    ' + b));
    console.error('\nA page must not scroll. Give the cards a floor they stay');
    console.error('legible at and let the one that still overflows scroll itself.');
    process.exit(1);
  }
  console.log(`\npage-scroll check passed at ${SIZE}: no page scrolls`);
})();
