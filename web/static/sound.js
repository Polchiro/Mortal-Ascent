/* The open world's sound (docs/web.md "The map screen"), made in the browser with Web Audio: no sound files.
   Each kind of place has its own bed, which crossfades as you walk from one to the next:
     town    a soft wind, a low murmur of the street and wind chimes now and then
     meadow  (the Crossroads) wind over grass, a few crickets and a bird now and then
     forest  (the Moon Forest) wind in the trees, crickets all round, an owl far off
   and a few little sounds: footsteps (stone in town, earth outside), the whoosh of walking into the next land, a
   beast's growl when it notices you, kneeling at a herb, a chime when it is picked (a dull note when not), the
   sparkle of a glint, a bell when a task is done.

   town.js calls window.MASound.place(kind) and the others (step, whoosh, growl, kneel, picked, missed, glint, task).
   The gear's Settings panel has Sound On / Off and a volume, kept on this device (localStorage ma.sound, ma.vol).
   Browsers only allow sound after a click or a key press, so the first one wakes it. It goes quiet while the tab is
   hidden. Only how the page sounds: nothing here touches the game. */
(function () {
  'use strict';
  var on = true, vol = 0.6, ctx = null, master = null, kind = null, beds = {}, wind = null, nextAt = {};
  try {
    on = localStorage.getItem('ma.sound') !== 'off';
    var v0 = parseFloat(localStorage.getItem('ma.vol')); if (v0 >= 0 && v0 <= 100) vol = v0 / 100;
  } catch (e) {}

  function ac(wake) {                       // the context: made only by a click or a key (wake), never before
    if (!on) return null;
    if (!ctx) {
      if (!wake) return null;
      var A = window.AudioContext || window.webkitAudioContext; if (!A) return null;
      ctx = new A(); master = ctx.createGain(); master.gain.value = vol * vol; master.connect(ctx.destination);
      if (kind) setBed(kind);
    }
    if (ctx.state === 'suspended' && !document.hidden) ctx.resume();
    return ctx;
  }
  ['pointerdown', 'keydown', 'touchstart'].forEach(function (n) { document.addEventListener(n, function () { ac(true); }, {capture: true}); });
  document.addEventListener('visibilitychange', function () {
    if (!ctx) return;
    if (document.hidden) ctx.suspend(); else if (on) ctx.resume();
  });

  /* building blocks */
  var noiseBuf = null;
  function noise() {                       // 2 s of soft (pink-ish) noise, looped wherever it is needed
    if (noiseBuf) return noiseBuf;
    var n = ctx.sampleRate * 2, b = ctx.createBuffer(1, n, ctx.sampleRate), d = b.getChannelData(0), last = 0;
    for (var i = 0; i < n; i++) { last = 0.97 * last + 0.03 * (Math.random() * 2 - 1) * 4; d[i] = last; }
    return (noiseBuf = b);
  }
  function out(node, pan) {                // to the master, panned left/right (-1 .. 1)
    if (ctx.createStereoPanner) { var p = ctx.createStereoPanner(); p.pan.value = pan || 0; node.connect(p); p.connect(master); }
    else node.connect(master);
  }
  function tone(f, at, len, v, type, pan, f2) {
    var o = ctx.createOscillator(), g = ctx.createGain();
    o.type = type || 'sine'; o.frequency.setValueAtTime(f, at);
    if (f2) o.frequency.exponentialRampToValueAtTime(f2, at + len);
    g.gain.setValueAtTime(0.0001, at); g.gain.exponentialRampToValueAtTime(v, at + Math.min(0.02, len / 4));
    g.gain.exponentialRampToValueAtTime(0.0001, at + len);
    o.connect(g); out(g, pan); o.start(at); o.stop(at + len + 0.05);
  }
  function burst(at, len, v, type, freq, q, pan, freq2) {
    var s = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain();
    s.buffer = noise(); f.type = type; f.frequency.setValueAtTime(freq, at); if (q) f.Q.value = q;
    if (freq2) f.frequency.exponentialRampToValueAtTime(freq2, at + len);
    g.gain.setValueAtTime(0.0001, at); g.gain.exponentialRampToValueAtTime(v, at + Math.min(0.03, len / 3));
    g.gain.exponentialRampToValueAtTime(0.0001, at + len);
    s.connect(f); f.connect(g); out(g, pan); s.start(at, Math.random()); s.stop(at + len + 0.05);
  }
  function rnd(a, b) { return a + Math.random() * (b - a); }

  /* the beds: wind under everything (louder outside), and each place's own little events */
  var BED = {
    town:   {wind: 0.05, windHz: 380, every: {chime: [7, 16], murmur: [0, 0]}},
    meadow: {wind: 0.09, windHz: 520, every: {cricket: [0.6, 1.8], bird: [6, 15]}},
    forest: {wind: 0.11, windHz: 420, every: {cricket: [0.15, 0.55], owl: [18, 40], creak: [12, 30]}}
  };
  function startWind() {
    if (wind) return;
    var s = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain(), lfo = ctx.createOscillator(), lg = ctx.createGain();
    s.buffer = noise(); s.loop = true; f.type = 'lowpass'; f.frequency.value = 400; f.Q.value = 0.6; g.gain.value = 0;
    lfo.frequency.value = 0.07; lg.gain.value = 160; lfo.connect(lg); lg.connect(f.frequency);
    s.connect(f); f.connect(g); g.connect(master); s.start(); lfo.start();
    var hum = ctx.createBufferSource(), hf = ctx.createBiquadFilter(), hg = ctx.createGain();   // the town's murmur
    hum.buffer = noise(); hum.loop = true; hf.type = 'bandpass'; hf.frequency.value = 260; hf.Q.value = 1.2; hg.gain.value = 0;
    hum.connect(hf); hf.connect(hg); hg.connect(master); hum.start(0, 1);
    wind = {f: f, g: g, hum: hg};
  }
  function setBed(k) {
    kind = k;
    if (!ctx) return;
    startWind();
    var b = BED[k] || BED.forest, t = ctx.currentTime;
    wind.g.gain.cancelScheduledValues(t); wind.g.gain.setTargetAtTime(b.wind, t, 1.2);
    wind.f.frequency.setTargetAtTime(b.windHz, t, 1.2);
    wind.hum.gain.cancelScheduledValues(t); wind.hum.gain.setTargetAtTime(k === 'town' ? 0.035 : 0, t, 1.2);
    nextAt = {};
  }

  var EVENTS = {
    cricket: function (t) {                // a short trill, somewhere to the side
      var f = rnd(4200, 5200), pan = rnd(-0.9, 0.9), v = rnd(0.006, 0.016), n = 2 + Math.floor(Math.random() * 3);
      for (var i = 0; i < n; i++) tone(f, t + i * 0.055, 0.035, v, 'sine', pan);
    },
    bird: function (t) {                   // two or three quick chirps
      var pan = rnd(-0.8, 0.8), base = rnd(2300, 3400);
      for (var i = 0; i < 2 + Math.floor(Math.random() * 2); i++) tone(base, t + i * 0.13, 0.09, 0.02, 'sine', pan, base * rnd(1.3, 1.6));
    },
    owl: function (t) {                    // far off: hoo ... hoo-hoo
      var pan = rnd(-0.7, 0.7);
      tone(390, t, 0.38, 0.03, 'sine', pan, 360); tone(400, t + 0.7, 0.2, 0.025, 'sine', pan, 370); tone(395, t + 0.95, 0.42, 0.028, 'sine', pan, 350);
    },
    creak: function (t) { burst(t, 0.7, 0.018, 'bandpass', 900, 8, rnd(-0.6, 0.6), 600); },   // a branch in the wind
    chime: function (t) {                  // wind chimes: a few notes of a pentatonic scale, ringing out
      var notes = [784, 880, 1047, 1175, 1319, 1568], pan = rnd(-0.5, 0.5);
      for (var i = 0; i < 2 + Math.floor(Math.random() * 3); i++) {
        var f = notes[Math.floor(Math.random() * notes.length)], at = t + i * rnd(0.12, 0.3);
        tone(f, at, 2.2, 0.018, 'sine', pan); tone(f * 2.76, at, 0.9, 0.004, 'sine', pan);
      }
    },
    murmur: function () {}
  };
  setInterval(function () {               // the beds' little events, each at its own random pace
    if (!ctx || !on || ctx.state !== 'running' || !kind) return;
    var b = BED[kind] || BED.forest, t = ctx.currentTime;
    Object.keys(b.every).forEach(function (e) {
      var r = b.every[e]; if (!r[1]) return;
      if (nextAt[e] == null) { nextAt[e] = t + rnd(r[0], r[1]); return; }
      if (t >= nextAt[e]) { EVENTS[e](t + 0.02); nextAt[e] = t + rnd(r[0], r[1]); }
    });
  }, 100);

  /* the little sounds */
  var lastStep = 0;
  var SFX = {
    step: function (surface) {
      var t = ctx.currentTime; if (t - lastStep < 0.12) return; lastStep = t;
      if (surface === 'stone') burst(t, 0.07, 0.05 * rnd(0.7, 1), 'bandpass', rnd(1500, 2100), 1.5, rnd(-0.1, 0.1));
      else burst(t, 0.11, 0.06 * rnd(0.7, 1), 'lowpass', rnd(500, 750), 0.7, rnd(-0.1, 0.1));
    },
    whoosh: function () { burst(ctx.currentTime, 0.75, 0.09, 'bandpass', 300, 1.2, 0, 1600); },
    growl: function (tier) {
      var t = ctx.currentTime, big = tier === 'beast_king' ? 1.6 : tier === 'elite' ? 1.25 : 1, len = 0.6 * big;
      var o = ctx.createOscillator(), f = ctx.createBiquadFilter(), g = ctx.createGain(), lfo = ctx.createOscillator(), lg = ctx.createGain();
      o.type = 'sawtooth'; o.frequency.setValueAtTime(95 / big, t); o.frequency.linearRampToValueAtTime(70 / big, t + len);
      f.type = 'lowpass'; f.frequency.value = 420; lfo.frequency.value = 22; lg.gain.value = 0.05; lfo.connect(lg); lg.connect(g.gain);
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.11, t + 0.06); g.gain.exponentialRampToValueAtTime(0.0001, t + len);
      o.connect(f); f.connect(g); out(g, 0); o.start(t); lfo.start(t); o.stop(t + len + 0.05); lfo.stop(t + len + 0.05);
      burst(t, len, 0.03, 'lowpass', 300, 1, 0);
    },
    kneel: function () { burst(ctx.currentTime, 0.35, 0.05, 'highpass', 2500, 0.7, 0, 5000); },
    picked: function () { var t = ctx.currentTime; tone(880, t, 0.5, 0.06); tone(1319, t + 0.1, 0.8, 0.05); },
    missed: function () { tone(196, ctx.currentTime, 0.5, 0.06, 'triangle', 0, 150); },
    glint: function () { var t = ctx.currentTime; [1568, 2093, 2637].forEach(function (f, i) { tone(f, t + i * 0.07, 0.4, 0.03); }); },
    task: function () {
      var t = ctx.currentTime;
      [523, 659, 784].forEach(function (f, i) { tone(f, t + i * 0.12, 1.6, 0.05); tone(f * 2.01, t + i * 0.12, 0.8, 0.012); });
    }
  };

  window.MASound = {
    place: function (k) { kind = k; if (ac()) setBed(k); }
  };
  Object.keys(SFX).forEach(function (k) {
    window.MASound[k] = function (a) { if (on && ac() && ctx.state === 'running') SFX[k](a); };
  });

  /* Settings: Sound On / Off and the volume */
  document.addEventListener('DOMContentLoaded', function () {
    var btns = document.querySelectorAll('[data-sound]'), slider = document.getElementById('soundVol');
    function mark() {
      Array.prototype.forEach.call(btns, function (b) { var m = (b.dataset.sound === 'on') === on; b.classList.toggle('on', m); b.setAttribute('aria-pressed', m); });
      if (slider) { slider.value = Math.round(vol * 100); slider.disabled = !on; }
    }
    Array.prototype.forEach.call(btns, function (b) {
      b.addEventListener('click', function () {
        on = b.dataset.sound === 'on';
        try { localStorage.setItem('ma.sound', on ? 'on' : 'off'); } catch (e) {}
        if (on) { if (ac(true) && kind) setBed(kind); } else if (ctx) ctx.suspend();
        mark();
      });
    });
    if (slider) slider.addEventListener('input', function () {
      vol = slider.value / 100;
      try { localStorage.setItem('ma.vol', slider.value); } catch (e) {}
      if (master) master.gain.setTargetAtTime(vol * vol, ctx.currentTime, 0.05);
    });
    mark();
  });
})();
