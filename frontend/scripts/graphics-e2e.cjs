const puppeteer = require("puppeteer-core");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
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
  let posts = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/api/graphics")) posts++;
  });
  const click = async (label) => {
    await page.waitForFunction((text) => [...document.querySelectorAll("button")]
      .some((b) => !b.disabled && b.textContent.trim() === text), {}, label);
    await page.evaluate((text) => [...document.querySelectorAll("button")]
      .find((b) => !b.disabled && b.textContent.trim() === text).click(), label);
  };
  const fill = async (selector, value) => {
    await page.focus(selector);
    await page.keyboard.down("Control"); await page.keyboard.press("a"); await page.keyboard.up("Control");
    await page.keyboard.type(value);
  };
  const selectStyle = (name) => page.evaluate((text) => [...document.querySelectorAll("#phong-cach button")]
    .find((b) => b.querySelector("span")?.textContent.trim() === text).click(), name);
  const draft = () => page.evaluate(() => {
    const state = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
    return state?.projects.find((p) => p.id === state.activeId);
  });
  const waitScript = () => page.waitForFunction(() => {
    const state = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
    const p = state?.projects.find((p) => p.id === state.activeId);
    return p?.scriptId && !p.scriptJobId && !document.querySelector("#source-text").disabled;
  });
  const waitGraphics = () => page.waitForFunction(() => {
    const state = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
    const p = state?.projects.find((p) => p.id === state.activeId);
    return p?.graphicsJobId && document.querySelector("#source-text").disabled;
  });
  const waitComplete = () => page.waitForFunction(() => {
    const state = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
    const p = state?.projects.find((p) => p.id === state.activeId);
    return p?.snapshot && !p.graphicsJobId && !document.querySelector("#source-text").disabled;
  }, { timeout: 60000 });
  const openProject = async (title) => {
    await click("Dự án của tôi");
    await page.evaluate((text) => [...document.querySelectorAll("dialog button strong")]
      .find((el) => el.textContent === text).closest("button").click(), title);
  };
  try {
    await page.setViewport({ width: 1440, height: 1000 });
    await page.goto(process.env.STUDIO_URL || "http://127.0.0.1:8123", { waitUntil: "networkidle0" });
    assert.equal(await page.$$eval("#phong-cach button", (buttons) => buttons.find((b) => b.textContent.trim() === "Tạo đồ họa").disabled), true);
    await fill('input[aria-label="Tên dự án"]', "Đồ họa A");
    await fill("#source-text", "Vì sao có mưa? Giải thích sự hình thành mây.");
    await click("Tạo kịch bản"); await waitScript();
    const firstScript = await draft();
    const canonicalPath = path.join(qa, "script-api/scripts", firstScript.scriptId, "kich_ban.json");
    const canonical = fs.readFileSync(canonicalPath, "utf8");
    await selectStyle("Flat with black");
    await page.evaluate(() => {
      const button = [...document.querySelectorAll("button")].find((b) => b.textContent.trim() === "Tạo đồ họa");
      button.click(); button.click();
    });
    await waitGraphics();
    const firstJob = (await draft()).graphicsJobId;
    assert.equal(await page.$eval("#source-text", (input) => input.disabled), true);
    assert.equal(await page.$$eval('#phong-cach button[aria-pressed]', (buttons) => buttons.every((b) => b.disabled)), true);
    assert.equal(await page.$("#xem-truoc iframe"), null);
    let failPolls = true;
    await page.setRequestInterception(true);
    page.on("request", (request) => {
      if (failPolls && /\/api\/graphics\/[a-f0-9]{32}$/.test(request.url())) request.abort();
      else request.continue();
    });
    await page.waitForFunction(() => document.body.textContent.includes("Đang tự kết nối lại để theo dõi đồ họa"));
    failPolls = false;
    await page.reload({ waitUntil: "domcontentloaded" });
    await waitComplete();
    const first = await draft();
    assert.equal(first.snapshot.id, firstJob);
    assert.equal(posts, 1);
    assert.equal(first.snapshot.styleId, "flat-with-black");
    assert.equal(first.snapshot.phases.length, 5);
    assert.equal(first.snapshot.duration, 2.5);
    assert.equal(fs.readFileSync(canonicalPath, "utf8"), canonical);
    const fullOutput = path.join(qa, "script-api/previews", firstJob);
    assert.equal(fs.readFileSync(path.join(fullOutput, "kich_ban.json"), "utf8"), canonical);
    const context = JSON.parse(fs.readFileSync(path.join(fullOutput, "render_config.json"), "utf8"));
    assert.equal(context.id, "flat-with-black");
    const imagePrompt = fs.readdirSync(path.join(fullOutput, "prompts")).find((name) => name.startsWith("image_"));
    for (const name of [imagePrompt, "phase_1.txt"]) {
      assert.ok(fs.readFileSync(path.join(fullOutput, "prompts", name), "utf8").includes("SELECTED ILLUSTRATION STYLE: flat-with-black"));
    }
    report.checks.push("full screenplay + selected style reach image/animation prompts; one POST; no partial preview; reload/reconnect recovery");

    await page.waitForFunction(() => !document.querySelector('button[aria-label="Phát preview"]').disabled);
    const frame = page.frames().find((f) => f.url().endsWith("phase_1.html"));
    assert.ok(frame);
    const seek = (time) => frame.evaluate((t) => {
      window.renderAt(t);
      return { transform: getComputedStyle(document.querySelector(".motion")).transform,
        currentTime: document.getAnimations()[0].currentTime,
        images: document.querySelectorAll("image").length };
    }, time);
    const start = await seek(0);
    const middle = await seek(.25);
    assert.equal(start.images, 1);
    assert.notEqual(start.transform, middle.transform);
    assert.deepEqual(await seek(0), start);
    await frame.evaluate(() => window.postMessage({ t: .4 }, "*"));
    assert.equal(await frame.evaluate(() => document.getAnimations()[0].currentTime), 0);
    await page.click('button[aria-label="Phát preview"]');
    await page.waitForSelector('button[aria-label="Tạm dừng preview"]');
    await page.click('button[aria-label="Tạm dừng preview"]');
    await page.$eval('input[aria-label="Tua preview"]', (input) => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input, ".2");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await page.waitForFunction(() => document.querySelector('input[aria-label="Tua preview"]').value === "0.2");
    await page.$$eval('#xem-truoc [aria-label="Danh sách phase"] button', (buttons) => buttons[1].click());
    await page.waitForFunction(() => document.querySelector("#xem-truoc iframe").src.endsWith("phase_2.html"));
    assert.equal(await page.$$eval("#xem-truoc button", (buttons) => buttons
      .filter((b) => /Sửa phase|Xóa phase|Tạo lại animation|Chat với AI/.test(b.textContent)).every((b) => b.disabled)), true);
    assert.equal(await page.$$eval("#xem-truoc button", (buttons) => buttons.find((b) => b.textContent.trim() === "Xuất video").disabled), false);
    report.checks.push("generated PNG HTML moves deterministically when seeking; play/pause/phase selection work; export enabled after all phases complete");

    await selectStyle("Halftone line");
    await page.waitForFunction(() => document.querySelector("#xem-truoc").textContent.includes("Cần cập nhật preview"));
    assert.equal(await page.evaluate(async () => (await fetch('/_qa/fail-next-phase', { method: 'POST' })).ok), true);
    await click("Tạo đồ họa"); await waitGraphics();
    const failedId = (await draft()).graphicsJobId;
    await page.waitForFunction(() => !document.querySelector("#source-text").disabled &&
      document.querySelector("#phong-cach").textContent.includes("HTTP 503"), { timeout: 30000 });
    assert.equal((await draft()).snapshot.id, firstJob);
    const partialStatus = await page.evaluate(async (id) => (await fetch(`/api/previews/${id}/phase_1.html`)).status, failedId);
    assert.equal(partialStatus, 404);
    await click("Tạo đồ họa"); await waitGraphics();
    assert.equal((await draft()).graphicsJobId, failedId);
    await waitComplete();
    assert.equal((await draft()).snapshot.id, failedId);
    assert.equal((await draft()).snapshot.styleId, "halftone-line");
    report.checks.push("style change marks stale; mid-render error preserves previous preview; retry resumes same job and completes all phases");

    await selectStyle("Flat"); await click("Tạo đồ họa"); await waitGraphics();
    const secondA = (await draft()).graphicsJobId;
    await click("Dự án của tôi"); await click("Bắt đầu dự án mới");
    assert.equal(await page.$eval("#source-text", (input) => input.disabled), false);
    await fill('input[aria-label="Tên dự án"]', "Đồ họa B");
    await fill("#source-text", "Giải thích vòng tuần hoàn nước.");
    await click("Tạo kịch bản"); await waitScript();
    await click("Tạo đồ họa"); await waitGraphics();
    const jobB = (await draft()).graphicsJobId;
    await waitComplete();
    assert.equal((await draft()).snapshot.id, jobB);
    await openProject("Đồ họa A");
    await page.waitForFunction((id) => {
      const state = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
      const p = state.projects.find((p) => p.id === state.activeId);
      return p.snapshot?.id === id && !p.graphicsJobId;
    }, {}, secondA);
    report.checks.push("graphics jobs keep their own project and immutable snapshot when switching projects");

    for (const width of [1440, 768, 375]) {
      await page.setViewport({ width, height: 1000 });
      await page.evaluate(() => document.querySelector("#xem-truoc").scrollIntoView());
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `overflow at ${width}`);
      await page.screenshot({ path: path.join(qa, `graphics-${width}.png`), fullPage: true });
    }
    await page.evaluate(() => {
      const state = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
      state.projects.forEach((p) => { delete p.scriptId; delete p.graphicsJobId; });
      localStorage.setItem("ai-video-studio:v1", JSON.stringify(state));
    });
    await page.reload({ waitUntil: "networkidle0" });
    assert.equal(await page.$$eval("#phong-cach button", (buttons) => buttons.find((b) => b.textContent.trim() === "Tạo đồ họa").disabled), true);
    assert.ok(await page.$("#xem-truoc iframe"));
    report.checks.push("desktop/tablet/mobile without overflow; legacy draft can still view saved preview and is prompted to recreate screenplay");
    assert.deepEqual(report.errors, []);
    report.ok = true;
    report.previewId = secondA;
  } catch (error) {
    report.failure = String(error.stack || error);
    await page.screenshot({ path: path.join(qa, "graphics-failure.png"), fullPage: true }).catch(() => {});
    process.exitCode = 1;
  } finally {
    fs.writeFileSync(path.join(qa, "graphics-browser-report.json"), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
    await browser.close();
  }
})();
