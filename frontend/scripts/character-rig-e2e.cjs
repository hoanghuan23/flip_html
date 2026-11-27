const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');
const puppeteer = require('puppeteer-core');

const root = path.resolve(__dirname, '../..');
const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'character-rig-e2e-'));
const presets = JSON.parse(fs.readFileSync(path.join(root, 'config/character_presets.json'), 'utf8')).presets;

async function assertVisibleConfigs(page) {
  const cards = await page.$$('article');
  assert.equal(cards.length, Object.keys(presets).length);
  for (const card of cards) {
    const name = await card.$eval('h2', node => node.textContent);
    const config = await card.$('.preset-config pre');
    assert.ok(config, name + ': missing config.');
    assert.deepEqual(JSON.parse(await config.evaluate(node => node.textContent)), presets[name]);
    await config.scrollIntoView();
    const visible = await config.evaluate(node => {
      const range = document.createRange();
      range.selectNodeContents(node);
      const style = getComputedStyle(node);
      return range.getClientRects().length > 0 && style.visibility === 'visible' && style.opacity !== '0';
    });
    assert.ok(visible, name + ': config text is not rendered.');
  }
}

async function assertPaintedHead(element, label) {
  const screenshot = await element.screenshot({ omitBackground: true });
  const pixels = spawnSync('python3', ['-c', [
    'from PIL import Image',
    'import io, sys',
    'im = Image.open(io.BytesIO(sys.stdin.buffer.read())).convert("RGBA")',
    'w, h = im.size',
    'face = im.crop((int(w*.25), int(h*.1), int(w*.8), int(h*.48)))',
    'print(sum(a>128 and r>170 and 100<g<240 and 70<b<210 and r>g>b for r,g,b,a in face.getdata()))',
  ].join('\n')], { input: screenshot, encoding: 'utf8' });
  assert.equal(pixels.status, 0, pixels.stderr);
  assert.ok(Number(pixels.stdout) > 200, label + ': head is not visibly painted.');
}

(async () => {
  let browser;
  try {
    const output = path.join(directory, 'gallery.html');
    const build = spawnSync('python3', [path.join(root, 'assemble_character.py'),
      '--gallery', '--output', output], { cwd: root, encoding: 'utf8' });
    assert.equal(build.status, 0, build.stderr);
    browser = await puppeteer.launch({
      executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
      headless: true, args: ['--no-sandbox'],
    });
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    // The last card starts below the viewport, matching the reported missing-head case.
    await page.setViewport({ width: 1100, height: 640 });
    await page.goto(pathToFileURL(output).href, { waitUntil: 'networkidle0' });
    assert.equal(await page.evaluate(() => window.characterPreviewReady), true);
    assert.equal(await page.$$('.character[data-state="ready"]').then(nodes => nodes.length), 5);
    await assertVisibleConfigs(page);
    await page.$eval('article:last-child', node => node.scrollIntoView());
    await page.evaluate(() => new Promise(requestAnimationFrame));
    const neutral = await page.$('article:last-child .character svg');
    // Inspect actual painted skin pixels above the collar, not just a decoded image URL.
    await assertPaintedHead(neutral, 'neutral after scrolling');
    await page.setViewport({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await assertVisibleConfigs(page);

    const html = fs.readFileSync(output, 'utf8');
    // Script is blocked by CSP while scripting remains enabled: noscript is not a fallback.
    const restrictedOutput = path.join(directory, 'script-blocked.html');
    const policy = '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'none\'; style-src \'unsafe-inline\'; img-src data:;">';
    fs.writeFileSync(restrictedOutput, html.replace('<meta charset="utf-8">', '<meta charset="utf-8">' + policy));
    await page.setViewport({ width: 1100, height: 640 });
    await page.goto(pathToFileURL(restrictedOutput).href, { waitUntil: 'networkidle0' });
    assert.equal(await page.evaluate(() => window.characterPreviewReady), undefined);
    assert.equal(await page.$$('.character[data-state="static"]').then(nodes => nodes.length), 5);
    await assertVisibleConfigs(page);
    for (const [index, character] of (await page.$$('.character')).entries()) {
      assert.equal(await character.$eval('svg', node => getComputedStyle(node).visibility), 'visible');
      assert.equal(await character.$eval('.image-status', node => getComputedStyle(node).display), 'none');
      await assertPaintedHead(await character.$('svg'), 'script blocked, character ' + index);
    }
    if (process.env.QA_SCREENSHOT) await page.screenshot({ path: process.env.QA_SCREENSHOT, fullPage: true });

    const broken = html.replace(
      /(<image id="bitmap-\d+" data-source="HEAD\/variant_neutral\.png"[^>]*href=")[^"]+/,
      '$1data:image/png;base64,broken');
    assert.notEqual(broken, html, 'Could not inject the missing-head fixture.');
    const brokenOutput = path.join(directory, 'broken.html');
    fs.writeFileSync(brokenOutput, broken);
    await page.goto(pathToFileURL(brokenOutput).href, { waitUntil: 'networkidle0' });
    assert.equal(await page.evaluate(() => window.characterPreviewReady), false);
    assert.equal(await page.$$('.character[data-state="ready"]').then(nodes => nodes.length), 4);
    assert.equal(await page.$eval('article:last-child .character', node => node.dataset.state), 'error');
    assert.match(await page.$eval('article:last-child .image-status', node => node.textContent), /variant_neutral/);
    assert.equal(await page.$eval('article:last-child .character svg', node => getComputedStyle(node).visibility), 'hidden');
    assert.deepEqual(errors, []);
    console.log('Passed: all 5 configs visible on desktop/mobile and with script blocked; characters visible, neutral head after scrolling, broken head reports an error.');
  } finally {
    if (browser) await browser.close();
    fs.rmSync(directory, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
