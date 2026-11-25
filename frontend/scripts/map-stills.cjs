const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const puppeteer = require("puppeteer-core");

async function main() {
  const root = path.resolve(process.argv[2]);
  const count = Number(process.argv[3]);
  const types = { ".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css", ".png": "image/png" };
  const server = http.createServer((request, response) => {
    const filename = decodeURIComponent(new URL(request.url, "http://localhost").pathname).replace(/^\/+/, "");
    const target = path.resolve(root, filename);
    if (!target.startsWith(root + path.sep) || !fs.existsSync(target) || !fs.statSync(target).isFile()) {
      response.writeHead(404); response.end(); return;
    }
    response.setHeader("Content-Type", types[path.extname(target)] || "application/octet-stream");
    fs.createReadStream(target).pipe(response);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const candidates = [process.env.PUPPETEER_EXECUTABLE_PATH, process.env.CHROME_PATH,
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "/usr/bin/google-chrome",
    "/usr/bin/chromium", "/usr/bin/chromium-browser"];
  const executablePath = candidates.find((candidate) => candidate && fs.existsSync(candidate));
  if (!executablePath) throw new Error("Không tìm thấy Chrome/Chromium. Đặt CHROME_PATH.");
  const browser = await puppeteer.launch({
    executablePath,
    headless: true, args: ["--no-sandbox"],
  });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 1 });
    for (let index = 1; index <= count; index++) {
      await page.goto(`http://127.0.0.1:${server.address().port}/phase_${index}.html`, { waitUntil: "domcontentloaded", timeout: 60000 });
      await page.waitForFunction(() => window.mapInstance && window.mapInstance.isStyleLoaded(), { timeout: 60000 });
      const duration = await page.$eval("#map-data", (node) => JSON.parse(node.textContent).duration);
      await page.evaluate((t) => window.renderAt(t), duration * .55);
      await page.waitForFunction(() => window.mapInstance && window.mapInstance.areTilesLoaded(), { timeout: 60000 });
      await page.screenshot({ path: path.join(root, `phase_${index}.preview.png`) });
    }
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
}
main().catch((error) => { process.stderr.write(String(error.stack || error)); process.exitCode = 1; });
