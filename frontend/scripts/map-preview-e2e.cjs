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
    const mime = { ".html": "text/html", ".js": "application/javascript", ".css": "text/css" };
    res.setHeader("Content-Type", mime[path.extname(target)] || "application/octet-stream");
    fs.createReadStream(target).pipe(res);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROME_PATH || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    headless: true, args: ["--no-sandbox"],
  });
  try {
    const page = await browser.newPage();
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
          return { marker: [rect.x + rect.width / 2, rect.y + rect.height / 2],
            projected: [point.x, point.y], gradient: map.getPaintProperty('active-route', 'line-gradient'),
            heading: car.style.getPropertyValue('--heading') };
        }, fraction);
        assert.ok(Math.hypot(motion.marker[0] - motion.projected[0], motion.marker[1] - motion.projected[1]) < 3,
          `phase ${index + 1}: car stays on its map position`);
        assert.ok(Math.abs(motion.gradient[3] - fraction) < .001,
          `phase ${index + 1}: drawn route ends at car progress`);
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
    assert.deepEqual(errors, []);
    console.log(`PASS: ${snapshot.phases.length} phases, illustration cards and car/route synchronization.`);
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
