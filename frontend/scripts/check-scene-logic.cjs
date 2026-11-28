// Validate physical relationships on actual seeked SVG transforms, never on
// the transparent image canvas or model-reported screen coordinates.
const fs = require('node:fs');
const puppeteer = require('puppeteer-core');

async function main() {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
    headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  try {
    const page = await browser.newPage();
    await page.setViewport({width: 1920, height: 1080});
    await page.setContent('<!doctype html><meta http-equiv="Content-Security-Policy" '
      + 'content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:">'
      + '<style>html,body{margin:0}svg{display:block;width:1920px;height:1080px}</style>');
    await page.evaluate(svg => {
      const documentSvg = new DOMParser().parseFromString(svg, 'image/svg+xml');
      if (documentSvg.querySelector('parsererror')) throw new Error('Invalid SVG XML');
      document.body.append(document.importNode(documentSvg.documentElement, true));
    }, input.svg);
    await page.evaluate(async () => {
      await Promise.all(Array.from(document.querySelectorAll('image')).map(node => new Promise((resolve, reject) => {
        const image = new Image(); image.onload = resolve;
        image.onerror = () => reject(new Error('PNG decode failed'));
        image.src = node.getAttribute('href');
      })));
      await document.fonts.ready;
    });
    const report = await page.evaluate(({contract, geometry, phase, times}) => {
      const errors = [], reported = new Set();
      const fail = message => {
        if (!reported.has(message) && errors.length < 30) { reported.add(message); errors.push(message); }
      };
      const nodes = Object.fromEntries(contract.instances.map(i => [i.id, document.getElementById(i.id)]));
      const order = Array.from(document.querySelectorAll('#artwork use')).map(e => e.id);
      const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
      const visible = node => {
        let opacity = 1;
        for (let element = node; element && element instanceof SVGElement; element = element.parentElement) {
          const style = getComputedStyle(element);
          if (style.display === 'none' || style.visibility !== 'visible') return 0;
          opacity *= Number(style.opacity);
        }
        return opacity;
      };
      const active = (r, t) => t >= r.start && (t < r.end || (t === phase.duration && r.end === t));
      const animations = document.getAnimations();
      // A polygon is a conservative alpha bounding rectangle after all transforms.
      const overlaps = (a, b) => {
        for (const polygon of [a, b]) {
          for (let i = 0; i < polygon.length; i++) {
            const p = polygon[i], q = polygon[(i + 1) % polygon.length];
            const axis = {x: -(q.y - p.y), y: q.x - p.x};
            const projection = points => points.map(v => v.x * axis.x + v.y * axis.y);
            const aa = projection(a), bb = projection(b);
            if (Math.max(...aa) <= Math.min(...bb) + 0.01 || Math.max(...bb) <= Math.min(...aa) + 0.01) return false;
          }
        }
        return true;
      };
      for (const t of times) {
        animations.forEach(animation => { animation.pause(); animation.currentTime = t * 1000; });
        const states = Object.create(null);
        for (const item of contract.instances) {
          const node = nodes[item.id], bounds = geometry[item.asset]?.bounds;
          if (!node || !bounds) { fail(`${item.id}: missing actual geometry/node`); continue; }
          const matrix = node.getCTM();
          if (!matrix || Math.abs(matrix.a * matrix.d - matrix.b * matrix.c) < 1e-8) {
            if (visible(node) > .02) fail(`${item.id}: singular transform at ${t.toFixed(3)}s`);
            continue;
          }
          const point = (uv, transform = matrix, bb = bounds) => {
            const p = new DOMPoint(bb[0] + uv[0] * (bb[2] - bb[0]), bb[1] + uv[1] * (bb[3] - bb[1]));
            return p.matrixTransform(transform);
          };
          states[item.id] = {node, point, bounds, matrix, opacity: visible(node),
            polygon: [[0,0], [1,0], [1,1], [0,1]].map(p => point(p))};
          const needed = {supported: 'supported_by', attached: 'contact', contained: 'contained_in'}[item.mode];
          if (needed && states[item.id].opacity > .02 && !contract.relations.some(r =>
            r.a === item.id && r.type === needed && active(r, t))) {
            fail(`${item.id}: visible without ${needed} at ${t.toFixed(3)}s`);
          }
        }
        for (const r of contract.relations.filter(r => active(r, t))) {
          const a = states[r.a], b = states[r.b];
          if (!a || !b || a.opacity <= .02) continue;
          const label = `${r.a}/${r.b} ${r.type} at ${t.toFixed(3)}s`;
          if (b.opacity <= .02) {
            if (r.type !== 'separate' && r.type !== 'in_front') fail(`${label}: target/support invisible`);
            continue;
          }
          const tolerance = r.tolerance ?? 8;
          if (r.type === 'contact' && distance(a.point(r.a_point), b.point(r.b_point)) > tolerance) {
            fail(`${label}: contact points detached`);
          }
          if (r.type === 'size_ratio') {
            const extent = (state, axis) => distance(state.point([0,0]), state.point(axis === 'width' ? [1,0] : [0,1]));
            const ratio = extent(a, r.a_axis) / extent(b, r.b_axis);
            if (ratio < r.min || ratio > r.max) fail(`${label}: physical size ratio ${ratio.toFixed(3)} outside ${r.min}..${r.max}`);
          }
          if (r.type === 'supported_by') {
            const p = a.point(r.point), u = b.point(r.surface[0]), v = b.point(r.surface[1]);
            const dx = v.x - u.x, dy = v.y - u.y;
            const k = Math.max(0, Math.min(1, ((p.x-u.x)*dx + (p.y-u.y)*dy) / (dx*dx+dy*dy)));
            if (distance(p, {x: u.x+k*dx, y: u.y+k*dy}) > tolerance) fail(`${label}: no contact with support surface`);
          }
          if (r.type === 'contained_in') {
            const inverse = b.matrix.inverse(), region = r.region;
            const min = b.point([region[0], region[1]], new DOMMatrix());
            const max = b.point([region[2], region[3]], new DOMMatrix());
            // Convert the scene-pixel tolerance to conservative local-axis margins.
            const tx = tolerance / Math.hypot(b.matrix.a, b.matrix.b);
            const ty = tolerance / Math.hypot(b.matrix.c, b.matrix.d);
            if (a.polygon.some(p => {
              const local = p.matrixTransform(inverse);
              return local.x < min.x-tx || local.x > max.x+tx || local.y < min.y-ty || local.y > max.y+ty;
            })) fail(`${label}: outside receiving region`);
          }
          if ((r.type === 'covers' || r.type === 'in_front') && order.indexOf(r.a) <= order.indexOf(r.b)) {
            fail(`${label}: reversed paint order`);
          }
          if (r.type === 'covers' && !overlaps(a.polygon, b.polygon)) fail(`${label}: covering object does not overlap subject`);
          if (r.type === 'separate' && overlaps(a.polygon, b.polygon)) fail(`${label}: solid silhouettes intersect`);
        }
        for (const dependency of contract.causality) {
          const effect = phase.actions[dependency.effect];
          if (effect.type === 'fade' && effect.from?.opacity === 0 && effect.to?.opacity > 0
              && t < effect.start && !phase.actions.some((action, i) => i !== dependency.effect
                && action.target === effect.target && action.start < effect.start)) {
            const premature = contract.instances.some(item => item.asset.split('--pose-')[0] === effect.target
              && states[item.id]?.opacity > .02);
            if (premature) fail(`${effect.target}: visible effect before its causal action at ${t.toFixed(3)}s`);
          }
        }
        const entities = Object.create(null);
        for (const item of contract.instances) {
          const state = states[item.id];
          if (state?.opacity > .02) (entities[item.asset.split('--pose-')[0]] ??= []).push(state);
        }
        for (const [asset, copies] of Object.entries(entities)) {
          if (copies.length < 2) continue;
          const morphing = phase.actions.some(a => a.target === asset && a.type === 'morph' && t >= a.start && t <= a.end);
          if (!morphing || copies.length > 2 || copies.reduce((sum, s) => sum + s.opacity, 0) > 1.05) {
            fail(`${asset}: duplicate visible copies at ${t.toFixed(3)}s`);
          }
        }
        if (errors.length >= 30) break;
      }
      return {passed: errors.length === 0, errors, samples: times.length,
        checks: ['support', 'contact', 'containment', 'occlusion', 'separation', 'size-ratio', 'causal-visibility', 'visibility', 'object-count'],
        limitations: 'Declared relationships and measured alpha bounds only. Pixel semantics, anatomy, baked-in duplicates and undeclared interactions still require visual review.'};
    }, input);
    process.stdout.write(JSON.stringify(report));
  } finally { await browser.close(); }
}
main().catch(error => { process.stderr.write(error.message); process.exitCode = 1; });
