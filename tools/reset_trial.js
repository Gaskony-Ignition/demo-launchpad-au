// Reset an Ignition trial licence headlessly.
//
// A gateway running unlicensed stops serving after 2 hours: Perspective, WebDev and
// the REST endpoints all return HTTP 402 "Trial Expired" while /StatusPing still
// reports RUNNING, so a health check alone will not tell you this has happened.
//
//   node reset_trial.js --gateway <name>     # credentials from the toolkit creds file
//   node reset_trial.js --url http://host:8088 --user admin   (password via env)
//
// Credentials resolve exactly as the toolkit's scan.js does, and are never read from
// argv. Exit 0 = trial reset (or gateway is licensed and needs no reset).
const fs = require('fs');
const path = require('path');

const loadPlaywright = () => require('./lib/toolkit').playwright('reset_trial');

function arg(n) { const i = process.argv.indexOf('--' + n); return i > -1 ? process.argv[i + 1] : undefined; }

const CREDS = arg('creds') || process.env.IGNITION_SCAN_CREDS ||
  (() => { try { return JSON.parse(fs.readFileSync(
      require('./lib/toolkit').toolkitFile('config.local.json'), 'utf8')).scan_credentials_file; }
    catch (e) { return undefined; } })();

const NAME = arg('gateway');
let url = arg('url');
let user = process.env.IGNITION_SCAN_USER;
let pass = process.env.IGNITION_SCAN_PASS;

if (CREDS && fs.existsSync(CREDS)) {
  const kv = {};
  for (const line of fs.readFileSync(CREDS, 'utf8').split('\n')) {
    const i = line.indexOf('=');
    if (i > 0 && !line.trim().startsWith('#')) kv[line.slice(0, i).trim()] = line.slice(i + 1).trim();
  }
  if (NAME) { url = url || kv[`${NAME}.url`]; user = user || kv[`${NAME}.user`]; pass = pass || kv[`${NAME}.password`]; }
}
if (!url || !user || !pass) { console.error('reset_trial: could not resolve url/user/password'); process.exit(2); }
url = url.replace(/\/+$/, '');

const STEP = parseInt(process.env.TIMEOUT_MS || '20000', 10);
const { chromium } = loadPlaywright();

(async () => {
  const browser = await chromium.launch({ headless: !process.env.HEADFUL });
  const pg = await (await browser.newContext({ viewport: { width: 1500, height: 1100 } })).newPage();
  let code = 1;
  try {
    await pg.goto(`${url}/web/home`, { waitUntil: 'networkidle', timeout: 30000 });

    // same two-page login as scan.js: username, Enter, then the password field appears
    await pg.click('text=Log In', { timeout: STEP });
    const u = pg.locator('input').first();
    await u.waitFor({ state: 'visible', timeout: STEP });
    await u.fill(user); await u.press('Enter');
    const p = pg.locator('input[type="password"]').first();
    await p.waitFor({ state: 'visible', timeout: STEP });
    await p.fill(pass); await p.press('Enter');
    await pg.waitForLoadState('networkidle', { timeout: STEP }).catch(() => {});

    const btn = pg.locator('button:has-text("Reset Trial"), a:has-text("Reset Trial")').first();
    if (await btn.count() === 0) {
      console.log('reset_trial: no Reset Trial control - gateway is licensed or already reset');
      code = 0;
    } else {
      await btn.click({ timeout: STEP });
      await pg.waitForTimeout(3000);
      console.log(`reset_trial: trial reset on ${NAME || url}`);
      code = 0;
    }
  } catch (e) {
    console.error('reset_trial: FAILED -', e.message.split('\n')[0]);
  } finally {
    await browser.close();
    process.exit(code);
  }
})();
