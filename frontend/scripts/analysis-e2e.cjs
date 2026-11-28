// Self-contained UI QA with local API fixtures; never calls a real AI service.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const puppeteer = require("puppeteer-core");

const dist = path.resolve(__dirname, "../dist");
const qa = path.resolve(__dirname, "../../storage/qa");
const report = { checks: [], errors: [] };
const jobId = "a".repeat(32);
let body, complete = false;
const scene = { id: "1", name: "Mưa đá hình thành", description: "Nước đóng băng trong mây.",
  narration: "", voiceover: "Nước đóng băng trong mây.", duration: 7.25, duration_status: "estimated",
  annotations: [{ text: "Nước đóng băng", target: "CLOUD", cue: "đóng băng", action_index: 0 }] };
const result = { title: "Mưa đá", scenes: [scene], input_type: "topic",
  warnings: ["Kiểm tra số liệu trước khi dựng video."],
  research: { status: "sources_reported", sources: [{ title: "Nguồn nghiên cứu", url: "https://example.org/hail",
    claims: ["Nước đóng băng trong mây."] }] } };
const server = http.createServer(async (req, res) => {
  if (req.url.startsWith("/api/")) {
    res.setHeader("Content-Type", "application/json");
    if (req.url === "/api/images" && req.method === "POST") {
      return res.end(JSON.stringify({ id: "b".repeat(32), number: 7, kind: "reference" }));
    }
    if (req.url === "/api/scripts" && req.method === "POST") {
      let raw = ""; for await (const chunk of req) raw += chunk;
      body = JSON.parse(raw);
      res.statusCode = 202;
    } else if (!req.url.startsWith("/api/scripts/")) {
      return res.end(JSON.stringify({ url: null }));
    }
    return res.end(JSON.stringify({ id: jobId, projectId: body?.projectId, status: complete ? "succeeded" : "running",
      stage: complete ? "completed" : "researching", result: complete ? result : null, error: null }));
  }
  const pathname = new URL(req.url, "http://localhost").pathname;
  let file = path.resolve(dist, "." + (pathname === "/" ? "/index.html" : pathname));
  if (!file.startsWith(dist + path.sep) || !fs.existsSync(file)) { res.statusCode = 404; return res.end(); }
  res.setHeader("Content-Type", ({ ".html": "text/html", ".js": "text/javascript", ".css": "text/css" })[path.extname(file)] || "application/octet-stream");
  fs.createReadStream(file).pipe(res);
});

(async () => {
  fs.mkdirSync(qa, { recursive: true });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  let browser;
  try {
    browser = await puppeteer.launch({ executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome",
      headless: true, args: ["--no-sandbox"] });
    const page = await browser.newPage();
    page.on("pageerror", (error) => report.errors.push(error.message));
    const draft = () => page.evaluate(() => {
      const s = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
      return s.projects.find((p) => p.id === s.activeId);
    });
    const click = (label) => page.evaluate((text) => {
      const button = [...document.querySelectorAll("button")].find((b) => !b.disabled && b.textContent.trim() === text);
      if (!button) throw new Error("Missing button: " + text);
      button.click();
    }, label);
    await page.setViewport({ width: 1440, height: 1000 });
    await page.goto(`http://127.0.0.1:${server.address().port}`, { waitUntil: "networkidle0" });
    await page.waitForFunction(() => localStorage.getItem("ai-video-studio:v1"));
    await page.evaluate(() => {
      const s = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
      const p = s.projects.find((p) => p.id === s.activeId);
      p.title = "Dự án phân tích";
      p.referenceImages = [{ id: "local-image", name: "local.png", number: 7,
        dataUrl: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2tAAAAABJRU5ErkJggg==" }];
      localStorage.setItem("ai-video-studio:v1", JSON.stringify(s));
    });
    await page.reload({ waitUntil: "networkidle0" });
    await page.type("#source-text", "Mưa đá hình thành như thế nào?");
    await click("Tạo kịch bản");
    await page.waitForFunction(() => {
      const s = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
      return s.projects.some((p) => p.scriptJobId);
    });
    assert.deepEqual(Object.keys(body).sort(), ["content", "images", "projectId"]);
    assert.deepEqual(body.images, [{ number: 7, kind: "reference", imageId: "b".repeat(32) }]);
    assert.ok(!JSON.stringify(body).includes("data:image/"));
    assert.equal(body.content, "Mưa đá hình thành như thế nào?");
    await page.reload({ waitUntil: "networkidle0" });
    await page.waitForFunction(() => document.body.textContent.includes("nghiên cứu chủ đề"));
    report.checks.push("text POST with image IDs only; pending research restores on reload");
    await click("Dự án của tôi");
    await click("Bắt đầu dự án mới");
    complete = true;
    await page.waitForFunction(() => {
      const s = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
      return s.projects.some((p) => p.scriptReview?.research?.status === "sources_reported");
    });
    assert.equal((await draft()).scriptReview, undefined);
    await click("Dự án của tôi");
    await page.evaluate(() => [...document.querySelectorAll("dialog button strong")]
      .find((el) => el.textContent === "Dự án phân tích").closest("button").click());
    await page.waitForFunction(() => document.querySelector("#kich-ban")?.textContent.includes("Chú giải trên màn hình"));
    await page.waitForFunction(() => {
      const s = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
      return s.projects.find((p) => p.id === s.activeId)?.scenes.length === 1;
    });
    const restored = await draft();
    assert.deepEqual(restored.scenes, [scene]);
    assert.equal(restored.scriptReview.input_type, "topic");
    await page.reload({ waitUntil: "networkidle0" });
    assert.deepEqual((await draft()).scriptReview, restored.scriptReview);
    assert.deepEqual((await draft()).scenes, restored.scenes);
    report.checks.push("completion isolated to original project; annotations and review survive switching and reload");
    await page.click("#kich-ban details summary");
    assert.ok(await page.$eval("#kich-ban", (el) => el.textContent.includes("chưa được hệ thống xác minh độc lập")));
    assert.equal(await page.$eval("#kich-ban details a", (a) => a.href), "https://example.org/hail");
    for (const width of [1440, 768, 375]) {
      await page.setViewport({ width, height: 1000 });
      await page.evaluate(() => document.querySelector("#kich-ban").scrollIntoView());
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `Overflow at ${width}`);
      await page.screenshot({ path: path.join(qa, `analysis-review-${width}.png`), fullPage: true });
    }
    report.checks.push("source attribution, warnings and annotations readable without horizontal overflow at 1440/768/375px");
    assert.deepEqual(report.errors, []);
    report.ok = true;
  } catch (error) {
    report.failure = String(error.stack || error);
    process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
    await new Promise((resolve) => server.close(resolve));
    fs.writeFileSync(path.join(qa, "analysis-browser-report.json"), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  }
})();
