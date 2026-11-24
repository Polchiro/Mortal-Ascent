/* The spar's music (docs/technique.md "On the website"), made in the browser with Web Audio like the map's tune
   (sound.js): no recording. A duel's mood: a slow drum, a low string under it, and a plucked five-note tune made up
   as it goes, with a bamboo flute now and then. A mastery trial is the same a little faster, lower and heavier.

   spar.js calls window.SparMusic.start('spar' | 'trial') (practice.js: 'practice') and .stop(), and .ambience(url) for the place's own sound
   (the yard video's wind and chimes, art/spar/yard.wav), which loops under the tune and follows Sound, not Music. It shares the map's settings (the gear there:
   Sound On / Off, the volume, Music On / Off; localStorage ma.sound, ma.vol, ma.music), so someone who turned music
   off hears none here. Browsers allow sound only after a click or a key press, so the first one wakes it. It goes
   quiet while the tab is hidden. Only how the page sounds: nothing here touches the game. */
(function () {
  'use strict';
  var on = true, tune = true, vol = 0.6, ctx = null, bus = null, kind = null, timer = null, nextAt = 0, step = 0, note = 2, rest = 0, nbuf = null;
  var airUrl = null, airBuf = null, airSrc = null, airBus = null;
  try {
    on = localStorage.getItem('ma.sound') !== 'off'; tune = localStorage.getItem('ma.music') !== 'off';
    var v0 = parseFloat(localStorage.getItem('ma.vol')); if (v0 >= 0 && v0 <= 100) vol = v0 / 100;
  } catch (e) {}
  var MOODS = {
    spar:  {root: 146.83, scale: [0, 3, 5, 7, 10], beat: 0.36, drum: [1, 0, 0, 0.5, 1, 0, 0.6, 0], v: 1},
    trial: {root: 130.81, scale: [0, 3, 5, 7, 10], beat: 0.31, drum: [1, 0, 0.5, 0.5, 1, 0, 0.7, 0.4], v: 1.1},
    /* Practice (practice.js): a bright, steady drill hall. A major five-note tune, a soft drum keeping time like a
       teacher's count, and the flute more often */
    practice: {root: 196.0, scale: [0, 2, 4, 7, 9], beat: 0.4, drum: [0.8, 0, 0, 0, 0.5, 0, 0, 0], v: 0.8, flute: 0.9}
  };
  function ac() {
    if (!on) return null;
    if (!ctx) {
      var AC = window.AudioContext || window.webkitAudioContext; if (!AC) return null;
      ctx = new AC();
      bus = ctx.createGain(); bus.gain.value = 0; bus.connect(ctx.destination);
      nbuf = ctx.createBuffer(1, ctx.sampleRate * 0.5, ctx.sampleRate);
      var d = nbuf.getChannelData(0); for (var i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    }
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  }
  function hz(m, deg) {                                  // a step of the scale, any octave
    var n = m.scale.length, o = Math.floor(deg / n), i = ((deg % n) + n) % n;
    return m.root * Math.pow(2, o + m.scale[i] / 12);
  }
  function env(g, t, peak, attack, decay) {
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(peak, t + attack);
    g.gain.exponentialRampToValueAtTime(0.0001, t + attack + decay);
  }
  function pluck(f, t, v, pan) {                         // a plucked string: bright at the pick, then dull and ringing
    var o = ctx.createOscillator(), o2 = ctx.createOscillator(), lp = ctx.createBiquadFilter(), g = ctx.createGain();
    o.type = 'sawtooth'; o.frequency.value = f; o2.type = 'triangle'; o2.frequency.value = f * 2.003;
    lp.type = 'lowpass'; lp.frequency.setValueAtTime(f * 7, t); lp.frequency.exponentialRampToValueAtTime(f * 1.4, t + 0.5);
    env(g, t, v, 0.006, 1.5);
    o.connect(lp); o2.connect(lp); lp.connect(g); out(g, pan);
    o.start(t); o2.start(t); o.stop(t + 1.7); o2.stop(t + 1.7);
  }
  function flute(f, t, len, v) {
    var o = ctx.createOscillator(), g = ctx.createGain(), vib = ctx.createOscillator(), vg = ctx.createGain();
    o.type = 'sine'; o.frequency.value = f; vib.frequency.value = 5; vg.gain.value = f * 0.006; vib.connect(vg); vg.connect(o.frequency);
    g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(v, t + 0.18); g.gain.setValueAtTime(v, t + len - 0.3);
    g.gain.linearRampToValueAtTime(0.0001, t + len);
    o.connect(g); out(g, -0.2); o.start(t); vib.start(t); o.stop(t + len + 0.05); vib.stop(t + len + 0.05);
  }
  function drum(t, v) {                                  // a big skin drum: a falling thump and the slap of the stick
    var o = ctx.createOscillator(), g = ctx.createGain();
    o.type = 'sine'; o.frequency.setValueAtTime(120, t); o.frequency.exponentialRampToValueAtTime(46, t + 0.22);
    env(g, t, v, 0.004, 0.5); o.connect(g); out(g, 0); o.start(t); o.stop(t + 0.6);
    var n = ctx.createBufferSource(), bp = ctx.createBiquadFilter(), ng = ctx.createGain();
    n.buffer = nbuf; bp.type = 'bandpass'; bp.frequency.value = 900; bp.Q.value = 0.7;
    env(ng, t, v * 0.35, 0.002, 0.07); n.connect(bp); bp.connect(ng); out(ng, 0); n.start(t); n.stop(t + 0.1);
  }
  function out(node, pan) {
    if (pan && ctx.createStereoPanner) { var p = ctx.createStereoPanner(); p.pan.value = pan; node.connect(p); p.connect(bus); }
    else node.connect(bus);
  }
  function tick() {
    if (!ctx || !kind || ctx.state !== 'running') return;
    var m = MOODS[kind];
    while (nextAt < ctx.currentTime + 0.25) {
      var t = Math.max(nextAt, ctx.currentTime + 0.02), i = step % 8, bar = Math.floor(step / 8);
      if (m.drum[i] && (i === 0 || Math.random() < 0.85)) drum(t, 0.20 * m.drum[i] * m.v);
      if (i === 0 && bar % 2 === 0) pluck(hz(m, -5), t, 0.09, 0);            // the low string marks the phrase
      if (rest > 0) rest--;
      else if (Math.random() < (i % 2 ? 0.42 : 0.7)) {
        note = Math.max(-1, Math.min(8, note + [-2, -1, -1, 1, 1, 2][Math.floor(Math.random() * 6)]));
        pluck(hz(m, note), t, 0.075, 0.25);
        if (Math.random() < 0.12) rest = 4 + Math.floor(Math.random() * 6);  // a breath between phrases
      }
      if (i === 0 && bar % (m.flute ? 2 : 4) === (m.flute ? 1 : 2) && Math.random() < (m.flute || 0.7)) flute(hz(m, 5 + Math.floor(Math.random() * 3)), t, m.beat * 6, 0.035);
      nextAt = t + m.beat; step++;
    }
  }
  function air() {                                       // the place's own sound, looping under everything
    if (!airUrl || airSrc || !ac()) return;
    if (!airBus) { airBus = ctx.createGain(); airBus.gain.value = 0; airBus.connect(ctx.destination); }
    var play = function () {
      if (airSrc || !airBuf) return;
      airSrc = ctx.createBufferSource(); airSrc.buffer = airBuf; airSrc.loop = true; airSrc.connect(airBus); airSrc.start();
      airBus.gain.setTargetAtTime(Math.min(1, vol * 1.5), ctx.currentTime, 1.2);
    };
    if (airBuf) { play(); return; }
    var url = airUrl; airUrl = null;                     // one fetch
    fetch(url).then(function (r) { return r.arrayBuffer(); })
      .then(function (b) { return new Promise(function (ok, no) { ctx.decodeAudioData(b, ok, no); }); })
      .then(function (buf) { airBuf = buf; airUrl = url; play(); }).catch(function () {});
  }
  function begin() {
    air();
    if (!kind || !tune || !ac()) return;
    bus.gain.cancelScheduledValues(ctx.currentTime);
    bus.gain.setTargetAtTime(vol * 0.7, ctx.currentTime, 0.8);
    if (!timer) { nextAt = ctx.currentTime + 0.3; timer = setInterval(tick, 80); }
  }
  window.SparMusic = {
    start: function (k) { kind = MOODS[k] ? k : 'spar'; begin(); },
    ambience: function (url) { if (on) { airUrl = url; begin(); } },
    stop: function () {
      kind = null;
      if (timer) { clearInterval(timer); timer = null; }
      if (ctx && bus) bus.gain.setTargetAtTime(0, ctx.currentTime, 0.6);
    },
    playing: function () { return !!(timer && ctx && ctx.state === 'running'); }
  };
  ['pointerdown', 'keydown'].forEach(function (ev) { document.addEventListener(ev, begin, {passive: true}); });
  document.addEventListener('visibilitychange', function () {
    if (!ctx) return;
    if (document.hidden) ctx.suspend(); else if (kind || airSrc) ctx.resume();
  });
})();
