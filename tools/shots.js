// Capture the README screenshots from a running gateway.
//
//   node tools/shots.js [--url http://localhost:8088] [--out docs/images] [name ...]
//
// Defaults to every shot in SHOTS. Naming a subset re-takes just those, which is
// what you want when one page needed a longer settle or a different selection.
//
// Two things this has to get right that a naive page.goto+screenshot does not:
//
//   * Perspective renders the shell long before the bindings resolve, so a shot
//     taken at networkidle catches empty charts and "--" tiles. Every shot waits
//     for its own settle, and then for no element on the page to still be showing
//     a loading overlay.
//   * These are 1600x950 captures of pages whose layouts have real scroll. The
//     viewport is the frame the reader sees, so nothing is scrolled or expanded --
//     if content does not fit at this size, that is worth seeing in the shot.
const path = require('path');
const fs = require('fs');

const loadPlaywright = () => require('./lib/toolkit').playwright('shots');
function arg(n, d) { const i = process.argv.indexOf('--' + n); return i > -1 ? process.argv[i + 1] : d; }

const URL = (arg('url', 'http://localhost:8088')).replace(/\/+$/, '');
const OUT = arg('out', path.join(__dirname, '..', 'docs', 'images'));
const W = parseInt(arg('width', '1600'), 10);
const H = parseInt(arg('height', '950'), 10);

// `height` overrides the default for a page whose content genuinely needs more room
// than 950px. Every OEE page now fits 1600x900 with nothing clipped -- measured, not
// assumed -- so the overrides that used to compensate for cropped cards are gone.
const SHOTS = [
  { name: 'oee-overview',   project: 'OEE', page: '',                   settle: 20000 },
  { name: 'oee-line-view',  project: 'OEE', page: 'line-view',          settle: 20000 },
  // the summary table now sizes itself to its rows, so the shot can too
  { name: 'oee-production', project: 'OEE', page: 'production-summary', settle: 20000, height: 660 },
  { name: 'kpi-overview',   project: 'KPI', page: '',                   settle: 22000, height: 1000 },
  { name: 'kpi-dashboard',  project: 'KPI', page: 'dashboard',          settle: 22000, height: 1050 },
  // the install is "import the project, press this" -- the README should show it
  // the Rates card ends at 742 and Project Settings starts at 766, so the frame has
  // to land in that gap -- anything past 766 shows a headline with no card under it
  { name: 'oee-setup',      project: 'OEE', page: 'settings',           settle: 18000, height: 758 },
];
// The Trending page is deliberately not in the README shot set. It is the stock
// Power Chart with two default pens on very different scales, and it pins a cursor
// readout in the top-left corner of every capture -- the result says less about the
// page than a sentence of prose does.

const only = process.argv.slice(2).filter((a) => !a.startsWith('--') &&
  !process.argv.includes('--' + a) && SHOTS.some((s) => s.name === a));
const jobs = only.length ? SHOTS.filter((s) => only.includes(s.name)) : SHOTS;

const { chromium } = loadPlaywright();

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  // Perspective takes the session locale from the browser, so a default headless
  // Chromium (en-US) renders the built-in chart axes and range footers in US format
  // however the project is configured. Ask for the locale an Australian user has.
  const ctx = await browser.newContext({ viewport: { width: W, height: H },
                                         deviceScaleFactor: 1,
                                         locale: 'en-AU',
                                         timezoneId: 'Australia/Sydney' });
  const page = await ctx.newPage();

  for (const s of jobs) {
    const url = `${URL}/data/perspective/client/${s.project}/${s.page}`;
    process.stdout.write(`  ${s.name.padEnd(14)} `);
    if (s.height && s.height !== H) await page.setViewportSize({ width: W, height: s.height });
    else await page.setViewportSize({ width: W, height: H });
    // the pointer starts at 0,0, which on the trending page sits inside the chart and
    // leaves a hover tooltip pinned in the corner of every capture
    await page.mouse.move(150, 40);
    await page.goto(url, { waitUntil: 'networkidle' });
    await page.waitForTimeout(s.settle);
    await page.mouse.move(150, 40);

    // bindings can resolve after networkidle; wait for the loading overlays to clear
    try {
      await page.waitForFunction(
        () => !document.querySelector('.ia_loadingOverlay, .loading-overlay, [class*="LoadingOverlay"]'),
        { timeout: 15000 });
    } catch (e) { process.stdout.write('(overlay timeout) '); }

    const file = path.join(OUT, `${s.name}.png`);
    await page.screenshot({ path: file });
    const kb = Math.round(fs.statSync(file).size / 1024);
    console.log(`-> ${path.relative(process.cwd(), file)} (${kb}K)`);
  }

  await browser.close();
})();
