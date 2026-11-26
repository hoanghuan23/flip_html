// Exercise generated camera timelines and the playlist offline, without tiles/WebGL.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(process.argv[2]);
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');
const scripts = (html) => [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)]
  .filter(([tag]) => !/^<script[^>]*(?:application\/json|\bsrc=)/.test(tag))
  .map(([, code]) => code);
const data = (html, id) => JSON.parse(html.match(new RegExp(`<script[^>]*id="${id}"[^>]*>([\\s\\S]*?)</script>`))[1]);
const plain = (value) => JSON.parse(JSON.stringify(value));
const angleDelta = (a, b) => Math.abs(((a - b + 540) % 360) - 180);

function scene(file) {
  const html = read(file), d = data(html, 'map-data');
  const elements = [];
  const element = () => {
    const el = { style: { setProperty(name, value) { this[name] = value; } },
      getBoundingClientRect: () => ({ width: 140, height: 36 }) };
    elements.push(el); return el;
  };
  class Map {
    constructor(options) {
      this.camera = options; this.handlers = {};
      this.container = { clientWidth: 960, clientHeight: 540 };
      this.fitCamera = { center: { lng: 106.5, lat: 16.5 }, zoom: 4.25 };
    }
    getContainer() { return this.container; }
    cameraForBounds(bounds, options) { this.fit = { bounds, options }; return this.fitCamera; }
    on(event, callback) { this.handlers[event] = callback; }
    once(event, callback) { callback(); }
    jumpTo(camera) { this.camera = camera; }
    setPaintProperty(id, name, value) { this.gradient = value; }
    addSource() {}
    addLayer() {}
  }
  class Marker {
    constructor() {}
    setLngLat(coord) { this.coord = coord; return this; }
    addTo() { return this; }
  }
  const context = vm.createContext({
    document: { getElementById: () => ({ textContent: JSON.stringify(d) }), createElement: element },
    maplibregl: { Map, Marker }, parent: { postMessage() {} }, addEventListener() {},
  });
  context.window = context;
  vm.runInContext(scripts(html)[0], context);
  const initialCamera = plain(context.mapInstance.camera);
  context.mapInstance.handlers.load();
  function at(t) {
    context.renderAt(t);
    return plain({ center: context.mapInstance.camera.center, zoom: context.mapInstance.camera.zoom,
      coord: context.carMarker.coord, heading: parseFloat(elements[0].style['--heading']),
      progress: context.mapInstance.gradient?.[3] });
  }
  assert.deepEqual(initialCamera.center, at(0).center, `${file}: initialize at this scene's camera`);
  assert.equal(initialCamera.zoom, at(0).zoom);
  return { d, at, file, map: context.mapInstance };
}

const playlist = read('index.html'), entries = data(playlist, 'data');
const scenes = entries.map((entry) => scene(entry.src));
for (const item of scenes) {
  const { d, at, file } = item;
  const sample = at(d.duration * .7);
  at(d.duration); at(0);
  assert.deepEqual(at(d.duration * .7), sample, `${file}: seeking must be deterministic`);
  assert.deepEqual(at(-1), at(0));
  assert.deepEqual(at(d.duration + 1), at(d.duration));
  if (d.phase.mode === 'summary') {
    const camera = item.map.fitCamera, end = at(d.duration);
    assert.deepEqual(end.center, [camera.center.lng, camera.center.lat], `${file}: use the fitted overview center`);
    assert.equal(end.zoom, camera.zoom, `${file}: use the fitted overview zoom`);
    const { bounds, options } = item.map.fit;
    for (const coord of [...d.stops.map((stop) => stop.coord), ...d.legs.flatMap((leg) => leg.coordinates)]) {
      assert.ok(coord.every((v, i) => v >= bounds[0][i] && v <= bounds[1][i]), `${file}: bounds contain the whole journey`);
    }
    assert.ok(options.padding.top >= 48 && options.padding.bottom >= 64 && options.padding.right >= 140,
      `${file}: overview reserves room for labels, car and attribution`);
    item.map.container = { clientWidth: 540, clientHeight: 304 };
    item.map.fitCamera = { center: { lng: 107, lat: 16 }, zoom: 3.5 };
    item.map.handlers.resize();
    assert.equal(item.map.camera.zoom, 3.5, `${file}: resize reapplies the fitted camera at the same timeline time`);
    item.map.container = { clientWidth: 960, clientHeight: 540 };
    item.map.fitCamera = camera;
    item.map.handlers.resize();
  }
  if (d.phase.mode !== 'move') continue;
  const end = at(d.duration), arrivalStart = d.duration - 4.5;
  assert.equal(at(0).progress, 0);
  assert.ok(at(0).zoom - at(1).zoom < .75, `${file}: departure zoom must not rush in the first second`);
  assert.ok(at(2).zoom > 7.5, `${file}: allow time to open up the departure map`);
  assert.equal(at(1).progress, 0, `${file}: wait for a wider map before moving the car`);
  let departure = at(0);
  for (let t = 1 / 60; t < Math.min(4.5, d.duration * .4); t += 1 / 60) {
    const next = at(t);
    assert.ok(next.zoom <= departure.zoom + 1e-10 && departure.zoom - next.zoom < .06,
      `${file}: departure zoom is gradual at 60 fps`);
    if (next.progress > 0) assert.ok(next.zoom < 10, `${file}: car only moves once the view is wide enough`);
    departure = next;
  }
  assert.ok(Math.abs(end.progress - 1) < 1e-12);
  assert.equal(end.zoom, 13);
  assert.ok(end.zoom - at(d.duration - 1).zoom < .6, `${file}: no last-second zoom rush`);
  let before = at(Math.max(0, arrivalStart));
  for (let t = Math.max(0, arrivalStart) + 1 / 60; t < d.duration; t += 1 / 60) {
    const next = at(t);
    assert.ok(next.zoom >= before.zoom - 1e-10 && next.zoom - before.zoom < .055,
      `${file}: arrival zoom is gradual at 60 fps`);
    assert.ok(next.progress >= before.progress, `${file}: never reverse on the route`);
    before = next;
  }
  const lastSecond = end.progress - at(d.duration - 1).progress;
  const previousSecond = at(d.duration - 1).progress - at(d.duration - 2).progress;
  assert.ok(lastSecond < previousSecond * .15, `${file}: car brakes before arrival`);
  assert.ok(end.zoom - at(d.duration - 1 / 60).zoom < .001,
    `${file}: zoom velocity settles at the scene boundary`);
  const headings = Array.from({ length: 121 }, (_, i) => at(d.duration * i / 120).heading);
  const turns = headings.slice(1).map((angle, i) => angleDelta(angle, headings[i]));
  const p95 = [...turns].sort((a, b) => a - b)[Math.floor(turns.length * .95)];
  assert.ok(Math.max(...turns) < 20 && p95 < 12,
    `${file}: heading must not shake (max=${Math.max(...turns).toFixed(2)}, p95=${p95.toFixed(2)})`);
}
for (let i = 1; i < scenes.length; i++) {
  const before = scenes[i - 1].at(scenes[i - 1].d.duration), after = scenes[i].at(0);
  assert.ok(Math.hypot(...before.coord.map((v, j) => v - after.coord[j])) < 1e-7,
    `scene ${i + 1}: car position stays continuous`);
  assert.ok(Math.hypot(...before.center.map((v, j) => v - after.center[j])) < 1e-7,
    `scene ${i + 1}: camera center stays continuous`);
  assert.ok(Math.abs(before.zoom - after.zoom) < 1e-7, `scene ${i + 1}: no zoom reset`);
  assert.ok(angleDelta(before.heading, after.heading) < 1e-7, `scene ${i + 1}: no heading reset`);
}

// Slow incoming tiles must leave the outgoing map visible, then switch when ready.
const nodes = Object.fromEntries(['stage', 'play', 'seek', 'clock', 'data'].map((id) => [id, { style: {} }]));
nodes.data.textContent = JSON.stringify(entries);
const frames = [], handlers = {};
nodes.stage.appendChild = (frame) => frames.push(frame);
const context = vm.createContext({
  document: { getElementById: (id) => nodes[id], createElement: () => ({
    dataset: {}, style: {}, setAttribute() {}, addEventListener() {},
    contentWindow: { messages: [], postMessage(message) { this.messages.push(message); } },
  }) },
  performance: { now: () => 0 }, requestAnimationFrame() {},
  addEventListener: (event, callback) => { handlers[event] = callback; },
  Audio: class { constructor() { this.currentTime = 0; } pause() {} play() { return Promise.resolve(); } },
});
context.window = context;
vm.runInContext(scripts(playlist)[0], context);
const ready = (i) => handlers.message({ data: { type: 'preview-ready' }, source: frames[i].contentWindow });
assert.equal(frames[1].src, entries[1].src, 'preload next scene');
ready(0);
assert.equal(frames[0].style.visibility, 'visible');
context.renderAt(entries[0].duration);
assert.equal(frames[0].style.visibility, 'visible', 'hold outgoing scene while tiles load');
assert.equal(frames[0].contentWindow.messages.at(-1).t, entries[0].duration);
ready(1);
assert.equal(frames[1].style.visibility, 'visible', 'show incoming map after ready');
assert.equal(frames[0].style.visibility, 'hidden');
assert.equal(frames[2].src, entries[2].src, 'preload continues across boundaries');
nodes.data.textContent = JSON.stringify(entries.map(({ waitForReady, ...entry }) => entry));
frames.length = 0;
vm.runInContext(scripts(playlist)[0], context);
assert.equal(frames[0].style.visibility, 'visible', 'other renderers do not need a map-ready signal');
context.renderAt(entries[0].duration);
assert.equal(frames[1].style.visibility, 'visible', 'other renderers still switch immediately');
console.log(`PASS: ${scenes.length} map scenes; gradual zoom, braking, continuous seams, seeking and preloading.`);
