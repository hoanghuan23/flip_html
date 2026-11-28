const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const {spawn} = require('node:child_process');
const puppeteer = require('puppeteer-core');

const root = path.resolve(__dirname, '../..');
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLttAAAAABJRU5ErkJggg==', 'base64');
const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'character-ai-e2e-'));
const slots = ['head', 'suit', 'arm_L', 'arm_R', 'legs_pair'];
const calls = [];
let failGeneration = false;

async function listen(server) {
  await new Promise((resolve, reject) => {server.once('error', reject); server.listen(0, '127.0.0.1', resolve);});
  return server.address().port;
}

(async () => {
  let browser, backend;
  const mock = http.createServer(async (request, response) => {
    try {
      assert.equal(request.url, '/generate-image');
      assert.equal(request.headers['x-api-key'], 'browser-test-key');
      const chunks = []; for await (const chunk of request) chunks.push(chunk);
      const data = JSON.parse(Buffer.concat(chunks)); calls.push(data);
      assert.deepEqual(Object.keys(data).sort(), ['model', 'prompt', 'reference_images']);
      assert.equal(data.reference_images.length, 5);
      assert.equal(data.model, 'browser-test-model');
      assert.match(data.prompt, /Image 1: head/);
      assert.match(data.prompt, /exact facial expression/);
      for (const image of data.reference_images) assert.ok(image.startsWith('data:image/png;base64,iVBOR'));
      response.writeHead(failGeneration ? 401 : 200, {'Content-Type': 'application/json'});
      response.end(JSON.stringify(failGeneration ? {detail: 'Unauthorized fixture'} : {
        success: true, output_format: 'png', usage: {input_tokens: 100, output_tokens: 10},
        data: [{b64_json: png.toString('base64')}],
      }));
    } catch (error) { response.writeHead(500, {'Content-Type': 'application/json'}); response.end(JSON.stringify({detail: error.message})); }
  });
  try {
    const mockPort = await listen(mock);
    const reservation = http.createServer(); const port = await listen(reservation);
    await new Promise(resolve => reservation.close(resolve));
    let logs = '';
    backend = spawn(process.env.PYTHON || 'python3', ['-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1', '--port', String(port)], {
      cwd: root, env: {...process.env, VIDEO_STORAGE_DIR: path.join(directory, 'storage'),
        CODEX_API_TOKEN: 'browser-test-key', CODEX_MODEL: 'browser-test-model',
        CODEX_IMAGE_API_URL: `http://127.0.0.1:${mockPort}/generate-image`}, stdio: ['ignore', 'pipe', 'pipe'],
    });
    backend.stdout.on('data', chunk => logs += chunk); backend.stderr.on('data', chunk => logs += chunk);
    const base = `http://127.0.0.1:${port}`;
    let ready = false;
    for (let i = 0; i < 60; i++) {
      if (backend.exitCode !== null) throw new Error(logs);
      try { if ((await fetch(base + '/api/health')).ok) { ready = true; break; } } catch {}
      await new Promise(resolve => setTimeout(resolve, 200));
    }
    assert.ok(ready, logs || 'Backend did not start');
    browser = await puppeteer.launch({executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox']});
    const page = await browser.newPage(); const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setViewport({width: 1360, height: 1000});
    await page.goto(base + '/character-ai', {waitUntil: 'networkidle0'});
    await page.waitForFunction(() => !document.getElementById('fields').disabled);
    assert.equal(await page.$$eval('#parts img', nodes => nodes.length), 5);
    assert.equal(await page.$$eval('#parts img', nodes => nodes.every(n => n.complete && n.naturalWidth > 0)), true);
    assert.equal(await page.$('#api-key, #model, #endpoint, textarea#prompt'), null);
    assert.ok(!(await page.content()).includes('browser-test-key'));
    const submitted = [];
    page.on('request', request => {
      if (request.url().endsWith('/api/character-ai/generate')) submitted.push(JSON.parse(request.postData()));
    });
    await page.screenshot({path: '/tmp/character-ai-desktop.png', fullPage: true});
    await page.select('#preset', 'front_neutral');
    await page.waitForFunction(() => document.querySelector('#parts img').src.length > 100 && document.querySelector('#parts .path').textContent.includes('neutral'));
    await page.setViewport({width: 390, height: 844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.screenshot({path: '/tmp/character-ai-mobile.png', fullPage: true});
    const config = JSON.parse(fs.readFileSync(path.join(root, 'config/character_presets.json'))).presets.front_happy;
    const imported = {default_preset: 'my_character', presets: {my_character: config}};
    const file = path.join(directory, 'custom.json'); fs.writeFileSync(file, JSON.stringify(imported));
    await (await page.$('#file')).uploadFile(file);
    await page.waitForFunction(() => document.getElementById('preset').value === 'my_character' && document.getElementById('status').textContent.includes('Đã nạp'));
    await page.$eval('#config', node => {node.value = '{invalid'; node.dispatchEvent(new Event('input'));});
    await page.click('#preview');
    await page.waitForFunction(() => document.getElementById('status').dataset.error === 'true');
    assert.equal(calls.length, 0);
    await page.$eval('#config', (node, parts) => {node.value = JSON.stringify(parts);}, Object.fromEntries(slots.map(slot => [slot, config.parts[slot]])));
    const cdp = await page.createCDPSession();
    await cdp.send('Page.setDownloadBehavior', {behavior: 'allow', downloadPath: directory});
    await page.click('#generate');
    await page.waitForFunction(() => !document.getElementById('result').hidden && !document.getElementById('fields').disabled);
    assert.equal(calls.length, 1);
    assert.deepEqual(Object.keys(submitted[0]).sort(), ['config', 'preset_id', 'prompt']);
    const fixedPrompt = await page.$eval('#character-prompt', node => node.textContent.trim());
    assert.ok(submitted[0].prompt.startsWith(fixedPrompt));
    assert.equal(calls[0].prompt, submitted[0].prompt);
    assert.equal(await page.$eval('#result', node => node.naturalWidth), 1);
    await page.click('#download');
    const download = path.join(directory, 'my_character-ai.png');
    for (let i = 0; i < 30 && !fs.existsSync(download); i++) await new Promise(resolve => setTimeout(resolve, 100));
    assert.deepEqual(fs.readFileSync(download), png);
    const savedId = await page.$eval('#saved', node => node.value);
    assert.match(savedId, /^[a-f0-9]{32}$/);
    await page.click('#download-config');
    const savedFile = path.join(directory, savedId + '.json');
    for (let i = 0; i < 30 && !fs.existsSync(savedFile); i++) await new Promise(resolve => setTimeout(resolve, 100));
    const manifest = JSON.parse(fs.readFileSync(savedFile, 'utf8'));
    assert.equal(manifest.id, savedId);
    assert.equal(manifest.kind, 'character-ai-result');
    assert.deepEqual(manifest.input.config, submitted[0].config);
    assert.ok(!JSON.stringify(manifest).includes('browser-test-key'));
    await page.reload({waitUntil: 'networkidle0'});
    await page.select('#saved', savedId);
    await page.click('#open-saved');
    await page.waitForFunction(() => !document.getElementById('result').hidden && document.getElementById('usage').textContent.includes('Không gọi AI'));
    assert.equal(await page.$eval('#result', node => node.naturalWidth), 1);
    assert.equal(calls.length, 1);
    assert.equal(submitted.length, 1);
    await page.reload({waitUntil: 'networkidle0'});
    await (await page.$('#file')).uploadFile(savedFile);
    await page.waitForFunction(() => document.getElementById('usage').textContent.includes('Không gọi AI'));
    assert.equal(calls.length, 1);
    failGeneration = true;
    await page.click('#generate');
    await page.waitForFunction(() => document.getElementById('status').dataset.error === 'true' && !document.getElementById('fields').disabled);
    assert.match(await page.$eval('#status', node => node.textContent), /Unauthorized/);
    assert.equal(calls.length, 2);
    assert.deepEqual(errors, []);
    const missingConfig = await browser.newPage();
    await missingConfig.setRequestInterception(true);
    missingConfig.on('request', request => {
      if (request.url().endsWith('/api/character-ai/config')) {
        request.respond({status: 200, contentType: 'text/html', body: '<html>Static server fallback</html>'});
      } else request.continue();
    });
    await missingConfig.goto(base + '/character-ai', {waitUntil: 'networkidle0'});
    await missingConfig.waitForFunction(() => document.getElementById('status').dataset.error === 'true');
    assert.equal(await missingConfig.$eval('#fields', node => node.disabled), false);
    assert.equal(await missingConfig.$('#connection-help'), null);
    await missingConfig.type('#config', '{"parts":{}}');
    assert.equal(await missingConfig.$eval('#config', node => node.value), '{"parts":{}}');
    await (await missingConfig.$('#file')).uploadFile(file);
    await missingConfig.waitForFunction(() => document.getElementById('status').textContent.includes('Đã nạp'));
    assert.equal(await missingConfig.$$eval('#parts img', nodes => nodes.length), 5);
    assert.equal(calls.length, 2);
    await missingConfig.close();

    const staticPage = await browser.newPage();
    await staticPage.setRequestInterception(true);
    const destination = 'http://127.0.0.1:8001/character-ai';
    staticPage.on('request', request => {
      if (request.url() === destination) {
        request.respond({status: 200, contentType: 'text/html', body: '<p id="canonical">Backend page</p>'});
      } else if (request.url() === 'http://static.test/character_ai.html') {
        request.respond({status: 200, contentType: 'text/html', body: fs.readFileSync(path.join(root, 'character_ai.html'), 'utf8')});
      } else request.continue();
    });
    await staticPage.goto('http://static.test/character_ai.html', {waitUntil: 'networkidle0'});
    await staticPage.waitForSelector('#canonical');
    assert.equal(staticPage.url(), destination);
    await staticPage.close();

    const delayedConfig = await browser.newPage();
    await delayedConfig.setRequestInterception(true);
    let release;
    const pending = new Promise(resolve => {release = resolve;});
    delayedConfig.on('request', async request => {
      if (request.url().endsWith('/api/character-ai/config')) await pending;
      request.continue();
    });
    await delayedConfig.goto(base + '/character-ai', {waitUntil: 'domcontentloaded'});
    const typed = JSON.stringify(config);
    await delayedConfig.$eval('#config', (node, value) => {node.value = value; node.dispatchEvent(new Event('input'));}, typed);
    release();
    await delayedConfig.waitForFunction(() => document.getElementById('status').textContent.includes('Sẵn sàng'));
    assert.equal(await delayedConfig.$eval('#config', node => node.value), typed);
    await delayedConfig.close();
    console.log('Passed: canonical page, desktop/mobile, generation, PNG + JSON persistence/download, reload and JSON import without AI calls, errors and config loading recovery. No live AI calls.');
  } finally {
    if (browser) await browser.close();
    if (backend) {
      const exited = new Promise(resolve => backend.once('exit', resolve));
      backend.kill('SIGTERM');
      await Promise.race([exited, new Promise(resolve => setTimeout(resolve, 3000))]);
      if (backend.exitCode === null) backend.kill('SIGKILL');
    }
    await new Promise(resolve => mock.close(resolve));
    fs.rmSync(directory, {recursive: true, force: true});
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
