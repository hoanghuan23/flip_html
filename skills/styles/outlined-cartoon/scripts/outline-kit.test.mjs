import test from 'node:test';
import assert from 'node:assert/strict';
import * as K from './outline-kit.mjs';

const close = (a, b, epsilon = 1e-8) => assert.ok(K.dist(a, b) < epsilon, `${a} != ${b}`);

test('chirality is stable when cylindrical contacts rotate, for both views and approach sides', () => {
  for (const degrees of [-150, -30, 0, 40, 130]) {
    const v = K.rot([1, 0], degrees), n = K.perp(v), c = [200, 200];
    for (const side of [-1, 1]) {
      const el = K.at(K.at(c, n, -45 * side), v, -25);
      for (const view of ['palm', 'back']) {
        const h = K.fist({ c, v, elbow: el, view, k: 0.95 });
        const expected = side > 0 ? (view === 'back' ? 'right' : 'left') : (view === 'back' ? 'left' : 'right');
        assert.equal(h.hand, expected);
        close(h.wrist, K.wristFromGrip(c, v, el, 0.95));
      }
    }
  }
});

test('planning a perpendicular grip and inverse planning agree on a consistent approach side', () => {
  for (const k of [0.85, 1, 1.25]) {
    const c = [250, 210], v = K.unit([0, 0], [1, -0.3]), el = [210, 150];
    const wrist = K.wristFromGrip(c, v, el, k);
    close(K.gripFromWrist(wrist, v, el, k), c);
  }
});

test('an explicit oblique wrist stays on its planned joint instead of snapping across the rod', () => {
  const c = [250, 220], v = K.unit([0, 0], [1, -0.2]), wrist = [230, 221], el = [201, 208];
  for (const view of ['palm', 'back']) {
    const h = K.fist({ c, v, wrist, elbow: el, from: [220, 218], k: 0.95, view });
    close(h.wrist, wrist);
    assert.ok(K.dist(h.wrist, K.wristFromGrip(c, v, el, 0.95)) > 15);
    assert.ok(!/NaN|Infinity/.test(h.front + h.behind));
  }
});

test('reachable two-bone planning preserves lengths and allows wrist-aligned elbow choices', () => {
  const v = K.unit([0, 0], [1, -0.2]);
  const hip = [210, 229];
  for (const [shoulder0, c] of [[[190, 175], [255, 222]], [[235, 170], [307, 211.6]]]) {
    const shoulder = K.rot(shoulder0, 14, hip);
    const wrist = K.at(K.at(c, v, -20), K.perp(v), -3);
    assert.ok(K.dist(shoulder, wrist) < 72);
    const candidates = [-1, 1].map(side => K.elbow(shoulder, wrist, 36, 36, side));
    assert.ok(candidates.some(e => {
      assert.ok(Math.abs(K.dist(shoulder, e) - 36) < 1e-8);
      assert.ok(Math.abs(K.dist(e, wrist) - 36) < 1e-8);
      const a = K.unit(e, wrist), b = K.unit(wrist, c);
      return a[0] * b[0] + a[1] * b[1] >= Math.cos(Math.PI / 6);
    }));
  }
});

test('invalid scales, radii, views and detached explicit wrists fail before SVG emission', () => {
  const base = { c: [200, 200], v: [1, 0], elbow: [160, 170] };
  for (const k of [0, -1, Infinity, NaN]) assert.throws(() => K.fist({ ...base, k }), RangeError);
  for (const rr of [0, -1, Infinity, NaN]) assert.throws(() => K.fist({ ...base, rr }), RangeError);
  assert.throws(() => K.fist({ ...base, view: 'side' }), RangeError);
  for (const wrist of [[200, 200], [130, 200], [NaN, 200]]) assert.throws(() => K.fist({ ...base, wrist, k: 1 }), RangeError);
});
