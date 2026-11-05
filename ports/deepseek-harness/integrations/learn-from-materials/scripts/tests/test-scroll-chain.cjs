const {test} = require('node:test');
const assert = require('node:assert/strict');
const {route} = require('../../templates/scroll-chain.js');

// Exercise the route used by both hovercards, including ancestry and native
// event cancellation. Outer scroll boxes detect accidental forwarding.
class ScrollBox {
  constructor(top = 0, max = 0, options = {}) {
    Object.assign(this, {scrollTop: top, clientHeight: 100, scrollHeight: max + 100,
      scrollLeft: 0, clientWidth: 100, scrollWidth: 100, parentElement: null,
      overflowY: 'auto', overflowX: 'auto'}, options);
  }
  contains(node) {
    for (; node; node = node.parentElement) if (node === this) return true;
    return false;
  }
}
global.Element = ScrollBox;
global.getComputedStyle = element => element;
function event(target, y, extra = {}) {
  return {target, deltaX: 0, deltaY: y, deltaMode: 0, cancelable: true,
    prevented: 0, stopped: 0, preventDefault() {this.prevented++;},
    stopPropagation() {this.stopped++;}, ...extra};
}
function fixture(innerTop = 0, hoverTop = 0) {
  const page = new ScrollBox(250, 1000);
  const viewport = new ScrollBox(120, 500, {parentElement: page});
  const hover = new ScrollBox(hoverTop, 200, {parentElement: page});
  const inner = new ScrollBox(innerTop, 100, {parentElement: hover});
  const text = new ScrollBox(0, 0, {parentElement: inner, overflowY: 'visible', overflowX: 'visible'});
  return {page, viewport, hover, inner, text};
}
function outerStill(f) {
  assert.deepEqual([f.viewport.scrollTop, f.page.scrollTop], [120, 250]);
  assert.deepEqual([f.viewport.scrollLeft, f.page.scrollLeft], [0, 0]);
}
function cancelled(e) {
  assert.equal(e.prevented, 1);
  assert.equal(e.stopped, 1);
}

test('inner list consumes input before the floating card', () => {
  const f = fixture(20), e = event(f.text, 60);
  assert.equal(route(e, f.hover, f.viewport), true);
  assert.deepEqual([f.inner.scrollTop, f.hover.scrollTop], [80, 0]);
  cancelled(e); outerStill(f);
});
test('residual list movement reaches the card, never the graph or page', () => {
  const f = fixture(90, 180), e = event(f.text, 100);
  route(e, f.hover, f.viewport);
  assert.deepEqual([f.inner.scrollTop, f.hover.scrollTop], [100, 200]);
  cancelled(e); outerStill(f);
});
test('repeated downward gestures at the bottom remain contained', () => {
  const f = fixture(100, 200);
  for (const delta of [12, 0.25, 80, 300]) {
    const e = event(f.text, delta);
    assert.equal(route(e, f.hover, f.viewport), true); cancelled(e);
  }
  assert.deepEqual([f.inner.scrollTop, f.hover.scrollTop], [100, 200]); outerStill(f);
});
test('upward input reaches the card and stops at the top', () => {
  const f = fixture(10, 20), e = event(f.text, -100);
  route(e, f.hover, f.viewport);
  assert.deepEqual([f.inner.scrollTop, f.hover.scrollTop], [0, 0]);
  cancelled(e); outerStill(f);
  for (const delta of [-0.5, -50, -400]) {
    const next = event(f.text, delta); route(next, f.hover, f.viewport); cancelled(next);
  }
  outerStill(f);
});
test('a card without scroll range still consumes boundary input', () => {
  const f = fixture(); f.hover.scrollHeight = f.hover.clientHeight;
  const e = event(f.hover, 60);
  route(e, f.hover, f.viewport);
  assert.equal(f.hover.scrollTop, 0); cancelled(e); outerStill(f);
});
test('nested scrollable descendants receive input before parents', () => {
  const f = fixture(10, 20);
  const nested = new ScrollBox(45, 50, {parentElement: f.inner});
  const e = event(nested, 30);
  route(e, f.hover, f.viewport);
  assert.deepEqual([nested.scrollTop, f.inner.scrollTop, f.hover.scrollTop], [50, 35, 20]);
  cancelled(e); outerStill(f);
});
test('line and page units use the floating card dimensions', () => {
  const f = fixture(); f.hover.scrollHeight = 2100;
  route(event(f.hover, 2, {deltaMode: 1}), f.hover, f.viewport);
  assert.equal(f.hover.scrollTop, 80);
  route(event(f.hover, 1, {deltaMode: 2}), f.hover, f.viewport);
  assert.equal(f.hover.scrollTop, 180); outerStill(f);
});
test('fractional trackpad deltas preserve their distance', () => {
  const f = fixture(), e = event(f.text, 0.5);
  route(e, f.hover, f.viewport);
  assert.equal(f.inner.scrollTop, 0.5); cancelled(e); outerStill(f);
});
test('Shift-wheel scrolls horizontally inside the card only', () => {
  const f = fixture(); f.inner.scrollWidth = 200; f.inner.scrollLeft = 90;
  f.hover.scrollWidth = 300; f.hover.scrollLeft = 180;
  const e = event(f.text, 60, {shiftKey: true});
  route(e, f.hover, f.viewport);
  assert.deepEqual([f.inner.scrollLeft, f.hover.scrollLeft, f.hover.scrollTop], [100, 200, 0]);
  cancelled(e); outerStill(f);
});
test('two-axis input discards residual movement on each axis', () => {
  const f = fixture(95, 195); f.inner.scrollWidth = 120; f.inner.scrollLeft = 15;
  f.hover.scrollWidth = 150; f.hover.scrollLeft = 45;
  const e = event(f.text, 50, {deltaX: 50});
  route(e, f.hover, f.viewport);
  assert.deepEqual([f.inner.scrollTop, f.hover.scrollTop, f.inner.scrollLeft, f.hover.scrollLeft], [100, 200, 20, 50]);
  cancelled(e); outerStill(f);
});
test('browser zoom and non-cancelable input retain native handling', () => {
  for (const extra of [{ctrlKey: true}, {metaKey: true}, {cancelable: false}]) {
    const f = fixture(), e = event(f.text, 100, extra);
    assert.equal(route(e, f.hover, f.viewport), false);
    assert.deepEqual([f.inner.scrollTop, f.hover.scrollTop, e.prevented, e.stopped], [0, 0, 0, 0]);
    outerStill(f);
  }
});
test('zero-distance input leaves the event untouched', () => {
  const f = fixture(), e = event(f.text, 0);
  assert.equal(route(e, f.hover, f.viewport), false);
  assert.deepEqual([e.prevented, e.stopped], [0, 0]); outerStill(f);
});
