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
//   * Treat "nothing assertable on this screen" as a FAILURE, not a pass. Demonstrated
//     by pointing the probes at a selector that exists nowhere: both themes report
//     FAIL even though the variable is correct and the excluded button is drawn.
//
// In one line: assert only on controls Ignition styles itself, never pin a value, and
// treat nothing-assertable as a failure.
//
// The load-bearing assertion is the VARIABLE, not the elements. If --containerBorder
// computes to a bare colour the run fails whatever any control on screen is doing, so
// a page where every control happens to be project-styled still cannot go green for
// the wrong reason. The element probes corroborate it.
//
// Negative-tested 28/08/2026: with the repair removed, the six stock themes pass and
// all ten custom ones fail with `0px none`. A check that has never failed is not a
// check.
const { chromium } = require('./lib/toolkit').playwright('theme_border_check');
const UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36';
const URL = process.argv[2];
const THEMES = process.argv.slice(3);
const MEASURE = () => {
  // Ask the question by DOING what .ia_inputField does, rather than matching the
  // variable's text against a regex and hoping the regex agrees with the CSS parser.
  // A throwaway element takes `border: var(--containerBorder)`; if the value is a
  // bare colour the shorthand is invalid and the computed width comes back 0px.
  // This also stops the check pinning a width, which its own rule forbids -- the
  // earlier version tested /^1px solid / and would have failed a theme that
  // legitimately said 2px.
  const raw = getComputedStyle(document.documentElement)
                .getPropertyValue('--containerBorder').trim();
  const probe = document.createElement('div');
  probe.style.border = 'var(--containerBorder)';
  document.body.appendChild(probe);
  const probed = getComputedStyle(probe).borderTopWidth;
  probe.remove();
  const out = { containerBorder: raw, borderVarUsable: probed !== '0px',
                probedWidth: probed, els: {} };
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
    const shorthandOk = r.borderVarUsable;
    const isDrawn = (v) => /^(?!0px)\d+(\.\d+)?px (solid|dashed|dotted) /.test(v)
                           && !/rgba\(0, 0, 0, 0\)/.test(v);
    const drawn = Object.entries(r.els)
      .filter(([, v]) => v !== 'absent')
      .map(([k, v]) => `${k}=${isDrawn(v) ? 'drawn ' + v.split(' ')[0] : 'MISSING(' + v + ')'}`);
    // Assert only on the controls Ignition styles itself. A project style class that
    // sets its own border cannot fail, so including one would only make the check
    // green for the wrong reason. Explicit list rather than a prefix match: if a
    // project class ever gives .ia_dropdown a border of its own, that probe has to be
    // moved here deliberately, not silently absorbed by a pattern.
    const BORDERED_BY_PROJECT = ['.ia_button--primary', '.ia_button--secondary'];
    const asserted = drawn.filter(d => !BORDERED_BY_PROJECT.some(x => d.startsWith(x + '=')));
    const ok = shorthandOk && asserted.length > 0 && asserted.every(d => d.includes('drawn'));
    if (!ok) bad++;
    // Name the fault, not its symptom: "NOT A SHORTHAND (#d3dbd8)" says what to go
    // and fix, where "0/2 bordered" only says something is wrong.
    const varState = shorthandOk
      ? `border-var: ok (${r.containerBorder})`
      : `border-var: NOT A SHORTHAND (${r.containerBorder})`;
    const assertState = asserted.length
      ? drawn.join('  ')
      : 'NOTHING ASSERTABLE ON SCREEN';
    console.log(`  ${ok ? 'ok  ' : 'FAIL'}  ${theme.padEnd(16)} ${varState}  ${assertState}`);
  }
  await b.close();
  console.log(bad ? `\n${bad} theme(s) FAILED` : '\nevery theme draws the borders Ignition asks for');
  process.exit(bad ? 1 : 0);
})();
