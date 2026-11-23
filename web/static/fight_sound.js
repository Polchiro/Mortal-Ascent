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
   either. Browsers allow sound only after a click or key press; choosing a move is one. Pitches are kept in the range
   small laptop and phone speakers can play. */
(function () {
  'use strict';
  var on = true, vol = 0.6, ctx = null, master = null, nbuf = null;
  try {
    on = localStorage.getItem('ma.sound') !== 'off';
    var v0 = parseFloat(localStorage.getItem('ma.vol')); if (v0 >= 0 && v0 <= 100) vol = v0 / 100;
  } catch (e) {}

  function ac(wake) {
    if (!on) return null;
    if (!ctx) {
      if (!wake) return null;
      var A = window.AudioContext || window.webkitAudioContext; if (!A) return null;
      ctx = new A(); master = ctx.createGain(); master.gain.value = vol * vol;
      var comp = ctx.createDynamicsCompressor();               // several sounds at once (a hit, a ring, a boom) stay clean
      master.connect(comp); comp.connect(ctx.destination);
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
  function env(g, at, len, v, attack) {
    g.gain.setValueAtTime(0.0001, at); g.gain.exponentialRampToValueAtTime(v, at + (attack || Math.min(0.01, len / 4)));
    g.gain.exponentialRampToValueAtTime(0.0001, at + len);
  }
  function tone(f, at, len, v, type, f2, attack) {
    var o = ctx.createOscillator(), g = ctx.createGain();
    o.type = type || 'sine'; o.frequency.setValueAtTime(f, at);
    if (f2) o.frequency.exponentialRampToValueAtTime(f2, at + len);
    env(g, at, len, v, attack); o.connect(g); g.connect(master); o.start(at); o.stop(at + len + 0.05);
  }
  function air(at, len, v, type, f, f2, q, attack) {            // filtered noise: whooshes, thuds, cracks
    var s = ctx.createBufferSource(), fl = ctx.createBiquadFilter(), g = ctx.createGain();
    s.buffer = noise(); fl.type = type; fl.frequency.setValueAtTime(f, at); fl.Q.value = q || 0.8;
    if (f2) fl.frequency.exponentialRampToValueAtTime(f2, at + len);
    env(g, at, len, v, attack); s.connect(fl); fl.connect(g); g.connect(master); s.start(at, Math.random()); s.stop(at + len + 0.05);
  }
  function growl(at, len, v, f, f2, wob) {                      // a rough voice: a saw through a low filter, shaking
    var o = ctx.createOscillator(), fl = ctx.createBiquadFilter(), g = ctx.createGain(), l = ctx.createOscillator(), lg = ctx.createGain();
    o.type = 'sawtooth'; o.frequency.setValueAtTime(f, at); o.frequency.exponentialRampToValueAtTime(f2, at + len);
    fl.type = 'lowpass'; fl.frequency.setValueAtTime(1400, at); fl.frequency.exponentialRampToValueAtTime(600, at + len); fl.Q.value = 2;
    l.frequency.value = wob || 24; lg.gain.value = v * 0.45; l.connect(lg); lg.connect(g.gain);
    env(g, at, len, v, 0.05); o.connect(fl); fl.connect(g); g.connect(master);
    o.start(at); l.start(at); o.stop(at + len + 0.05); l.stop(at + len + 0.05);
  }

  var S = {
    press: function (t) { tone(880, t, 0.08, 0.14, 'triangle'); air(t, 0.04, 0.08, 'highpass', 3500); },
    swing: function (t, a) {
      var heavy = a === 'break';
      air(t, heavy ? 0.34 : 0.24, heavy ? 0.42 : 0.34, 'bandpass', heavy ? 500 : 800, heavy ? 2600 : 3600, 1.4, 0.08);
      tone(heavy ? 1400 : 2100, t + 0.05, 0.3, 0.05, 'sine', heavy ? 1700 : 2600);          // the blade sings
    },
    hit: function (t, a) {
      var big = a === 'big';
      air(t, big ? 0.22 : 0.14, big ? 0.6 : 0.45, 'lowpass', 1800, 500, 0.8);                // the thud
      air(t, 0.07, 0.3, 'highpass', 3000);                                                   // the cut
      tone(big ? 240 : 300, t, big ? 0.3 : 0.18, big ? 0.45 : 0.32, 'triangle', big ? 110 : 150);
      if (big) { tone(160, t + 0.02, 0.45, 0.3, 'triangle', 80); air(t + 0.03, 0.4, 0.2, 'lowpass', 900, 250); }
    },
    hurt: function (t, a) {
      var big = a === 'big';
      air(t, big ? 0.24 : 0.16, big ? 0.55 : 0.42, 'lowpass', 1300, 380, 0.8);
      tone(big ? 210 : 260, t, big ? 0.34 : 0.22, big ? 0.42 : 0.32, 'square', big ? 100 : 130);
      if (big) tone(520, t + 0.03, 0.4, 0.1, 'sine', 300);
    },
    block: function (t) {                                                                    // steel on steel
      air(t, 0.05, 0.4, 'highpass', 2500);
      [[1244, 0.5, 0.22], [1865, 0.38, 0.14], [2637, 0.3, 0.1], [3520, 0.2, 0.06]].forEach(function (p) { tone(p[0], t, p[1], p[2], 'triangle'); });
    },
    miss: function (t) { air(t, 0.22, 0.25, 'bandpass', 2400, 5000, 1.2, 0.07); },
    dodge: function (t) { air(t, 0.14, 0.28, 'bandpass', 1500, 4000, 1.5, 0.04); air(t + 0.12, 0.16, 0.2, 'bandpass', 3000, 1200, 1.5, 0.04); },
    guardup: function (t) { air(t, 0.12, 0.25, 'bandpass', 900, 1600, 1.2); tone(740, t + 0.03, 0.25, 0.12, 'triangle'); tone(1110, t + 0.03, 0.2, 0.07, 'triangle'); },
    gather: function (t) {
      tone(220, t, 0.6, 0.18, 'sawtooth', 780, 0.4); tone(440, t, 0.6, 0.1, 'sine', 1560, 0.45);
      air(t, 0.6, 0.18, 'bandpass', 600, 3200, 2, 0.5);
    },
    boom: function (t) {
      tone(200, t, 0.7, 0.6, 'triangle', 55); tone(300, t, 0.3, 0.3, 'square', 90);
      air(t, 0.7, 0.6, 'lowpass', 1400, 200, 0.7); air(t + 0.06, 0.5, 0.2, 'highpass', 2000, 4000, 0.7);       // stones
      [0.12, 0.2, 0.31, 0.4].forEach(function (d) { air(t + d, 0.05, 0.14, 'bandpass', 1800 + Math.random() * 1500, 0, 3); });
    },
    cast: function (t, a) {                                     // Qi swells (0.45 s), then is let go
      var g = Math.max(0, Math.min(4, +a || 0)), base = 392 / (1 + g * 0.12), v = 0.16 + g * 0.03;
      tone(base, t, 0.5, v, 'sine', base * 2, 0.4); tone(base * 1.5, t, 0.5, v * 0.6, 'sine', base * 3, 0.42);
      air(t, 0.5, 0.14 + g * 0.02, 'bandpass', 800, 4500, 2.5, 0.45);
      var r = t + 0.47;
      air(r, 0.4 + g * 0.08, 0.4 + g * 0.04, 'bandpass', 3000, 500, 1, 0.02);
      tone(base * 2, r, 0.5 + g * 0.1, v * 1.2, 'triangle', base * 0.9);
      [1, 1.25, 1.5, 2].slice(0, 2 + Math.min(2, g)).forEach(function (m, i) { tone(base * 4 * m, r + 0.04 * i, 0.5, 0.06, 'sine'); });
      if (g >= 3) tone(110, r, 0.7, 0.3, 'triangle', 60);
    },
    lunge: function (t) { growl(t, 0.32, 0.4, 260, 160, 30); air(t + 0.08, 0.22, 0.25, 'bandpass', 700, 2600, 1.2, 0.06); },
    roar: function (t, a) {
      var big = a === 'big', len = big ? 1.5 : 1.0;
      growl(t, len, big ? 0.55 : 0.45, big ? 190 : 230, big ? 120 : 150, 19);
      growl(t, len * 0.9, big ? 0.3 : 0.22, big ? 285 : 345, big ? 170 : 220, 23);
      air(t, len, big ? 0.3 : 0.2, 'bandpass', 900, 500, 1.2, 0.1);
    },
    heal: function (t) { [659, 880, 1319].forEach(function (f, i) { tone(f, t + i * 0.09, 0.6, 0.14); }); air(t, 0.5, 0.06, 'highpass', 5000, 0, 0.7, 0.2); },
    stun: function (t) {
      var o = ctx.createOscillator(), g = ctx.createGain(), l = ctx.createOscillator(), lg = ctx.createGain();
      o.type = 'triangle'; o.frequency.setValueAtTime(900, t); o.frequency.exponentialRampToValueAtTime(420, t + 0.7);
      l.frequency.value = 11; lg.gain.value = 90; l.connect(lg); lg.connect(o.frequency);
      env(g, t, 0.7, 0.2, 0.03); o.connect(g); g.connect(master); o.start(t); l.start(t); o.stop(t + 0.8); l.stop(t + 0.8);
    },
    death: function (t) {
      growl(t, 0.9, 0.4, 240, 110, 14); air(t + 0.75, 0.35, 0.5, 'lowpass', 900, 220);       // a last cry, and it falls
      tone(180, t + 0.75, 0.4, 0.4, 'triangle', 70);
    },
    victory: function (t) {
      [523, 659, 784, 1047].forEach(function (f, i) { var a = t + i * 0.13; tone(f, a, 1.2, 0.2, 'triangle'); tone(f * 2, a, 0.6, 0.06, 'sine'); });
      tone(196, t + 0.5, 2.2, 0.25, 'triangle', 190); tone(392, t + 0.5, 1.6, 0.12, 'sine'); tone(1568, t + 0.55, 1.4, 0.08, 'sine');   // a gong under it
    },
    defeat: function (t) {
      [392, 330, 262, 196].forEach(function (f, i) { tone(f, t + i * 0.22, 0.9, 0.2, 'triangle', f * 0.97); });
      air(t + 0.7, 0.9, 0.2, 'lowpass', 600, 200);
    }
  };

  window.FightSound = {
    names: Object.keys(S),
    /* play a sound now, or `delay` ms from now */
    play: function (name, arg, delay) {
      if (!S[name] || !on || !ac(false) || ctx.state !== 'running') return;
      try { S[name](ctx.currentTime + (delay || 0) / 1000, arg); } catch (e) {}
    }
  };
})();
