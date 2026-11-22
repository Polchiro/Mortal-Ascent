/* The alchemy's little sounds, made in the browser (Web Audio; no sound files): chimes for a good move, a crack for
   a bad one, thunder and a rumbling warning for the Tribulation, a tick for its countdown. A mute button (🔊 in the
   scene) is remembered. Browsers only allow sound after the page has been clicked or a key pressed, so the first
   press wakes it. window.AlchemySound.play(name). */
(function () {
  'use strict';
  var KEY = 'ma-alchemy-mute', ctx = null, muted = false;
  try { muted = localStorage.getItem(KEY) === '1'; } catch (e) {}
  function ac() {
    if (!ctx) { var A = window.AudioContext || window.webkitAudioContext; if (!A) return null; ctx = new A(); }
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  }
  ['pointerdown', 'keydown'].forEach(function (n) { document.addEventListener(n, function () { if (!muted) ac(); }, {once: true, capture: true}); });

  function tone(c, f, at, len, vol, type) {
    var o = c.createOscillator(), g = c.createGain();
    o.type = type || 'sine'; o.frequency.value = f;
    g.gain.setValueAtTime(0.0001, at); g.gain.exponentialRampToValueAtTime(vol, at + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, at + len);
    o.connect(g); g.connect(c.destination); o.start(at); o.stop(at + len + 0.05);
  }
  function noise(c, at, len, vol, filter, freq, attack) {
    var n = Math.floor(c.sampleRate * len), buf = c.createBuffer(1, n, c.sampleRate), d = buf.getChannelData(0);
    for (var i = 0; i < n; i++) d[i] = Math.random() * 2 - 1;
    var src = c.createBufferSource(), f = c.createBiquadFilter(), g = c.createGain();
    src.buffer = buf; f.type = filter; f.frequency.value = freq;
    g.gain.setValueAtTime(0.0001, at); g.gain.exponentialRampToValueAtTime(vol, at + (attack || 0.005));
    g.gain.exponentialRampToValueAtTime(0.0001, at + len);
    src.connect(f); f.connect(g); g.connect(c.destination); src.start(at); src.stop(at + len);
  }
  var SOUNDS = {
    good: function (c, t) { tone(c, 660, t, 0.35, 0.12); tone(c, 990, t + 0.06, 0.4, 0.08); },
    chime: function (c, t) { tone(c, 880, t, 0.7, 0.14); tone(c, 1320, t + 0.08, 0.8, 0.1); tone(c, 1760, t + 0.16, 0.9, 0.06); },
    bad: function (c, t) { noise(c, t, 0.18, 0.25, 'highpass', 1800); tone(c, 110, t, 0.25, 0.2, 'triangle'); },
    tick: function (c, t) { tone(c, 1200, t, 0.06, 0.08, 'square'); },
    ring: function (c, t) { tone(c, 1046 + Math.random() * 300, t, 0.5, 0.06); },
    warn: function (c, t) { noise(c, t, 1.0, 0.18, 'lowpass', 180, 0.6); },
    thunder: function (c, t) { noise(c, t, 0.12, 0.5, 'highpass', 900); noise(c, t + 0.02, 1.6, 0.55, 'lowpass', 320, 0.02); },
    shield: function (c, t) { tone(c, 520, t, 0.5, 0.12, 'triangle'); tone(c, 780, t + 0.05, 0.6, 0.1); noise(c, t, 0.3, 0.12, 'bandpass', 2400); },
    whoosh: function (c, t) { noise(c, t, 0.35, 0.18, 'bandpass', 900, 0.12); }
  };
  window.AlchemySound = {
    play: function (name) {
      if (muted || !SOUNDS[name]) return;
      var c = ac(); if (!c) return;
      try { SOUNDS[name](c, c.currentTime + 0.01); } catch (e) {}
    },
    muted: function () { return muted; },
    toggle: function () { muted = !muted; try { localStorage.setItem(KEY, muted ? '1' : '0'); } catch (e) {} if (!muted) ac(); return muted; }
  };
  document.addEventListener('DOMContentLoaded', function () {
    var b = document.getElementById('lmute');
    if (!b) return;
    var show = function () { b.textContent = muted ? '🔇' : '🔊'; b.setAttribute('aria-pressed', muted ? 'true' : 'false'); };
    show();
    b.addEventListener('click', function (e) { e.stopPropagation(); window.AlchemySound.toggle(); show(); });
  });
})();
