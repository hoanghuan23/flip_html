// Run against frontend/scripts/qa_server.py (AI responses are fixtures).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const puppeteer = require('puppeteer-core');

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
    headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  const click = async (label) => {
    await page.waitForFunction((text) => [...document.querySelectorAll('button')]
      .some((b) => !b.disabled && b.textContent.trim() === text), {}, label);
    await page.evaluate((text) => [...document.querySelectorAll('button')]
      .find((b) => !b.disabled && b.textContent.trim() === text).click(), label);
  };
  const project = () => page.evaluate(() => {
    const saved = JSON.parse(localStorage.getItem('ai-video-studio:v1'));
    return saved.projects.find((p) => p.id === saved.activeId);
  });
  try {
    await page.setViewport({ width: 1440, height: 1000 });
    await page.goto(process.env.STUDIO_URL || 'http://127.0.0.1:8123', { waitUntil: 'networkidle0' });
    await page.type('#source-text', 'Vì sao có mưa? Giải thích quá trình hình thành mây.');
    await click('Tạo kịch bản');
    await page.waitForFunction(() => {
      const s = JSON.parse(localStorage.getItem('ai-video-studio:v1'));
      const p = s?.projects.find((p) => p.id === s.activeId);
      return !!p?.scriptId && !p.scriptJobId;
    }, { timeout: 30000 });
    let current = await project();
    assert.equal(current.tokenUsage.script.input_tokens, 240);
    assert.equal(current.tokenUsage.script.output_tokens, 60);
    await click('Tất cả phong cách');
    await page.evaluate(() => [...document.querySelectorAll('#phong-cach button')]
      .find((b) => b.querySelector('span')?.textContent.trim() === 'Flat with black').click());
    await click('Tạo đồ họa');
    await page.waitForFunction(() => [...document.querySelectorAll('button')]
      .some((b) => !b.disabled && b.textContent.trim() === 'Xác nhận và tạo hoàn chỉnh'), { timeout: 60000 });
    await page.waitForFunction(() => {
      const s = JSON.parse(localStorage.getItem('ai-video-studio:v1'));
      const p = s.projects.find((p) => p.id === s.activeId);
      return !!p.graphicsPreviewId && !p.graphicsJobId;
    });
    current = await project();
    assert.equal(current.tokenUsage.graphics.requests, 5);
    assert.equal(current.tokenUsage.graphics.input_tokens, 600);
    assert.equal(current.tokenUsage.graphics.output_tokens, 150);
    assert.equal(current.tokenUsage.animation, undefined);
    await page.reload({ waitUntil: 'networkidle0' });
    assert.deepEqual((await project()).tokenUsage, current.tokenUsage);
    await click('Xác nhận và tạo hoàn chỉnh');
    await page.waitForFunction(() => {
      const s = JSON.parse(localStorage.getItem('ai-video-studio:v1'));
      const p = s.projects.find((p) => p.id === s.activeId);
      return !!p.snapshot && !p.graphicsJobId;
    }, { timeout: 60000 });
    current = await project();
    assert.equal(current.tokenUsage.graphics.requests, 5, 'confirmation must not recount stills');
    assert.ok(current.tokenUsage.animation.requests > 0);
    assert.equal(current.tokenUsage.animation.unknown_requests, 0);
    assert.equal(current.tokenUsage.graphics.phases['1'].total_tokens, 150);
    assert.equal(current.tokenUsage.animation.phases['1'].total_tokens, 150);
    assert.equal(current.tokenUsage.animation.shared.total_tokens, 150);
    assert.deepEqual(current.snapshot.tokenUsage, {
      graphics: current.tokenUsage.graphics, animation: current.tokenUsage.animation,
    });
    const phaseCard = () => page.$eval('[aria-label^="Token Phase "]', (el) => el.textContent);
    assert.match(await phaseCard(), /Token · Phase 1/);
    assert.match(await phaseCard(), /Tổng phase300/);
    assert.match(await phaseCard(), /dùng chung cho các phase: 150 token/);
    await page.$$eval('[aria-label="Danh sách phase"] button', (buttons) => buttons[1].click());
    assert.match(await phaseCard(), /Token · Phase 2/);
    assert.match(await phaseCard(), /Tổng phase300/);
    const expected = Object.values(current.tokenUsage).reduce((sum, u) => sum + u.total_tokens, 0);
    const shown = await page.$eval('#xem-truoc tfoot td:last-child', (el) => el.textContent);
    assert.equal(shown, expected.toLocaleString('vi-VN'));
    assert.equal(await page.$$eval('[aria-label^="Token "]', (els) => els.length), 3);
    await page.reload({ waitUntil: 'networkidle0' });
    assert.deepEqual((await project()).tokenUsage, current.tokenUsage);
    assert.match(await phaseCard(), /Token · Phase 1/);
    assert.match(await phaseCard(), /Tổng phase300/);
    await page.$eval('#xem-truoc', (el) => el.scrollIntoView());
    const output = path.resolve(__dirname, '../../storage/qa');
    fs.mkdirSync(output, { recursive: true });
    await page.screenshot({ path: path.join(output, 'token-usage-desktop.png'), fullPage: true });
    await page.setViewport({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(output, 'token-usage-mobile.png'), fullPage: true });
    const table = await page.$('#xem-truoc table');
    await table.screenshot({ path: path.join(output, 'token-usage-mobile-table.png') });
    assert.ok(await page.$eval('#xem-truoc table', (el) => el.scrollWidth <= el.parentElement.clientWidth), 'all totals should fit the mobile table');
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'page should fit mobile viewport');
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ ok: true, tokenUsage: current.tokenUsage, total: expected, screenshots: output }));
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
