// Find the Ignition toolkit that these dev scripts borrow Playwright and the
// gateway credentials from.
//
// The toolkit's own docs call it /claude, which on this machine is a symlink to
// /Home-Claude that does not always resolve -- a require() through it fails with
// "Cannot find module", which reads exactly like Playwright not being installed.
// Look under both, and let the environment override for a machine that keeps it
// somewhere else again.
const path = require('path');

const ROOTS = [
  process.env.IGNITION_TOOLKIT,
  '/Home-Claude/ignition-claude-toolkit',
  '/claude/ignition-claude-toolkit',
].filter(Boolean);

const PLAYWRIGHT = [].concat(
  ...ROOTS.map((r) => [
    path.join(r, 'plugins/ignition/skills/verify-view/tool/node_modules/playwright'),
    path.join(r, 'plugins/ignition/skills/scan/tool/node_modules/playwright'),
  ]),
);

function playwright(who) {
  for (const p of [null].concat(PLAYWRIGHT)) {
    try { return p ? require(p) : require('playwright'); } catch (e) { /* next */ }
  }
  console.error(`${who || 'tools'}: playwright not found - looked in ${PLAYWRIGHT.join(', ')}`);
  process.exit(2);
}

// <toolkit>/plugins/ignition/<rel>, first root that has it; undefined if none do.
function toolkitFile(rel) {
  const fs = require('fs');
  for (const r of ROOTS) {
    const p = path.join(r, 'plugins/ignition', rel);
    if (fs.existsSync(p)) return p;
  }
  return undefined;
}

module.exports = { playwright, toolkitFile, ROOTS };
