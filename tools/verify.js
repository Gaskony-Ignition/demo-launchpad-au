// Acceptance check against a running install. Reads the rendered DOM rather than
// looking at screenshots, because the things most likely to be wrong -- a stray
// imperial unit, a percentage that lost its leading zero, a US date -- are small
// text that a human skims straight past in a picture.
//
//   node tools/verify.js [--url http://localhost:8091]
//
// Exits non-zero if any check fails.
const path = require('path');
const { chromium } = require('./lib/toolkit').playwright('verify');

function arg(n, d) { const i = process.argv.indexOf('--' + n); return i > -1 ? process.argv[i + 1] : d; }
const URL = arg('url', 'http://localhost:8091').replace(/\/+$/, '');

const PAGES = [
  ['OEE', ''], ['OEE', 'line-view'], ['OEE', 'production-summary'], ['OEE', 'settings'],
  ['KPI', ''], ['KPI', 'dashboard'], ['KPI', 'trending'], ['KPI', 'alarming'],
];

let failures = 0;
const fail = (m) => { failures++; console.log('  FAIL  ' + m); };
const pass = (m) => console.log('  ok    ' + m);

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1100 },
                                         locale: 'en-AU', timezoneId: 'Australia/Sydney' });
  const allText = [];
  const topProduction = [];

  for (const [proj, p] of PAGES) {
    const label = `${proj}/${p || '(home)'}`;
    // one page per view: eight Perspective sessions in a single page eventually take
    // the renderer down, and a crashed browser looks exactly like a failing check
    const page = await ctx.newPage();
    // domcontentloaded, not networkidle: a Perspective session holds a websocket open,
    // so "network idle" is not guaranteed to arrive and the run dies on a timeout that
    // has nothing to do with the page.
    await page.goto(`${URL}/data/perspective/client/${proj}/${p}`,
                    { waitUntil: 'domcontentloaded', timeout: 60000 });
    // wait for the shell to mount rather than guessing a duration, then let the
    // bindings resolve -- a fixed sleep alone reports a slow page as an empty one
    try {
      await page.waitForFunction(() => document.querySelectorAll('*').length > 300,
                                 { timeout: 60000 });
    } catch (e) { /* fall through: the node-count check below reports it properly */ }
    await page.waitForTimeout(18000);

    const r = await page.evaluate(() => ({
      text: document.body.innerText,
      // Perspective keeps a HIDDEN quality-overlay template in the DOM for every
      // component, whose text is literally "overlay-error ERROR". Only a rendered
      // overlay has a size -- without this filter every page fails and the check
      // tells you nothing. textContent, not innerText: SVG elements match too.
      errors: [...document.querySelectorAll('.ia_qualityOverlay--error, [class*="ComponentError" i]')]
        .filter((e) => { const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0; })
        .map((e) => (e.textContent || '').trim()).slice(0, 5),
      // per-pen errors on a Power Chart DO render, and are how a bad history path shows
      penErrors: [...new Set([...document.querySelectorAll('[class*="rowOverlay"]')]
        .map((e) => (e.textContent || '').trim()).filter((t) => t.length > 3))].slice(0, 3),
      // a page that rendered nothing at all still has a body
      nodes: document.querySelectorAll('*').length,
      // The used colour scheme, read off an SVG rather than the root: SVG fills are
      // what Chrome's auto dark mode repaints, and color-scheme is inherited, so this
      // asserts the declaration actually REACHES the elements at risk. It cannot
      // prove force-dark behaves -- Chromium ignores --force-dark-mode when headless
      // -- but a missing declaration is the whole defect and that is catchable.
      scheme: (() => {
        const svg = document.querySelector('svg');
        return svg ? getComputedStyle(svg).colorScheme
                   : getComputedStyle(document.documentElement).colorScheme;
      })(),
      // text the PROJECT formats. The Time Series and Power Chart render their own
      // axis labels and range footer in a fixed US format we do not control, so hide
      // exactly those nodes -- not whole chart components, which would take the pen
      // table and its real values with them and make the checks below meaningless.
      //
      // Hidden in the LIVE dom, not removed from a clone: innerText is layout-derived,
      // so a detached clone yields '' and the textContent fallback runs adjacent
      // numbers together -- which invents percentages over 100% that are not on screen.
      ownText: (() => {
        document.querySelectorAll('.chart-footer, [class*="powerChartComponent__timeAxis"],'
                                + ' [class*="powerChartComponent__yAxis"],'
                                + ' [class*="powerChartComponent__eventMarker"]')
          .forEach((e) => { e.style.display = 'none'; });
        return document.body.innerText;
      })(),
      // "Top Production" lists production against the hourly target, which a line that
      // beat its target legitimately exceeds -- 108% there is correct, not the
      // unclamped-OEE bug. Collect that panel's text separately and subtract it from
      // the <=100% assertion only. Do NOT hide it in the DOM: walking N parents up to
      // find the panel takes most of the page with it, and then the date assertions
      // have nothing left to find and "pass" by being starved.
      topProduction: (() => {
        const label = [...document.querySelectorAll('*')]
          .find((e) => e.children.length === 0 && e.textContent.trim() === 'Top Production');
        if (!label) return '';
        let n = label;
        // climb only until the subtree actually contains the list, not a fixed depth
        while (n.parentElement && !/\d+\.\d%[\s\S]*\d+\.\d%/.test(n.innerText || '')) {
          n = n.parentElement;
          if (n === document.body) return '';
        }
        return n.innerText || '';
      })(),
    }));
    allText.push(r.ownText);
    topProduction.push(r.topProduction);

    if (r.nodes < 200) fail(`${label}: page looks empty (${r.nodes} nodes)`);
    else if (r.errors.length) fail(`${label}: component error - ${r.errors[0].slice(0, 120)}`);
    else if (r.penErrors.length) fail(`${label}: chart pen error - ${r.penErrors[0].slice(0, 120)}`);
    else if (r.scheme !== 'dark') fail(`${label}: colour scheme is "${r.scheme}", not dark `
      + '- Chrome auto dark mode will repaint the charts white')
    else pass(`${label}: rendered (${r.nodes} nodes), scheme dark`);
    await page.close();
  }
  const text = allText.join('\n');

  // --- units: the port converts at source, so nothing imperial should survive ---
  const imperial = text.match(/\bPSI\b|\bpsi\b|°F\b|\bFahrenheit\b/g);
  if (imperial) fail(`imperial units on screen: ${[...new Set(imperial)].join(', ')}`);
  else pass('no imperial units anywhere');
  for (const u of ['kPa', '°C']) {
    if (text.includes(u)) pass(`metric unit present: ${u}`);
    else fail(`metric unit missing: ${u}`);
  }

  // --- percentages keep their leading zero (##.0% made it optional) ---
  const stripped = text.match(/(^|[\s>(])\.\d+%/gm);
  if (stripped) fail(`percentage missing its leading zero: ${stripped.slice(0, 5).join(' ')}`);
  else pass('every percentage keeps its leading zero');

  // --- OEE components must be within 0-100% ---
  let pctText = text;
  for (const tp of topProduction) if (tp) pctText = pctText.split(tp).join('');
  const pcts = [...pctText.matchAll(/(\d+(?:\.\d+)?)%/g)].map((m) => parseFloat(m[1]));
  const over = pcts.filter((v) => v > 100);
  if (over.length) fail(`percentage over 100%: ${[...new Set(over)].slice(0, 5).join(', ')}`);
  else pass(`all ${pcts.length} percentages within 0-100%`);

  // --- dates the projects format themselves are DD/MM/YYYY, times 24-hour ---
  const usDate = text.match(/\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*,? \d{1,2},? \d{4}\b/g);
  if (usDate) fail(`US-style date: ${[...new Set(usDate)].slice(0, 3).join(', ')}`);
  else pass('no US-style month-name dates');
  // AM/PM in project-formatted text only -- chart components were stripped above.
  const ampm = text.match(/\b\d{1,2}:\d{2}(?::\d{2})?\s?[AP]M\b/g);
  if (ampm) fail(`12-hour time in project text: ${[...new Set(ampm)].slice(0, 3).join(', ')}`);
  else pass('no 12-hour times in project-formatted text');

  const ddmm = text.match(/\b\d{2}\/\d{2}\/\d{4}\b/g);
  if (ddmm) pass(`DD/MM/YYYY dates present (${ddmm.length})`);
  else fail('no DD/MM/YYYY dates found - are the pages showing data?');

  await browser.close();
  console.log(failures ? `\n${failures} check(s) FAILED` : '\nall checks passed');
  process.exit(failures ? 1 : 0);
})();
