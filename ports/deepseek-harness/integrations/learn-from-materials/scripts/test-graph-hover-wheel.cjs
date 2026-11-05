// Integration check: both diagrams route floating-detail wheel events through
// the shared scroll-chain helper. The helper's movement logic is tested in
// scripts/tests/test-scroll-chain.cjs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
for (const name of ['graph-studio.js', 'relationship-mindmap.js']) {
  const source = fs.readFileSync(path.join(root, 'templates', name), 'utf8');
  assert.match(source, /hover\.addEventListener\('wheel',\s*(?:event|e)\s*=>\s*window\.LFMScrollChain\.route\(/,
    name + ' must contain floating-detail wheel input through the shared route');
}
const css = fs.readFileSync(path.join(root, 'templates', 'visual-finish.css'), 'utf8');
assert.match(css, /\.lfm-mm-hover \.relation-edge-list\{[^}]*overflow:auto/,
  'The framework relation list must keep an inner scrollbar');
console.log('PASS both floating details use the shared contained wheel route');
