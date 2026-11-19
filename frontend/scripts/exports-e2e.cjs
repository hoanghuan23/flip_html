const puppeteer = require("puppeteer-core");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const qa = path.resolve(__dirname, "../../storage/qa");
fs.mkdirSync(qa, { recursive: true });

(async () => {
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome",
    headless: true, args: ["--no-sandbox"],
  });
  const page = await browser.newPage();
  const report = { errors: [], checks: [] };
  page.on("pageerror", (error) => report.errors.push(error.message));
  let posts = 0, failPolls = false, rejectCreate = false, mockJob;
  await page.setRequestInterception(true);
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/api/exports")) {
      posts++;
      if (rejectCreate) return request.respond({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Lỗi kiểm thử khi gửi yêu cầu xuất." }) });
      if (mockJob) return request.respond({ status: 202, contentType: "application/json", body: JSON.stringify(mockJob) });
    }
    if (/\/api\/exports\/[a-f0-9]{32}$/.test(request.url())) {
      if (failPolls) return request.abort();
      if (mockJob && request.url().endsWith(mockJob.id)) return request.respond({ status: 200, contentType: "application/json", body: JSON.stringify(mockJob) });
    }
    request.continue();
  });
  const click = async (label) => {
    await page.waitForFunction((text) => [...document.querySelectorAll("button")]
      .some((b) => !b.disabled && b.textContent.trim() === text), {}, label);
    await page.evaluate((text) => [...document.querySelectorAll("button")]
      .find((b) => !b.disabled && b.textContent.trim() === text).click(), label);
  };
  const draft = () => page.evaluate(() => {
    const state = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
    return state.projects.find((p) => p.id === state.activeId);
  });
  const openProject = async (title) => {
    await click("Dự án của tôi");
    await page.evaluate((text) => [...document.querySelectorAll("dialog button strong")]
      .find((el) => el.textContent === text).closest("button").click(), title);
  };
  const waitText = (text, timeout = 30000) => page.waitForFunction((t) => document.body.textContent.includes(t), { timeout }, text);
  try {
    await page.setViewport({ width: 1440, height: 1050 });
    await page.goto(process.env.STUDIO_URL || "http://127.0.0.1:8123", { waitUntil: "networkidle0" });
    const exportDisabled = () => page.$$eval("#xem-truoc button", (buttons) => buttons.find((b) => b.textContent.trim() === "Xuất video")?.disabled);
    assert.equal(await exportDisabled(), true);
    await page.evaluate(async () => {
      const projects = [];
      for (const [id, title] of [["export-a", "Xuất A"], ["export-b", "Xuất B"]]) {
        const scenes = [1, 2].map((n) => ({ id: String(n), name: `Cảnh ${n}`, duration: 1.5,
          narration: "Kiểm thử xuất video giữ đúng thứ tự.", description: "Animation kiểm thử." }));
        const config = { projectId: id, categoryId: "news_current_affairs", styleId: "flat" };
        const response = await fetch("/api/previews", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...config, title, scenes }) });
        if (!response.ok) throw new Error("Không tạo được fixture preview.");
        const snapshot = await response.json();
        snapshot.sourceSignature = JSON.stringify(config);
        projects.push({ id, title, categoryId: config.categoryId, styleId: config.styleId, scenes,
          sourceContent: "Kiểm thử xuất MP4.", messages: [], updatedAt: new Date().toISOString(), snapshot });
      }
      localStorage.setItem("ai-video-studio:v1", JSON.stringify({ version: 1, activeId: "export-a", projects }));
    });
    await page.reload({ waitUntil: "networkidle0" });
    assert.equal(await exportDisabled(), false);
    await click("Xuất video");
    // Validate browser pattern semantics, including Vietnamese names and literal backslashes.
    assert.equal(await page.$eval("dialog input", (input) => {
      input.value = "Trung tâm dữ liệu AI"; return input.checkValidity();
    }), true);
    assert.equal(await page.$eval("dialog input", (input) => {
      input.value = "sai\\ten"; return input.checkValidity();
    }), false);
    await page.$eval("dialog input", (input) => {
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
      setter.call(input, "Các phase kiểm thử"); input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await page.select("dialog select", "24");
    const selects = await page.$$("dialog select");
    await selects[1].select("draft");
    await page.screenshot({ path: path.join(qa, "exports-dialog.png") });
    rejectCreate = true;
    await click("Bắt đầu xuất");
    await waitText("Lỗi kiểm thử khi gửi yêu cầu xuất.");
    rejectCreate = false;
    failPolls = true;
    await page.evaluate(() => {
      const button = [...document.querySelectorAll("dialog button")].find((b) => b.textContent.trim() === "Bắt đầu xuất");
      button.click(); button.click();
    });
    await page.waitForFunction(() => {
      const state = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
      return state.projects.find((p) => p.id === "export-a").jobId;
    });
    const active = await draft();
    assert.equal(posts, 2); // Rejected request and exactly one accepted request.
    await waitText("Đang tự kết nối lại để theo dõi xuất video");
    await page.reload({ waitUntil: "domcontentloaded" });
    await waitText("Đang tự kết nối lại để theo dõi xuất video");
    await openProject("Xuất B");
    assert.equal(await page.$('video[aria-label="Video MP4 đã xuất"]'), null);
    assert.equal(await exportDisabled(), false);
    failPolls = false;
    await openProject("Xuất A");
    await waitText("Video đã sẵn sàng", 180000);
    assert.equal((await draft()).jobId, active.jobId);
    assert.equal(posts, 2);
    const job = await page.evaluate(async (id) => (await fetch(`/api/exports/${id}`)).json(), active.jobId);
    assert.equal(job.config.fps, 24);
    assert.equal(job.config.quality, "draft");
    assert.equal(job.config.filename, "Các phase kiểm thử.mp4");
    assert.equal(job.duration, 3);
    const payload = await page.evaluate(async (result) => {
      const partial = await fetch(result.videoUrl, { headers: { Range: "bytes=0-31" } });
      const download = await fetch(result.downloadUrl);
      return { partial: partial.status, range: partial.headers.get("content-range"),
        disposition: download.headers.get("content-disposition"), bytes: [...new Uint8Array(await download.arrayBuffer())] };
    }, job.result);
    assert.equal(payload.partial, 206);
    assert.ok(payload.range.startsWith("bytes 0-31/"));
    assert.ok(payload.disposition.startsWith("attachment"));
    assert.equal(payload.bytes.length, job.result.bytes);
    const videoPath = path.join(qa, "export-browser.mp4");
    fs.writeFileSync(videoPath, Buffer.from(payload.bytes));
    const probe = JSON.parse(execFileSync("ffprobe", ["-v", "error", "-show_streams", "-show_format", "-of", "json", videoPath], { encoding: "utf8" }));
    const video = probe.streams.find((stream) => stream.codec_type === "video");
    assert.equal(video.width, 1920); assert.equal(video.height, 1080);
    assert.equal(video.avg_frame_rate, "24/1"); assert.ok(Math.abs(Number(probe.format.duration) - 3) < .05);
    assert.equal(probe.streams.length, 1);
    await page.reload({ waitUntil: "networkidle0" });
    await waitText("Video đã sẵn sàng");
    assert.ok((await page.$eval('a[download]', (a) => a.getAttribute("href"))).endsWith("/download"));
    report.checks.push("actual MP4 render: all phases, configured filename/FPS/quality, correct duration/resolution, silent stream, Range and attachment download");
    report.checks.push("duplicate submit prevented, create error recoverable, reconnect/reload/project switching retain the correct job, completed video restored after reload");
    for (const width of [1440, 768, 375]) {
      await page.setViewport({ width, height: 1000 });
      await page.$eval("#xem-truoc", (el) => el.scrollIntoView());
      await page.screenshot({ path: path.join(qa, `exports-${width}.png`), fullPage: true });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    }
    mockJob = { ...job, id: "f".repeat(32), status: "queued", stage: "queued", result: null, progress: null };
    await click("Xuất video"); await click("Bắt đầu xuất");
    await waitText("Đang chờ xuất video…");
    mockJob = { ...mockJob, status: "failed", stage: "failed", error: "Máy chủ đã khởi động lại. Hãy thử xuất lại video." };
    await waitText(mockJob.error);
    await click("Thử xuất lại");
    await page.waitForSelector("dialog[open]");
    await page.keyboard.press("Escape");
    await page.evaluate(() => {
      const state = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
      state.projects.find((p) => p.id === state.activeId).jobId = "e".repeat(32);
      localStorage.setItem("ai-video-studio:v1", JSON.stringify(state));
    });
    mockJob = undefined;
    await page.reload({ waitUntil: "networkidle0" });
    await waitText("Không tìm thấy tác vụ xuất video.");
    assert.equal((await draft()).jobId, undefined);
    await page.evaluate(() => [...document.querySelectorAll("#phong-cach button")]
      .find((b) => b.querySelector("span")?.textContent.trim() === "Flat with black").click());
    await waitText("Cần cập nhật preview");
    assert.equal(await exportDisabled(), true);
    report.checks.push("responsive at 375/768/1440, server restart failure offers retry, missing job recoverable, stale preview blocks export");
    assert.deepEqual(report.errors, []);
  } catch (error) {
    await page.screenshot({ path: path.join(qa, "exports-failure.png"), fullPage: true });
    throw error;
  } finally {
    fs.writeFileSync(path.join(qa, "exports-browser-report.json"), JSON.stringify(report, null, 2));
    await browser.close();
  }
  console.log(JSON.stringify(report, null, 2));
})().catch((error) => { console.error(error); process.exitCode = 1; });
