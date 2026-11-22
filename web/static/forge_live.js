/* The live forge (forge_play.html #flive; web/forge_live.py decides everything; docs/web.md "Live forge").

   Same handshake as the live alchemy (static/alchemy_live.js): the page asks for the stage (/forge/live), shows its
   intro, says it began (/forge/live/begin) and starts its own clock at that moment; every press goes to
   /forge/live/press and the server times it. The page shows its own guess at once and the server's verdict after.
   Quench and Inscribe are still the bot's button decisions here (/forge/live/act).

   The smith is SHOAIB's videos as frame sheets (scripts/make_forge_sheets.py): the bellows move only while you pump,
   the hammer falls when you strike. Keys: Space = the stage's main action (pump / pull / hard strike), V = vent,
   K = light strike, R = reheat. */
(function () {
  'use strict';
  var root = document.getElementById('flive');
  if (!root) return;
  var $ = function (id) { return document.getElementById(id); };
  var scene = $('fscene'), hint = $('lhint'), kick = $('lkick'), banner = $('lbanner'), btns = $('lbtns'), fill = $('lfill');
  var furnace = scene.querySelector('.ffurnace'), fctx = furnace.getContext('2d');
  var heatCv = scene.querySelector('.fheat'), hctx = heatCv.getContext('2d');
  var spotCv = scene.querySelector('.fspot'), sctx = spotCv.getContext('2d');
  var over = scene.querySelector('.fover'), octx = over.getContext('2d');
  var anvilBlank = scene.querySelector('.fblank.onanvil'), blankImg = scene.querySelector('.fblank.inforge');
  var sparks = scene.querySelector('.fsparks');
  var gear = root.dataset.gear;
  var calm = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var FW = furnace.width, FH = furnace.height;
  var COLORS = [[122, 42, 34], [192, 57, 43], [247, 148, 60], [245, 208, 74], [255, 246, 224]];

  var cur = null, ending = false, firstApply = true;
  function Snd(n) { if (window.AlchemySound) window.AlchemySound.play(n); }

  // ── the server ──
  function post(url, data) {
    return fetch(url, {method: 'POST', body: new URLSearchParams(data), credentials: 'same-origin', cache: 'no-store',
                       headers: {'Content-Type': 'application/x-www-form-urlencoded'}}).then(function (r) { return r.json(); });
  }
  function getState() { return fetch('/forge/live', {credentials: 'same-origin', cache: 'no-store'}).then(function (r) { return r.json(); }); }
  function press(data) {
    if (!cur || !cur.live) return Promise.resolve(null);
    var id = cur.id;
    data.id = id;
    return post('/forge/live/press', data).then(function (r) {
      var st = r.state;
      if (st && (st.gone || st.done || !st.live || st.live.id !== id) && cur && cur.id === id) finishStage(st);
      return r.reply;
    }).catch(function () { return null; });
  }

  // ── the smith's frame sheets ──
  function Sheet(el) {
    if (!el) return null;
    var m = JSON.parse(el.dataset.sheet);
    el.style.backgroundSize = (m.cols * 100) + '% ' + (m.rows * 100) + '%';
    var me = {m: m, el: el, at: 0, show: function (i) {
      i = Math.max(0, Math.min(m.frames - 1, Math.round(i)));
      me.at = i;
      var c = i % m.cols, r = Math.floor(i / m.cols);
      el.style.backgroundPosition = (m.cols > 1 ? c / (m.cols - 1) * 100 : 0) + '% ' + (m.rows > 1 ? r / (m.rows - 1) * 100 : 0) + '%';
    }};
    me.show(0);
    return me;
  }
  var bellows = Sheet(scene.querySelector('.fbellows')), hammer = Sheet(scene.querySelector('.fhammer'));
  var qsheets = {water: Sheet(scene.querySelector('.fqwater')), oil: Sheet(scene.querySelector('.fqoil'))};
  var qset = scene.querySelector('.fqset'), plate = $('fplate'), runeCv = scene.querySelector('.frune'), rctx = runeCv.getContext('2d');
  var runeGlow = scene.querySelector('.fruneglow');

  // ── little helpers ──
  var bannerTimer;
  function flash(text, kind, ms) {
    banner.textContent = text; banner.className = 'lbanner on' + (kind ? ' ' + kind : '');
    clearTimeout(bannerTimer); bannerTimer = setTimeout(function () { banner.className = 'lbanner'; }, ms || 900);
  }
  function show(id, on) { $(id).hidden = !on; }
  function now() { return cur && cur.t0 !== null ? (performance.now() - cur.t0) / 1000 : 0; }
  function setLog(lines) {
    var box = $('llog'); box.innerHTML = '';
    (lines || []).forEach(function (h) { var p = document.createElement('p'); p.className = 'flog'; p.innerHTML = h; box.appendChild(p); });
  }
  function track(state) {
    var rows = document.querySelectorAll('.track .stg:not(.total)');
    (state.points || []).forEach(function (pt, i) {
      var row = rows[i]; if (!row) return;
      row.classList.toggle('on', !!pt.active); row.classList.toggle('done', pt.pts !== null);
      var b = row.querySelector('b'); if (b) b.textContent = pt.pts !== null ? pt.pts : '—';
    });
    var tot = document.querySelector('.track .stg.total b'); if (tot) tot.textContent = state.total + ' / 100';
  }
  function setStageClass(k) {
    scene.classList.remove('st-ignite', 'st-heat', 'st-hammer', 'st-quench', 'st-inscribe', 'st-other', 'hot', 'steam');
    scene.classList.add('st-' + (S[k] ? k : 'other'));
  }
  function button(label, key, on, kind) {
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'btn ' + (kind || 'btn-gold'); b.innerHTML = label + (key ? '<kbd>' + key + '</kbd>' : '');
    b.addEventListener('pointerdown', function (e) { e.preventDefault(); if (b.setPointerCapture) b.setPointerCapture(e.pointerId); on('down', b); });
    ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(function (n) { b.addEventListener(n, function () { on('up', b); }); });
    b.addEventListener('contextmenu', function (e) { e.preventDefault(); });
    btns.appendChild(b);
    return b;
  }
  function mix(a, b, k) { return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k]; }
  function colorAt(c) {                       // c: 0..5 continuous (5 = past white)
    if (c < 0) return mix([70, 70, 74], COLORS[0], Math.max(0, 1 + c));
    var i = Math.min(4, Math.floor(c)), k = Math.min(1, c - i);
    return i >= 4 ? COLORS[4] : mix(COLORS[i], COLORS[i + 1], k);
  }
  function rgb(c, a) { return 'rgba(' + Math.round(c[0]) + ',' + Math.round(c[1]) + ',' + Math.round(c[2]) + ',' + (a === undefined ? 1 : a) + ')'; }

  // the furnace: its glow, sparks and smoke follow the heat (0..100)
  var embers = [];
  function drawFurnace(heat, pumping, t) {
    fctx.clearRect(0, 0, FW, FH);
    var x = FW * 0.4, y = FH * 0.52, k = Math.max(0, Math.min(1, heat / 100));
    var g = fctx.createRadialGradient(x, y, 10, x, y, FW * (0.12 + 0.16 * k));
    g.addColorStop(0, 'rgba(255,' + Math.round(150 + 90 * k) + ',' + Math.round(60 + 120 * k * k) + ',' + (0.35 + 0.55 * k) + ')');
    g.addColorStop(0.5, 'rgba(230,90,30,' + (0.15 + 0.35 * k) + ')');
    g.addColorStop(1, 'rgba(120,30,10,0)');
    fctx.fillStyle = g; fctx.fillRect(0, 0, FW, FH);
    scene.style.setProperty('--room', (0.62 + 0.38 * k).toFixed(2));
    if (!calm && (pumping || k > 0.75) && Math.random() < 0.6 + k) embers.push({x: x + (Math.random() - 0.5) * 120, y: y, vx: (Math.random() - 0.5) * 60, vy: -80 - 160 * Math.random() * (0.5 + k), life: 1});
    embers = embers.filter(function (e) { return e.life > 0; });
    embers.forEach(function (e) {
      e.x += e.vx / 60; e.y += e.vy / 60; e.vy += 30 / 60; e.life -= 1 / 50;
      fctx.fillStyle = 'rgba(255,' + Math.round(180 * e.life + 60) + ',60,' + e.life + ')';
      fctx.fillRect(e.x, e.y, 3, 3);
    });
    if (k > 0.82) {                           // too hot: smoke rolls out of the furnace mouth
      octx.save(); octx.globalAlpha = Math.min(0.5, (k - 0.82) * 3);
      for (var i = 0; i < 6; i++) {
        var sy = FH * 0.42 - ((t * 40 + i * 37) % 160), sx = FW * 0.4 + Math.sin(t * 2 + i) * 30;
        var sg = octx.createRadialGradient(sx, sy, 5, sx, sy, 60); sg.addColorStop(0, 'rgba(60,55,55,.8)'); sg.addColorStop(1, 'rgba(60,55,55,0)');
        octx.fillStyle = sg; octx.beginPath(); octx.arc(sx, sy, 60, 0, 2 * Math.PI); octx.fill();
      }
      octx.restore();
    }
  }

  // ── the stages ──
  var S = {};

  // 🔥 Ignite: pump (hold), vent (tap); the coals burn down
  S.ignite = {
    title: 'Ignite the Forge', keys: 'Hold Space (or Pump) to work the bellows · V (or Vent) dumps heat fast',
    setup: function (c) {
      var p = c.pub;
      c.st = {heat: p.heat, speed: 0, pumping: false, k: 0, lastVent: -99, counted: 0, inside: 0, frame: 0};
      show('lgauge', true);
      btns.innerHTML = '';
      c.st.pumpBtn = button('💨 Pump', 'Space', function (e) { if (e === 'down') pump(c, true); else pump(c, false); }, 'btn-jade');
      c.st.ventBtn = button('🌬️ Vent', 'V', function (e) { if (e === 'down') vent(c); });
      show('lbtns', true);
    },
    tick: function (c, t) {
      var p = c.pub, s = c.st, steps = Math.min(Math.floor(t / p.tick), Math.round(p.length / p.tick));
      while (s.k < steps) {                   // the same simulation as forge_live.ignite_run
        var tt = s.k * p.tick, rest = p.down * (1 + p.burn * tt / p.length), want = s.pumping ? p.up : -rest;
        s.speed += (want - s.speed) * Math.min(1, p.tick / p.ease);
        s.heat = Math.max(0, Math.min(100, s.heat + (s.speed + pushAt(p, tt)) * p.tick));
        if (tt >= p.warmup) { s.counted++; if (s.heat >= p.lo && s.heat <= p.lo + p.width) s.inside++; }
        s.k++;
      }
      if (bellows && s.pumping) { s.frame = (s.frame + bellows.m.fps / 60) % bellows.m.frames; bellows.show(s.frame); }
      var heat = s.heat, mood = heat < p.lo ? 'cold' : heat > p.lo + p.width ? 'hot' : 'zone';
      $('lband').style.left = p.lo + '%'; $('lband').style.width = p.width + '%';
      $('lneedle').style.left = heat + '%'; $('lheat').textContent = Math.round(heat) + '°';
      scene.classList.toggle('hot', mood === 'hot' && heat > 92);
      octx.clearRect(0, 0, FW, FH);
      drawFurnace(heat, s.pumping, t);
      var cool = t - s.lastVent < p.cooldown || jammed(p, t);
      s.ventBtn.classList.toggle('cool', cool);
      var omen = '';
      p.gusts.forEach(function (g) {
        if (t >= g[0] - p.omen && t < g[0]) omen = g[1] > 0 ? 'The wind gusts into the bellows… the fire will leap!' : 'A cold draught creeps under the forge…';
        else if (t >= g[0] && t < g[0] + p.gust) omen = g[1] > 0 ? '🔥 A gust feeds the fire!' : '🌬️ The draught chills the coals!';
      });
      if (p.jam) {
        if (t >= p.jam[0] - p.jamomen && t < p.jam[0]) omen = '⚠️ The damper creaks… the vent is about to stick!';
        else if (jammed(p, t)) omen = '⚠️ The vent is stuck! Stop pumping to cool it.';
      }
      if (p.flare) {
        if (t >= p.flare[0] - p.flareomen && t < p.flare[0]) omen = '🔥 The coals hiss… a flare-up is coming!';
        else if (t >= p.flare[0] && t < p.flare[0] + p.flare[1]) omen = '🔥 FLARE-UP! Vent it, stop pumping!';
      }
      if (omen && omen !== s.lastOmen) Snd('warn');
      s.lastOmen = omen;
      var share = s.counted ? s.inside / s.counted : 0;
      hint.textContent = omen || (t < p.warmup ? 'Bring the forge into the band.' : mood === 'zone' ? 'A clean orange fire hums in the forge. In the band ' + Math.round(share * 100) + '%'
        : mood === 'cold' ? 'The coals glow dull and sleepy. Pump!' : 'Sparks roar out of the forge mouth! Let it cool, or vent.');
    }
  };
  function pushAt(p, t) {
    var push = p.flare && p.flare[0] <= t && t < p.flare[0] + p.flare[1] ? p.flarepush : 0;
    p.gusts.forEach(function (g) { if (g[0] <= t && t < g[0] + p.gust) push += g[1] * p.push; });
    return push;
  }
  function jammed(p, t) { return !!p.jam && p.jam[0] <= t && t < p.jam[0] + p.jam[1]; }
  function pump(c, on) {
    if (!c.st || c.st.pumping === on) return;
    c.st.pumping = on;
    c.st.pumpBtn.classList.toggle('held', on);
    if (on) Snd('whoosh');
    press({do: on ? 'pump' : 'rest'});
  }
  function vent(c) {
    var p = c.pub, s = c.st, t = now();
    if (t - s.lastVent < p.cooldown || jammed(p, t)) { flash(jammed(p, t) ? 'The vent is stuck!' : 'The vent is still open…', 'bad', 600); press({do: 'vent'}); return; }
    s.lastVent = t; s.heat = Math.max(0, s.heat - p.vent);
    Snd('whoosh'); flash('🌬️ Vent!', '', 500);
    press({do: 'vent'});
  }

  // 🌡️ Heat: watch the colour, pull it out at the target
  S.heat = {
    title: 'Heat the Metal', keys: 'Space (or Pull it out) when the metal glows the target colour',
    setup: function (c) {
      var p = c.pub, tc = colorAt(p.target);
      c.st = {pulled: null};
      $('lswatchc').textContent = p.colors[p.target]; $('lswatchc').style.background = rgb(tc);
      $('lswatch').style.setProperty('--sw', rgb(tc));
      show('lswatch', true);
      btns.innerHTML = '';
      button('🪝 Pull it out', 'Space', function (e) { if (e === 'down') pull(c); }, 'btn-jade');
      show('lbtns', true);
    },
    tick: function (c, t) {
      var p = c.pub, s = c.st, tl = s.pulled !== null ? s.pulled : t, b = p.bounds;
      var i = 0; while (i + 1 < b.length && b[i + 1] <= tl) i++;
      var cc = i >= b.length - 1 ? 5 : i + (tl - b[i]) / (b[i + 1] - b[i]);
      if (p.shimmer && !calm && s.pulled === null) cc += 0.35 * Math.sin(t * 23) * Math.random();
      octx.clearRect(0, 0, FW, FH);
      drawFurnace(55 + cc * 8, false, t);
      drawHeat(cc, p.uneven, t, s.pulled !== null);
      var name = cc >= 5 ? 'burning!' : p.colors[Math.max(0, Math.min(4, Math.floor(cc)))];
      hint.textContent = s.pulled !== null ? 'You pull it out…' : cc >= 4.6 ? 'White-hot and spitting sparks: it is about to burn!'
        : 'The metal glows ' + name + (p.uneven ? ' (the tip runs ahead: judge the middle)' : '') + '.';
    }
  };
  function drawHeat(cc, uneven, t, pulled) {
    var W = heatCv.width, H = heatCv.height;
    hctx.clearRect(0, 0, W, H);
    if (!blankImg.complete || !blankImg.naturalWidth) return;
    var bw = gear === 'weapon' ? W * 0.62 : W * 0.24, bh = bw * blankImg.naturalHeight / blankImg.naturalWidth;
    hctx.save();
    hctx.translate(W * 0.5, H * 0.52);
    if (gear !== 'weapon') hctx.scale(1, 0.55);
    hctx.drawImage(blankImg, -bw / 2, -bh / 2, bw, bh);
    hctx.globalCompositeOperation = 'source-atop';
    var g = hctx.createLinearGradient(-bw / 2, 0, bw / 2, 0);
    var d = uneven ? 0.7 : 0;
    g.addColorStop(0, rgb(colorAt(cc - d), 0.88)); g.addColorStop(0.5, rgb(colorAt(cc), 0.88)); g.addColorStop(1, rgb(colorAt(cc + d), 0.88));
    hctx.fillStyle = g; hctx.fillRect(-bw / 2, -bh / 2, bw, bh);
    hctx.restore();
    hctx.save(); hctx.globalCompositeOperation = 'lighter';               // its own glow
    var gl = hctx.createRadialGradient(W * 0.5, H * 0.52, 5, W * 0.5, H * 0.52, bw * 0.6);
    gl.addColorStop(0, rgb(colorAt(cc), 0.25 + 0.1 * Math.min(cc, 5))); gl.addColorStop(1, rgb(colorAt(cc), 0));
    hctx.fillStyle = gl; hctx.fillRect(0, 0, W, H); hctx.restore();
    if (cc >= 4.4 && !pulled && !calm) {                                // overheating: spitting sparks
      for (var i = 0; i < 8; i++) { hctx.fillStyle = 'rgba(255,240,200,' + Math.random() + ')'; hctx.fillRect(W * 0.5 + (Math.random() - 0.5) * bw, H * 0.5 - Math.random() * 60, 3, 3); }
    }
  }
  function pull(c) {
    if (c.st.pulled !== null) return;
    var t = now(); c.st.pulled = t;
    var p = c.pub, b = p.bounds, i = 0; while (i + 1 < b.length && b[i + 1] <= t) i++;
    var miss = i >= b.length - 1 ? 9 : Math.abs(i - p.target);
    flash(miss === 0 ? '🌡️ Right on the colour!' : miss === 1 ? 'Close: one colour off' : i >= b.length - 1 ? 'Burnt!' : 'Off colour', miss === 0 ? 'good' : miss === 1 ? '' : 'bad', 1100);
    Snd(miss === 0 ? 'chime' : miss === 1 ? 'good' : 'bad');
    press({do: 'pull'});
  }

  // 🔨 Hammer: strike when the spot slides under the hammer; hard, light or reheat as the metal asks
  var HIT = {x: 0.486, y: 0.587};                                        // where the hammer lands (the set's pixels)
  var LINE = {weapon: [[0.30, 0.625], [0.76, 0.575]], armor: [[0.40, 0.575], [0.66, 0.575]], artifact: [[0.43, 0.585], [0.63, 0.585]]};
  S.hammer = {
    title: 'Hammer', keys: 'Space / J = Hard strike · K = Light tap · R = Reheat',
    setup: function (c) {
      c.st = {acts: {}, good: 0, frame: 0, anim: null};
      btns.innerHTML = '';
      button('🔨 Hard', 'J', function (e) { if (e === 'down') strike(c, 'hard'); });
      button('🪶 Light', 'K', function (e) { if (e === 'down') strike(c, 'light'); });
      button('🔥 Reheat', 'R', function (e) { if (e === 'down') strike(c, 'reheat'); });
      show('lbtns', true);
      anvilBlank.style.setProperty('--shape', 0.8);
    },
    tick: function (c, t) {
      var p = c.pub, s = c.st, i = strikeAt(p, t);
      octx.clearRect(0, 0, FW, FH);
      drawFurnace(45, false, t);
      animateHammer(s);
      sctx.clearRect(0, 0, spotCv.width, spotCv.height);
      if (i === null) { hint.textContent = 'Steady…'; anvilBlank.style.filter = ''; return; }
      var st = p.strikes[i], state = st.state, glow = {true: 'brightness(1.35) drop-shadow(0 0 10px #fff3c0) drop-shadow(0 0 4px #ffd27a)',
        dull: 'brightness(1.05) sepia(.6) saturate(2.4) hue-rotate(-18deg) drop-shadow(0 0 18px #ff7a2a) blur(.4px)',
        cooling: 'brightness(.55) sepia(.8) saturate(2) hue-rotate(-30deg) drop-shadow(0 0 3px #7a2a22)'}[state];
      anvilBlank.style.filter = glow;
      var line = LINE[gear], W = spotCv.width, H = spotCv.height, sweep = st.end - st.start;
      var u0 = (HIT.x - line[0][0]) / (line[1][0] - line[0][0]);
      function spotAt(under, tt) {
        var u = u0 + (tt - under) / sweep;
        if (st.wobble) u += st.wobble * Math.sin(2 * Math.PI * (tt - under) / sweep) * 0.5;
        return {x: (line[0][0] + (line[1][0] - line[0][0]) * u) * W, y: (line[0][1] + (line[1][1] - line[0][1]) * u) * H, u: u};
      }
      sctx.strokeStyle = 'rgba(255,255,255,.35)'; sctx.setLineDash([4, 5]);                   // where the hammer falls
      sctx.beginPath(); sctx.moveTo(HIT.x * W, HIT.y * H - 40); sctx.lineTo(HIT.x * W, HIT.y * H + 12); sctx.stroke(); sctx.setLineDash([]);
      if (state !== 'cooling') {
        if (st.decoy !== undefined) {
          var d = spotAt(st.decoy, t);
          if (d.u > -0.1 && d.u < 1.1 && Math.random() < 0.75) dot(d.x, d.y, 9, 'rgba(255,200,150,.45)');
        }
        st.under.forEach(function (u, k) {
          var sp = spotAt(u, t);
          if (sp.u < -0.15 || sp.u > 1.15) return;
          var near = Math.abs(t - u) <= p.window, done = (s.acts[i] || []).length > k;
          dot(sp.x, sp.y, near ? 14 : 11, done ? 'rgba(168,240,210,.9)' : near ? 'rgba(255,255,255,1)' : 'rgba(255,214,102,.95)');
          if (near && !done) { sctx.strokeStyle = 'rgba(255,255,255,.9)'; sctx.lineWidth = 3; sctx.beginPath(); sctx.arc(sp.x, sp.y, 20, 0, 2 * Math.PI); sctx.stroke(); }
        });
      }
      var n = i + 1, total = p.strikes.length;
      hint.innerHTML = 'Strike ' + n + ' of ' + total + ': ' + {true: 'the metal <b>rings bright</b> → strike <b>HARD</b> as the spot passes under the hammer',
        dull: 'a <b>soft, spreading glow</b> → a <b>LIGHT</b> tap as the spot passes under', cooling: 'the <b>glow is fading</b> → <b>REHEAT</b> it'}[state]
        + (st.under.length > 1 && state !== 'cooling' ? ' · <b>two spots</b>: hit both' : '');
    }
  };
  function dot(x, y, r, color) {
    sctx.save(); sctx.shadowColor = color; sctx.shadowBlur = 16; sctx.fillStyle = color;
    sctx.beginPath(); sctx.arc(x, y, r, 0, 2 * Math.PI); sctx.fill(); sctx.restore();
  }
  function strikeAt(p, t) {
    for (var i = 0; i < p.strikes.length; i++) {
      var nxt = i + 1 < p.strikes.length ? p.strikes[i + 1].start : p.length;
      if (p.strikes[i].start - 0.1 <= t && t < nxt) return i;
    }
    return null;
  }
  function animateHammer(s) {
    if (!hammer) return;
    if (!s.anim) { hammer.show(0); return; }
    var a = s.anim, el = (performance.now() - a.t) / 1000, m = hammer.m;
    var downFrames = m.impact - 4, f = el < downFrames / (m.fps * 2.4) ? 4 + el * m.fps * 2.4 : m.impact + (el - downFrames / (m.fps * 2.4)) * m.fps * 1.6;
    if (f >= m.frames - 1) { s.anim = null; hammer.show(0); return; }
    hammer.show(f);
  }
  function strike(c, what) {
    var p = c.pub, s = c.st, t = now(), i = strikeAt(p, t);
    if (i === null) return;
    s.acts[i] = s.acts[i] || [];
    var st = p.strikes[i], want = {true: 'hard', dull: 'light', cooling: 'reheat'}[st.state];
    if (s.acts[i].length >= (st.state === 'cooling' ? 1 : st.under.length)) return;
    s.acts[i].push([t, what]);
    if (what === 'reheat') {
      flash(want === 'reheat' ? '🔥 Reheated in time' : '💢 It wanted a ' + want + ' blow', want === 'reheat' ? 'good' : 'bad', 900);
      Snd(want === 'reheat' ? 'good' : 'bad');
    } else {
      s.anim = {t: performance.now()};
      var on = st.under.some(function (u) { return Math.abs(t - u) <= p.window; });
      var ok = what === want && on;
      setTimeout(function () {                                             // the blow lands
        Snd(ok ? 'clang' : 'bad');
        if (sparks && !calm) { sparks.currentTime = 0; sparks.style.opacity = what === 'hard' ? 1 : 0.5; sparks.classList.add('on'); var pr = sparks.play(); if (pr && pr.catch) pr.catch(function () {}); }
        if (ok) { s.good++; anvilBlank.style.setProperty('--shape', (0.8 + 0.2 * s.good / p.strikes.length).toFixed(3)); }
        flash(ok ? (what === 'hard' ? '🔨 A clean, ringing blow!' : '🪶 A gentle tap, just right') : what !== want ? '💢 It wanted ' + (want === 'reheat' ? 'reheating' : 'a ' + want + ' blow') : '💢 Off the spot!', ok ? 'good' : 'bad', 800);
      }, 120);
    }
    press({do: what});
  }
  if (sparks) sparks.addEventListener('ended', function () { sparks.classList.remove('on'); });

  // 💦 Quench: choose water or oil; the blade cools in real time; plunge it at the target
  var TLO = 300, THI = 950;
  function tpct(x) { return Math.max(0, Math.min(100, (x - TLO) / (THI - TLO) * 100)); }
  S.quench = {
    title: 'Quench', keys: '1 = Water · 2 = Oil, then Space (or Plunge) at the target temperature',
    setup: function (c) {
      c.st = {medium: null, chose: null, plunged: null, temp: c.pub.start, k: 0, anim: null};
      qset.dataset.medium = 'water';
      show('lgauge', true);
      $('lband').style.width = '0';
      btns.innerHTML = '';
      var w = c.pub.max;
      c.st.bw = button('💧 Water · up to ' + w.water, '1', function (e) { if (e === 'down') choose(c, 'water'); });
      c.st.bo = button('🛢️ Oil · up to ' + w.oil, '2', function (e) { if (e === 'down') choose(c, 'oil'); });
      c.st.bw.addEventListener('pointerenter', function () { if (!c.st.medium) qset.dataset.medium = 'water'; });
      c.st.bo.addEventListener('pointerenter', function () { if (!c.st.medium) qset.dataset.medium = 'oil'; });
      show('lbtns', true);
    },
    tick: function (c, t) {
      var p = c.pub, s = c.st;
      octx.clearRect(0, 0, FW, FH);
      drawFurnace(35, false, t);
      if (!s.medium) {
        hint.innerHTML = 'Choose the quench: <b>Water</b> is fast and risky (narrow window, up to ' + p.max.water + '), <b>Oil</b> slow and safe (wide window, up to ' + p.max.oil + ').';
        $('lneedle').style.left = tpct(p.start) + '%'; $('lheat').textContent = p.start + '°';
        return;
      }
      var since = (s.plunged !== null ? s.plunged : t) - s.chose, steps = Math.floor(Math.max(0, since) / p.tick);
      var rate0 = p.cool * p.medium[s.medium];
      while (s.k < steps) {                     // the same as forge_live.quench_temp
        var tt = s.k * p.tick, rate = rate0;
        if (p.wave) rate *= 1 + 0.3 * Math.sin(p.wave[1] * 2 * Math.PI * tt + p.wave[0]);
        if (p.rush) rate *= 1 + 0.6 * Math.max(0, 1 - (s.temp - p.target) / 250);
        s.temp -= rate * p.tick; s.k++;
      }
      var steam = p.steam.some(function (x) { return since >= x[0] && since < x[0] + x[1]; }) && s.plunged === null;
      scene.classList.toggle('steam', steam);
      $('lneedle').style.opacity = steam ? 0 : 1;
      $('lheat').textContent = steam ? 'steam!' : Math.round(s.temp) + '°';
      $('lneedle').style.left = tpct(s.temp) + '%';
      var sheet = qsheets[s.medium];
      if (sheet) {
        if (s.anim) {
          var f = s.anim.from + (performance.now() - s.anim.t) / 1000 * sheet.m.fps * 1.5;
          if (f >= sheet.m.frames - 1) { f = sheet.m.frames - 1; }
          sheet.show(f);
        } else sheet.show(Math.max(0, Math.min(1, (p.start - s.temp) / Math.max(1, p.start - p.target))) * (sheet.m.impact - 5));
      }
      var half = p.window[s.medium] / 2, off = Math.abs(s.temp - p.target);
      hint.innerHTML = s.plunged !== null ? 'The steel hisses…' : steam ? 'Steam hides the thermometer: read the blade\'s glow!'
        : 'Plunge at <b>' + p.target + '°</b> (± ' + Math.round(half) + '°). ' + (off <= half / 2 ? '<b>Now!</b>' : s.temp > p.target ? 'Still too hot…' : 'It\'s getting cold!');
    }
  };
  function choose(c, medium) {
    var s = c.st;
    if (s.medium) return;
    s.medium = medium; s.chose = now();
    qset.dataset.medium = medium;
    var p = c.pub, half = p.window[medium] / 2;
    $('lband').style.left = tpct(p.target - half) + '%'; $('lband').style.width = (tpct(p.target + half) - tpct(p.target - half)) + '%';
    btns.innerHTML = '';
    button('💦 Plunge', 'Space', function (e) { if (e === 'down') plunge(c); }, 'btn-jade');
    flash(medium === 'water' ? '💧 The water trough' : '🛢️ The oil bath', '', 700);
    press({do: medium});
  }
  function plunge(c) {
    var s = c.st, p = c.pub;
    if (!s.medium || s.plunged !== null) return;
    s.plunged = now();
    var half = p.window[s.medium] / 2, off = Math.abs(s.temp - p.target), sheet = qsheets[s.medium];
    if (sheet) s.anim = {t: performance.now(), from: Math.max(0, sheet.m.impact - 4)};
    var top = off <= half / 2, okish = off <= half;
    flash(top ? '💦 A perfect quench!' : okish ? 'Close enough' : 'The steel shudders…', top ? 'good' : okish ? '' : 'bad', 1400);
    Snd(s.medium === 'water' ? 'hiss' : 'roar');
    setTimeout(function () { Snd(top ? 'chime' : okish ? 'good' : 'bad'); }, 500);
    press({do: 'plunge'});
  }

  // ✍️ Inscribe: draw each stroke on the plate, in the clue's order
  var STROKE = {horizontal: ['横', '→', 'Horizontal'], vertical: ['竖', '↓', 'Vertical'], sweep: ['撇', '↙', 'Sweep'],
                press: ['捺', '↘', 'Press'], dot: ['点', '•', 'Dot'], hook: ['钩', '↩', 'Hook']};
  S.inscribe = {
    title: 'Inscribe', keys: 'Draw each stroke on the plate (drag; a tap is a dot), or use the stroke buttons',
    setup: function (c) {
      var p = c.pub;
      c.st = {i: 0, path: null, marks: []};
      var clue = $('lclue');
      clue.innerHTML = p.clue.map(function (k, i) { return '<span class="chip' + (i === 0 ? ' now' : '') + '" data-i="' + i + '"><b>' + STROKE[k][0] + '</b>' + STROKE[k][1] + ' ' + STROKE[k][2] + '</span>'; }).join('');
      clue.classList.remove('faded'); show('lclue', true);
      btns.innerHTML = ''; btns.classList.add('strokes');
      p.strokes.forEach(function (k) { button(STROKE[k][0] + ' ' + STROKE[k][1], '', function (e) { if (e === 'down') carve(c, k, null); }); });
      show('lbtns', true);
      rctx.clearRect(0, 0, runeCv.width, runeCv.height);
    },
    tick: function (c, t) {
      var p = c.pub, s = c.st;
      octx.clearRect(0, 0, FW, FH);
      if (p.fade && t > p.fade && !$('lclue').classList.contains('faded')) { $('lclue').classList.add('faded'); flash('The clue fades: carve it from memory', '', 1100); }
      hint.innerHTML = s.i < p.count ? 'The Rune of <b>' + p.rune + '</b> · stroke ' + (s.i + 1) + ' of ' + p.count + (p.fade && t > p.fade ? ' (from memory)' : ': ' + STROKE[p.clue[s.i]][2]) : 'The rune is complete…';
    }
  };
  function classify(pts) {
    var a = pts[0], b = pts[pts.length - 1], len = 0, maxY = a, i;
    for (i = 1; i < pts.length; i++) { len += Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y); if (pts[i].y > maxY.y) maxY = pts[i]; }
    if (len < 14) return 'dot';
    var dx = b.x - a.x, dy = b.y - a.y;
    var downThen = maxY.y - a.y, curl = Math.hypot(b.x - maxY.x, b.y - maxY.y);   // a hook: mostly straight down, then
    if (downThen > 30 && Math.abs(maxY.x - a.x) < downThen * 0.35 && curl >= 9 &&       // a curl after its lowest point,
        (b.x < maxY.x - 6 || b.y < maxY.y - 6)) return 'hook';                         // back left or up
    if (Math.abs(dx) > 2 * Math.abs(dy)) return 'horizontal';
    if (Math.abs(dy) > 2 * Math.abs(dx)) return 'vertical';
    return dx < 0 ? 'sweep' : 'press';
  }
  function cvPoint(e) {
    var r = runeCv.getBoundingClientRect();
    return {x: (e.clientX - r.left) * runeCv.width / r.width, y: (e.clientY - r.top) * runeCv.height / r.height};
  }
  function strokeLine(pts, color, width, glow) {
    rctx.save(); rctx.strokeStyle = color; rctx.lineWidth = width; rctx.lineCap = 'round'; rctx.lineJoin = 'round';
    rctx.shadowColor = glow; rctx.shadowBlur = 18; rctx.beginPath();
    pts.forEach(function (q, i) { if (i) rctx.lineTo(q.x, q.y); else rctx.moveTo(q.x, q.y); });
    if (pts.length === 1) { rctx.arc(pts[0].x, pts[0].y, width * 0.7, 0, 2 * Math.PI); }
    rctx.stroke(); rctx.restore();
  }
  function redraw(c) {
    rctx.clearRect(0, 0, runeCv.width, runeCv.height);
    c.st.marks.forEach(function (m) { strokeLine(m.pts, m.ok === false ? 'rgba(224,90,79,.9)' : 'rgba(255,224,150,.95)', m.ok === false ? 5 : 9, m.ok === false ? '#E05A4F' : '#FFD27A'); });
    if (c.st.path) strokeLine(c.st.path, 'rgba(255,240,200,.8)', 7, '#FFE6A8');
  }
  runeCv.addEventListener('pointerdown', function (e) {
    if (!cur || cur.stage !== 'inscribe' || cur.t0 === null || ending) return;
    e.preventDefault(); if (runeCv.setPointerCapture) runeCv.setPointerCapture(e.pointerId);
    cur.st.path = [cvPoint(e)]; Snd('tick');
  });
  runeCv.addEventListener('pointermove', function (e) {
    if (!cur || !cur.st || !cur.st.path) return;
    cur.st.path.push(cvPoint(e)); redraw(cur);
  });
  ['pointerup', 'pointercancel'].forEach(function (n) {
    runeCv.addEventListener(n, function () {
      if (!cur || !cur.st || !cur.st.path) return;
      var pts = cur.st.path; cur.st.path = null;
      carve(cur, classify(pts), pts);
    });
  });
  function carve(c, what, pts) {
    var s = c.st, p = c.pub;
    if (s.i >= p.count) return;
    var i = s.i++, mark = {pts: pts || defaultPath(what, i, p.count), ok: null};
    s.marks.push(mark); redraw(c);
    var chip = $('lclue').querySelector('[data-i="' + i + '"]'), next = $('lclue').querySelector('[data-i="' + (i + 1) + '"]');
    if (chip) chip.classList.remove('now'); if (next) next.classList.add('now');
    Snd('clang');
    press({do: what}).then(function (r) {
      if (!r || r.i === undefined) return;
      mark.ok = r.ok; redraw(c);
      if (chip) chip.classList.add(r.ok ? 'ok' : 'bad');
      if (!r.ok) { flash('🩸 The chisel slips: it wanted a ' + STROKE[r.want][2].toLowerCase() + ' (' + STROKE[r.want][0] + ')', 'bad', 1300); Snd('bad'); }
      else flash('✨ A clean ' + STROKE[what][2].toLowerCase() + ' stroke', 'good', 600);
      if (r.over) { if (runeGlow && !calm) { runeGlow.currentTime = 2.4; runeGlow.classList.add('on'); var pr = runeGlow.play(); if (pr && pr.catch) pr.catch(function () {}); } Snd('chime'); }
    });
  }
  function defaultPath(what, i, n) {          // a stroke chosen with a button is carved in a tidy place
    var W = runeCv.width, H = runeCv.height, x = W * (0.25 + 0.5 * (n > 1 ? i / (n - 1) : 0.5)), y = H * 0.5, L = 70;
    return {horizontal: [{x: x - L, y: y}, {x: x + L, y: y}], vertical: [{x: x, y: y - L}, {x: x, y: y + L}],
            sweep: [{x: x + L * 0.6, y: y - L}, {x: x - L * 0.6, y: y + L}], press: [{x: x - L * 0.6, y: y - L}, {x: x + L * 0.6, y: y + L}],
            dot: [{x: x, y: y}], hook: [{x: x, y: y - L}, {x: x, y: y + L * 0.6}, {x: x - 26, y: y + L * 0.3}]}[what];
  }
  if (runeGlow) runeGlow.addEventListener('ended', function () { runeGlow.classList.remove('on'); });

  // ── the button stages (none now: every stage is live; kept for a forge started before this page changed) ──
  var promptTimer = null;
  function showPrompt(state) {
    var pr = state.prompt, box = $('lprompt');
    setStageClass(pr.stage);
    kick.textContent = 'STAGE ' + pr.no + ' OF 5 · ' + pr.title.toUpperCase();
    $('lkeys').textContent = 'Choose with the buttons below.';
    hint.textContent = '';
    var html = pr.lines.map(function (l) { return '<p class="pline">' + l + '</p>'; }).join('');
    var q = pr.gauge;
    if (q) {
      html += '<div class="gauge ' + q.kind + '"' + (q.kind === 'colors' ? ' style="background: linear-gradient(90deg,' + q.colors.join(',') + ')"' : '') + '>'
        + (q.kind === 'quench' ? '<div class="band" style="left:' + q.band_l + '%;width:' + q.band_w + '%"></div>' : '')
        + '<div class="needle" style="left:' + q.pct + '%"></div></div><div class="glabels"><span>' + q.left + '</span><span>' + q.right + '</span></div>';
    }
    html += '<div class="choices">' + pr.options.map(function (o) { return '<button class="btn btn-gold" type="button" data-key="' + o.key + '">' + o.label + '</button>'; }).join('') + '</div>';
    box.innerHTML = html; show('lprompt', true);
    var turn = state.turn, end = performance.now() + pr.left * 1000;
    box.querySelectorAll('button').forEach(function (b) {
      b.addEventListener('click', function () {
        box.querySelectorAll('button').forEach(function (x) { x.disabled = true; });
        clearInterval(promptTimer);
        post('/forge/live/act', {key: b.dataset.key, turn: turn}).then(apply);
      });
    });
    clearInterval(promptTimer);
    promptTimer = setInterval(function () {
      var l = Math.max(0, (end - performance.now()) / 1000);
      fill.style.width = (l / pr.seconds * 100) + '%';
      if (l <= 0) { clearInterval(promptTimer); setTimeout(function () { getState().then(apply); }, 1100); }
    }, 100);
  }

  // ── first-time help (the same switch as the live alchemy's: cookie ma_help, 📖, the card's checkbox) ──
  var HELP = {
    'f-ignite': ['🔥 Ignite the Forge', 'Hold <b>Space</b> (or Pump) to work the bellows; let go and the forge cools, faster as the coals burn down. Tap <b>V</b> (or Vent) to dump heat fast. Keep the needle in the <b>green band</b>.'],
    'f-jam': ['⚠️ A sticking vent', 'Sometimes the damper sticks and the vent does nothing for a while: stop pumping early.'],
    'f-flare': ['🔥 Flare-ups', 'The coals flare and the heat surges by itself: vent it and stop pumping.'],
    'f-heat': ['🌡️ Heat the Metal', 'The metal climbs from dull red to white in the furnace. Press <b>Space</b> (or Pull it out) when it glows the <b>target colour</b>. Past white it burns.'],
    'f-uneven': ['↔️ Uneven heat', 'The tip heats ahead of the base: judge the colour in the <b>middle</b>.'],
    'f-hammer': ['🔨 Hammer', 'A glowing spot slides along the metal: strike as it passes <b>under the hammer</b> (the dashed line). The metal tells you how: <b>rings bright → Hard</b> (Space/J), <b>soft spreading glow → Light</b> (K), <b>glow fading → Reheat</b> (R).'],
    'f-decoy': ['👻 False spots', 'A fainter, flickering spot may cross first. Striking it is a bad blow.'],
    'f-double': ['✌️ Double strikes', 'Some strikes show two spots: hit both.'],
    'f-quench': ['💦 Quench', 'Choose <b>Water</b> (1: fast, narrow window, up to 20) or <b>Oil</b> (2: slow, wide window, up to 15). The blade then cools: press <b>Space</b> (or Plunge) when the needle is in the <b>green band</b>.'],
    'f-steam': ['🌫️ Steam', 'Steam sometimes hides the thermometer: judge by the timing.'],
    'f-inscribe': ['✍️ Inscribe', 'Carve the rune stroke by stroke, in the order shown: <b>drag</b> on the plate (→ horizontal, ↓ vertical, ↙ sweep, ↘ press, a <b>tap</b> is a dot, ↓ then curl back is a hook), or use the stroke buttons.'],
    'f-fade': ['🧠 From memory', 'On fine gear the clue fades after a moment: remember the order.']
  };
  function helpOff() {
    var m = /(?:^|; )ma_help=(on|off)/.exec(document.cookie);
    if (m) return m[1] === 'off';
    try { return localStorage.getItem('ma-help-off') === '1'; } catch (e) { return false; }
  }
  function helpFor(stage, p) {
    if (helpOff()) return [];
    var k = [];
    if (stage === 'ignite') { k.push('f-ignite'); if (p.jam) k.push('f-jam'); if (p.flare) k.push('f-flare'); }
    if (stage === 'heat') { k.push('f-heat'); if (p.uneven) k.push('f-uneven'); }
    if (stage === 'quench') { k.push('f-quench'); if (p.steam && p.steam.length) k.push('f-steam'); }
    if (stage === 'inscribe') { k.push('f-inscribe'); if (p.fade) k.push('f-fade'); }
    if (stage === 'hammer') {
      k.push('f-hammer');
      if (p.strikes.some(function (s) { return s.decoy !== undefined; })) k.push('f-decoy');
      if (p.strikes.some(function (s) { return s.under.length > 1; })) k.push('f-double');
    }
    return k.filter(function (x) { try { return localStorage.getItem('ma-help-' + x) !== '1'; } catch (e) { return false; } });
  }
  function helpCard(keys, then) {
    if (!keys.length) return then();
    var box = $('lhelp');
    box.innerHTML = keys.map(function (k) { return '<h3>' + HELP[k][0] + '</h3><p>' + HELP[k][1] + '</p>'; }).join('')
      + '<label class="hoff"><input type="checkbox"> Don\'t show instructions again</label><button type="button" class="btn btn-gold">Got it</button>';
    box.hidden = false;
    var done = function () {
      box.hidden = true;
      keys.forEach(function (k) { try { localStorage.setItem('ma-help-' + k, '1'); } catch (e) {} });
      if (box.querySelector('.hoff input').checked) { try { localStorage.setItem('ma-help-off', '1'); } catch (e) {} document.cookie = 'ma_help=off;path=/;max-age=31536000;samesite=lax'; }
      document.removeEventListener('keydown', onKey, true); then();
    }, onKey = function (e) { if (e.code === 'Space' || e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); done(); } };
    box.querySelector('button.btn').addEventListener('click', done, {once: true});
    document.addEventListener('keydown', onKey, true);
  }
  var hb = $('lhelpbtn');
  if (hb) {
    var showHb = function () { hb.classList.toggle('off', helpOff()); };
    showHb();
    hb.addEventListener('click', function (e) {
      e.stopPropagation();
      var on = helpOff();
      try {
        localStorage.setItem('ma-help-off', on ? '0' : '1');
        if (on) Object.keys(localStorage).forEach(function (k) { if (k.indexOf('ma-help-') === 0 && k !== 'ma-help-off') localStorage.removeItem(k); });
      } catch (e2) {}
      document.cookie = 'ma_help=' + (on ? 'on' : 'off') + ';path=/;max-age=31536000;samesite=lax';
      showHb(); flash(on ? '📖 Instructions on' : '📖 Instructions off', '', 900);
    });
  }

  // ── the loop ──
  function reset() {
    ['lgauge', 'lswatch', 'lbtns', 'lprompt', 'lclue'].forEach(function (id) { show(id, false); });
    btns.innerHTML = ''; btns.classList.remove('strokes'); hint.innerHTML = '';
    $('lneedle').style.opacity = 1;
    clearInterval(promptTimer);
    hctx.clearRect(0, 0, heatCv.width, heatCv.height); sctx.clearRect(0, 0, spotCv.width, spotCv.height);
  }
  function apply(state) {
    if (!state || state.gone) { location.replace('/forge'); return; }
    track(state); setLog(state.log);
    if (state.done) { setTimeout(function () { location.replace('/forge/play'); }, 900); return; }
    reset();
    if (state.prompt) { cur = null; ending = false; showPrompt(state); return; }
    if (!state.live) { setTimeout(function () { getState().then(apply); }, 500); return; }
    var L = state.live, def = S[L.stage];
    cur = {live: true, id: L.id, stage: L.stage, pub: L.pub, t0: null, st: {}};
    ending = false;
    setStageClass(L.stage);
    kick.textContent = 'STAGE ' + L.no + ' OF 5 · ' + def.title.toUpperCase();
    $('lkeys').textContent = def.keys;
    if (L.began) { cur.t0 = performance.now() - L.t * 1000; def.setup(cur); return; }
    var c = cur;
    helpCard(helpFor(L.stage, L.pub), function () {
      if (cur !== c) return;
      flash(def.title, '', 1000);
      setTimeout(function () {
        if (cur !== c) return;
        def.setup(c); flash('Begin!', 'good', 600);
        c.t0 = performance.now();
        post('/forge/live/begin', {id: c.id}).catch(function () {});
      }, firstApply ? 900 : 1100);
      firstApply = false;
    });
  }
  function finishStage(state) {
    if (ending) return;
    ending = true;
    if (cur && cur.st && cur.st.pumping) { cur.st.pumping = false; }
    cur = null;
    if (state && state.last && state.last.pts !== undefined && state.last.pts !== null) flash(state.last.title + ': ' + state.last.pts + ' / 20', state.last.pts >= 14 ? 'good' : state.last.pts < 8 ? 'bad' : '', 1300);
    setTimeout(function () { (state ? Promise.resolve(state) : getState()).then(apply); }, state && state.done ? 300 : 1500);
  }
  function loop() {
    requestAnimationFrame(loop);
    if (!cur || cur.t0 === null || ending) { if (!cur && !ending) { octx.clearRect(0, 0, FW, FH); drawFurnace(40, false, performance.now() / 1000); } return; }
    var t = now();
    S[cur.stage].tick(cur, t);
    fill.style.width = Math.max(0, 100 - 100 * t / cur.pub.length) + '%';
    if (t > cur.pub.length + 0.35 && !cur.polling && t >= (cur.nextPoll || 0)) {
      var c = cur; c.polling = true; c.nextPoll = t + 0.4;
      getState().then(function (st) { c.polling = false; if (cur === c && st && (st.gone || st.done || !st.live || st.live.id !== c.id)) finishStage(st); },
                      function () { c.polling = false; });
    }
  }

  // ── hands ──
  function act(kind, arg) {
    if (!cur || cur.t0 === null || ending) return;
    var k = cur.stage;
    if (k === 'ignite') { if (kind === 'main') pump(cur, true); if (kind === 'mainup') pump(cur, false); if (kind === 'vent') vent(cur); }
    if (k === 'heat' && kind === 'main') pull(cur);
    if (k === 'quench') { if (kind === 'main') plunge(cur); if (kind === 'one') choose(cur, 'water'); if (kind === 'two') choose(cur, 'oil'); }
    if (k === 'hammer') {
      if (kind === 'main' || kind === 'hard') strike(cur, 'hard');
      if (kind === 'light') strike(cur, 'light');
      if (kind === 'reheat') strike(cur, 'reheat');
    }
  }
  document.addEventListener('keydown', function (e) {
    if (e.repeat) { if (e.code === 'Space') e.preventDefault(); return; }
    var k = e.key.toLowerCase();
    if (e.code === 'Space') { e.preventDefault(); act('main'); }
    else if (k === 'v') act('vent'); else if (k === 'j') act('hard'); else if (k === 'k') act('light'); else if (k === 'r') act('reheat');
    else if (k === '1') act('one'); else if (k === '2') act('two');
  });
  document.addEventListener('keyup', function (e) { if (e.code === 'Space') { e.preventDefault(); act('mainup'); } });
  window.addEventListener('blur', function () { act('mainup'); });

  // 👤 show or hide the smith (remembered): the forge, the props and the effects stay either way
  var sb = $('lsmithbtn');
  if (sb) {
    var smithOff = false;
    try { smithOff = localStorage.getItem('ma-forge-smith') === 'off'; } catch (e) {}
    var showSmith = function () { scene.classList.toggle('nosmith', smithOff); sb.classList.toggle('off', smithOff); };
    showSmith();
    sb.addEventListener('click', function (e) {
      e.stopPropagation(); smithOff = !smithOff;
      try { localStorage.setItem('ma-forge-smith', smithOff ? 'off' : 'on'); } catch (e2) {}
      showSmith(); flash(smithOff ? '👤 Smith hidden' : '👤 Smith shown', '', 800);
    });
  }

  getState().then(apply).catch(function () { hint.textContent = 'Lost the connection to the forge. Reload the page.'; });
  loop();
})();
