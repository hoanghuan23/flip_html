// Browser verification of a saved narrated project, without additional AI/TTS calls.
const puppeteer = require("puppeteer-core");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const root = path.resolve(__dirname,"../..");
const project = JSON.parse(fs.readFileSync(process.env.NARRATED_PROJECT || path.join(root,"storage/qa/narrated-project.json"),"utf8"));
const url = process.env.STUDIO_URL || "http://127.0.0.1:8134";
const delay = ms => new Promise(resolve=>setTimeout(resolve,ms));

(async()=>{
  const browser=await puppeteer.launch({executablePath:process.env.CHROME_PATH||"/usr/bin/google-chrome",headless:true,
    args:["--no-sandbox","--enable-unsafe-swiftshader"]});
  const page=await browser.newPage(),errors=[],checks=[];
  page.on("pageerror",error=>errors.push(error.message));
  await page.setViewport({width:1440,height:1050});
  try {
    await page.goto(url,{waitUntil:"networkidle0"});
    await page.evaluate(project=>localStorage.setItem("ai-video-studio:v1",JSON.stringify({version:1,projects:[project],activeId:project.id})),project);
    await page.reload({waitUntil:"networkidle0"});
    const play='button[aria-label="Phát preview"]';
    await page.waitForFunction(selector=>document.querySelector(selector)&&!document.querySelector(selector).disabled,{},play);
    await page.click(play);await delay(900);
    const progress=await page.$eval("#xem-truoc audio",a=>a.currentTime);
    assert(progress>.3,"Audio did not start");
    let frame=page.frames().find(f=>f.url().includes("/api/previews/"));
    const visualTime=await frame.evaluate(()=>window.currentTime);
    assert(Math.abs(visualTime-progress)<.2,"Audio and animation drifted");checks.push("audio drives animation");
    await page.click('button[aria-label="Tạm dừng preview"]');
    const frozen=await page.$eval("#xem-truoc audio",a=>a.currentTime);await delay(300);
    assert(Math.abs(await page.$eval("#xem-truoc audio",a=>a.currentTime)-frozen)<.08);checks.push("pause freezes audio");
    if(project.snapshot.phases.length>1) {
      await page.$eval('#xem-truoc button[aria-pressed="false"]',button=>button.click());
      await page.waitForFunction(selector=>document.querySelector(selector)&&!document.querySelector(selector).disabled,{},play);
      assert(await page.$eval('#xem-truoc audio',a=>a.paused&&a.currentTime===0));
      frame=page.frames().find(f=>f.url().includes('/api/previews/'));
      checks.push('phase switch pauses previous speech and resets time');
    }
    const duration=project.snapshot.phases[0].duration,seekTime=duration*.65;
    await page.$eval('input[aria-label="Tua preview"]',(input,time)=>{
      const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set;setter.call(input,String(time));
      input.dispatchEvent(new Event("input",{bubbles:true}));input.dispatchEvent(new Event("change",{bubbles:true}));
    },seekTime);
    await delay(300);
    assert(Math.abs(await page.$eval("#xem-truoc audio",a=>a.currentTime)-seekTime)<.1);checks.push("seek moves speech and scene together");
    const hashes=await frame.evaluate(duration=>{
      const canvas=document.querySelector("canvas");window.renderAt(duration*.2);const first=canvas.toDataURL();
      window.renderAt(duration*.8);const later=canvas.toDataURL();window.renderAt(duration*.2);return{same:first===canvas.toDataURL(),changes:first!==later};
    },duration);
    assert(hashes.same&&hashes.changes);checks.push("backward seeking is deterministic");
    await frame.evaluate(t=>window.renderAt(t),seekTime);
    if(!process.env.NARRATED_PROJECT) {
      const image=await frame.evaluate(()=>{const card=document.querySelector('.reference-card');return{visible:getComputedStyle(card).display!=='none',loaded:card.querySelector('img').naturalWidth>0,text:card.textContent}});
      assert(image.visible&&image.loaded&&image.text.includes('Hình 7'));checks.push('numbered reference photo loads in sandbox');
    }
    await page.$eval("#xem-truoc",el=>el.scrollIntoView());
    fs.mkdirSync(path.join(root,"storage/qa"),{recursive:true});
    await page.screenshot({path:path.join(root,"storage/qa/starlink-player.png")});
    await page.reload({waitUntil:"networkidle0"});
    await page.waitForSelector("#xem-truoc audio");
    assert(await page.$eval("#xem-truoc audio",a=>a.paused));checks.push("reload restores snapshot without autoplay");
    assert.equal(errors.length,0,errors.join("\n"));
    console.log(JSON.stringify({ok:true,checks,errors},null,2));
  } finally {await browser.close()}
})().catch(error=>{console.error(error);process.exit(1)});
