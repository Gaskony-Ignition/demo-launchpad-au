// Get a fresh Ignition 8.3 gateway into a state the scan tooling can drive.
//
// A gateway that has never been logged into shows an "Enable Quick Start" modal over
// the whole web UI. It intercepts every click, so config-scan/scan just time out
// looking for "Platform" -- with nothing in the logs to say why. This dismisses it,
// choosing "start from scratch": Quick Start would otherwise create its own sample
// project, device simulator and tag historian on the gateway we are installing to.
//
//   node preflight.js --gateway <name>
//
// Exit 0 = gateway is drivable (modal dismissed, or was never there).
const fs = require('fs');

const loadPlaywright = () => require('./lib/toolkit').playwright('preflight');
function arg(n) { const i = process.argv.indexOf('--' + n); return i > -1 ? process.argv[i + 1] : undefined; }

const CREDS = arg('creds') || process.env.IGNITION_SCAN_CREDS ||
  (() => { try { return JSON.parse(fs.readFileSync(
      require('./lib/toolkit').toolkitFile('config.local.json'), 'utf8')).scan_credentials_file; }
    catch (e) { return undefined; } })();

const NAME = arg('gateway');
let url = arg('url'), user = process.env.IGNITION_SCAN_USER, pass = process.env.IGNITION_SCAN_PASS;
if (CREDS && fs.existsSync(CREDS)) {
  const kv = {};
  for (const line of fs.readFileSync(CREDS, 'utf8').split('\n')) {
    const i = line.indexOf('=');
    if (i > 0 && !line.trim().startsWith('#')) kv[line.slice(0, i).trim()] = line.slice(i + 1).trim();
  }
  if (NAME) { url = url || kv[`${NAME}.url`]; user = user || kv[`${NAME}.user`]; pass = pass || kv[`${NAME}.password`]; }
}
if (!url || !user || !pass) { console.error('preflight: could not resolve url/user/password'); process.exit(2); }
url = url.replace(/\/+$/, '');

const STEP = parseInt(process.env.TIMEOUT_MS || '20000', 10);
const { chromium } = loadPlaywright();

(async () => {
  const browser = await chromium.launch({ headless: !process.env.HEADFUL });
  const pg = await (await browser.newContext({ viewport: { width: 1500, height: 1100 } })).newPage();
  let code = 1;
  try {
    await pg.goto(`${url}/web/home`, { waitUntil: 'networkidle', timeout: 30000 });

    // The modal is rendered by React a moment AFTER networkidle, so an immediate
    // count() reports zero and the dismissal is skipped -- wait for it explicitly.
    const decline = pg.locator('button:has-text("No thanks"), a:has-text("No thanks")').first();
    try {
      await decline.waitFor({ state: 'visible', timeout: 8000 });
      await decline.click({ timeout: STEP });
      await pg.waitForTimeout(2500);
      console.log('preflight: dismissed the Quick Start modal (start from scratch)');
    } catch (e) {
      console.log('preflight: no Quick Start modal');
    }

    const login = pg.locator('text=Log In').first();
    if (await login.count() > 0) {
      await login.click({ timeout: STEP });
      const u = pg.locator('input').first();
      await u.waitFor({ state: 'visible', timeout: STEP });
      await u.fill(user); await u.press('Enter');
      const p = pg.locator('input[type="password"]').first();
      await p.waitFor({ state: 'visible', timeout: STEP });
      await p.fill(pass); await p.press('Enter');
      await pg.waitForLoadState('networkidle', { timeout: STEP }).catch(() => {});
    }

    const reset = pg.locator('button:has-text("Reset Trial"), a:has-text("Reset Trial")').first();
    if (await reset.count() > 0) {
      await reset.click({ timeout: STEP }).catch(() => {});
      await pg.waitForTimeout(2000);
      console.log('preflight: trial reset');
    }

    // the whole point: is the Platform nav reachable now?
    await pg.click('text=Platform', { timeout: STEP });
    console.log('preflight: gateway is drivable');
    code = 0;
  } catch (e) {
    console.error('preflight: FAILED -', e.message.split('\n')[0]);
  } finally {
    await browser.close();
    process.exit(code);
  }
})();
