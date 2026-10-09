// Find the Ignition toolkit that these dev scripts borrow Playwright and the
// gateway credentials from. IGNITION_TOOLKIT must point at its checkout.
const path = require('path');

if (!process.env.IGNITION_TOOLKIT) {
  throw new Error('IGNITION_TOOLKIT is not set: point it at the ignition-claude-toolkit checkout');
}
const ROOTS = [process.env.IGNITION_TOOLKIT];

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
