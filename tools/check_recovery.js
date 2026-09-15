// Assert that a session opened BEFORE the gateway is set up recovers once it is.
//
//   node tools/install_ui.js --url URL --zip OEE=... --zip KPI=... --no-setup
//   node tools/check_recovery.js --url URL [--project OEE] [--minutes 2]
//
// Why this exists as its own check. Every other test here opens its browser AFTER
// setup has finished, and a session opened after setup cannot see this class of
// defect at all -- so all of them passed while a user following the documented order
// (import, look at the project, then press Set up) got a Line View with an empty line
// dropdown, null on every value and a quality overlay across the card, permanently.
//
// The mechanism was three things stacked, and only the first is obvious:
//   * the session's line list came from a tag browse taken once at session start,
//     when there were no tags, so it was empty for the life of the session;
//   * the view's onStartup did lines[0] on that empty list, raised IndexError, and
//     never selected a line -- and onStartup does not run again;
//   * with no line selected every downstream tag path was invalid, hence the nulls.
//
// The page has a refresh button that fixes all of it in one click, which is exactly
// why it survived: anyone testing interactively presses it without thinking.
const path = require('path');
const { chromium } = require('./lib/toolkit').playwright('check_recovery');

function arg(n, d) { const i = process.argv.indexOf('--' + n); return i > -1 ? process.argv[i + 1] : d; }
const URL = arg('url', 'http://localhost:8091').replace(/\/+$/, '');
const PROJECT = arg('project', 'OEE');
const MINUTES = parseFloat(arg('minutes', '2'));

let failures = 0;
const fail = (m) => { failures++; console.log('  FAIL  ' + m); };
const pass = (m) => console.log('  ok    ' + m);

async function state(page) {
  return page.evaluate(() => {
    const t = document.body.innerText;
    return {
      nulls: (t.match(/\bnull\b/g) || []).length,
      // a rendered quality overlay, not the hidden template every component carries
      overlay: [...document.querySelectorAll('.ia_qualityOverlay--error')]
        .filter((e) => { const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0; })
        .length,
      line: /Line [1-7]/.test(t),
    };
  });
}

(async () => {
  const browser = await chromium.launch();
  // ONE context for the whole run: that is what makes it one Perspective session,
  // which is the entire point of the check.
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });

  const app = await ctx.newPage();
  await app.goto(`${URL}/data/perspective/client/${PROJECT}/line-view`,
                 { waitUntil: 'domcontentloaded', timeout: 60000 });
  await app.waitForTimeout(25000);
  const before = await state(app);
  if (before.line) {
    console.log('  SKIP  the gateway is already set up - this check needs one that is not');
    await browser.close();
    process.exit(0);
  }
  pass(`session opened before setup, as a user would (nulls=${before.nulls}, `
     + `overlays=${before.overlay})`);

  const settings = await ctx.newPage();
  await settings.goto(`${URL}/data/perspective/client/${PROJECT}/settings`,
                      { waitUntil: 'domcontentloaded', timeout: 60000 });
  await settings.waitForTimeout(20000);
  await settings.locator('text="Set up this gateway"').first().click();
  let verdict = '';
  for (let i = 0; i < 100; i++) {
    await settings.waitForTimeout(3000);
    verdict = await settings.evaluate(() => {
      const hits = [...document.querySelectorAll('div,span,p')]
        .filter((e) => /SETUP (COMPLETE|FAILED|FINISHED)/.test(e.innerText || ''))
        .sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
      return hits.length ? hits[0].innerText.trim() : '';
    });
    if (verdict) break;
  }
  if (/SETUP COMPLETE/.test(verdict)) pass('setup completed');
  else fail(`setup did not complete: ${verdict.split('\n').pop() || '(no verdict)'}`);

  // The recovery is on a timer, so give it more than one tick before judging.
  await app.bringToFront();
  let healed = null;
  for (let i = 0; i < Math.ceil((MINUTES * 60) / 30); i++) {
    await app.waitForTimeout(30000);
    const now = await state(app);
    if (now.line && !now.nulls && !now.overlay) { healed = (i + 1) * 30; break; }
  }
  if (healed !== null) pass(`the page recovered ${healed}s after setup, same session`);
  else {
    const now = await state(app);
    fail(`still broken ${MINUTES} min after setup in the same session `
       + `(nulls=${now.nulls}, overlays=${now.overlay}, a line selected: ${now.line})`);
  }

  await browser.close();
  console.log(failures ? `\n${failures} check(s) FAILED` : '\nrecovery check passed');
  process.exit(failures ? 1 : 0);
})();
