/* The fights' sounds (docs/web.md "Fight sounds"), made in the browser with Web Audio: no sound files. For the beast
   fight (fight.js) and the Arena's duels (duel.js), which call window.FightSound.play(name, arg) at the moment
   something happens on screen:

     press     a move chosen
     swing     the blade's whoosh as a Strike or Break goes in ('break': heavier)
     hit       your blow lands on the enemy ('big': a fifth of its HP or more)
     hurt      a blow lands on you ('big' likewise)
     block     a blow stopped: steel rings
     miss      a blow that meets nothing
     dodge     a sidestep
     guardup   Guard raised
     gather    Qi gathering for a Break
     boom      the ground splits (Break's slam, a pounce landing)
     cast      a technique: Qi swells and is let go (arg 0-4: the technique's grade, deeper and fuller the higher)
     lunge     the beast springs at you
     roar      the beast roars ('big': a Beast King's, or its last)
     heal      HP restored
     stun      stunned
     death     the beast goes down
     victory / defeat   the fight's end

   Only sound: it is told what happened and never decides anything. It shares the map's settings (the gear there:
   Sound On / Off and the volume, localStorage ma.sound / ma.vol), so someone who turned sound off hears nothing here
   either. Browsers allow sound only after a click or key press; choosing a move is one. They are built from noise,
   impact and clashing metal (see below), never a clean note alone, and sit in a short echo. */
(function () {
  'use strict';
  var on = true, vol = 0.6, ctx = null, master = null, nbuf = null;
  try {
    on = localStorage.getItem('ma.sound') !== 'off';
    var v0 = parseFloat(localStorage.getItem('ma.vol')); if (v0 >= 0 && v0 <= 100) vol = v0 / 100;
  } catch (e) {}

  /* How the sounds are built. A real blow is mostly noise, not a note: a sharp crack, a thud of the body behind it
     and the room answering. So nothing here plays a clean tone on its own (that is what makes a sound a "beep"):
       crack   a few milliseconds of raw noise: the instant of contact
       thud    low, dull noise falling fast, with a short drop in pitch under it: weight
       whoosh  noise through a moving filter: something cutting the air
       metal   many clashing partials that are NOT in tune with each other, each dying at its own speed, struck
               with a crack: steel
       voice   a rough buzz and breath pushed through the shapes of a throat, shaking unevenly: a beast
     Everything goes through `drive` (a little overdrive, which makes a hit punch instead of tick) and partly into
     `room` (an echo made from decaying noise), so a blow sits in a place instead of in your ear. */
  var drive = null, room = null;
  function ac(wake) {
    if (!on) return null;
    if (!ctx) {
      if (!wake) return null;
      var A = window.AudioContext || window.webkitAudioContext; if (!A) return null;
      ctx = new A(); master = ctx.createGain(); master.gain.value = vol * vol;
      var comp = ctx.createDynamicsCompressor();               // several sounds at once (a hit, a ring, a boom) stay clean
      comp.threshold.value = -14; comp.ratio.value = 5; comp.attack.value = 0.002; comp.release.value = 0.18;
      master.connect(comp); comp.connect(ctx.destination);
      drive = ctx.createWaveShaper();                          // soft overdrive: tanh
      var curve = new Float32Array(1024);
      for (var i = 0; i < 1024; i++) { var x = i / 511.5 - 1; curve[i] = Math.tanh(2.6 * x); }
      drive.curve = curve; drive.connect(master);
      var len = Math.floor(ctx.sampleRate * 1.3), ir = ctx.createBuffer(2, len, ctx.sampleRate);   // the room: 1.3 s of dying noise
      for (var ch = 0; ch < 2; ch++) {
        var d = ir.getChannelData(ch);
        for (var k = 0; k < len; k++) d[k] = (Math.random() * 2 - 1) * Math.pow(1 - k / len, 3.2) * (k < 400 ? k / 400 : 1);
      }
      var conv = ctx.createConvolver(), wet = ctx.createGain(), dark = ctx.createBiquadFilter();
      conv.buffer = ir; dark.type = 'lowpass'; dark.frequency.value = 4200; wet.gain.value = 0.5;
      room = ctx.createGain(); room.connect(conv); conv.connect(dark); dark.connect(wet); wet.connect(master);
      loadTakes();
    }
    if (ctx.state === 'suspended' && !document.hidden) ctx.resume();
    return ctx;
  }
  ['pointerdown', 'keydown', 'touchstart'].forEach(function (n) { document.addEventListener(n, function () { ac(true); }, {capture: true}); });
  document.addEventListener('visibilitychange', function () { if (ctx) { if (document.hidden) ctx.suspend(); else if (on) ctx.resume(); } });

  function noise() {
    if (nbuf) return nbuf;
    var n = ctx.sampleRate * 2, b = ctx.createBuffer(1, n, ctx.sampleRate), d = b.getChannelData(0);
    for (var i = 0; i < n; i++) d[i] = Math.random() * 2 - 1;
    return (nbuf = b);
  }
  function rnd(a, b) { return a + Math.random() * (b - a); }
  function out(g, wet) { g.connect(drive); if (wet) { var s = ctx.createGain(); s.gain.value = wet; g.connect(s); s.connect(room); } }
  /* how loud each sound is against the others (measured: a hit should be as strong as a technique's blast) */
  var LEVEL = {hit: 2.4, hurt: 2.4, press: 0.6, swing: 0.6, miss: 0.6, dodge: 0.6, gather: 0.5, guardup: 0.6, cast: 0.55, heal: 1.2, block: 1.3}, K = 1;
  function env(g, at, len, v, attack) {
    v *= K;
    g.gain.setValueAtTime(0.0001, at); g.gain.exponentialRampToValueAtTime(v, at + (attack || 0.003));
    g.gain.exponentialRampToValueAtTime(0.0001, at + len);
  }
  /* noise through a filter that may move (f → f2): whooshes, thuds, cracks, breath */
  function air(at, len, v, type, f, f2, q, attack, wet) {
    var s = ctx.createBufferSource(), fl = ctx.createBiquadFilter(), g = ctx.createGain();
    s.buffer = noise(); fl.type = type; fl.frequency.setValueAtTime(f, at); fl.Q.value = q || 0.8;
    if (f2) fl.frequency.exponentialRampToValueAtTime(f2, at + len);
    /* a narrow filter lets little of the noise through: make up for it, so `v` means "this loud" whatever the filter */
    var mid = f2 ? Math.sqrt(f * f2) : f, band = type === 'lowpass' ? mid : type === 'highpass' ? Math.max(2000, 20000 - mid) : mid / (q || 0.8);
    env(g, at, len, v * Math.min(4.5, 0.42 * Math.sqrt(22050 / band)), attack); s.connect(fl); fl.connect(g); out(g, wet == null ? 0.25 : wet);
    s.start(at, Math.random()); s.stop(at + len + 0.05);
  }
  function crack(at, v) { air(at, 0.012, v, 'highpass', 900, 0, 0.5, 0.001, 0.3); }
  /* weight: dull noise falling fast, and a short pitch drop under it (heard as a thump, not a note) */
  function thud(at, v, size) {
    size = size || 1;
    air(at, 0.14 * size, v * 1.6, 'lowpass', 900 / size, 220 / size, 0.9, 0.002, 0.35);
    air(at, 0.08 * size, v * 0.8, 'bandpass', 420 / size, 240 / size, 1.2, 0.002, 0.35);     // the part small speakers can play
    var o = ctx.createOscillator(), g = ctx.createGain();
    o.type = 'sine'; o.frequency.setValueAtTime(330 / size, at); o.frequency.exponentialRampToValueAtTime(95 / size, at + 0.07 * size);
    env(g, at, 0.1 * size, v * 0.55, 0.002); o.connect(g); out(g, 0.2); o.start(at); o.stop(at + 0.2 * size);
  }
  /* steel: partials out of tune with each other (so it clangs instead of singing), a little rough, each dying at its
     own speed, the high ones first */
  var STEEL = [1, 1.41, 1.93, 2.58, 3.17, 3.96, 4.81, 5.93];
  function metal(at, base, len, v, wet) {
    STEEL.forEach(function (r, i) {
      var o = ctx.createOscillator(), g = ctx.createGain(), f = base * r * rnd(0.985, 1.015);
      o.type = i % 3 === 0 ? 'triangle' : 'sine'; o.frequency.setValueAtTime(f * 1.02, at); o.frequency.exponentialRampToValueAtTime(f, at + 0.03);
      env(g, at, len / (1 + i * 0.45), v / (1 + i * 0.35), 0.001);
      o.connect(g); out(g, wet == null ? 0.5 : wet); o.start(at); o.stop(at + len + 0.05);
    });
    air(at, len * 0.5, v * 0.5, 'bandpass', base * 3.3, base * 2.6, 14, 0.001, 0.5);      // the blade's hiss under the ring
  }
  /* a throat: a rough buzz (two saws a little apart) and breath, through the shapes of a mouth, shaking unevenly */
  function voice(at, len, v, f, f2, open) {
    var g = ctx.createGain(), mix = ctx.createGain(), shake = ctx.createGain();
    [1, 1.012, 0.5].forEach(function (m) {
      var o = ctx.createOscillator(); o.type = 'sawtooth';
      o.frequency.setValueAtTime(f * m, at); o.frequency.exponentialRampToValueAtTime(f2 * m, at + len);
      o.connect(mix); o.start(at); o.stop(at + len + 0.05);
    });
    var br = ctx.createBufferSource(), bg = ctx.createGain(); br.buffer = noise(); bg.gain.value = 0.7; br.connect(bg); bg.connect(mix);
    br.start(at, Math.random()); br.stop(at + len + 0.05);
    [[open ? 620 : 420, 5], [open ? 1150 : 900, 6], [2300, 7]].forEach(function (p, i) {    // the mouth: three resonances
      var b = ctx.createBiquadFilter(), bgain = ctx.createGain(); b.type = 'bandpass'; b.frequency.setValueAtTime(p[0], at);
      b.frequency.exponentialRampToValueAtTime(p[0] * 0.75, at + len); b.Q.value = p[1]; bgain.gain.value = [1, 0.7, 0.3][i];
      mix.connect(b); b.connect(bgain); bgain.connect(shake);
    });
    [[31, 0.35], [47, 0.2], [7, 0.25]].forEach(function (l) {                               // the rattle: never even
      var lo = ctx.createOscillator(), lg = ctx.createGain(); lo.frequency.value = l[0] * rnd(0.9, 1.1); lg.gain.value = l[1];
      lo.connect(lg); lg.connect(shake.gain); lo.start(at); lo.stop(at + len + 0.05);
    });
    env(g, at, len, v, Math.min(0.08, len / 4)); shake.connect(g); out(g, 0.45);
  }
  /* a struck string (the victory and defeat phrases): bright at the pluck, then mellow as it rings away */
  function pluck(at, f, v, len) {
    var g = ctx.createGain(), lp = ctx.createBiquadFilter(); lp.type = 'lowpass';
    lp.frequency.setValueAtTime(Math.min(7000, f * 7), at); lp.frequency.exponentialRampToValueAtTime(f * 1.5, at + len * 0.5);
    [[1, 'sawtooth', 0.6], [2.003, 'triangle', 0.3], [0.5, 'sine', 0.4]].forEach(function (h) {
      var o = ctx.createOscillator(), og = ctx.createGain(); o.type = h[1]; og.gain.value = h[2];
      o.frequency.setValueAtTime(f * h[0] * 0.98, at); o.frequency.exponentialRampToValueAtTime(f * h[0], at + 0.04);
      o.connect(og); og.connect(lp); o.start(at); o.stop(at + len + 0.05);
    });
    env(g, at, len, v, 0.004); lp.connect(g); out(g, 0.6);
  }
  function drum(at, v, size) { crack(at, v * 0.4); thud(at, v, size || 1.5); air(at, 0.5, v * 0.25, 'lowpass', 300, 90, 0.8, 0.005, 0.7); }

  var S = {
    press: function (t) { thud(t, 0.22, 0.55); air(t, 0.03, 0.3, 'bandpass', 1400, 700, 1, 0.001, 0.1); },   // a soft tap of wood, no note
    swing: function (t, a) {                                                                 // steel cutting air
      var heavy = a === 'break', len = heavy ? 0.38 : 0.26;
      air(t, len, heavy ? 0.5 : 0.42, 'bandpass', heavy ? 380 : 620, heavy ? 2400 : 4200, 2.2, len * 0.55, 0.3);
      air(t + len * 0.35, len * 0.7, 0.2, 'highpass', 3800, 7000, 0.7, len * 0.3, 0.3);      // the edge
      if (heavy) air(t, len, 0.3, 'lowpass', 240, 480, 1, len * 0.6, 0.3);
    },
    hit: function (t, a) {                                                                   // your blade bites
      var big = a === 'big';
      crack(t, big ? 0.9 : 0.7);
      air(t, 0.09, big ? 0.6 : 0.5, 'bandpass', 2600, 1100, 1.1, 0.001, 0.3);                // the slice through
      thud(t + 0.004, big ? 0.95 : 0.8, big ? 1.6 : 1.3);
      metal(t, big ? 1500 : 1900, big ? 0.3 : 0.2, big ? 0.1 : 0.08, 0.4);                   // a short ring off the blade
      if (big) { air(t + 0.03, 0.5, 0.35, 'lowpass', 500, 110, 0.8, 0.01, 0.8); thud(t + 0.05, 0.5, 2.2); }
    },
    hurt: function (t, a) {                                                                  // a blow to the body
      var big = a === 'big';
      crack(t, big ? 0.6 : 0.45);
      thud(t, big ? 1.0 : 0.85, big ? 1.8 : 1.45);
      air(t, 0.07, big ? 0.45 : 0.35, 'bandpass', 1300, 600, 1, 0.001, 0.3);                 // the smack
      air(t + 0.03, 0.18, 0.14, 'bandpass', 3000, 1500, 0.8, 0.02, 0.3);                     // cloth
      if (big) air(t + 0.04, 0.45, 0.3, 'lowpass', 420, 100, 0.8, 0.01, 0.8);
    },
    block: function (t) {                                                                    // steel stops steel
      crack(t, 0.9); thud(t, 0.35, 0.8);
      metal(t, rnd(1050, 1250), 0.75, 0.34, 0.6);
      metal(t + 0.012, rnd(1700, 1900), 0.4, 0.16, 0.6);                                     // the second blade answers
    },
    miss: function (t) { air(t, 0.24, 0.3, 'bandpass', 1500, 4800, 1.8, 0.1, 0.3); },
    dodge: function (t) {
      air(t, 0.16, 0.3, 'bandpass', 900, 3200, 1.6, 0.06, 0.3); air(t + 0.03, 0.2, 0.16, 'highpass', 4000, 0, 0.7, 0.05, 0.3);   // robes
      thud(t + 0.17, 0.25, 0.7);                                                             // the foot comes down
    },
    guardup: function (t) {                                                                  // the blade brought across, feet set
      air(t, 0.16, 0.3, 'bandpass', 700, 2200, 1.6, 0.08, 0.3);
      metal(t + 0.09, 2100, 0.25, 0.07, 0.5); thud(t + 0.1, 0.35, 0.9);
    },
    gather: function (t) {                                                                   // Qi drawn in: wind closing on you, the ground humming
      air(t, 0.65, 0.4, 'bandpass', 300, 2600, 3.5, 0.55, 0.5);
      air(t, 0.65, 0.3, 'lowpass', 120, 320, 1.2, 0.5, 0.5);
      air(t + 0.3, 0.35, 0.16, 'highpass', 5000, 9000, 0.7, 0.3, 0.5);
    },
    boom: function (t) {                                                                     // the ground breaks
      crack(t, 1.0); thud(t, 1.2, 2.4); thud(t + 0.03, 0.8, 1.4);
      air(t, 1.1, 0.8, 'lowpass', 900, 70, 0.7, 0.005, 0.9);                                 // the rumble rolling off
      air(t + 0.02, 0.3, 0.4, 'bandpass', 1800, 500, 0.9, 0.003, 0.5);                       // rock splitting
      for (var i = 0; i < 9; i++) { var d = 0.1 + Math.random() * 0.6; crack(t + d, 0.12 + Math.random() * 0.15); thud(t + d, 0.12, 0.6); }   // stones landing
    },
    cast: function (t, a) {                                     // Qi gathers like wind rising (0.47 s), then is loosed like a thunderclap
      var g = Math.max(0, Math.min(4, +a || 0));
      air(t, 0.5, 0.36 + g * 0.03, 'bandpass', 260, 2400 + g * 300, 4, 0.44, 0.5);
      air(t, 0.5, 0.22 + g * 0.04, 'lowpass', 110, 300, 1.2, 0.42, 0.5);
      air(t + 0.25, 0.25, 0.14, 'highpass', 5200, 9000, 0.7, 0.2, 0.5);
      var r = t + 0.47;
      crack(r, 0.8 + g * 0.05);
      air(r, 0.5 + g * 0.1, 0.6 + g * 0.05, 'bandpass', 3400, 320, 1.1, 0.004, 0.7);         // the blast tearing outward
      thud(r, 0.7 + g * 0.1, 1.4 + g * 0.3);
      air(r + 0.02, 0.7 + g * 0.2, 0.3 + g * 0.08, 'lowpass', 700, 80, 0.8, 0.01, 0.9);      // and rolling away
      if (g >= 2) for (var i = 0; i < g; i++) crack(r + 0.06 + Math.random() * 0.25, 0.25);  // it crackles
    },
    lunge: function (t) {                                                                    // it springs: a snarl, claws on earth
      voice(t, 0.38, 0.6, 210, 150, false);
      air(t + 0.1, 0.24, 0.3, 'bandpass', 500, 2400, 1.4, 0.1, 0.3); thud(t + 0.02, 0.3, 1.1);
    },
    roar: function (t, a) {
      var big = a === 'big', len = big ? 1.7 : 1.15;
      voice(t, len, big ? 0.85 : 0.7, big ? 150 : 185, big ? 95 : 120, true);
      voice(t + 0.03, len * 0.9, big ? 0.4 : 0.3, big ? 228 : 280, big ? 140 : 180, true);
      air(t, len, big ? 0.3 : 0.2, 'lowpass', 260, 110, 1, 0.12, 0.9);                       // the chest under it
      if (big) thud(t, 0.5, 2.2);
    },
    heal: function (t) {                                                                     // warmth: a soft bell in a hall, breath
      [523, 784, 1047].forEach(function (f, i) { pluck(t + i * 0.1, f, 0.12, 1.1); });
      air(t, 0.7, 0.12, 'bandpass', 1800, 4200, 2, 0.4, 0.8);
    },
    stun: function (t) {                                                                     // the skull rings
      thud(t, 0.8, 1.6); crack(t, 0.5); metal(t + 0.02, 2600, 0.9, 0.09, 0.9);
      air(t + 0.05, 0.8, 0.14, 'bandpass', 3400, 2200, 18, 0.2, 0.9);
    },
    death: function (t) {                                                                    // a last cry, and the body comes down
      voice(t, 0.95, 0.65, 200, 85, true);
      thud(t + 0.8, 1.0, 2.3); air(t + 0.8, 0.5, 0.4, 'lowpass', 600, 100, 0.8, 0.005, 0.8); air(t + 0.84, 0.3, 0.2, 'bandpass', 2400, 900, 0.8, 0.01, 0.4);
    },
    victory: function (t) {                                                                  // a drum, strings rising, a gong
      drum(t, 0.9, 1.8);
      [392, 523, 587, 784].forEach(function (f, i) { pluck(t + 0.18 + i * 0.14, f, 0.26, 1.6); });
      drum(t + 0.8, 0.8, 2); metal(t + 0.8, 196, 2.6, 0.2, 0.9); metal(t + 0.8, 311, 1.8, 0.1, 0.9);
    },
    defeat: function (t) {                                                                   // two slow drums, strings falling
      drum(t, 0.9, 2.2); drum(t + 0.6, 0.7, 2.6);
      [330, 294, 220].forEach(function (f, i) { pluck(t + 0.15 + i * 0.3, f, 0.2, 1.8); });
      air(t + 0.6, 1.4, 0.2, 'lowpass', 300, 90, 0.8, 0.3, 0.9);
    }
  };

  /* Recorded sounds (art/fx/sounds/, cut from SHOAIB's animation videos by scripts/make_fight_sound.py). sounds.json
     lists them: {"swing": [{"file": "swing.mp3", "lead": 0.16}], "hit:big": [...], "roar@wolf": [...]}. A sound that has a recording
     plays it (one of its takes, not the same twice running) instead of the one made in code; "hit:big" is used for
     a big hit if it is there, else "hit". They load when the page opens; until one is ready the made one plays. */
  var BASE = '/art/fx/sounds/', takes = {}, bufs = {}, lastTake = {};
  function fetchTakes() {
    fetch(BASE + 'sounds.json', {cache: 'no-cache'}).then(function (r) { return r.ok ? r.json() : {}; }).then(function (j) { takes = j || {}; loadTakes(); }).catch(function () {});
  }
  function loadTakes() {                                      // decoding needs the context, which needs a first click
    if (!ctx) return;
    Object.keys(takes).forEach(function (k) {
      takes[k].forEach(function (t) {
        var file = fileOf(t);
        if (file in bufs) return;
        bufs[file] = null;
        fetch(BASE + file).then(function (r) { return r.arrayBuffer(); })
          .then(function (a) { return new Promise(function (ok, no) { ctx.decodeAudioData(a, ok, no); }); })
          .then(function (b) { bufs[file] = b; }).catch(function () {});
      });
    });
  }
  /* which takes answer this sound: the narrowest listed. For a beast's voice, its body's own first
     ("roar:big@wolf", "roar@wolf"); `as` narrows a technique to its movement ("cast:kick"); then "hit:big"; then
     "hit". */
  function takesFor(name, arg, opts) {
    var body = window.FightSound.body, tries = [];
    var narrow = opts && opts.as ? opts.as : (arg !== undefined && arg !== null && arg !== '' ? arg : null);
    if (body) { if (narrow !== null) tries.push(name + ':' + narrow + '@' + body); tries.push(name + '@' + body); }
    var voice = window.FightSound.voice;                      // the cultivator's own take first ("swing:strike#male")
    if (voice) { if (narrow !== null) tries.push(name + ':' + narrow + '#' + voice); tries.push(name + '#' + voice); }
    if (narrow !== null) tries.push(name + ':' + narrow);
    tries.push(name);
    for (var i = 0; i < tries.length; i++) if (takes[tries[i]]) return tries[i];
    return null;
  }
  function fileOf(t) { return typeof t === 'string' ? t : t.file; }
  function recorded(name, arg, at, opts) {
    var key = takesFor(name, arg, opts);
    if (!key) return false;
    var ready = takes[key].filter(function (t) { return bufs[fileOf(t)]; });
    if (!ready.length) return false;
    var pick = ready[Math.floor(Math.random() * ready.length)];
    if (ready.length > 1 && fileOf(pick) === lastTake[key]) pick = ready[(ready.indexOf(pick) + 1) % ready.length];
    lastTake[key] = fileOf(pick);
    /* `land` (ms): the blow lands that long from now, and the recording's own loudest moment is `lead` seconds
       in: start it so the two meet */
    if (opts && opts.land) at += Math.max(0, opts.land / 1000 - (pick.lead || 0));
    var src = ctx.createBufferSource(), g = ctx.createGain(), send = ctx.createGain();
    src.buffer = bufs[fileOf(pick)]; g.gain.value = 0.9; send.gain.value = 0.12;
    src.connect(g); g.connect(master); g.connect(send); send.connect(room);
    src.start(at);
    return true;
  }
  fetchTakes();

  window.FightSound = {
    /* which sounds have a recording ready (for checks) */
    recorded: function () { return Object.keys(takes).filter(function (k) { return takes[k].some(function (t) { return bufs[fileOf(t)]; }); }); },
    body: '',                                                 // the beast's body type (fight.js sets it): whose voice
    voice: '',                                                // the cultivator's ("male"): his own recordings first (fight.js sets it)
    names: Object.keys(S),
    /* play a sound now, or `delay` ms from now */
    play: function (name, arg, delay, opts) {
      if (!S[name] || !on || !ac(false) || ctx.state !== 'running') return;
      var at = ctx.currentTime + (delay || 0) / 1000;
      try { if (recorded(name, arg, at, opts)) return; } catch (e) {}
      K = LEVEL[name] || 1;
      try { S[name](at, arg); } catch (e) {}
      K = 1;
    }
  };
})();
