// Install the packaged projects the way a user does: through the gateway's own
// Platform > Projects > Import Project dialog, then press "Set up this gateway".
//
//   node tools/install_ui.js --url http://localhost:8091 \
//        --zip OEE=dist/launchpad_oee_au.2.1.2.zip \
//        --zip KPI=dist/launchpad_kpi_au.2.1.2.zip [--overwrite] [--no-setup]
//
// This exists because `tools/install.sh` untars the projects straight into
// data/projects, and untarring tolerates things the importer rejects. A resource
// folder containing a file its resource.json does not declare -- a stray
// __pycache__, say -- loads fine when copied and is silently DROPPED by the
// importer, taking its whole resource with it. That shipped once. Every test we
// had passed, because every test took the shortcut past the real entry point.
//
// So: install.sh is for installing, this is for proving. The zips it takes are
// the release artefacts, not the working tree.
//
// Exits non-zero if an import fails or a Setup run does not reach SETUP COMPLETE.
const path = require('path');
const fs = require('fs');
const { chromium } = require('./lib/toolkit').playwright('install_ui');

function arg(n, d) { const i = process.argv.indexOf('--' + n); return i > -1 ? process.argv[i + 1] : d; }
function args(n) {
  const out = [];
  process.argv.forEach((a, i) => { if (a === '--' + n) out.push(process.argv[i + 1]); });
  return out;
}
const URL = arg('url', 'http://localhost:8091').replace(/\/+$/, '');
const USER = arg('user', 'admin');
const PASS = arg('password', 'password');
const OVERWRITE = process.argv.includes('--overwrite');
const SETUP = !process.argv.includes('--no-setup');
const STEP = 30000;
// A headless browser with the default user agent is served a degraded "Browser Not
// Supported" page that has no Import control on it at all -- which looks exactly
// like the gateway not offering one.
const UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
         + 'Chrome/140.0.0.0 Safari/537.36';

const ZIPS = args('zip').map((s) => {
  const [name, ...rest] = s.split('=');
  const file = rest.join('=');
  if (!file) throw new Error(`--zip wants NAME=path, got "${s}"`);
  if (!fs.existsSync(file)) throw new Error(`no such package: ${file}`);
  return { name, file: path.resolve(file) };
});
if (!ZIPS.length) { console.error('nothing to install: pass --zip NAME=path'); process.exit(2); }

let failures = 0;
const fail = (m) => { failures++; console.log('  FAIL  ' + m); };
const pass = (m) => console.log('  ok    ' + m);

// A gateway nobody has logged into yet puts an "Enable Quick Start" modal over the
// page. It intercepts every click including the Log In link, so it has to go before
// the login and again after -- it is re-offered once you are authenticated.
async function dismissQuickStart(page) {
  for (let i = 0; i < 6; i++) {
    const modal = page.locator('[data-component="web-ui.quick-start-modal"]');
    if (!(await modal.count())) return;
    const labels = (await modal.locator('button').allInnerTexts()).filter(Boolean);
    if (labels.length) {
      const pick = labels.find((l) => /no thanks|scratch|close|cancel|skip/i.test(l)) || labels[0];
      // dispatchEvent, not click: the modal's own backdrop covers its buttons, so a
      // real mouse click lands on the backdrop however hard it is forced. Dispatching
      // sends the event to the node itself and ignores what is painted over it.
      // Removing the modal from the DOM instead does not work -- React puts it back.
      await modal.locator(`button:has-text("${pick}")`).first()
        .dispatchEvent('click').catch(() => {});
    } else {
      await page.keyboard.press('Escape');
    }
    await page.waitForTimeout(2000);
  }
}

// The modal is re-offered at moments that are not worth predicting, so anything that
// has to be clicked on the gateway's own web UI goes through here.
async function clickThrough(page, selector, tries) {
  for (let i = 0; i < (tries || 5); i++) {
    await dismissQuickStart(page);
    const target = page.locator(selector).first();
    try {
      await target.waitFor({ state: 'visible', timeout: 15000 });
      await target.dispatchEvent('click');
      return true;
    } catch (e) { await page.waitForTimeout(2000); }
  }
  return false;
}

async function login(page) {
  await page.goto(`${URL}/web/home`, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(4000);
  await dismissQuickStart(page);
  if (!(await clickThrough(page, 'text=Log In'))) {
    throw new Error('could not reach the login form - the gateway web UI never settled');
  }
  const user = page.locator('input').first();
  await user.waitFor({ state: 'visible', timeout: STEP });
  await user.fill(USER); await user.press('Enter');
  const pw = page.locator('input[type="password"]').first();
  await pw.waitFor({ state: 'visible', timeout: STEP });
  await pw.fill(PASS); await pw.press('Enter');
  await page.waitForLoadState('networkidle', { timeout: STEP }).catch(() => {});
  await page.waitForTimeout(3000);
  await dismissQuickStart(page);
}

async function importProject(page, { name, file }) {
  await clickThrough(page, 'text=Platform');
  await clickThrough(page, 'text=Projects');
  await page.waitForTimeout(5000);

  const open = page.locator('button:has-text("Import")').first();
  if (!(await open.count())) { fail(`${name}: no Import Project control on the Projects page`); return; }
  await open.click({ timeout: STEP });
  await page.waitForTimeout(2500);

  const chooser = page.locator('input[type="file"]').first();
  await chooser.waitFor({ state: 'attached', timeout: STEP });
  await chooser.setInputFiles(file);
  // The dialog will not enable its Import button until a project name is typed, and
  // the name is load-bearing: setup points the gateway scripting project at "OEE" by
  // name, so a project imported under any other name half-works.
  await page.locator('input[type="text"]').last().fill(name);
  if (OVERWRITE) {
    const box = page.locator('input[type="checkbox"]').last();
    if (await box.count()) await box.check({ timeout: 8000 }).catch(() => {});
  }
  await page.waitForTimeout(1500);

  // "Import Project" on the page behind the dialog also contains the word, so the
  // confirm has to be matched by exact accessible name.
  const confirm = page.getByRole('button', { name: 'Import', exact: true });
  for (let i = 0; i < 15 && !(await confirm.isEnabled().catch(() => false)); i++) {
    await page.waitForTimeout(1000);
  }
  if (!(await confirm.isEnabled().catch(() => false))) { fail(`${name}: Import stayed disabled`); return; }
  await confirm.click({ timeout: STEP });

  // The modal's backdrop keeps intercepting clicks until the import finishes, so it
  // doubles as the progress indicator the dialog does not have.
  const backdrop = page.locator('#import-project-modal-backdrop');
  for (let i = 0; i < 60 && (await backdrop.count()); i++) await page.waitForTimeout(2000);
  await page.waitForTimeout(5000);
  if (await backdrop.count()) fail(`${name}: import dialog never closed`);
  else pass(`imported ${name} from ${path.basename(file)}`);
}

async function pressSetup(page, project) {
  await page.goto(`${URL}/data/perspective/client/${project}/settings`,
                  { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(22000);
  const button = page.locator('text="Set up this gateway"').first();
  if (!(await button.count())) { fail(`${project}: no Setup button - did the project load?`); return; }
  await button.click();

  // Setup takes minutes on an empty gateway: it waits for the tag provider and the
  // historian to come up, then backfills history once the historian has registered
  // the tags. Read the transcript rather than a fixed sleep.
  for (let i = 0; i < 90; i++) {
    await page.waitForTimeout(3000);
    const verdict = await page.evaluate(() => {
      const hits = [...document.querySelectorAll('div,span,p')]
        .filter((e) => /SETUP (COMPLETE|FINISHED|FAILED)/.test(e.innerText || ''))
        .sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
      return hits.length ? hits[0].innerText.trim() : '';
    });
    if (!verdict) continue;
    console.log(verdict.split('\n').map((l) => '        ' + l).join('\n'));
    if (/SETUP COMPLETE/.test(verdict)) pass(`${project}: setup complete`);
    else fail(`${project}: setup did not complete`);
    return;
  }
  fail(`${project}: no verdict after 4.5 minutes`);
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 }, userAgent: UA });
  const page = await ctx.newPage();

  await login(page);
  console.log(`logged in to ${URL}${OVERWRITE ? ' (importing with overwrite)' : ''}`);
  for (const zip of ZIPS) await importProject(page, zip);
  if (SETUP) for (const zip of ZIPS) await pressSetup(page, zip.name);

  await browser.close();
  console.log(failures ? `\n${failures} step(s) FAILED` : '\ninstalled and set up cleanly');
  process.exit(failures ? 1 : 0);
})();
