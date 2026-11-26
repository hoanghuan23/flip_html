const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const puppeteer = require("puppeteer-core");

(async () => {
  const root = path.resolve(process.argv[2]);
  const snapshot = JSON.parse(fs.readFileSync(path.join(root, "snapshot.json"), "utf8"));
  const mapPlan = JSON.parse(fs.readFileSync(path.join(root, "map_plan.json"), "utf8"));
  assert.deepEqual(mapPlan.stops.map((stop) => stop.name), ["Hà Nội", "Huế", "Đà Nẵng", "Nha Trang"]);
  const server = http.createServer((req, res) => {
    const target = path.resolve(root, decodeURIComponent(new URL(req.url, "http://localhost").pathname).replace(/^\/+/, ""));
    if (!target.startsWith(root + path.sep) || !fs.existsSync(target)) { res.writeHead(404); res.end(); return; }
    const mime = { ".html": "text/html", ".js": "application/javascript", ".css": "text/css", ".wav": "audio/wav" };
    res.setHeader("Content-Type", mime[path.extname(target)] || "application/octet-stream");
    const size = fs.statSync(target).size;
    const range = /^bytes=(\d+)-(\d*)$/.exec(req.headers.range || '');
    res.setHeader('Accept-Ranges', 'bytes');
    if (range) {
      const start = Number(range[1]), end = range[2] ? Math.min(Number(range[2]), size - 1) : size - 1;
      if (start > end || start >= size) { res.writeHead(416); res.end(); return; }
      res.writeHead(206, { 'Content-Range': `bytes ${start}-${end}/${size}`, 'Content-Length': end - start + 1 });
      fs.createReadStream(target, { start, end }).pipe(res);
    } else {
      res.setHeader('Content-Length', size);
      fs.createReadStream(target).pipe(res);
    }
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROME_PATH || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    headless: true, args: ["--no-sandbox"],
  });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1080, height: 720 });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("response", (response) => { if (response.status() >= 400 && !response.url().endsWith('/favicon.ico')) errors.push(`${response.status()} ${response.url()}`); });
    page.on("requestfailed", (request) => {
      if (request.failure()?.errorText !== "net::ERR_ABORTED")
        errors.push(`${request.failure()?.errorText} ${request.url()}`);
    });
    await page.goto(`http://127.0.0.1:${server.address().port}/index.html`, { waitUntil: "domcontentloaded" });
    if (snapshot.demoNoAudio) {
      await page.click("#play");
    } else {
      await page.click("#play");
      await page.waitForFunction(() => window.audios[0]?.currentTime > .1 && !window.audios[0].paused);
      await page.click("#play");
    }
    const durations = snapshot.phases.map((phase) => phase.duration);
    const at = (index, fraction) => durations.slice(0, index).reduce((a, b) => a + b, 0) + durations[index] * fraction;
    async function checkPlayback(startTime, endTime, index, label) {
      await page.evaluate((time) => window.renderAt(time), startTime);
      await page.waitForFunction((i) => document.querySelectorAll('iframe')[i].dataset.ready === '1', { timeout: 60000 }, index);
      const frame = page.frames().find((item) => item.url().endsWith(`phase_${index + 1}.html`));
      const local = startTime - at(index, 0);
      await frame.waitForFunction((time) => Math.abs(appliedTime - time) < .001, {}, local);
      await frame.waitForFunction(() => window.mapInstance.areTilesLoaded(), { timeout: 60000 });
      await frame.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      await page.waitForFunction(({ index, local }) => !audios[index] ||
        (!audios[index].seeking && Math.abs(audios[index].currentTime - local) < .05), {}, { index, local });
      const playback = await page.evaluate((end) => new Promise((resolve) => {
        const start = performance.now(), samples = [];
        document.querySelector('#play').click();
        function sample() {
          const visibleFrames = [...document.querySelectorAll('iframe')].filter((frame) => frame.style.visibility === 'visible');
          samples.push({ count: visibleFrames.length, zoom: visibleFrames[0]?.contentWindow.mapInstance?.getZoom(), time: t, scene: shown });
          if (t >= end || performance.now() - start > 12000) {
            if (playing) document.querySelector('#play').click();
            resolve({ time: t, samples });
          } else requestAnimationFrame(sample);
        }
        requestAnimationFrame(sample);
      }), endTime);
      assert.ok(playback.time >= endTime, `${label}: narrated playback crosses the boundary`);
      assert.ok(playback.samples.every((sample) => sample.count === 1 && Number.isFinite(sample.zoom)),
        `${label}: one loaded map remains visible`);
      const steps = playback.samples.slice(1).map((sample, i) => Math.abs(sample.zoom - playback.samples[i].zoom));
      const largest = steps.indexOf(Math.max(...steps));
      assert.ok(Math.max(...steps) < 1,
        `${label}: no camera reset: ${JSON.stringify(playback.samples.slice(largest, largest + 2))}`);
    }
    await checkPlayback(durations[0] - .4, durations[0] + 4.8, 0, 'Hanoi departure');
    for (const [index, fraction, expected] of [[0, .55, "image_1"], [2, .55, "image_7"], [4, .55, "image_5"], [6, .55, "image_3"]]) {
      await page.evaluate((time) => window.renderAt(time), at(index, fraction));
      await page.waitForFunction((i) => document.querySelectorAll('iframe')[i].contentWindow.location.pathname.endsWith(`phase_${i + 1}.html`), {}, index);
      const frame = page.frames().find((item) => item.url().endsWith(`phase_${index + 1}.html`));
      assert.ok(frame, `phase ${index + 1} loaded`);
      await frame.waitForFunction(() => window.mapInstance && window.mapInstance.isStyleLoaded(), { timeout: 20000 });
      const data = await frame.$eval("#illustration-data", (node) => JSON.parse(node.textContent));
      assert.ok(data.images[Number(expected.split("_")[1])]);
      await frame.waitForFunction(() => document.querySelector("#illustration-card").style.display === "block");
    }
    for (const index of [1, 3, 5]) {
      await page.evaluate((time) => window.renderAt(time), at(index, .35));
      await page.waitForFunction((i) => document.querySelectorAll('iframe')[i].contentWindow.location.pathname.endsWith(`phase_${i + 1}.html`), {}, index);
      const motionFrame = page.frames().find((item) => item.url().endsWith(`phase_${index + 1}.html`));
      await motionFrame.waitForFunction(() => window.mapInstance?.isStyleLoaded());
      for (const fraction of [.2, .5, .8]) {
        const motion = await motionFrame.evaluate((fraction) => {
          const duration = JSON.parse(document.querySelector('#map-data').textContent).duration;
          window.renderAt(duration * fraction);
          const rect = car.getBoundingClientRect(), point = map.project(marker.getLngLat());
          const progress = map.getPaintProperty('active-route', 'line-gradient')[3];
          return { marker: [rect.x + rect.width / 2, rect.y + rect.height / 2],
            projected: [point.x, point.y], gradient: map.getPaintProperty('active-route', 'line-gradient'),
            location: marker.getLngLat().toArray(), routeEnd: locate(paths[phase.legIndex], progress).coord,
            heading: car.style.getPropertyValue('--heading') };
        }, fraction);
        assert.ok(Math.hypot(motion.marker[0] - motion.projected[0], motion.marker[1] - motion.projected[1]) < 3,
          `phase ${index + 1}: car stays on its map position`);
        assert.ok(Math.hypot(...motion.location.map((value, i) => value - motion.routeEnd[i])) < 1e-8,
          `phase ${index + 1}: drawn route ends at car after easing`);
        assert.ok(motion.heading.endsWith('deg'), `phase ${index + 1}: car follows route direction`);
      }
      const turnDeltas = await motionFrame.evaluate(() => {
        const duration = JSON.parse(document.querySelector('#map-data').textContent).duration;
        const headings = [];
        for (let step = 0; step <= 120; step++) {
          window.renderAt(duration * step / 120);
          headings.push(parseFloat(car.style.getPropertyValue('--heading')));
        }
        return headings.slice(1).map((angle, i) => Math.abs(((angle - headings[i] + 540) % 360) - 180));
      });
      const p95 = [...turnDeltas].sort((a, b) => a - b)[Math.floor(turnDeltas.length * .95)];
      assert.ok(Math.max(...turnDeltas) < 20 && p95 < 12,
        `phase ${index + 1}: car heading must not shake between nearby frames`);
    }
    if (!snapshot.demoNoAudio) {
      await page.evaluate((time) => window.renderAt(time), at(1, .3));
      await page.waitForFunction(() => document.querySelectorAll('iframe')[1].contentWindow.location.pathname.endsWith('phase_2.html'));
      const frame = page.frames().find((item) => item.url().endsWith('phase_2.html'));
      await frame.waitForFunction(() => window.mapInstance?.isStyleLoaded());
      const before = await frame.evaluate(() => ({ location: marker.getLngLat().toArray(),
        progress: map.getPaintProperty('active-route', 'line-gradient')[3] }));
      const startAudio = await page.evaluate(() => window.audios[1].currentTime);
      await page.click('#play');
      await page.waitForFunction((start) => window.audios[1].currentTime > start + .6, {}, startAudio);
      await page.click('#play');
      const after = await frame.evaluate(() => ({ location: marker.getLngLat().toArray(),
        progress: map.getPaintProperty('active-route', 'line-gradient')[3] }));
      assert.ok(Math.hypot(after.location[0] - before.location[0], after.location[1] - before.location[1]) > .005,
        'car moves while narration plays');
      assert.ok(after.progress > before.progress, 'red route grows behind the moving car');
    }
    // Verify camera and car continuity across the preloaded arrival handoff.
    await page.evaluate((time) => window.renderAt(time), at(5, .65));
    await page.waitForFunction(() => document.querySelectorAll('iframe')[5].dataset.ready === '1', { timeout: 60000 });
    await page.waitForFunction(() => document.querySelectorAll('iframe')[6].dataset.ready === '1', { timeout: 60000 });
    const boundary = at(6, 0);
    const beforeFrame = page.frames().find((frame) => frame.url().endsWith('phase_6.html'));
    const afterFrame = page.frames().find((frame) => frame.url().endsWith('phase_7.html'));
    const state = (time) => {
      window.renderAt(time);
      return { center: map.getCenter().toArray(), zoom: map.getZoom(),
        coord: marker.getLngLat().toArray(), heading: parseFloat(car.style.getPropertyValue('--heading')) };
    };
    const before = await beforeFrame.evaluate(state, durations[5]);
    const after = await afterFrame.evaluate(state, 0);
    assert.ok(Math.hypot(...before.center.map((value, i) => value - after.center[i])) < 1e-7, 'arrival camera center is continuous');
    assert.ok(Math.abs(before.zoom - after.zoom) < 1e-7, 'arrival zoom is continuous');
    assert.ok(Math.abs(((before.heading - after.heading + 540) % 360) - 180) < 1e-7, 'parked car keeps arrival heading');
    await checkPlayback(boundary - 4.8, boundary + .3, 5, 'Nha Trang arrival');
    const summaryStart = at(7, 0);
    const summaryTime = at(7, .8);
    await checkPlayback(summaryStart - .3, summaryStart + 4.8, 6, 'Full journey summary');
    for (const viewport of [{ width: 1080, height: 720 }, { width: 640, height: 480 }]) {
      await page.setViewport(viewport);
      await page.evaluate((time) => window.renderAt(time), summaryTime);
      await page.waitForFunction(() => document.querySelectorAll('iframe')[7].dataset.ready === '1', { timeout: 60000 });
      const summary = page.frames().find((frame) => frame.url().endsWith('phase_8.html'));
      await summary.waitForFunction((local) => Math.abs(appliedTime - local) < .001, {}, summaryTime - summaryStart);
      await summary.waitForFunction(() => window.mapInstance.areTilesLoaded(), { timeout: 60000 });
      await summary.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const overview = await summary.evaluate(() => {
        const { width, height } = map.getContainer().getBoundingClientRect();
        const inside = (coord) => {
          const p = map.project(coord);
          return p.x >= 12 && p.x <= width - 12 && p.y >= 12 && p.y <= height - 12;
        };
        const labels = [...document.querySelectorAll('.stop-label')].map((label) => label.getBoundingClientRect());
        return { zoom: map.getZoom(), stops: D.stops.map((stop) => ({ name: stop.name, inside: inside(stop.coord) })),
          routeInside: paths.every((path) => path.points.every(inside)),
          labelsApart: labels.every((a, i) => labels.slice(i + 1).every((b) =>
            a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top)),
          labelsInside: labels.every((r) => {
            return r.left >= 4 && r.top >= 4 && r.right <= width - 4 && r.bottom <= height - 4;
          }) };
      });
      assert.ok(overview.stops.every((stop) => stop.inside), `summary shows all stops: ${JSON.stringify(overview)}`);
      assert.ok(overview.routeInside, 'summary shows the entire road route');
      assert.ok(overview.labelsInside, 'summary labels stay inside the frame');
      assert.ok(overview.labelsApart, 'all four summary labels are readable without overlap');
    }
    assert.deepEqual(errors, []);
    console.log(`PASS: ${snapshot.phases.length} phases, illustration cards, car/route synchronization, camera continuity and full-journey summary.`);
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
