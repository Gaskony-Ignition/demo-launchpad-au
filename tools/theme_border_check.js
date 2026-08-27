// Do the borders Ignition draws with var(--containerBorder) actually land, on every
// theme this gateway offers?
//
//   node tools/theme_border_check.js http://localhost:8091 dark-cool nord-light ...
//
// Ignition's own CSS says `border: var(--containerBorder)` in 85 rules and needs that
// variable to hold a SHORTHAND. The ten Gaskony custom themes hold a bare colour, which
// invalidates all 85 at once; each project stylesheet restates the shorthand. This is
// what proves the restatement still works.
//
// Three things this has to get right, each of which produced a wrong answer first:
//
//   * COMPUTED STYLE, never a screenshot. On several packs the border colour sits
//     close enough to the card that a crop cannot settle it either way.
//   * Assert that a border is DRAWN, not that it is 1px. The nav and action buttons
//     carry a project style class setting 2px deliberately, and asserting the width
//     reported every theme as broken.
//   * Assert only on controls Ignition styles ITSELF. .ia_button--primary carries a
//     project class with its own border, so it stays green whatever the theme does --
//     verified by deleting the repair and watching the buttons pass while every input
//     failed. It is reported, never asserted on.
//
// Negative-tested 28/08/2026: with the repair removed, the six stock themes pass and
// all ten custom ones fail with `0px none`. A check that has never failed is not a
// check.
const { chromium } = require('./lib/toolkit').playwright('theme_border_check');
const UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36';
const URL = process.argv[2];
const THEMES = process.argv.slice(3);
const MEASURE = () => {
  const out = { containerBorder: getComputedStyle(document.documentElement)
                  .getPropertyValue('--containerBorder').trim(), els: {} };
  for (const sel of ['.ia_inputField', '.ia_dropdown', '.ia_button--primary']) {
    const e = document.querySelector(sel);
    if (!e) { out.els[sel] = 'absent'; continue; }
    const cs = getComputedStyle(e);
    out.els[sel] = `${cs.borderTopWidth} ${cs.borderTopStyle} ${cs.borderTopColor}`;
  }
  return out;
};
(async () => {
  const b = await chromium.launch();
  let bad = 0;
  const ctx = await b.newContext({ viewport: { width: 1600, height: 950 }, userAgent: UA });
  const p = await ctx.newPage();
  await p.goto(`${URL}/data/perspective/client/OEE/settings`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await p.waitForTimeout(18000);
  for (const theme of THEMES) {
    const label = theme.replace(/-/g, ' ').replace(/^./, c => c.toUpperCase());
    const dd = p.locator('.ia_dropdown').first();
    await dd.click(); await p.waitForTimeout(1200);
    const opt = p.locator('.ia_dropdown__option').filter({ hasText: new RegExp('^' + label + '$') }).first();
    if (!(await opt.count())) { console.log(`  MISSING ${label}`); bad++; continue; }
    await opt.click(); await p.waitForTimeout(6000);
    const r = await p.evaluate(MEASURE);
    const shorthandOk = /^1px solid /.test(r.containerBorder);
    const isDrawn = (v) => /^(?!0px)\d+(\.\d+)?px (solid|dashed|dotted) /.test(v)
                           && !/rgba\(0, 0, 0, 0\)/.test(v);
    const drawn = Object.entries(r.els)
      .filter(([, v]) => v !== 'absent')
      .map(([k, v]) => `${k}=${isDrawn(v) ? 'drawn ' + v.split(' ')[0] : 'MISSING(' + v + ')'}`);
    // assert only on the controls Ignition styles itself. A project style class
    // that sets its own border cannot fail, so including one would only make the
    // check green for the wrong reason.
    const asserted = drawn.filter(d => !d.startsWith('.ia_button'));
    const ok = shorthandOk && asserted.length > 0 && asserted.every(d => d.includes('drawn'));
    if (!ok) bad++;
    console.log(`  ${ok ? 'ok  ' : 'FAIL'}  ${theme.padEnd(16)} --containerBorder="${r.containerBorder}"  ${drawn.join('  ')}`);
  }
  await b.close();
  console.log(bad ? `\n${bad} theme(s) FAILED` : '\nevery theme draws the borders Ignition asks for');
  process.exit(bad ? 1 : 0);
})();
