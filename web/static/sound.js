/* The open world's sound (docs/web.md "The map screen"), made in the browser with Web Audio: no sound files but
   the footsteps.
   Each kind of place has its own bed, which crossfades as you walk from one to the next:
     town    a soft wind, a low murmur of the street and wind chimes now and then
     meadow  (the Crossroads) wind over grass, a few crickets and a bird now and then
     forest  (the Moon Forest) wind in the trees, crickets all round, an owl far off
   Over the bed a quiet tune plays, made up as it goes (plucked strings and a bamboo flute; MUSIC below), in each
   place's own mood; Settings has Music On / Off (ma.music). Talking to someone unrolls a scroll and plays a few
   notes of their "voice" (VOICES), a choice clicks, leaving rustles.
   and a few little sounds: footsteps (recorded from SHOAIB's videos, see `recordedStep`; stone in town, earth outside), the whoosh of walking into the next land, a
   beast's growl when it notices you, kneeling at a herb, a chime when it is picked (a dull note when not), the
   sparkle of a glint, a bell when a task is done.

   town.js calls window.MASound.place(kind) and the others (step, whoosh, growl, kneel, picked, missed, glint, task).
   The gear's Settings panel has Sound On / Off and a volume, kept on this device (localStorage ma.sound, ma.vol).
   Browsers only allow sound after a click or a key press, so the first one wakes it. It goes quiet while the tab is
   hidden. Only how the page sounds: nothing here touches the game. */
(function () {
  'use strict';
  var on = true, vol = 0.6, ctx = null, master = null, kind = null, beds = {}, wind = null, nextAt = {};
  var music = true, musicBus = null;
  try {
    on = localStorage.getItem('ma.sound') !== 'off';
    music = localStorage.getItem('ma.music') !== 'off';
    var v0 = parseFloat(localStorage.getItem('ma.vol')); if (v0 >= 0 && v0 <= 100) vol = v0 / 100;
  } catch (e) {}

  function ac(wake) {                       // the context: made only by a click or a key (wake), never before
    if (!on) return null;
    if (!ctx) {
      if (!wake) return null;
      var A = window.AudioContext || window.webkitAudioContext; if (!A) return null;
      ctx = new A(); master = ctx.createGain(); master.gain.value = vol * vol; master.connect(ctx.destination);
      musicBus = ctx.createGain(); musicBus.gain.value = music ? 1 : 0; musicBus.connect(master);
      if (kind) setBed(kind);
      loadSteps();                          // the recorded footsteps, decoded now it is awake
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
    forest: {wind: 0.11, windHz: 420, every: {cricket: [0.15, 0.55], owl: [18, 40], creak: [12, 30]}},
    quarry: {wind: 0.1, windHz: 300, every: {pebble: [5, 13], hammer: [9, 22], bird: [14, 30]}}       // wind over stone, loose stones falling, a far-off hammer
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
    if (tune.kind !== k) { tune.kind = k; tune.at = t + 2.5; tune.left = 0; tune.i = 2; }   // the next place's music, after a breath
  }

  /* the music (docs/world.md "Sound"): no recording, a quiet tune made up as it goes, in the manner of a guzheng
     (plucked strings on a five-note scale) with a bamboo flute now and then. Each kind of place has its own scale,
     pace and mood: the town warm and unhurried, the Crossroads open and light, the forest slow, low and sparse.
     It plays a phrase, rests, plays another; a low string marks each phrase's start. */
  var MUSIC = {
    town:   {root: 293.66, scale: [0, 2, 4, 7, 9],  beat: 0.46, len: [6, 10], rest: [3, 6],  v: 0.050, flute: 0.25, low: 0.5},
    meadow: {root: 329.63, scale: [0, 2, 4, 7, 9],  beat: 0.52, len: [5, 8],  rest: [4, 8],  v: 0.045, flute: 0.4,  low: 0.5},
    forest: {root: 220.00, scale: [0, 3, 5, 7, 10], beat: 0.72, len: [3, 6],  rest: [6, 12], v: 0.042, flute: 0.55, low: 0.5},
    quarry: {root: 196.00, scale: [0, 2, 5, 7, 9],  beat: 0.66, len: [3, 5],  rest: [7, 13], v: 0.04,  flute: 0.3,  low: 0.7}
  };
  var tune = {kind: null, at: 0, left: 0, i: 2};
  function mout(node, pan) {
    if (ctx.createStereoPanner) { var p = ctx.createStereoPanner(); p.pan.value = pan || 0; node.connect(p); p.connect(musicBus); }
    else node.connect(musicBus);
  }
  function hz(m, step) {                    // a step of the place's scale (may run over several octaves) as a pitch
    var n = m.scale.length, oct = Math.floor(step / n), deg = ((step % n) + n) % n;
    return m.root * Math.pow(2, oct + m.scale[deg] / 12);
  }
  function pluck(f, at, v, pan) {           // a plucked string: a quick bend up into the note, then it rings away
    var len = 2.6, g = ctx.createGain(), lp = ctx.createBiquadFilter();
    lp.type = 'lowpass'; lp.frequency.setValueAtTime(Math.min(6000, f * 6), at); lp.frequency.exponentialRampToValueAtTime(f * 1.5, at + 1.2);
    g.gain.setValueAtTime(0.0001, at); g.gain.exponentialRampToValueAtTime(v, at + 0.006); g.gain.exponentialRampToValueAtTime(0.0001, at + len);
    [[1, 'triangle', 1], [2, 'sine', 0.35], [3, 'sine', 0.12]].forEach(function (h) {
      var o = ctx.createOscillator(), og = ctx.createGain();
      o.type = h[1]; o.frequency.setValueAtTime(f * h[0] * 0.985, at); o.frequency.exponentialRampToValueAtTime(f * h[0], at + 0.05);
      og.gain.value = h[2]; o.connect(og); og.connect(lp); o.start(at); o.stop(at + len + 0.05);
    });
    lp.connect(g); mout(g, pan);
  }
  function flute(f, at, len, v) {           // a bamboo flute: a soft breathy note that swells, wavers and fades
    var o = ctx.createOscillator(), g = ctx.createGain(), vib = ctx.createOscillator(), vg = ctx.createGain();
    o.type = 'sine'; o.frequency.value = f; vib.frequency.value = 5; vg.gain.setValueAtTime(0, at); vg.gain.linearRampToValueAtTime(f * 0.008, at + len * 0.6);
    vib.connect(vg); vg.connect(o.frequency);
    g.gain.setValueAtTime(0.0001, at); g.gain.exponentialRampToValueAtTime(v, at + len * 0.3); g.gain.exponentialRampToValueAtTime(0.0001, at + len);
    o.connect(g); mout(g, 0.15); o.start(at); vib.start(at); o.stop(at + len + 0.05); vib.stop(at + len + 0.05);
    var s = ctx.createBufferSource(), bf = ctx.createBiquadFilter(), bg = ctx.createGain();           // its breath
    s.buffer = noise(); bf.type = 'bandpass'; bf.frequency.value = f * 2; bf.Q.value = 3;
    bg.gain.setValueAtTime(0.0001, at); bg.gain.exponentialRampToValueAtTime(v * 0.25, at + len * 0.3); bg.gain.exponentialRampToValueAtTime(0.0001, at + len);
    s.connect(bf); bf.connect(bg); mout(bg, 0.15); s.start(at, Math.random()); s.stop(at + len + 0.05);
  }
  setInterval(function () {                 // write the tune a little ahead of where it is playing
    if (!ctx || !on || !music || ctx.state !== 'running' || !tune.kind) return;
    var m = MUSIC[tune.kind] || MUSIC.forest, now = ctx.currentTime;
    if (tune.at < now) tune.at = now + 0.1;
    while (tune.at < now + 0.6) {
      if (tune.left <= 0) {                 // a new phrase: a low string, and now and then a flute over it
        tune.left = Math.round(rnd(m.len[0], m.len[1]));
        tune.i = Math.max(0, Math.min(7, tune.i + Math.round(rnd(-2, 2))));
        pluck(hz(m, 0) * m.low, tune.at, m.v * 0.9, -0.2);
        if (Math.random() < m.flute) flute(hz(m, 5 + Math.floor(Math.random() * 4)), tune.at + m.beat, m.beat * rnd(4, 7), m.v * 0.5);
      }
      var r = Math.random(), step = r < 0.42 ? 1 : r < 0.84 ? -1 : r < 0.92 ? 2 : -2;       // mostly to the next note
      tune.i += step; if (tune.i > 9) tune.i -= 3; if (tune.i < 0) tune.i += 3;
      pluck(hz(m, tune.i), tune.at, m.v * rnd(0.7, 1), rnd(-0.3, 0.3));
      if (Math.random() < 0.12) pluck(hz(m, tune.i + 2), tune.at + 0.03, m.v * 0.5, 0.2);    // two strings together
      var d = Math.random() < 0.25 ? 2 : Math.random() < 0.3 ? 0.5 : 1;                     // long, short or even
      tune.at += m.beat * d; tune.left--;
      if (tune.left <= 0) tune.at += m.beat * rnd(m.rest[0], m.rest[1]);                    // and a rest
    }
  }, 100);

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
    pebble: function (t) { for (var i = 0; i < 3; i++) burst(t + i * rnd(0.08, 0.2), 0.05, 0.03, 'bandpass', rnd(1800, 3200), 6, rnd(-0.7, 0.7)); },   // loose stones
    hammer: function (t) { var p = rnd(-0.6, 0.6); for (var i = 0; i < 3; i++) { tone(1650, t + i * 0.55, 0.25, 0.012, 'sine', p); burst(t + i * 0.55, 0.03, 0.02, 'highpass', 3500, 0.7, p); } },
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

  /* the townsfolk's voices (web/town.py NPCS, by key): f the pitch, notes the little tune of their greeting
     (semitones), pace how fast they speak, end whether it falls (< 1) or rises (> 1), extra a sound of their trade */
  var VOICE = 0.16;                         // how loud a voice is (the footsteps are about 0.06)
  var VOICES = {
    gate:       {f: 233, notes: [0, 0, 3], pace: 0.15, wave: 'triangle', end: 0.94},                 // the warden: short, firm
    blacksmith: {f: 175, notes: [0, 2, 0], pace: 0.17, wave: 'triangle', end: 0.92,                  // deep, with the anvil
                 extra: function (t) { tone(2100, t, 0.6, 0.12, 'sine'); tone(3150, t, 0.35, 0.05, 'sine'); burst(t, 0.04, 0.15, 'highpass', 4000, 0.7, 0); }},
    alchemist:  {f: 440, notes: [0, 4, 7, 4], pace: 0.13, wave: 'sine', end: 1.05,                   // Lan: light and quick
                 extra: function (t) { burst(t, 0.35, 0.07, 'highpass', 5000, 0.7, 0.2); }},         // dried herbs rustle
    merchant:   {f: 330, notes: [0, 5, 3, 7], pace: 0.12, wave: 'triangle', end: 1.08,               // lively, with coins
                 extra: function (t) { [3100, 3700, 4200].forEach(function (f, i) { tone(f, t + i * 0.05, 0.2, 0.06, 'sine'); }); }},
    elder:      {f: 196, notes: [0, -2, 0], pace: 0.28, wave: 'triangle', end: 0.95},                // slow and low
    keeper:     {f: 294, notes: [0, 4, 0], pace: 0.3, wave: 'sine', end: 1,                          // the Quiet Pavilion: calm, a small bell
                 extra: function (t) { tone(1175, t, 1.6, 0.07, 'sine'); tone(1762, t, 1.1, 0.03, 'sine'); }},
    master:     {f: 220, notes: [0, 5], pace: 0.18, wave: 'triangle', end: 0.9},                     // two words, no more
    sister:     {f: 392, notes: [0, 3, 0, 5], pace: 0.11, wave: 'triangle', end: 1.02},              // Senior Sister Xue: brisk, clipped
    arena:      {f: 262, notes: [0, 3, 5], pace: 0.14, wave: 'triangle', end: 1.04,                  // with a far gong
                 extra: function (t) { tone(196, t, 1.8, 0.12, 'triangle', 0, 190); tone(392, t, 1.2, 0.06, 'sine'); tone(588, t, 0.8, 0.03, 'sine'); }},
    pavilion:   {f: 349, notes: [0, 4, 7, 5], pace: 0.16, wave: 'sine', end: 1.03,                  // Keeper Yue: soft, a moon chime
                 extra: function (t) { tone(2637, t, 1.2, 0.05, 'sine'); tone(3520, t + 0.08, 0.9, 0.03, 'sine'); }},
    stele:      {extra: function (t) { burst(t, 0.6, 0.18, 'lowpass', 700, 0.8, 0, 350); tone(196, t, 0.9, 0.08, 'triangle', 0, 170); }},   // stone
    exit:       {extra: function (t) { burst(t, 0.7, 0.14, 'bandpass', 500, 1, 0, 900); }},          // a road's end: wind
    other:      {f: 262, notes: [0, 2], pace: 0.16, wave: 'triangle', end: 1}
  };

  /* the little sounds */
  /* Recorded footsteps (art/fx/sounds/step_*.mp3, cut from SHOAIB's walking and running videos by
     scripts/make_step_sound.py; steps.json lists them by gait). A footfall plays one of its gait's takes, never the
     same twice running, a little different in pitch and loudness each time; softer and duller on earth than on the
     town's stone. A gait with no takes of its own borrows the other's (a walk: the run's, quieter and lower), and
     with none at all the step made in code is kept. A cultivator's own takes ("walk#male", Nov 25: the new male's, from
     his videos) come first when the map says whose feet these are (MASound.voice, set from looks WALK_SHEETS `voice`). */
  var STEP_BASE = '/art/fx/sounds/', stepTakes = {}, stepBufs = {}, lastTake = '';
  var STEP_LEVEL = {run: 0.5, walk: 0.34};
  function loadSteps() {                    // decoding needs the context: called once it is awake
    Object.keys(stepTakes).forEach(function (g) {
      stepTakes[g].forEach(function (file) {
        if (stepBufs[file] !== undefined) return;
        stepBufs[file] = null;
        fetch(STEP_BASE + file).then(function (r) { return r.arrayBuffer(); })
          .then(function (b) { return new Promise(function (ok, no) { ctx.decodeAudioData(b, ok, no); }); })
          .then(function (buf) { stepBufs[file] = buf; }).catch(function () {});
      });
    });
  }
  fetch(STEP_BASE + 'steps.json', {cache: 'no-cache'}).then(function (r) { return r.ok ? r.json() : {}; })
    .then(function (j) { stepTakes = j || {}; if (ctx) loadSteps(); }).catch(function () {});
  function recordedStep(surface, gait, t) {
    if (ctx && !Object.keys(stepBufs).length) loadSteps();
    var mine = window.MASound.voice ? gait + '#' + window.MASound.voice : '';
    var own = mine && stepTakes[mine] && stepTakes[mine].length ? mine
      : stepTakes[gait] && stepTakes[gait].length ? gait : gait === 'walk' ? 'run' : 'walk';
    var ready = (stepTakes[own] || []).filter(function (f) { return stepBufs[f]; });
    if (!ready.length) return false;
    var pick = ready.filter(function (f) { return f !== lastTake; });
    var file = (pick.length ? pick : ready)[Math.floor(Math.random() * (pick.length || ready.length))];
    lastTake = file;
    var src = ctx.createBufferSource(), g = ctx.createGain(), borrowed = own.split('#')[0] !== gait;
    src.buffer = stepBufs[file];
    src.playbackRate.value = rnd(0.94, 1.06) * (borrowed && gait === 'walk' ? 0.9 : 1);
    g.gain.value = STEP_LEVEL[gait] * rnd(0.8, 1) * (surface === 'stone' ? 1 : 0.85);
    var last = src;
    if (surface !== 'stone') {              // earth: the click of the sole taken off
      var f = ctx.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = 2600; f.Q.value = 0.5;
      src.connect(f); last = f;
    }
    last.connect(g); out(g, rnd(-0.08, 0.08)); src.start(t);
    return true;
  }

  var lastStep = 0;
  var SFX = {
    step: function (surface, gait) {
      var t = ctx.currentTime; if (t - lastStep < 0.12) return; lastStep = t;
      if (recordedStep(surface, gait === 'run' ? 'run' : 'walk', t)) return;
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
    /* talking: the dialogue unrolls like a scroll, then a few notes of that person's "voice" (no words): each of
       the town's people has their own pitch and manner, and some a sound of their trade */
    talk: function (who) {
      var t = ctx.currentTime, v = VOICES[who] || VOICES.other;
      burst(t, 0.28, 0.16, 'bandpass', 1800, 0.8, 0, 3200);                                 // the scroll
      if (v.extra) v.extra(t + 0.05);
      if (v.f) v.notes.forEach(function (n, i) {
        var at = t + 0.2 + i * v.pace, f = v.f * Math.pow(2, n / 12), end = i === v.notes.length - 1 ? v.end : 1.03;
        tone(f, at, v.pace * 0.95, VOICE, v.wave, 0, f * end);
        tone(f * 2, at, v.pace * 0.8, VOICE * 0.45, 'sine', 0, f * 2 * end);     // an octave above: small speakers carry it
        burst(at, v.pace * 0.7, VOICE * 0.25, 'bandpass', f * 4, 4, 0);
      });
    },
    click: function () { var t = ctx.currentTime; tone(1175, t, 0.1, 0.12, 'triangle'); burst(t, 0.05, 0.08, 'highpass', 3000, 0.7, 0); },
    bye: function () { burst(ctx.currentTime, 0.25, 0.12, 'bandpass', 2600, 0.8, 0, 1200); },
    task: function () {
      var t = ctx.currentTime;
      [523, 659, 784].forEach(function (f, i) { tone(f, t + i * 0.12, 1.6, 0.05); tone(f * 2.01, t + i * 0.12, 0.8, 0.012); });
    }
  };

  /* recorded sounds by kind (web/gather_art.py: kneeling, the hands in the leaves, rising, the pick's blows, cut
     from SHOAIB's videos): one of a kind's takes each time, a little different in pitch */
  var sampleMap = {}, sampleBufs = {};
  function loadSample(url, then) {
    var b = sampleBufs[url];
    if (b && b !== 1) { if (then) then(b); return; }
    if (b === 1) return;
    sampleBufs[url] = 1;
    fetch(url).then(function (r) { return r.arrayBuffer(); })
      .then(function (d) { return new Promise(function (ok, no) { ctx.decodeAudioData(d, ok, no); }); })
      .then(function (buf) { sampleBufs[url] = buf; if (then) then(buf); }).catch(function () { delete sampleBufs[url]; });
  }
  SFX.sample = function (kind, v) {
    var list = sampleMap[kind] || [];
    if (!list.length) return;
    loadSample(list[Math.floor(Math.random() * list.length)], function (buf) {
      var s = ctx.createBufferSource(), g = ctx.createGain();
      s.buffer = buf; s.playbackRate.value = rnd(0.95, 1.05); g.gain.value = v || 0.5;
      s.connect(g); out(g, rnd(-0.1, 0.1)); s.start();
    });
  };

  window.MASound = {
    samples: function (m) { sampleMap = m || {}; if (ctx) Object.keys(sampleMap).forEach(function (k) { if (k !== 'pillar') sampleMap[k].forEach(function (u) { loadSample(u); }); }); },
    voice: '',                              // whose footsteps: the map sets it ("male"), his own takes first
    place: function (k) { kind = k; if (ac()) setBed(k); },
    steps: function () {                    // which gaits have recorded footsteps ready, and how many (for checks)
      var o = {}; Object.keys(stepTakes).forEach(function (g) { o[g] = stepTakes[g].filter(function (f) { return stepBufs[f]; }).length; });
      return o;
    }
  };
  Object.keys(SFX).forEach(function (k) {
    window.MASound[k] = function (a, b) { if (on && ac() && ctx.state === 'running') SFX[k](a, b); };
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
    var mbtns = document.querySelectorAll('[data-music]');
    function markM() { Array.prototype.forEach.call(mbtns, function (b) { var m = (b.dataset.music === 'on') === music; b.classList.toggle('on', m); b.setAttribute('aria-pressed', m); }); }
    Array.prototype.forEach.call(mbtns, function (b) {
      b.addEventListener('click', function () {
        music = b.dataset.music === 'on';
        try { localStorage.setItem('ma.music', music ? 'on' : 'off'); } catch (e) {}
        ac(true);
        if (musicBus) musicBus.gain.setTargetAtTime(music ? 1 : 0, ctx.currentTime, 0.3);
        markM();
      });
    });
    markM();
    if (slider) slider.addEventListener('input', function () {
      vol = slider.value / 100;
      try { localStorage.setItem('ma.vol', slider.value); } catch (e) {}
      if (master) master.gain.setTargetAtTime(vol * vol, ctx.currentTime, 0.05);
    });
    mark();
  });
})();
