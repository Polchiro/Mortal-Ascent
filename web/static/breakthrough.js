/* Breakthrough (web/breakthrough_play.py, docs/web.md "Breakthrough").
   The server rolls with the bot's own rules the moment you begin; this page only shows what happened. Until the
   result, everything looks and sounds the same whatever the outcome: the three pulses of light and the three
   lightning strikes always come, so nothing gives the answer away early.

   Looks: inner  (a phase bottleneck)        the meditation chamber: Qi gathers into the Dantian, it compresses,
                                             then the inner breakthrough (its video) or the Qi deviation
          dawn   (realms up to Martial Expert) the peak at dawn: the sky opens, a beam comes down, three pulses,
                                             then the realm ascension or the deviation
          storm  (Martial Master and up)     the peak in the storm: three strikes, then the ascension or the
                                             deviation
   The art (scripts/make_breakthrough_art.py) is drawn on a 1920x1080 stage that covers the window. */
(function () {
  var S = JSON.parse(document.getElementById('btstate').textContent), A = S.a, ART = S.art, HERO = ART.hero;
  function $(id) { return document.getElementById(id); }
  var main = $('bt'), scene = $('btscene');
  var LOOK = (A && A.look) || 'inner', SCN = ART[LOOK] || ART.inner;
  var reduced = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var soundOn = true, soundVol = 0.6, quick = false;
  try {
    soundOn = localStorage.getItem('ma.sound') !== 'off';
    var v0 = parseFloat(localStorage.getItem('ma.vol')); if (v0 >= 0 && v0 <= 100) soundVol = v0 / 100;
    quick = localStorage.getItem('ma.bt.quick') === '1';
  } catch (e0) {}
  function LOUD() { return Math.min(1, soundVol * 1.7); }
  function fs(name, arg, delay) { var F = window.FightSound; if (F) F.play(name, arg, delay); }
  if (window.FightSound) window.FightSound.voice = S.gender;
  function audio(url, vol, loop) {
    if (!soundOn || !url) return null;
    var a = new Audio(url); a.volume = Math.min(1, vol); a.loop = !!loop;
    var p = a.play(); if (p && p.catch) p.catch(function () {});
    return a;
  }
  function fade(a, ms) {
    if (!a) return;
    var v = a.volume, t0 = performance.now();
    (function step() { var k = Math.min(1, (performance.now() - t0) / ms); a.volume = v * (1 - k); if (k < 1) requestAnimationFrame(step); else a.pause(); })();
  }

  /* ── the stage ──────────────────────────────────────────────────── */
  var SEAT = {inner: {x: 1050, y: 790, s: 0.5}, dawn: {x: 960, y: 915, s: 0.56}, storm: {x: 960, y: 915, s: 0.56}};
  var HX = 968, HY = 1062;                                       // where the figure sits in its own video (px)
  var DANTIAN = S.gender === 'male' ? 770 : 745;                // the Dantian, in the hero video's px
  var W = 0, H = 0, DPR = 1, K = 1, OX = 0, OY = 0;
  var charC = $('btchar'), cc = charC.getContext('2d'), fxC = $('btfx'), fx = fxC.getContext('2d');
  function resize() {
    var r = scene.getBoundingClientRect();
    DPR = Math.min(2, window.devicePixelRatio || 1); W = r.width; H = r.height;
    [charC, fxC].forEach(function (c) { c.width = Math.round(W * DPR); c.height = Math.round(H * DPR); c.style.width = W + 'px'; c.style.height = H + 'px'; });
    K = Math.max(W / 1920, H / 1080); OX = (W - 1920 * K) / 2; OY = (H - 1080 * K) / 2;
    drawn = null;
  }
  window.addEventListener('resize', resize);
  function seat() { return SEAT[LOOK] || SEAT.inner; }
  function onStage(x, y) { return [OX + x * K, OY + y * K]; }
  /* where the figure sits on the screen: on the stage's seat. A tall phone would show it too big and behind the card,
     so there it is smaller, and sits above the card (or the scroll) while one is open: `up`, eased */
  var up = 1, upTo = 1;
  function tall() { return W / H < 0.85; }
  function place() {
    var s = seat(), k = s.s * K, x = OX + s.x * K, y = OY + s.y * K;
    if (tall()) {
      k = 0.36 * H / 996;
      x = W / 2; y = y * (1 - up) + 0.5 * H * up;
    }
    return {k: k, x: x, y: y};
  }
  function heroRect(box) {                                       // a box in the hero video's px, on the screen
    var p = place();
    return [p.x + (box[0] - HX) * p.k, p.y + (box[1] - HY) * p.k, box[2] * p.k, box[3] * p.k];
  }
  function heroPoint(px, py) { var p = place(); return [p.x + (px - HX) * p.k, p.y + (py - HY) * p.k]; }

  /* the place: its picture, its video (looping, or the dawn's one play), its sound */
  var bg = $('btbg'), still = $('btstill'), amb = null;
  still.src = SCN.picture || '';
  if (SCN.video && SCN.loop) {
    bg.src = SCN.video; bg.loop = true; bg.poster = SCN.picture || '';
    var p0 = bg.play(); if (p0 && p0.catch) p0.catch(function () {});
    bg.addEventListener('playing', function () { still.classList.add('off'); });
  } else if (SCN.video) {
    bg.src = SCN.video; bg.loop = false;
  }
  function ambience() { if (!amb && SCN.loop && SCN.sound) amb = audio(SCN.sound, soundVol * 0.8, true); }
  ['pointerdown', 'keydown'].forEach(function (ev) { document.addEventListener(ev, ambience, {once: true, passive: true}); });

  /* ── you: the meditation loop (Train's), and the endings (inner, ascend, and Train's deviation) ─────────── */
  var loopImg = null, ENDS = {}, endNow = null, endBuf = {}, drawn = null;
  if (HERO) {
    loopImg = new Image(); loopImg.src = HERO.loop.src;
    Object.keys(HERO.ends).forEach(function (k) {
      if (['inner', 'ascend', 'deviation'].indexOf(k) < 0) return;
      var v = document.createElement('video');
      v.muted = true; v.playsInline = true; v.setAttribute('playsinline', ''); v.preload = 'auto'; v.src = HERO.ends[k].src;
      ENDS[k] = v;
    });
  }
  var endSound = null;
  function playEnd(name) {
    var v = ENDS[name]; if (!v) return false;
    try { v.currentTime = 0; } catch (e) {}
    var p = v.play(); if (p && p.catch) p.catch(function () {});
    endNow = {name: name, v: v, spec: HERO.ends[name], t0: performance.now(), ready: false};
    endSound = audio(endNow.spec.sound, LOUD());
    return true;
  }
  function unmask(buf, v, w, h) {
    if (!buf.raw || buf.raw.width !== w || buf.raw.height !== h * 2) {
      buf.raw = document.createElement('canvas'); buf.raw.width = w; buf.raw.height = h * 2;
      buf.rc = buf.raw.getContext('2d', {willReadFrequently: true});
      buf.out = document.createElement('canvas'); buf.out.width = w; buf.out.height = h;
      buf.oc = buf.out.getContext('2d');
    }
    buf.rc.drawImage(v, 0, 0, w, h * 2);
    var px = buf.rc.getImageData(0, 0, w, h * 2), d = px.data, n = w * h * 4, i, a;
    for (i = 0; i < n; i += 4) {
      a = d[i + n];
      if (a > 3) { d[i] = Math.min(255, d[i] * 255 / a); d[i + 1] = Math.min(255, d[i + 1] * 255 / a); d[i + 2] = Math.min(255, d[i + 2] * 255 / a); d[i + 3] = a; }
      else d[i + 3] = 0;
    }
    buf.oc.putImageData(px, 0, 0, 0, 0, w, h);
    buf.oc.clearRect(0, 0, w, 3); buf.oc.clearRect(0, h - 3, w, 3); buf.oc.clearRect(0, 0, 3, h); buf.oc.clearRect(w - 3, 0, 3, h);
    return buf.out;
  }
  function drawChar(now) {
    if (!HERO || !loopImg.complete || !loopImg.naturalWidth) { drawPlain(); return; }
    var L = HERO.loop, n = L.frames, span = Math.max(1, 2 * n - 2), i = Math.floor(now * L.fps / 1000) % span, f = i < n ? i : span - i;
    var key = 'L' + f, pic = null, blend = 0;
    if (endNow) {
      var e = endNow;
      if (e.v.ended && e.name !== 'deviation' && e.name !== 'inner' && e.name !== 'ascend') endNow = null;
      else if (e.v.readyState >= 2 && e.v.currentTime > 0) {
        if (!e.ready) { e.ready = true; e.t1 = now; }
        blend = Math.max(0, 1 - (now - e.t1) / 350);
        key = 'E' + e.name + e.v.currentTime + (blend ? 'b' + f : '');
        pic = e;
      }
    }
    if (key === drawn) return;
    drawn = key;
    cc.setTransform(DPR, 0, 0, DPR, 0, 0); cc.clearRect(0, 0, W, H);
    var r;
    if (pic) { r = heroRect(pic.spec.box); try { cc.drawImage(unmask(endBuf, pic.v, pic.spec.w, pic.spec.h), r[0], r[1], r[2], r[3]); } catch (err) { endNow = null; } }
    if (!pic || blend) {
      r = heroRect(L.box);
      cc.globalAlpha = pic ? blend : 1;
      cc.drawImage(loopImg, (f % L.cols) * L.fw, Math.floor(f / L.cols) * L.fh, L.fw, L.fh, r[0], r[1], r[2], r[3]);
      cc.globalAlpha = 1;
    }
  }
  function drawPlain() {                                       // no art yet: a quiet seated silhouette
    if (drawn === 'plain') return; drawn = 'plain';
    cc.setTransform(DPR, 0, 0, DPR, 0, 0); cc.clearRect(0, 0, W, H);
    var c = heroPoint(HX, 760), r = 150 * seat().s * K;
    cc.fillStyle = 'rgba(200,210,235,.85)';
    cc.beginPath(); cc.arc(c[0], c[1] - r * 2.3, r * 0.45, 0, 7); cc.fill();
    cc.beginPath(); cc.ellipse(c[0], c[1] + r * 0.6, r * 1.6, r * 0.7, 0, 0, 7); cc.fill();
    cc.fillRect(c[0] - r * 0.55, c[1] - r * 1.8, r * 1.1, r * 2.2);
  }

  /* ── effects, drawn in code: Qi motes, the compression, the dawn's pulses, the storm's strikes, rings ──────── */
  var parts = [], rings = [], bolts = [], squeeze = 0, glow = 0, tint = LOOK === 'storm' ? [196, 170, 255] : LOOK === 'dawn' ? [255, 214, 140] : [150, 205, 255];
  function dantian() { return heroPoint(HX, DANTIAN); }
  function motes(ms) {                                          // Qi drifting in from all round to the Dantian
    var t0 = performance.now(), n = reduced ? 30 : 90;
    for (var i = 0; i < n; i++) parts.push({t: t0 + Math.random() * ms * 0.8, life: 900 + Math.random() * 900, a: Math.random() * 6.283, d: 0.35 + Math.random() * 0.45});
  }
  function ring(color, size, life) { rings.push({t: performance.now(), c: color, s: size, life: life || 1400}); }
  function strike(power) {                                      // a bolt from the eye of the storm to you
    var top = onStage(960 + (Math.random() - 0.5) * 160, 190), end = heroPoint(HX, 120 + 300), pts = [top], segs = 11;
    for (var i = 1; i < segs; i++) {
      var k = i / segs;
      pts.push([top[0] + (end[0] - top[0]) * k + (Math.random() - 0.5) * 70 * K * (1 - Math.abs(0.5 - k)), top[1] + (end[1] - top[1]) * k]);
    }
    pts.push(end);
    bolts.push({t: performance.now(), pts: pts, p: power});
    flash(0.35 + power * 0.2, '#E8DCFF');
    fs('boom'); fs('stun', null, 60);
    ring('rgba(210,190,255,', 260 * power, 900);
  }
  function flash(alpha, color) {
    if (reduced) alpha = Math.min(alpha, 0.25);
    var el = $('btflash'); el.style.background = color || '#fff';
    el.style.transition = 'none'; el.style.opacity = alpha; void el.offsetWidth;
    el.style.transition = 'opacity 700ms ease-out'; el.style.opacity = 0;
  }
  function drawFx(now) {
    fx.setTransform(DPR, 0, 0, DPR, 0, 0); fx.clearRect(0, 0, W, H);
    var d = dantian(), R = Math.max(W, H);
    if (squeeze > 0) {                                          // the world narrows to the Dantian
      var g = fx.createRadialGradient(d[0], d[1], R * (0.55 - squeeze * 0.45), d[0], d[1], R * (0.9 - squeeze * 0.4));
      g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,' + (0.85 * squeeze) + ')');
      fx.fillStyle = g; fx.fillRect(0, 0, W, H);
    }
    if (glow > 0) {
      var narrow = tall() ? 0.55 : 1;                           // a phone: the glow stays round the body, not a wash
      var g2 = fx.createRadialGradient(d[0], d[1], 0, d[0], d[1], 220 * K * (1 + glow) * narrow);
      g2.addColorStop(0, 'rgba(' + tint + ',' + Math.min(0.42, glow * 0.3) * (0.6 + 0.4 * narrow) + ')');   // a halo: you stay solid
      g2.addColorStop(0.55, 'rgba(' + tint + ',' + Math.min(0.16, glow * 0.12) + ')'); g2.addColorStop(1, 'rgba(' + tint + ',0)');
      fx.globalCompositeOperation = 'lighter'; fx.fillStyle = g2; fx.fillRect(0, 0, W, H); fx.globalCompositeOperation = 'source-over';
    }
    fx.globalCompositeOperation = 'lighter';
    parts = parts.filter(function (p) {
      var k = (now - p.t) / p.life; if (k < 0) return true; if (k >= 1) return false;
      var r = R * p.d * (1 - k * k), x = d[0] + Math.cos(p.a + k * 1.4) * r, y = d[1] + Math.sin(p.a + k * 1.4) * r * 0.75;
      fx.fillStyle = 'rgba(' + tint + ',' + (0.9 * Math.sin(k * 3.14)) + ')';
      fx.beginPath(); fx.arc(x, y, (2 + 3 * k) * Math.max(0.6, K * 1.6), 0, 7); fx.fill();
      return true;
    });
    rings = rings.filter(function (o) {
      var k = (now - o.t) / o.life; if (k >= 1) return false;
      fx.strokeStyle = o.c + (0.85 * (1 - k)) + ')'; fx.lineWidth = (10 * (1 - k) + 1.5) * Math.max(0.6, K * 1.3);
      fx.beginPath(); fx.ellipse(d[0], d[1], o.s * K * (0.2 + k), o.s * K * (0.2 + k) * 0.5, 0, 0, 7); fx.stroke();
      return true;
    });
    bolts = bolts.filter(function (b) {
      var k = (now - b.t) / 420; if (k >= 1) return false;
      [[10, 'rgba(170,140,255,'], [3, 'rgba(255,255,255,']].forEach(function (w) {
        fx.strokeStyle = w[1] + (1 - k) + ')'; fx.lineWidth = w[0] * (0.7 + b.p * 0.3) * Math.max(0.6, K * 1.4);
        fx.beginPath(); fx.moveTo(b.pts[0][0], b.pts[0][1]); for (var i = 1; i < b.pts.length; i++) fx.lineTo(b.pts[i][0], b.pts[i][1]); fx.stroke();
      });
      return true;
    });
    if (pillar) {                                               // heaven's golden pillar on a realm success
      var k2 = Math.min(1, (now - pillar) / 600), out = Math.max(0, 1 - (now - pillar - 2600) / 1400);
      if (out > 0) {
        var wdt = 200 * K * k2, x0 = d[0] - wdt / 2, gp = fx.createLinearGradient(x0, 0, x0 + wdt, 0);
        gp.addColorStop(0, 'rgba(255,220,140,0)'); gp.addColorStop(0.5, 'rgba(255,236,190,' + (0.3 * out) + ')'); gp.addColorStop(1, 'rgba(255,220,140,0)');
        fx.fillStyle = gp; fx.fillRect(x0, 0, wdt, d[1] + 120 * K);
      } else pillar = 0;
    }
    fx.globalCompositeOperation = 'source-over';
  }
  var pillar = 0;
  function loop(now) {
    if (up !== upTo) { up += Math.sign(upTo - up) * Math.min(Math.abs(upTo - up), 0.05); drawn = null; }
    drawChar(now); drawFx(now); requestAnimationFrame(loop);
  }
  resize(); requestAnimationFrame(loop);

  /* ── the Qi bar ─────────────────────────────────────────────────── */
  function bar(pct, text, cls) {
    $('btqifill').style.width = Math.max(0, Math.min(100, pct)) + '%';
    if (text != null) $('btqitext').textContent = text;
    $('btqi').className = 'btqi' + (cls ? ' ' + cls : '');
  }
  if (A && A.full) bar(100, null, A.ready ? 'press' : '');
  function say(t) { var el = $('btsay'); el.textContent = t; el.classList.remove('go'); void el.offsetWidth; el.classList.add('go'); }

  /* ── begin: a press for a phase gate, a 1-second hold for a realm gate (an injury can't come from a slip) ─── */
  var btn = $('btbegin');
  if (btn) {
    var holdT = null, holdAt = 0;
    var fill = $('btbeginfill');
    var hold = btn.classList.contains('hold');
    var stop = function () { if (holdT) { cancelAnimationFrame(holdT); holdT = null; fill.style.width = '0'; } };
    var tick = function () {
      var k = (performance.now() - holdAt) / 1000;
      fill.style.width = Math.min(100, k * 100) + '%';
      if (k >= 1) { holdT = null; begin(); return; }
      holdT = requestAnimationFrame(tick);
    };
    var press = function (e) {
      if (main.dataset.phase !== 'assess') return;
      if (e) e.preventDefault();
      if (!hold) { begin(); return; }
      if (holdT) return;
      holdAt = performance.now(); holdT = requestAnimationFrame(tick); fs('gather');
    };
    btn.addEventListener('pointerdown', press);
    ['pointerup', 'pointerleave', 'pointercancel'].forEach(function (ev) { btn.addEventListener(ev, stop); });
    btn.addEventListener('keydown', function (e) { if ((e.key === 'Enter' || e.key === ' ') && !e.repeat) press(e); });
    btn.addEventListener('keyup', function (e) { if (e.key === 'Enter' || e.key === ' ') stop(); });
    btn.addEventListener('click', function (e) { e.preventDefault(); });
  }
  var qbox = $('btquick');
  if (qbox) { qbox.checked = quick; qbox.addEventListener('change', function () { quick = qbox.checked; try { localStorage.setItem('ma.bt.quick', quick ? '1' : '0'); } catch (e) {} }); }

  var GATE = A ? 'ma.bt.tries.' + A.realm + ':' + A.layer : '', tries = 0;
  try { tries = parseInt(localStorage.getItem(GATE) || '0', 10) || 0; } catch (e1) {}
  var R = null, timers = [], skipped = false, shown = false, started = 0;
  function later(fn, ms) { timers.push(setTimeout(fn, ms)); }

  function begin() {
    if (main.dataset.phase !== 'assess') return;
    main.dataset.phase = 'rite'; started = performance.now(); upTo = 0;
    ambience();
    var keep = $('btkeep') && $('btkeep').checked;
    fetch('/breakthrough/attempt', {method: 'POST', headers: {'Content-Type': 'application/json'}, credentials: 'same-origin',
      body: JSON.stringify({token: A.token, keep_pill: !!keep})})
      .then(function (r) { return r.json(); })
      .then(function (v) {
        if (v.gone) { location.href = '/'; return; }
        if (v.error || !v.result) { refused(v.error || 'Something went wrong. Try again.'); return; }
        R = v.result;
        try { localStorage.setItem(GATE, String(tries + 1)); } catch (e) {}
      })
      .catch(function () { refused('The connection dropped. Look again before you try.'); });
    if (quick) { waitFor(function () { decide(true); }); return; }
    $('btskip').hidden = false;
    rite();
  }
  function refused(why) {
    timers.forEach(clearTimeout); timers = [];
    say(why);
    setTimeout(function () { location.reload(); }, 2200);
  }
  function waitFor(fn) {                                          // the result, when it has come
    (function check() { if (R) fn(); else if (main.dataset.phase === 'rite') setTimeout(check, 120); })();
  }
  $('btskip').addEventListener('click', function () { skipped = true; waitFor(function () { decide(true); }); });

  /* the ceremony, the same whatever is coming; then decide() shows what came */
  function rite() {
    var again = tries > 0, g = again ? 900 : (LOOK === 'storm' ? 1800 : 3000);
    if (A.first) say('This first gate cannot fail. Feel it open.');
    else if (again) say('Again. Gather yourself.');
    bar(100, 'Qi ' + A.qi + ' / ' + A.need, 'press');
    if (LOOK === 'inner') {
      if (window.SparMusic && !again) window.SparMusic.start('meditation');
      motes(g); fs('gather'); glow = 0.4;
      later(function () {                                        // the compression: everything narrows, a heartbeat, quiet
        if (window.SparMusic) window.SparMusic.stop();
        var t0 = performance.now();
        (function sq() { var k = Math.min(1, (performance.now() - t0) / 1100); squeeze = k; glow = 0.4 + k; if (k < 1 && main.dataset.phase === 'rite') requestAnimationFrame(sq); })();
        heartbeat(3);
      }, g);
      later(function () { waitFor(function () { decide(false); }); }, g + 1500);
    } else if (LOOK === 'dawn') {
      var off = again ? 2.4 : 0;
      still.classList.add('off');
      try { bg.currentTime = off; } catch (e) {}
      var pv = bg.play(); if (pv && pv.catch) pv.catch(function () {});
      var dsound = audio(SCN.sound, soundVol * 0.9); if (dsound && off) try { dsound.currentTime = off; } catch (e2) {}
      motes(3000); glow = 0.2;
      var t1 = 3600 - off * 1000;
      [0, 1400, 2800].forEach(function (dt, i) {
        later(function () { glow = 0.45 + i * 0.2; ring('rgba(255,226,160,', 240 + i * 90, 1300); fs('cast'); setTimeout(function () { glow = 0.2; }, 600); }, t1 + dt);
      });
      later(function () { waitFor(function () { decide(false); }); }, t1 + 3700);
    } else {
      motes(g); glow = 0.2; fs('gather');
      [0, 1500, 3000].forEach(function (dt, i) { later(function () { strike(1 + i * 0.5); }, g + dt); });
      later(function () { waitFor(function () { decide(false); }); }, g + 3900);
    }
  }
  function heartbeat(n) {
    if (!soundOn) return;
    try {
      var C = window.AudioContext || window.webkitAudioContext, ac = heartbeat.ac || (heartbeat.ac = new C());
      for (var i = 0; i < n; i++) [0, 0.22].forEach(function (d, j) {
        var t = ac.currentTime + i * 0.75 + d, o = ac.createOscillator(), gn = ac.createGain();
        o.type = 'sine'; o.frequency.setValueAtTime(j ? 52 : 60, t); o.frequency.exponentialRampToValueAtTime(34, t + 0.18);
        gn.gain.setValueAtTime(0.0001, t); gn.gain.exponentialRampToValueAtTime(0.6 * soundVol * (j ? 0.6 : 1), t + 0.02);
        gn.gain.exponentialRampToValueAtTime(0.0001, t + 0.25);
        o.connect(gn); gn.connect(ac.destination); o.start(t); o.stop(t + 0.3);
      });
    } catch (e) {}
  }

  /* ── the result ─────────────────────────────────────────────────── */
  function decide(fast) {
    if (shown) return;
    shown = true;
    timers.forEach(clearTimeout); timers = [];
    main.dataset.phase = 'result'; $('btskip').hidden = true;
    squeeze = 0; parts = [];
    var ok = R.ok, d = dantian(), title = 0;
    if (fast) {
      if (endNow) { try { endNow.v.pause(); } catch (e) {} endNow = null; }
      if (endSound) endSound.pause();
      if (!skipped || !ok) flash(ok ? 0.5 : 0.3, ok ? '#FFF1C8' : '#2A0A10');
      if (ok) { ring('rgba(255,226,160,', 420, 1600); fs('victory'); } else fs('defeat');
      glow = ok ? 0.6 : 0;
      title = 50;
    } else if (ok) {
      var name = LOOK === 'inner' ? 'inner' : 'ascend', v = playEnd(name);
      title = v ? (name === 'inner' ? 3300 : 3400) : 600;
      later(function () {
        flash(0.55, LOOK === 'inner' ? '#DCEEFF' : '#FFF1C8');
        ring(LOOK === 'inner' ? 'rgba(170,220,255,' : 'rgba(255,226,160,', 520, 1800);
        if (LOOK !== 'inner') pillar = performance.now();
        fs('victory'); fs('heal', null, 300); glow = 0.7;
        setTimeout(function () { glow = 0.2; }, 1400);
      }, title - 200);
    } else {
      var dv = playEnd('deviation');
      title = dv ? 1700 : 500;
      glow = 0;
      later(function () { flash(0.35, '#2A0A10'); scene.classList.add('shake'); fs('defeat'); setTimeout(function () { scene.classList.remove('shake'); }, 600); }, title - 250);
    }
    if (amb && LOOK === 'storm') { amb.volume = amb.volume * 0.5; }
    later(function () { showTitle(); qiAfter(); }, title);
    later(function () { showScroll(); }, title + (fast ? 900 : 2600));
  }
  function lotus(e) {
    var s = '<svg class="btlotus" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="47" fill="none" stroke="currentColor" stroke-width="1.2" opacity=".55"/>';
    for (var k = 0; k < e.petals; k++) s += '<path d="M50 50 C43.5 39 43.5 24 50 10 C56.5 24 56.5 39 50 50Z" fill="currentColor" fill-opacity=".16" stroke="currentColor" stroke-width="1.1" transform="rotate(' + (360 / e.petals * k).toFixed(2) + ' 50 50)"/>';
    return s + '<circle cx="50" cy="50" r="19" class="core"/><circle cx="50" cy="50" r="19" fill="none" stroke="currentColor" stroke-width="1.3"/><text x="50" y="50" text-anchor="middle" dominant-baseline="central" class="num">' + e.roman + '</text></svg>';
  }
  function showTitle() {
    var t = $('bttitle'), a = R.after, extra = R.ok ? R.layers - 1 : 0;
    t.className = 'bttitle ' + (R.ok ? 'win' : 'lose');
    $('btemb').innerHTML = R.ok ? lotus(a.emblem) : '';
    if (R.ok && R.realm_up) {
      $('bttkick').textContent = 'REALM BREAKTHROUGH';
      $('btthead').textContent = a.realm; $('bttsub').textContent = a.layer + ' Layer · ' + a.phase;
    } else if (R.ok) {
      $('bttkick').textContent = 'BOTTLENECK BROKEN';
      $('btthead').textContent = a.phase; $('bttsub').textContent = a.realm + ' · ' + a.layer + ' Layer';
    } else {
      $('bttkick').textContent = R.kind === 'realm' ? 'BREAKTHROUGH FAILED' : 'THE BOTTLENECK HOLDS';
      $('btthead').textContent = R.kind === 'realm' ? 'Your meridians recoil' : 'The gate holds';
      $('bttsub').textContent = '−' + R.lost + ' Qi' + (R.injury ? ' · injured for ' + R.injury : '');
    }
    var L = $('btlayers');
    if (extra > 0) { L.hidden = false; L.textContent = '+' + extra + ' more layer' + (extra > 1 ? 's' : '') + ' from the Qi that waited'; }
    t.hidden = false; void t.offsetWidth; t.classList.add('go');
  }
  function qiAfter() {
    var a = R.after;
    if (R.ok) {
      bar(0, null, 'flood');
      setTimeout(function () { bar(a.pct, 'Qi ' + a.qi + ' / ' + a.need); }, 500);
    } else {
      bar(80, '−' + R.lost + ' Qi', 'lost');
      setTimeout(function () { bar(a.pct, 'Qi ' + a.qi + ' / ' + a.need + (a.waiting ? ' · ' + a.waiting + ' still waiting' : '')); }, 1400);
    }
  }
  function showScroll() {
    var b = R.before, a = R.after, rows = [];
    $('btreskick').textContent = R.ok ? (R.realm_up ? 'A NEW REALM' : 'A NEW PHASE') : 'NOT THIS TIME';
    $('btresh').textContent = R.ok ? (R.realm_up ? a.realm : a.phase) : (R.kind === 'realm' ? 'Breakthrough failed' : 'The bottleneck holds');
    rows.push(['Before', b.realm + ' · ' + b.layer + ' Layer']);
    rows.push(['Now', a.realm + ' · ' + a.layer + ' Layer']);
    rows.push(['Your chance', R.chance]);
    if (R.pill) rows.push(['Pill', R.pill + ' (used)']);
    if (!R.ok) rows.push(['Qi lost', R.lost]);
    if (R.injury) rows.push(['Injured', R.injury]);
    rows.push(['Qi', a.qi + ' / ' + a.need + (a.waiting ? ' · ' + a.waiting + ' waiting' : '')]);
    $('btrows').innerHTML = rows.map(function (r) { return '<div><span></span><b></b></div>'; }).join('');
    Array.prototype.forEach.call($('btrows').children, function (el, i) { el.firstChild.textContent = rows[i][0]; el.lastChild.textContent = rows[i][1]; });
    $('btlines').innerHTML = R.lines.map(function (l) { return '<li>' + l + '</li>'; }).join('');   // the server escapes them
    $('btdew').innerHTML = '';
    R.dew.forEach(function (d) {
      var c = document.createElement('div'); c.className = 'btchip';
      if (d.picture) { var im = document.createElement('img'); im.src = d.picture; im.alt = ''; im.width = 30; im.height = 30; c.appendChild(im); }
      var sp = document.createElement('span'); sp.textContent = "Heaven's dew: " + d.name + (d.qty > 1 ? ' ×' + d.qty : ''); c.appendChild(sp);
      $('btdew').appendChild(c);
    });
    $('btagain').hidden = R.ok;
    $('btresult').hidden = false; upTo = 1;
    var card = $('btcard'); if (card) card.hidden = true;
  }
})();
