const puppeteer = require("puppeteer-core");
const assert = require("node:assert/strict");

(async () => {
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome",
    headless: true, args: ["--no-sandbox"],
  });
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  let exportRequests = 0;
  const snapshotId = "a".repeat(32);
  const jobId = "b".repeat(32);
  let job;
  await page.setRequestInterception(true);
  page.on("request", (request) => {
    const pathname = new URL(request.url()).pathname;
    if (pathname === `/api/previews/${snapshotId}`) {
      return request.respond({ contentType: "application/json", body: JSON.stringify({
        id: snapshotId, duration: 2, width: 1920, height: 1080,
        phases: [{ id: "1", name: "Cảnh", duration: 2, url: `/api/previews/${snapshotId}/phase_1.html` }],
      }) });
    }
    if (pathname === `/api/previews/${snapshotId}/phase_1.html`) {
      return request.respond({ contentType: "text/html", body:
        '<svg viewBox="0 0 1920 1080"></svg><script>window.renderAt=function(){};window.previewReady=Promise.resolve(true);</script>' });
    }
    if (pathname === "/api/exports" && request.method() === "POST") {
      exportRequests++;
      const input = JSON.parse(request.postData());
      assert.equal(input.snapshotId, snapshotId);
      job = { id: jobId, snapshotId, status: "running", stage: "rendering", progress: 42,
        config: input.config, duration: 2, width: 1920, height: 1080, result: null, error: null };
      return request.respond({ status: 202, contentType: "application/json", body: JSON.stringify(job) });
    }
    if (pathname === `/api/exports/${jobId}`) {
      return request.respond({ contentType: "application/json", body: JSON.stringify(job) });
    }
    return request.continue();
  });
  const click = async (label) => {
    await page.waitForFunction((text) => [...document.querySelectorAll("button")]
      .some((b) => !b.disabled && b.textContent.trim() === text), {}, label);
    await page.evaluate((text) => [...document.querySelectorAll("button")]
      .find((b) => !b.disabled && b.textContent.trim() === text).click(), label);
  };
  try {
    await page.setViewport({ width: 1440, height: 1050 });
    await page.goto(process.env.STUDIO_URL || "http://127.0.0.1:8001", { waitUntil: "networkidle0" });
    await page.evaluate(() => localStorage.clear());
    await page.reload({ waitUntil: "networkidle0" });
    assert.equal(await page.$$("#noi-dung, #phong-cach, #xem-truoc").then((nodes) => nodes.length), 3);
    assert.equal(await page.$$eval('#phong-cach [aria-pressed]', (nodes) => nodes.length), 0);
    assert.equal(await page.$eval('#phong-cach button:last-child', (button) => button.disabled), true);
    await page.evaluate((id) => {
      const config = { projectId: "saved-preview", categoryId: "all_styles", styleId: "flat" };
      const project = { id: config.projectId, title: "Preview đã lưu", sourceContent: "", messages: [],
        categoryId: config.categoryId, styleId: config.styleId, updatedAt: new Date().toISOString(),
        scenes: [{ id: "1", name: "Cảnh", duration: 2, narration: "", description: "" }],
        snapshot: { id, revision: "fixture", sourceSignature: JSON.stringify(config),
          duration: 2, width: 1920, height: 1080,
          phases: [{ id: "1", name: "Cảnh", duration: 2, url: `/api/previews/${id}/phase_1.html` }] } };
      localStorage.setItem("ai-video-studio:v1", JSON.stringify({ version: 1, activeId: project.id, projects: [project] }));
    }, snapshotId);
    await page.reload({ waitUntil: "networkidle0" });
    await click("Xuất video");
    await page.select("dialog select", "24");
    await click("Bắt đầu xuất");
    await page.waitForFunction(() => document.body.textContent.includes("42%"));
    assert.equal(exportRequests, 1);
    job = { ...job, status: "failed", stage: "failed", error: "Kiểm thử thử lại export." };
    await page.waitForFunction(() => document.body.textContent.includes("Kiểm thử thử lại export."));
    await click("Thử xuất lại");
    await click("Bắt đầu xuất");
    await page.waitForFunction(() => document.body.textContent.includes("42%"));
    assert.equal(exportRequests, 2);
    for (const width of [390, 1440]) {
      await page.setViewport({ width, height: 900 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    }
    if (process.env.QA_SCREENSHOT) await page.screenshot({ path: process.env.QA_SCREENSHOT, fullPage: true });
    assert.deepEqual(errors, []);
    console.log("Passed: unchanged layout, empty config, saved preview, export progress/retry, mobile layout.");
  } catch (error) {
    console.error(await page.evaluate(() => ({
      text: document.body.innerText.slice(-500),
      state: localStorage.getItem("ai-video-studio:v1"),
      buttons: [...document.querySelectorAll("#xem-truoc button")].map(button => [button.textContent, button.disabled]),
    })));
    throw error;
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
