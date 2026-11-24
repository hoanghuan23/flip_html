(() => {
  'use strict';
  const timing = window.phaseAudioTiming;
  if (!timing || !timing.cue || !Number.isFinite(timing.duration)) throw new Error('Thiếu audio-timing.js của Phase 1.');
  const D = timing.duration;
  const el = (id) => document.getElementById(id);
  const scenes = ['intro', 'alarm', 'power', 'fight', 'phone', 'recap'].map((id) => el(`scene-${id}`));
  const voice = el('voice');
  const slider = el('timeline');
  const button = el('play');
  const output = el('time');
  const status = el('audioStatus');
  const embedded = window.parent !== window;
  document.body.classList.toggle('embedded', embedded);
  const start = {
    alarm: 2.3,
    power: timing.cue.power,
    fight: timing.cue.fight,
    phone: timing.cue.escape,
    recap: Math.max(timing.audioDuration - .2, timing.cue.escape + 1.6),
  };
  const cuts = [0, start.alarm, start.power, start.fight, start.phone, start.recap, D];
  slider.max = String(D);
  let playhead = 0;
  let playing = embedded;
  let lastFrame = performance.now();
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const smooth = (v) => { const x = clamp(v, 0, 1); return x*x*(3-2*x); };
  const fade = (t, left, right, first, last) => {
    const enter = first ? 1 : smooth((t-left+.24)/.48);
    const leave = last ? 1 : smooth((right-t+.24)/.48);
    return Math.min(enter, leave);
  };
  const setOpacity = (node, value) => { node.style.opacity = String(clamp(value, 0, 1)); };
  const fmt = (seconds) => `${Math.floor(seconds/60)}:${String(Math.floor(seconds%60)).padStart(2, '0')}`;

  function draw(t) {
    scenes.forEach((scene, i) => setOpacity(scene, fade(t, cuts[i], cuts[i+1], i === 0, i === scenes.length-1)));
    const intro = clamp(t / start.alarm, 0, 1);
    el('introCamera').setAttribute('transform', `translate(${-14*intro} ${-9*intro}) scale(${(1+.016*intro).toFixed(4)})`);
    el('introSmoke').setAttribute('transform', `translate(0 ${(-9*Math.sin(t*3)).toFixed(2)})`);
    setOpacity(el('introSmoke'), .28 + .20 * Math.sin(t*4)**2);

    const bellAngle = t >= start.alarm && t < start.power ? Math.sin(t*17) * 2.5 : 0;
    el('bellSwing').setAttribute('transform', `rotate(${bellAngle.toFixed(2)} 1380 637)`);
    setOpacity(el('bellWaves'), t >= start.alarm && t < start.power ? .68 + .32*Math.sin(t*7)**2 : 0);

    const powerProgress = smooth((t-start.power)/2.2);
    const switchedOff = smooth((powerProgress-.43)/.16);
    setOpacity(el('powerOn'), 1-switchedOff);
    setOpacity(el('powerOff'), switchedOff);
    setOpacity(el('powerArrow'), .48+.52*powerProgress);
    const fightProgress = clamp((t-start.fight)/(start.phone-start.fight), 0, 1);
    el('fightCamera').setAttribute('transform', `translate(${(-16*fightProgress).toFixed(2)} ${(-8*fightProgress).toFixed(2)}) scale(${(1+.018*fightProgress).toFixed(4)})`);
    setOpacity(el('exitArrow'), t >= start.fight ? .55 + .42*Math.sin(t*4)**2 : .3);

    const phoneProgress = smooth((t-start.phone)/1.7);
    const phoneScale = 1 + .07*phoneProgress;
    el('phoneZoom').setAttribute('transform', `translate(${(1250*(1-phoneScale)).toFixed(2)} ${(590*(1-phoneScale)).toFixed(2)}) scale(${phoneScale.toFixed(4)})`);
    setOpacity(el('callWaves'), .35 + .65*Math.sin(t*6)**2);
    const recapElapsed = t-start.recap;
    ['card1','card2','card3','card4'].forEach((id, i) => {
      const reveal = smooth((recapElapsed-i*.38)/.52);
      const card = el(id);
      setOpacity(card, reveal);
      card.setAttribute('transform', `translate(0 ${(28*(1-reveal)).toFixed(2)})`);
    });
    const callShown = t >= timing.cue.call && t < start.phone;
    setOpacity(el('early114'), callShown ? .88 + .12*Math.sin(t*5)**2 : 0);
    slider.value = String(t);
    output.textContent = `${fmt(t)} / ${fmt(D)}`;
  }

  function pause() {
    playing = false;
    voice.pause();
    button.textContent = 'Phát';
  }
  function seek(t) {
    playhead = clamp(Number(t) || 0, 0, D);
    if (voice.readyState >= 1) voice.currentTime = Math.min(playhead, timing.audioDuration);
    draw(playhead);
  }
  window.phaseSeek = (t) => { pause(); seek(t); };
  window.phaseDuration = D;
  window.phaseVoiceover = timing.voiceover;
  window.previewReady = Promise.all([
    document.fonts.ready,
    ...[...document.querySelectorAll('svg image')].map((node) => new Promise((resolve, reject) => {
      const asset = new Image();
      asset.onload = resolve;
      asset.onerror = () => reject(new Error(`Không tải được ${node.getAttribute('href')}`));
      asset.src = node.getAttribute('href');
    })),
  ]).then(() => true);
  button.addEventListener('click', async () => {
    if (playing) { pause(); return; }
    if (playhead >= D) seek(0);
    if (playhead < timing.audioDuration) {
      try { await voice.play(); }
      catch { status.textContent = 'Không phát được thuyết minh. Kiểm tra file MP3.'; status.style.display = 'block'; return; }
    }
    playing = true;
    button.textContent = 'Tạm dừng';
  });
  slider.addEventListener('input', () => {
    seek(slider.value);
    if (playing && playhead < timing.audioDuration && voice.paused && !embedded) void voice.play().catch(pause);
  });
  voice.addEventListener('error', () => {
    status.textContent = 'Không tải được MP3 thuyết minh.';
    status.style.display = 'block';
    if (!embedded) pause();
  });
  voice.addEventListener('loadedmetadata', () => {
    if (Math.abs(voice.duration-timing.audioDuration) > .15) {
      status.textContent = 'Thời lượng MP3 khác dữ liệu đồng bộ; cần tạo lại audio-timing.js.';
      status.style.display = 'block';
    }
  });
  addEventListener('message', (event) => {
    if (event.source === parent && Number.isFinite(event.data?.t)) window.renderAt(event.data.t);
  });
  function tick(now) {
    const delta = Math.max(0, (now-lastFrame)/1000);
    lastFrame = now;
    if (playing) {
      if (!embedded && playhead < timing.audioDuration && !voice.paused && !voice.ended) playhead = voice.currentTime;
      else playhead = Math.min(D, playhead+delta);
      draw(playhead);
      if (playhead >= D) pause();
    }
    requestAnimationFrame(tick);
  }
  draw(0);
  requestAnimationFrame(tick);
})();
