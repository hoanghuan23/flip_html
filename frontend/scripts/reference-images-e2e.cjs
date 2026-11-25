const puppeteer = require("puppeteer-core");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

(async () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "reference-images-"));
  let browser;
  try {
    browser = await puppeteer.launch({
      executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome",
      headless: true, args: ["--no-sandbox"],
    });
    const page = await browser.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewport({ width: 1280, height: 1000 });
    await page.goto(process.env.STUDIO_URL || "http://127.0.0.1:5174", { waitUntil: "networkidle0" });
    await page.evaluate(() => localStorage.clear());
    await page.reload({ waitUntil: "networkidle0" });
    const fill = async (text) => {
      await page.focus("#source-text");
      await page.keyboard.down("Control");
      await page.keyboard.press("a");
      await page.keyboard.up("Control");
      await page.keyboard.type(text);
    };
    const value = () => page.$eval("#source-text", (el) => el.value);
    const options = () => page.$$eval('[role="option"]', (items) => items.map((el) => el.textContent));
    const draft = () => page.evaluate(() => {
      const state = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
      return state.projects.find((p) => p.id === state.activeId);
    });
    const upload = async (...files) => {
      await (await page.$("#reference-images-input")).uploadFile(...files);
      await page.waitForFunction(() => !document.querySelector("#reference-images-input").disabled);
    };
    const openChooser = async () => {
      const [chooser] = await Promise.all([
        page.waitForFileChooser({ timeout: 5000 }),
        page.click('button[aria-describedby="reference-images-help"]'),
      ]);
      assert.equal(chooser.isMultiple(), true);
      return chooser;
    };
    const cancelled = await openChooser();
    assert.equal(await page.$eval("#reference-images-input", (el) => el.disabled), false);
    assert.equal(await page.$$eval("#noi-dung figcaption", (els) => els.length), 0);
    await cancelled.cancel();
    await fill("Vẫn nhập được sau khi hủy chọn ảnh.");
    assert.equal(await value(), "Vẫn nhập được sau khi hủy chọn ảnh.");
    const png = await page.evaluate(() => {
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 40;
      const context = canvas.getContext("2d");
      context.fillStyle = "#7552df";
      context.fillRect(0, 0, 40, 40);
      return canvas.toDataURL("image/png").split(",")[1];
    });
    const files = ["original-a.png", "original-b.png", "original-c.png"].map((name) => {
      const file = path.join(temp, name);
      fs.writeFileSync(file, Buffer.from(png, "base64"));
      return file;
    });
    const chooser = await openChooser();
    await chooser.accept(files);
    await page.waitForFunction(() => document.querySelectorAll("#noi-dung figcaption").length === 3);
    assert.deepEqual(await page.$$eval("#noi-dung figcaption", (els) => els.map((el) => el.textContent)), ["image_1", "image_2", "image_3"]);
    await fill("Minh họa @");
    assert.deepEqual(await options(), ["image_1", "image_2", "image_3"]);
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");
    assert.equal(await value(), "Minh họa @image_2 ");
    assert.equal(await page.$('[role="listbox"]'), null);
    await page.keyboard.type("và @image_3");
    assert.deepEqual(await options(), ["image_3"]);
    await page.click('[role="option"]');
    assert.equal(await value(), "Minh họa @image_2 và @image_3 ");
    assert.equal(await page.$eval("#source-text", (el) => document.activeElement === el && el.selectionStart === el.value.length), true);

    await fill("Liên hệ user@example.com");
    assert.equal(await page.$('[role="listbox"]'), null);
    await fill("@missing");
    assert.deepEqual(await options(), []);
    assert.match(await page.$eval('[role="listbox"]', (el) => el.textContent), /Không tìm thấy/);
    await page.keyboard.press("Escape");
    assert.equal(await page.$('[role="listbox"]'), null);
    await page.keyboard.press("Enter");
    assert.equal(await value(), "@missing\n");

    await fill("Trước @ sau");
    await page.keyboard.press("Home");
    for (let i = 0; i < 7; i++) await page.keyboard.press("ArrowRight");
    await page.waitForSelector('[role="option"]');
    await page.keyboard.press("ArrowUp");
    await page.keyboard.press("Tab");
    assert.equal(await value(), "Trước @image_3 sau");

    await fill("@image_1 sau");
    await page.keyboard.press("Home");
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("ArrowRight");
    await page.waitForSelector('[role="option"]');
    await page.keyboard.press("Enter");
    assert.equal(await value(), "@image_1 sau");
    assert.equal(await page.$eval("#source-text", (el) => el.selectionStart), 8);

    await fill("Xem @, tiếp tục.");
    await page.keyboard.press("Home");
    for (let i = 0; i < 5; i++) await page.keyboard.press("ArrowRight");
    await page.waitForSelector('[role="option"]');
    await page.keyboard.press("Enter");
    assert.equal(await value(), "Xem @image_1, tiếp tục.");

    await page.click('button[aria-label="Xóa image_2"]');
    await upload(files[0]);
    await fill("@");
    assert.deepEqual(await options(), ["image_1", "image_3", "image_4"]);
    await page.keyboard.press("Escape");
    await page.waitForFunction(() => {
      const state = JSON.parse(localStorage.getItem("ai-video-studio:v1"));
      return state.projects.find((p) => p.id === state.activeId).lastReferenceImageNumber === 4;
    });
    assert.deepEqual((await draft()).referenceImages.map((image) => image.name), ["image_1", "image_3", "image_4"]);
    await page.reload({ waitUntil: "networkidle0" });
    await fill("@");
    assert.deepEqual(await options(), ["image_1", "image_3", "image_4"]);
    await page.setViewport({ width: 390, height: 844 });
    const bounds = await page.$eval('[role="listbox"]', (el) => {
      const rect = el.getBoundingClientRect();
      return { left: rect.left, right: rect.right, width: innerWidth };
    });
    assert.ok(bounds.left >= 0 && bounds.right <= bounds.width);
    await page.keyboard.press("Escape");
    await page.click('button[aria-label="Xóa image_1"]');
    await page.click('button[aria-label="Xóa image_3"]');
    await page.click('button[aria-label="Xóa image_4"]');
    await fill("@");
    assert.equal(await page.$('[role="listbox"]'), null);
    assert.deepEqual(errors, []);
    console.log("PASS: upload names, keyboard/mouse selection, filtering, caret insertion, Escape, stable numbering, reload, mobile, empty gallery.");
  } finally {
    await browser?.close();
    fs.rmSync(temp, { recursive: true, force: true });
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
