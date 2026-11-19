const puppeteer = require("puppeteer-core");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
process.chdir(path.resolve(__dirname, "../.."));
fs.mkdirSync("storage/qa", { recursive: true });
fs.writeFileSync(
  "storage/qa/sample.txt",
  "Đây là nội dung kiểm tra tải file tiếng Việt. Một câu chuyện mới bắt đầu.",
);
execFileSync(process.env.PYTHON_COMMAND || "python3", [
  "-c",
  `
from pathlib import Path
import zipfile
with zipfile.ZipFile(Path('storage/qa/sample.docx'),'w') as z:
 z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
 z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
 z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Đây là văn bản DOCX tiếng Việt.</w:t></w:r></w:p></w:body></w:document>')
`,
]);
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
(async () => {
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome",
    headless: true,
    args: ["--no-sandbox"],
  });
  const report = { errors: [], checks: [] };
  let page;
  try {
    page = await browser.newPage();
    page.on("pageerror", (error) => report.errors.push(error.message));
    const click = async (text, exact = false) => {
      await page.waitForFunction(
        (text, exact) =>
          [...document.querySelectorAll("button")].some(
            (b) =>
              !b.disabled &&
              (exact
                ? b.textContent.trim() === text
                : b.textContent.includes(text)),
          ),
        {},
        text,
        exact,
      );
      await page.evaluate(
        (text, exact) =>
          [...document.querySelectorAll("button")]
            .find(
              (b) =>
                !b.disabled &&
                (exact
                  ? b.textContent.trim() === text
                  : b.textContent.includes(text)),
            )
            .click(),
        text,
        exact,
      );
    };
    const fill = async (selector, value) => {
      await page.waitForSelector(selector, { visible: true });
      await page.focus(selector);
      await page.keyboard.down("Control");
      await page.keyboard.press("a");
      await page.keyboard.up("Control");
      await page.keyboard.type(value);
    };
    await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 1 });
    await page.goto(process.env.STUDIO_URL || "http://127.0.0.1:8000", {
      waitUntil: "networkidle0",
    });
    assert.equal(await page.$eval("#input-file", (panel) => panel.hidden), true);
    await click("Tải tài liệu", true);
    await page.waitForFunction(() => document.querySelector("#input-text").hidden);
    const fileInput = await page.$("#noi-dung input[type=file]");
    await fileInput.uploadFile(path.resolve("storage/qa/sample.txt"));
    await page.waitForFunction(() =>
      document
        .querySelector("#source-text")
        .value.includes("kiểm tra tải file"),
    );
    await fileInput.uploadFile(path.resolve("storage/qa/sample.docx"));
    await page.waitForFunction(() =>
      document.querySelector("#source-text").value.includes("DOCX tiếng Việt"),
    );
    report.checks.push("TXT and DOCX uploads preserve Vietnamese text");
    await click("Nhập văn bản", true);
    await click("Thử với nội dung mẫu");
    assert.equal(await page.$("#kich-ban"), null);
    await click("Tạo kịch bản", true);
    await page.waitForSelector('button[aria-label="Sửa cảnh 1"]');
    assert.ok(await page.$("#noi-dung #kich-ban"));
    assert.equal(await page.$$eval('nav[aria-label="Các bước tạo video"] a', (links) => links.length), 3);
    report.checks.push("generated script appears inside step 1 with three navigation steps");
    assert.equal(await page.$eval('button[aria-label="Sửa cảnh 1"]', (button) => button.disabled), true);
    assert.equal(await page.$$eval("#kich-ban button", (buttons) => buttons
      .filter((button) => /Chat với AI|Thêm cảnh/.test(button.textContent))
      .every((button) => button.disabled)), true);
    await click("Tạo đồ họa", true);
    await page.waitForSelector("#xem-truoc iframe");
    await page.waitForFunction(
      () =>
        !document.querySelector('button[aria-label="Phát preview"]').disabled,
    );
    await page.click('button[aria-label="Phát preview"]');
    await pause(250);
    assert.ok(await page.$('button[aria-label="Tạm dừng preview"]'));
    await page.click('button[aria-label="Tạm dừng preview"]');
    await page.$eval('input[aria-label="Tua preview"]', (input) => {
      input.value = "0.2";
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await fill(
      'input[aria-label="Tên dự án"]',
      "Video kiểm tra từ trình duyệt",
    );
    await page.waitForFunction(() =>
      document
        .querySelector("#xem-truoc")
        .textContent.includes("Cần cập nhật preview"),
    );
    assert.equal(
      await page.evaluate(
        () =>
          [...document.querySelectorAll("#xem-truoc button")].find(
            (b) => b.textContent.trim() === "Xuất video",
          ).disabled,
      ),
      true,
    );
    await click("Cập nhật", true);
    await page.waitForFunction(() =>
      document
        .querySelector("#xem-truoc")
        .textContent.includes("5/5 phase sẵn sàng"),
    );
    report.checks.push(
      "readonly AI script, preview playback, stale preview export guard",
    );
    await click("Xuất video", true);
    await page.waitForSelector("dialog[open]");
    const selects = await page.$$("dialog select");
    await selects[0].select("24");
    await selects[1].select("draft");
    await page.screenshot({
      path: "storage/qa/export-dialog.png",
      fullPage: false,
    });
    await click("Bắt đầu xuất", true);
    await page.waitForFunction(() => {
      const p = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
      return p?.projects?.find((d) => d.id === p.activeId)?.jobId;
    });
    const before = await page.evaluate(() => {
      const p = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
      return p.projects.find((d) => d.id === p.activeId).jobId;
    });
    await page.reload({ waitUntil: "networkidle0" });
    await page.waitForFunction(
      () => document.querySelector("#xem-truoc video"),
      { timeout: 180000 },
    );
    assert.equal(
      await page.evaluate(() => {
        const p = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
        return p.projects.find((d) => d.id === p.activeId).jobId;
      }),
      before,
    );
    await page.waitForFunction(
      () => document.querySelector("video").readyState >= 1,
    );
    const media = await page.$eval("video", (video) => ({
      duration: video.duration,
      width: video.videoWidth,
      height: video.videoHeight,
      paused: video.paused,
    }));
    assert.equal(media.width, 1920);
    assert.equal(media.height, 1080);
    assert.equal(media.paused, true);
    assert.ok(Math.abs(media.duration - 2.5) < 0.1);
    await page.$eval("video", (video) => {
      video.currentTime = 1;
    });
    await page.waitForFunction(
      () =>
        !document.querySelector("video").seeking &&
        document.querySelector("video").currentTime >= 0.9,
    );
    const download = await page.$eval("a[download]", async (link) => {
      const response = await fetch(link.href);
      return {
        status: response.status,
        bytes: (await response.arrayBuffer()).byteLength,
        disposition: response.headers.get("content-disposition"),
      };
    });
    assert.equal(download.status, 200);
    assert.ok(download.bytes > 10000);
    assert.ok(download.disposition.startsWith("attachment"));
    report.checks.push(
      "actual MP4 render, reload recovery, video dimensions/duration, paused by default, seek, download",
    );
    report.jobId = before;
    report.media = media;
    report.download = download;
    await page.evaluate(() => scrollTo({ top: 0, behavior: "instant" }));
    await page.screenshot({
      path: "storage/qa/desktop-complete.png",
      fullPage: true,
    });
    for (const width of [768, 375]) {
      await page.setViewport({ width, height: 900, deviceScaleFactor: 1 });
      await pause(300);
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
        false,
        `overflow at ${width}`,
      );
      await page.evaluate(() => scrollTo({ top: 0, behavior: "instant" }));
      await page.screenshot({
        path: `storage/qa/viewport-${width}.png`,
        fullPage: false,
      });
      await page.screenshot({
        path: `storage/qa/responsive-${width}.png`,
        fullPage: true,
      });
    }
    report.checks.push(
      "responsive 768px and 375px without horizontal overflow",
    );
    // Verify JSON export/import and project management in the actual UI.
    await click("Dự án của tôi", true);
    const exported = await page.evaluate(() => {
      const value = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
      return {
        version: 1,
        project: value.projects.find((p) => p.id === value.activeId),
      };
    });
    fs.writeFileSync(
      "storage/qa/exported-draft.json",
      JSON.stringify(exported),
    );
    await click("Bắt đầu dự án mới", true);
    await page.waitForFunction(
      () =>
        document.querySelector('input[aria-label="Tên dự án"]').value ===
        "Dự án chưa đặt tên",
    );
    await click("Dự án của tôi", true);
    await (
      await page.$("dialog input[type=file]")
    ).uploadFile(path.resolve("storage/qa/exported-draft.json"));
    await page.waitForFunction(
      () =>
        document.querySelector('input[aria-label="Tên dự án"]').value ===
        "Video kiểm tra từ trình duyệt",
    );
    assert.equal(await page.$("#xem-truoc iframe"), null);
    report.checks.push(
      "new project and JSON import restore editable content without stale server references",
    );
    assert.deepEqual(report.errors, []);
    report.ok = true;
  } catch (error) {
    report.failure = String(error.stack || error);
    process.exitCode = 1;
    if (page)
      await page
        .screenshot({ path: "storage/qa/browser-failure.png" })
        .catch(() => {});
  } finally {
    fs.writeFileSync(
      "storage/qa/browser-report.json",
      JSON.stringify(report, null, 2),
    );
    console.log(JSON.stringify(report, null, 2));
    await browser.close();
  }
})();
