const puppeteer = require("puppeteer-core");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const root = path.resolve(__dirname, "../..");
const qa = path.join(root, "storage/qa");
fs.mkdirSync(qa, { recursive: true });

(async () => {
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome",
    headless: true, args: ["--no-sandbox"],
  });
  const report = { errors: [], checks: [] };
  const page = await browser.newPage();
  page.on("pageerror", (e) => report.errors.push(e.message));
  let posts = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/api/scripts")) posts++;
  });
  const click = async (text) => {
    await page.waitForFunction((value) => [...document.querySelectorAll("button")]
      .some((b) => !b.disabled && b.textContent.trim() === value), {}, text);
    await page.evaluate((value) => [...document.querySelectorAll("button")]
      .find((b) => !b.disabled && b.textContent.trim() === value).click(), text);
  };
  const fill = async (selector, text) => {
    await page.focus(selector);
    await page.keyboard.down("Control"); await page.keyboard.press("a"); await page.keyboard.up("Control");
    await page.keyboard.type(text);
  };
  const activeDraft = () => page.evaluate(() => {
    const state = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
    return state?.projects.find((p) => p.id === state.activeId);
  });
  const waitJob = () => page.waitForFunction(() => {
    const s = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
    const p = s?.projects.find((p) => p.id === s.activeId);
    const input = document.querySelector("#source-text");
    return p?.scriptJobId && p.sourceContent === input.value && input.disabled;
  });
  const waitDone = () => page.waitForFunction(() => {
    const s = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
    const p = s?.projects.find((p) => p.id === s.activeId);
    return p?.scriptId && !p.scriptJobId && !document.querySelector("#source-text").disabled;
  }, { timeout: 30000 });
  const readFull = (id) => JSON.parse(fs.readFileSync(path.join(qa, "script-api/scripts", id, "kich_ban.json"), "utf8"));
  try {
    await page.setViewport({ width: 1440, height: 1000 });
    await page.goto(process.env.STUDIO_URL || "http://127.0.0.1:8123", { waitUntil: "networkidle0" });
    await fill('input[aria-label="Tên dự án"]', "Dự án A");
    const idea = "Vì sao có mưa? Hãy giải thích quá trình hình thành mây.";
    const inputFile = path.join(qa, "script-idea.txt");
    fs.writeFileSync(inputFile, idea);
    await click("Tải tài liệu");
    await (await page.$('#noi-dung input[type="file"]')).uploadFile(inputFile);
    await page.waitForFunction((text) => document.querySelector("#source-text").value === text, {}, idea);
    await page.evaluate(() => {
      const button = [...document.querySelectorAll("button")].find((b) => b.textContent.trim() === "Tạo kịch bản");
      button.click(); button.click();
    });
    await waitJob();
    assert.equal(await page.$eval("#source-text", (el) => el.disabled), true);
    const pendingId = (await activeDraft()).scriptJobId;
    await page.reload({ waitUntil: "domcontentloaded" });
    await waitDone();
    const first = await activeDraft();
    assert.equal(first.scriptId, pendingId);
    assert.equal(posts, 1);
    assert.equal(fs.readFileSync(path.join(qa, "script-api/scripts", first.scriptId, "input.txt"), "utf8"), idea);
    await click("Nhập văn bản");
    const full = readFull(first.scriptId);
    assert.deepEqual(first.scenes, full.phases.map((phase) => ({
      id: String(phase.id), name: phase.name, narration: phase.narration,
      description: phase.description, duration: phase.duration,
    })));
    assert.ok(full.assets.length && full.phases[0].actions.length);
    assert.equal(await page.$eval('button[aria-label="Sửa cảnh 1"]', (b) => b.disabled), true);
    assert.equal(await page.$$eval("#kich-ban button", (buttons) => buttons
      .filter((b) => /Chat với AI|Thêm cảnh/.test(b.textContent)).every((b) => b.disabled)), true);
    assert.ok(!(await page.$eval("#kich-ban", (el) => el.textContent)).includes("CLOUD"));
    report.checks.push("one POST despite double click; reload recovery; exact JSON projection; readonly controls");

    for (const [content, message] of [["THIEU_DU_KIEN", "Cần bổ sung sự kiện"], ["LOI_API", "HTTP 503"]]) {
      await fill("#source-text", content);
      await click("Tạo kịch bản"); await click("Tạo lại");
      await page.waitForFunction((text) => !document.querySelector("#source-text").disabled &&
        [...document.querySelectorAll('[role="alert"]')].some((el) => el.textContent.includes(text)), {}, message);
      const retained = await activeDraft();
      assert.equal(retained.scriptId, first.scriptId);
      assert.deepEqual(retained.scenes, first.scenes);
      assert.deepEqual(readFull(first.scriptId), full);
    }
    report.checks.push("AI rejection and upstream error preserve previous table and canonical file");

    await fill("#source-text", "Giải thích mây hình thành như thế nào.");
    await click("Tạo kịch bản"); await click("Tạo lại");
    await waitJob();
    const secondA = (await activeDraft()).scriptJobId;
    await click("Dự án của tôi");
    assert.equal(await page.$$eval("dialog button", (buttons) => buttons.some((b) => /Tải.*JSON/.test(b.textContent))), false);
    await click("Bắt đầu dự án mới");
    assert.equal(await page.$eval("#source-text", (el) => el.disabled), false);
    await fill('input[aria-label="Tên dự án"]', "Dự án B");
    await fill("#source-text", "Giải thích vòng tuần hoàn của nước.");
    await click("Tạo kịch bản"); await waitJob();
    let failPolls = true;
    await page.setRequestInterception(true);
    page.on("request", (request) => {
      if (failPolls && request.method() === "GET" && /\/api\/scripts\/[a-f0-9]{32}$/.test(request.url())) request.abort();
      else request.continue();
    });
    await page.waitForFunction(() => document.body.textContent.includes("Đang tự kết nối lại"));
    failPolls = false;
    await waitDone();
    const projectB = await activeDraft();
    assert.notEqual(projectB.id, first.id);
    assert.notEqual(projectB.scriptId, secondA);
    await click("Dự án của tôi");
    await page.evaluate(() => [...document.querySelectorAll("dialog button strong")]
      .find((el) => el.textContent === "Dự án A").closest("button").click());
    await page.waitForFunction((id) => {
      const state = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
      const p = state.projects.find((p) => p.id === state.activeId);
      return p.scriptId === id && !p.scriptJobId;
    }, {}, secondA);
    report.checks.push("two project jobs remain isolated; polling reconnects automatically; no JSON download button");

    for (const width of [1440, 768, 375]) {
      await page.setViewport({ width, height: 1000 });
      await page.evaluate(() => document.querySelector("#kich-ban").scrollIntoView());
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `overflow at ${width}`);
      await page.screenshot({ path: path.join(qa, `script-${width}.png`), fullPage: true });
    }
    // Simulate a legacy draft with no server/script references.
    await page.evaluate(() => {
      const s = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
      s.projects.forEach((p) => { delete p.scriptId; delete p.scriptJobId; });
      localStorage.setItem("ai-video-studio:v1", JSON.stringify(s));
    });
    await page.reload({ waitUntil: "networkidle0" });
    assert.equal(await page.$$eval('#kich-ban button[aria-label^="Chọn cảnh"]', (rows) => rows.length), 5);
    report.checks.push("desktop/tablet/mobile without overflow; legacy draft remains readable");
    assert.deepEqual(report.errors, []);
    report.ok = true;
    report.scriptId = first.scriptId;
  } catch (e) {
    report.failure = String(e.stack || e);
    await page.screenshot({ path: path.join(qa, "script-failure.png"), fullPage: true }).catch(() => {});
    process.exitCode = 1;
  } finally {
    fs.writeFileSync(path.join(qa, "script-browser-report.json"), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
    await browser.close();
  }
})();
