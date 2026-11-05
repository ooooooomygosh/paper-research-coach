// Static structural audit of a generated single-file learning page.
//
// Checks the invariants that a text-only edit can silently break: tag balance,
// the embedded pageData JSON, theme-token discipline, and — most importantly —
// the presence of the bounded direction-motion contract (one entrance,
// hover once, selected/demo batches, rebuild still state,
// hidden-panel guard, reduced-motion gate).
//
//   node scripts/verify-diagram-motion.cjs page.html
//
// Exit code 0 = all invariants hold, 1 = at least one failed.

const fs = require('fs');

const file = process.argv[2];
if (!file) {
  console.error('usage: node verify-diagram-motion.cjs <page.html>');
  process.exit(2);
}
const s = fs.readFileSync(file, 'utf8');

let failures = 0;
const check = (label, ok, detail) => {
  if (!ok) failures++;
  console.log((ok ? 'PASS  ' : 'FAIL  ') + label.padEnd(30) + (detail == null ? '' : detail));
};

// ---- structure ------------------------------------------------------------
const stripped = s
  .replace(/<script[\s\S]*?<\/script>/gi, '')
  .replace(/<style[\s\S]*?<\/style>/gi, '')
  .replace(/<!--[\s\S]*?-->/g, '');
const VOID = /^<(br|hr|img|input|meta|link|source|area|base|col|embed|param|track|wbr)\b/i;
const census = {};
let opens = 0;
for (const m of stripped.matchAll(/<(\w[\w-]*)(?:\s[^>]*)?>/g)) {
  if (/\/>$/.test(m[0]) || VOID.test(m[0])) continue;
  opens++;
  const t = m[1].toLowerCase();
  census[t] = (census[t] || 0) + 1;
}
let closes = 0;
for (const m of stripped.matchAll(/<\/(\w[\w-]*)>/g)) {
  closes++;
  const t = m[1].toLowerCase();
  census[t] = (census[t] || 0) - 1;
}
console.log('bytes          ', Buffer.byteLength(s));
console.log('lines          ', s.split('\n').length);
check('tag balance', opens === closes, opens + ' / ' + closes);
const unbalanced = Object.entries(census).filter(([, v]) => v !== 0);
check('no unbalanced tags', unbalanced.length === 0, JSON.stringify(unbalanced));

const pd = s.match(/<script id="pageData"[^>]*>([\s\S]*?)<\/script>/);
if (pd) {
  try { check('pageData JSON parses', true, 'keys=' + Object.keys(JSON.parse(pd[1])).length); }
  catch (e) { check('pageData JSON parses', false, e.message); }
} else check('pageData JSON parses', false, 'block missing');

// ---- theming discipline ---------------------------------------------------
const hardcoded = (s.match(/\.diagram-[^{]*\{[^}]*#[0-9a-fA-F]{3,6}/g) || []);
check('no hard-coded diagram colours', hardcoded.length === 0, hardcoded.length + ' rule(s)');

// ---- arrowheads: solid fill, never a stroked wedge ------------------------
check('three arrowhead markers',
  (s.match(/dg-arrow-normal/g) || []).length > 0 &&
  (s.match(/dg-arrow-feedback/g) || []).length > 0 &&
  (s.match(/dg-arrow-inference/g) || []).length > 0);
// The three marker paths are built in one loop, so the triangle literal appears
// once in the script while the marker *ids* appear once each. Assert the solid
// triangle exists and that all three markers are constructed from it.
const solidTriangle = /d:'M 0 0 L 10 5 L 0 10 Z'/.test(s);
const markerLoop = /\[\[['"]normal['"],['"]dg-arrow-normal['"],\d+\],\s*\[['"]feedback['"],['"]dg-arrow-feedback['"],\d+\],\s*\[['"]inference['"],['"]dg-arrow-inference['"],\d+\]\]/.test(s);
check('arrowheads are solid triangles', solidTriangle && markerLoop,
  solidTriangle ? (markerLoop ? '' : 'loop does not build all three') : 'triangle literal missing');
check('no stroked marker wedge', !/marker[\s\S]{0,400}stroke-width:\s*1/.test(s) || !solidTriangle);
check('inference arrowheads not stroked', /dg-arrow-inference\{fill:var\(--dg-arrow-inference\);opacity/.test(s.replace(/\s+/g, '')));
check('methodology inference remains solid', /diagram-wire\.is-inference\{stroke:var\(--dg-wire-inference\)\}/.test(s) && !/diagram-wire\.is-inference\{[^}]*stroke-dasharray/.test(s));
check('framework inference keeps dashes', /lfm-mm-wire\.is-inference\{[^}]*stroke-dasharray:7 6/.test(s));

// ---- motion contract ------------------------------------------------------
console.log('--- wire motion ---');
check('draw-in keyframes', /@keyframes\s+dg-draw/.test(s));
check('shared exact-geometry cue helper', /window\.LFMGraphMotion=\{mount,symmetric\}/.test(s) && /strokeDashoffset:-length/.test(s));
check('no perpetual feedback pulse', !/@keyframes\s+dg-breath/.test(s));
check('selected cue has bounded batches', /Math\.min\(3,eligible\.length\)/.test(s) && /setTimeout\(tick,2800\)/.test(s) && /iterations:1/.test(s));
check('hover cue runs one pass', /preview\(ids\)/.test(s) && /previewTimer=setTimeout\(refresh,2300\)/.test(s));
check('symmetric relations never travel', /\['contrasts','contrast','comparison','parallel','compares'\]/.test(s) && /if\(symmetric\(entry\.edge\)\)return/.test(s));
check('cue lifecycle cancels resources', /animations\.forEach\(animation=>animation\.cancel\(\)\)/.test(s) && /function destroy\(\)/.test(s) && /document\.hidden/.test(s));
check('direction demo opt-in', /demo=false/.test(s) && /directionButton/.test(s));
check('width and overview modes', /fitMode==='all'/.test(s) && /查看全图/.test(s));
check('is-drawn state', /is-drawn/.test(s));
check('is-flowing state', /is-flowing/.test(s));
check('flow layer is a separate path', /diagram-flow/.test(s));
check('geometry measured after insert', /getTotalLength/.test(s));
check('rebuild re-arms the draw', /function\s+settleWires/.test(s) && /function\s+armDraw/.test(s));
check('hidden-panel layout guard', /clientWidth<=0/.test(s));
check('visibility re-announce', /const\s+announce\s*=/.test(s));
check('refresh exported from mount', /refresh\(\)\{|refresh\s*:\s*function/.test(s) && /\{select,layout,root,positions,refresh,motion,destroy/.test(s));
check('host calls refresh', /diagram\.refresh/.test(s) || /\.refresh\(\)/.test(s));
check('reduced-motion still composed', (s.match(/prefers-reduced-motion/g) || []).length >= 2);
check('reduced-motion gated in JS', /RM\.matches/.test(s));

// ---- relationship labels and compact cards -------------------------------
console.log('--- card layout ---');
check('no repeated card relation rows', !/['"]diagram-transitions['"]/.test(s));
check('line labels have edge identities', /class:'diagram-edge-label'/.test(s) && /'data-edge-id':e\.id/.test(s));
check('line labels centered and focusable', /'text-anchor':'middle'/.test(s) && /tabindex:'0',role:'button','aria-label':labelText/.test(s));
check('labels above all wires and cues', /svg\.append\(wireLayer,flowLayer,labelLayer\)/.test(s) && /labelLayer\.append\(lg\)/.test(s));
check('wire and cue reserve label gap', /maskUnits:'userSpaceOnUse'/.test(s) && /paths\.get\(route\.id\)\.setAttribute\('mask'/.test(s) && /flows\.get\(route\.id\)\.setAttribute\('mask'/.test(s));
check('labels measured and wrapped', /labelMeasure\.measureText/.test(s) && /spec\.lines\.forEach/.test(s));
check('opaque themed label backing', /fill:var\(--dg-label-bg\);fill-opacity:1/.test(s.replace(/\s+/g,'')) && /diagram-edge-label\.is-dimmed\{opacity:1/.test(s.replace(/\s+/g,'')));
check('selected edge survives rebuild', /highlight\(selected,selectedEdge\)/.test(s));
check('card heights measured for rows', /cards\.get\(n\.id\)\.offsetHeight/.test(s) && /heights\[p\.row\]\s*=\s*Math\.max/.test(s));

// ---- registry -------------------------------------------------------------
console.log('--- wiring ---');
console.log('mount calls    ', (s.match(/LFMGraphStudio\.mount\(/g) || []).length);

console.log('');
if (failures) {
  console.log('RESULT: ' + failures + ' check(s) FAILED');
  process.exit(1);
}
console.log('RESULT: all checks passed');
process.exit(0);
