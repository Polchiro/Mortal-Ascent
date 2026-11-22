/* Live alchemy: each stage of the craft played with the hands (alchemy_play.html #alive; web/alchemy_live.py decides
   everything; docs/web.md "Live alchemy").

   The page asks the server for the stage (/alchemy/live), shows its intro, then tells the server it began
   (/alchemy/live/begin) and starts its own clock at that same moment, so the server's clock and this one agree up to
   the network jitter. Every press goes to /alchemy/live/press; the server times it and judges it. The page shows its
   own guess at once (so the hands feel instant) and the server's verdict when it answers. When the stage's time is
   up (or the server says it is over) the page asks for the next one; when the craft is done it reloads into the
   result page.

   Keys: Space = the stage's main action (pump / fuse / condense), 1-4 = herbs, ←/↑/→ = the shield. */
(function () {
  'use strict';
  var root = document.getElementById('alive');
  if (!root) return;
  var $ = function (id) { return document.getElementById(id); };
  var scene = $('lscene'), cv = scene.querySelector('canvas'), ctx = cv.getContext('2d');
  var hint = $('lhint'), kick = $('lkick'), banner = $('lbanner'), tap = $('ltap'), fill = $('lfill'), logBox = $('llog');
  var calm = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var W = cv.width, H = cv.height;

  var cur = null;          // {id, stage, pub, t0 (performance.now at begin), st (stage-local state)}
  var ending = false, frame = 0;

  // ── talking to the server ──
  function post(url, data) {
    var body = new URLSearchParams(data);
    return fetch(url, {method: 'POST', body: body, credentials: 'same-origin', cache: 'no-store',
                       headers: {'Content-Type': 'application/x-www-form-urlencoded'}}).then(function (r) { return r.json(); });
  }
  function getState() {
    return fetch('/alchemy/live', {credentials: 'same-origin', cache: 'no-store'}).then(function (r) { return r.json(); });
  }
  function press(data) {
    if (!cur) return Promise.resolve(null);
    var id = cur.id;
    data.id = id;
    return post('/alchemy/live/press', data).then(function (r) {
      if (r.state && (r.state.gone || r.state.done || !r.state.live || r.state.live.id !== id)) {
        if (cur && cur.id === id) finishStage(r.state);
      }
      return cur && cur.id === id ? r.reply : null;
    }).catch(function () { return null; });
  }

  // ── videos ──
  function play(v) {
    if (!v || calm) return;
    if (!v.src && v.dataset.src) v.src = v.dataset.src;
    v.addEventListener('playing', function () { v.classList.add('on'); }, {once: true});
    var p = v.play(); if (p && p.catch) p.catch(function () {});
  }
  function stop(v) { if (v) { v.pause(); v.classList.remove('on'); } }
  function once(v, keepEnd) {
    if (!v || calm) return;
    v.currentTime = 0;
    v.addEventListener('ended', function () { if (!keepEnd) v.classList.remove('on'); }, {once: true});
    play(v);
  }
  var fires = scene.querySelectorAll('.cfire'), fireNow = null;
  function fire(which) {
    if (which === fireNow) return;
    fireNow = which;
    fires.forEach(function (v) {
      var on = v.dataset.fire === which;
      v.classList.toggle('lit', on);
      if (on) play(v); else if (v.classList.contains('on')) setTimeout(function () { if (!v.classList.contains('lit')) v.pause(); }, 450);
    });
  }
  var V = {swirl: scene.querySelector('.cswirl'), splash: scene.querySelector('.csplash'), cin: scene.querySelector('.ccondin'),
           cond: scene.querySelector('.ccond'), light: scene.querySelector('.clight'), storm: scene.querySelector('.cstorm')};

  // ── little helpers ──
  var bannerTimer;
  function flash(text, kind, ms) {
    banner.textContent = text;
    banner.className = 'lbanner on' + (kind ? ' ' + kind : '');
    clearTimeout(bannerTimer);
    bannerTimer = setTimeout(function () { banner.className = 'lbanner'; }, ms || 900);
  }
  function show(id, on) { $(id).hidden = !on; }
  function setMood(m) {
    scene.classList.remove('cold', 'zone', 'hot');
    if (m) scene.classList.add(m);
  }
  function backlash() {
    scene.classList.add('backlash');
    setTimeout(function () { scene.classList.remove('backlash'); }, 450);
  }
  function now() { return cur ? (performance.now() - cur.t0) / 1000 : 0; }
  function setLog(lines) {
    logBox.innerHTML = '';
    (lines || []).forEach(function (h) { var p = document.createElement('p'); p.className = 'flog'; p.innerHTML = h; logBox.appendChild(p); });
  }
  function track(points) {                    // the stage list on the left
    var rows = document.querySelectorAll('.track .stg:not(.pillhead)');
    (points || []).forEach(function (pt, i) {
      var row = rows[i];
      if (!row) return;
      row.classList.toggle('on', !!pt.active);
      row.classList.toggle('done', pt.pct !== null);
      var b = row.querySelector('b'); if (b) b.textContent = pt.pct !== null ? pt.pct : '—';
    });
  }

  // ── the stages ──
  var S = {};

  // 🔥 Ignite: hold to pump the bellows
  S[1] = {
    title: 'Ignite the Cauldron', action: 'Hold to pump the bellows',
    keys: 'Hold Space (or the button) to pump the bellows; let go and the fire cools.',
    hint: 'Keep the heat inside the golden band.',
    setup: function (c) {
      var p = c.pub;
      c.st = {heat: p.heat, speed: 0, pumping: false, inside: 0, counted: 0, k: 0};
      show('lgauge', true);
      tap.hidden = false;
      tap.textContent = '🔥 Hold to pump the bellows';
      fire('low');
      drawIgnite(c, 0);
    },
    tick: function (c, t) {
      var p = c.pub, s = c.st, steps = Math.min(Math.floor(t / p.tick), Math.round(c.pub.length / p.tick));
      while (s.k < steps) {                   // the same simulation as alchemy_live.heat_run
        var tt = s.k * p.tick, want = s.pumping ? p.up : -p.down;
        s.speed += (want - s.speed) * Math.min(1, p.tick / p.ease);
        s.heat = Math.max(0, Math.min(100, s.heat + (s.speed + gustAt(p, tt)) * p.tick));
        if (tt >= p.warmup) { s.counted++; var lo = bandLo(p, tt); if (s.heat >= lo && s.heat <= lo + p.width) s.inside++; }
        s.k++;
      }
      drawIgnite(c, t);
    },
    down: function (c) { setPump(c, true); },
    up: function (c) { setPump(c, false); }
  };
  function bandLo(p, t) { return p.lo + p.sway * Math.sin(2 * Math.PI * t / p.period + p.phase); }
  function gustAt(p, t) {
    for (var i = 0; i < p.gusts.length; i++) if (p.gusts[i][0] <= t && t < p.gusts[i][0] + p.gust) return p.gusts[i][1] * p.push;
    return 0;
  }
  function setPump(c, on) {
    if (c.st.pumping === on) return;
    c.st.pumping = on;
    tap.classList.toggle('held', on);
    press({pump: on ? '1' : '0'});
  }
  function drawIgnite(c, t) {
    var p = c.pub, s = c.st, lo = bandLo(p, t), heat = s.heat;
    $('lband').style.left = lo + '%'; $('lband').style.width = p.width + '%';
    $('lneedle').style.left = heat + '%';
    $('lheat').textContent = Math.round(heat) + '°';
    var mood = heat < lo ? 'cold' : heat > lo + p.width ? 'hot' : 'zone';
    setMood(mood);
    fire(mood === 'cold' ? 'low' : mood === 'zone' ? 'mid' : 'high');
    var omen = '';
    p.gusts.forEach(function (g) {
      if (t >= g[0] - p.omen && t < g[0]) omen = g[1] > 0 ? 'The flames lick hungrily at the walls… a gust is coming!' : 'A cold draught creeps under the cauldron…';
      else if (t >= g[0] && t < g[0] + p.gust) omen = g[1] > 0 ? '🔥 A gust feeds the fire!' : '🌬️ The draught chills the fire!';
    });
    hint.textContent = omen || (t < p.warmup ? 'Bring the heat into the golden band.' : mood === 'zone' ? 'A soft golden glow fills the cauldron.'
      : mood === 'cold' ? 'The herbs lie dull and cold. Pump!' : 'The cauldron hisses and smokes! Let it cool.');
    hint.classList.toggle('warn', !!omen);
    clear();
    var share = s.counted ? s.inside / s.counted : 0;
    ring(W / 2, H * 0.6, 120, 'rgba(245,205,120,' + (mood === 'zone' ? 0.35 : 0.08) + ')', 10);
    label(t < p.warmup ? 'warming up' : 'in the band ' + Math.round(share * 100) + '%', H * 0.94);
  }

  // 🌿 Add Herbs: tap the right herb as the cauldron breathes in
  S[2] = {
    title: 'Add the Herbs', keys: 'Tap a herb (or press 1-4) as the ring at the cauldron\'s mouth swells to its fullest.',
    hint: '',
    setup: function (c) {
      var p = c.pub, tray = $('lherbs'), clues = $('lclues');
      c.st = {placed: 0, marks: [], since: 0};
      fire('mid');
      tray.innerHTML = ''; clues.innerHTML = '';
      p.clues.concat(p.insights).forEach(function (h) { var q = document.createElement('p'); q.className = 'sub'; q.innerHTML = h.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/\*(.+?)\*/g, '$1'); clues.appendChild(q); });
      p.herbs.forEach(function (h, i) {
        var b = document.createElement('button');
        b.type = 'button'; b.dataset.herb = h.key;
        b.innerHTML = (h.picture ? '<img src="' + h.picture + '" alt="">' : '<span>' + h.emoji + '</span>') + '<span>' + h.name + '</span><kbd>' + (i + 1) + '</kbd>';
        b.addEventListener('pointerdown', function (e) { e.preventDefault(); herb(c, h.key); });
        tray.appendChild(b);
      });
      show('lherbs', true); show('lclues', true);
    },
    tick: function (c, t) {
      var p = c.pub, s = c.st;
      while (s.placed < p.count && t > s.since + p.breath * p.per) { s.since += p.breath * p.per; s.placed++; flash('Too slow: it goes cold', 'bad'); }
      var phase = (t % p.breath) / p.breath, swell = Math.sin(Math.PI * phase), on = Math.abs(phase - 0.5) <= p.window;
      clear();
      ring(W / 2, H * 0.52, 70 + 55 * swell, on ? 'rgba(168,240,210,.95)' : 'rgba(245,205,120,' + (0.25 + 0.4 * swell) + ')', on ? 9 : 4);
      if (on) ring(W / 2, H * 0.52, 70 + 55 * swell + 14, 'rgba(168,240,210,.35)', 4);
      hint.textContent = s.placed < p.count ? 'Herb ' + (s.placed + 1) + ' of ' + p.count + ': which goes in ' + ['first', 'second', 'third', 'fourth', 'fifth', 'sixth'][s.placed] + '?' : 'The herbs settle…';
      label(on ? 'breathe in: now!' : '', H * 0.94);
    },
    key: function (c, k) { var h = c.pub.herbs[+k - 1]; if (h) herb(c, h.key); }
  };
  function herb(c, key) {
    var p = c.pub, s = c.st, t = now();
    if (s.placed >= p.count) return;
    var phase = (t % p.breath) / p.breath, on = Math.abs(phase - 0.5) <= p.window;
    s.placed++; s.since = t;
    once(V.splash);
    flash(on ? 'On the breath!' : 'In it goes', on ? 'good' : '', 700);
    press({herb: key}).then(function (r) {
      if (!r || !r.marks) return;
      var m = r.marks[r.marks.length - 1];
      s.placed = r.placed;
      if (m && m.how.indexOf('wrong') === 0) {
        backlash();
        flash(m.how === 'wrong-forgiven' ? 'Backlash! (forgiven)' : 'Backlash! It wanted ' + m.want, 'bad', 1400);
      }
    });
  }

  // ☯️ Fuse / 🔒 Seal: tap when the orbs meet
  function fuseStage(seal) {
    return {
      title: seal ? 'Seal the Core' : 'Fuse the Essences', keys: 'Press Space (or the button) the moment Yin and Yang meet.',
      hint: '',
      setup: function (c) {
        c.st = {fused: 0, unsteady: 0, used: {}, lastHit: -9};
        tap.hidden = false; tap.textContent = seal ? '🔒 Seal' : '☯️ Fuse';
        fire('mid'); play(V.swirl);
      },
      tick: function (c, t) {
        var p = c.pub, s = c.st, m = p.meet, prev = -m[0], next = m[0], i;
        for (i = 0; i < m.length; i++) { if (m[i] > t) { next = m[i]; prev = i ? m[i - 1] : 0; break; } prev = m[i]; next = m[i] + (m[i] - (i ? m[i - 1] : 0)); }
        var near = m.some(function (x) { return Math.abs(t - x) <= p.window; });
        var sep = 2 * Math.PI * Math.max(0, (next - t) / Math.max(0.2, next - prev));
        var base = t * 1.1, cx = W / 2, cy = H * 0.36, rx = 170, ry = 70;
        clear();
        ctx.strokeStyle = 'rgba(232,194,122,.25)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.ellipse(cx, cy, rx, ry, 0, 0, 2 * Math.PI); ctx.stroke();
        if (seal) {                         // the Beast Core, restless above the cauldron
          var j = s.unsteady * 3, r = 22 + 4 * Math.sin(t * 7);
          orb(cx + (Math.random() - .5) * j, cy + (Math.random() - .5) * j, r, '#E05A4F', '#5A0F0A');
        }
        orb(cx + rx * Math.cos(base), cy + ry * Math.sin(base), 20, '#DCE6FF', '#1B2850');
        orb(cx + rx * Math.cos(base + sep), cy + ry * Math.sin(base + sep), 20, '#FFE2A0', '#8A5A10');
        if (near) ring(cx + rx * Math.cos(base), cy + ry * Math.sin(base), 34, 'rgba(255,255,255,.8)', 4);
        if (t - s.lastHit < 0.5) ring(cx + rx * Math.cos(base), cy + ry * Math.sin(base), 30 + 80 * (t - s.lastHit), 'rgba(168,240,210,' + (1 - 2 * (t - s.lastHit)) + ')', 6);
        scene.style.setProperty('--calm', (0.35 + 0.6 * s.fused / p.need) * Math.max(0.2, 1 - 0.25 * s.unsteady));
        hint.textContent = (seal ? 'Seal the Beast Core: ' : 'Fuse Yin and Yang: ') + s.fused + ' of ' + p.need
          + (s.unsteady ? ' · ' + s.unsteady + ' unsteady' : '') + (seal && p.allowed ? ' · ' + p.allowed + ' miss allowed' : '');
      },
      down: function (c) {
        var p = c.pub, s = c.st, t = now(), hit = -1;
        p.meet.forEach(function (x, i) { if (hit < 0 && !s.used[i] && Math.abs(t - x) <= p.window) hit = i; });
        if (hit >= 0) { s.used[hit] = 1; s.fused++; s.lastHit = t; flash(seal ? 'Sealed!' : 'Fused!', 'good', 600); }
        else { flash('Unsteady!', 'bad', 600); backlash(); }
        press({}).then(function (r) {
          if (!r) return;
          if (r.fused !== undefined) s.fused = r.fused;
          if (r.unsteady !== undefined) s.unsteady = r.unsteady;
          if (r.hit === false && hit >= 0) { s.used[hit] = 0; flash('Unsteady!', 'bad', 600); }
        });
      }
    };
  }
  S[3] = fuseStage(false);
  S[5] = fuseStage(true);

  // 💊 Condense: tap in the glint
  S[4] = {
    title: 'Condense the Pill', keys: 'Press Space (or the button) when the pill glints, steady and golden.',
    hint: 'The pill pulses brighter with every beat. Condense in the glint: too early is weak, too late and it cracks.',
    intro: function (c, go) {                 // the light spirals in once, then the pill pulses
      fire('low');
      if (calm || !V.cin) return go();
      var done = false, fin = function () { if (done) return; done = true; V.cin.classList.remove('on'); go(); };
      V.cin.addEventListener('ended', fin, {once: true});
      once(V.cin, true);
      setTimeout(fin, 3500);
    },
    setup: function (c) {
      c.st = {pressed: false};
      tap.hidden = false; tap.textContent = '💊 Condense';
      play(V.cond);
    },
    tick: function (c, t) {
      var p = c.pub, beat = Math.floor(t / p.pulse), level = Math.min(5, p.start + beat), ph = (t % p.pulse) / p.pulse;
      var glint = level === 4 && Math.abs(ph - 0.5) <= p.glint, decoy = p.decoy === level && Math.abs(ph - 0.5) <= p.glint;
      scene.style.setProperty('--glow', Math.min(1, level / 4));
      V.cond.style.setProperty('--glow', Math.min(1, level / 4));
      clear();
      var cx = W / 2, cy = H * 0.33;
      ring(cx, cy, 40 + 90 * ph, 'rgba(245,220,166,' + (0.15 + 0.15 * level) * (1 - ph) + ')', 3 + level * 1.5);
      if (glint) star(cx, cy, 70, '#FFF3C4', 1);
      if (decoy && Math.random() < 0.7) star(cx, cy, 62, '#E8D6A0', 0.6);
      if (level >= 5) cracks(cx, cy);
      hint.textContent = ['A faint glow…', 'A steady light…', 'The light brightens…', 'The light swells, warm and full…',
                          'The light trembles, ready to set!', 'Cracks of light race across the pill!'][level];
    },
    down: function (c) {
      if (c.st.pressed) return;
      c.st.pressed = true;
      var p = c.pub, t = now(), level = Math.min(5, p.start + Math.floor(t / p.pulse)), ph = (t % p.pulse) / p.pulse;
      var glint = level === 4 && Math.abs(ph - 0.5) <= p.glint;
      flash(glint ? '✨ Perfect pulse!' : level === 4 ? 'Ready…' : level >= 5 ? 'Cracked!' : 'Too early', glint ? 'good' : level === 4 ? '' : 'bad', 1200);
      press({});
    }
  };

  // ⚡ Tribulation: raise the shield toward the lightning
  S[6] = {
    title: 'Pill Tribulation', keys: 'Watch the clouds: press ← ↑ → (or the buttons) toward where the lightning gathers.',
    hint: 'Dark clouds gather over the cauldron. The heavens will not let a nine-pattern pill be born without a trial!',
    setup: function (c) {
      c.st = {i: 0, from: {}, asked: {}, chose: {}, struck: {}};
      scene.classList.add('storm');
      play(V.storm);
      show('ldirs', true);
    },
    tick: function (c, t) {
      var p = c.pub, s = c.st;
      while (s.i < p.strikes.length && t > p.strikes[s.i][1] + 0.1) {        // the bolt lands
        var i = s.i, blocked = s.chose[i] && s.chose[i] === s.from[i];
        V.light.classList.remove('left', 'right'); if (s.from[i] && s.from[i] !== 'above') V.light.classList.add(s.from[i]);
        once(V.light);
        flash(blocked ? '🛡️ The lightning breaks on your shield!' : '⚡ The lightning strikes the cauldron!', blocked ? 'good' : 'bad', 1100);
        s.i++;
        document.querySelectorAll('#ldirs .btn').forEach(function (b) { b.classList.remove('chosen'); });
      }
      clear();
      if (s.i >= p.strikes.length) { hint.textContent = 'The clouds part…'; return; }
      var om = p.strikes[s.i][0], bolt = p.strikes[s.i][1];
      if (t >= om && !s.asked[s.i]) {
        s.asked[s.i] = 1;
        var k = s.i;
        press({omen: '1'}).then(function (r) { if (r && r.from && r.i === k) s.from[k] = r.from; });
      }
      var from = s.from[s.i];
      hint.textContent = 'Strike ' + (s.i + 1) + ' of ' + p.strikes.length + ': ' + (from && t >= om ? 'lightning gathers ' + {left: 'to the LEFT', above: 'ABOVE', right: 'to the RIGHT'}[from] + '! Raise your shield!' : 'the clouds churn…');
      if (from && t >= om) {
        var x = {left: W * 0.18, above: W / 2, right: W * 0.82}[from], f = (t - om) / (bolt - om);
        ctx.fillStyle = 'rgba(200,220,255,' + (0.25 + 0.5 * Math.abs(Math.sin(t * 30)) * f) + ')';
        ctx.beginPath(); ctx.ellipse(x, H * 0.16, 110, 60, 0, 0, 2 * Math.PI); ctx.fill();
        ring(x, H * 0.16, 70 + 40 * f, 'rgba(255,255,255,.6)', 3);
      }
      if (s.chose[s.i]) shield({left: W * 0.25, above: W / 2, right: W * 0.75}[s.chose[s.i]], H * 0.42);
    },
    dir: function (c, d) {
      var s = c.st, t = now(), p = c.pub;
      if (s.i >= p.strikes.length || s.chose[s.i] || t < p.strikes[s.i][0] - p.early) return;
      s.chose[s.i] = d;
      document.querySelectorAll('#ldirs .btn').forEach(function (b) { b.classList.toggle('chosen', b.dataset.dir === d); });
      press({shield: d});
    }
  };

  // ── drawing ──
  function clear() { ctx.clearRect(0, 0, W, H); }
  function ring(x, y, r, color, w) { ctx.strokeStyle = color; ctx.lineWidth = w; ctx.beginPath(); ctx.arc(x, y, Math.max(1, r), 0, 2 * Math.PI); ctx.stroke(); }
  function orb(x, y, r, light, dark) {
    var g = ctx.createRadialGradient(x - r / 3, y - r / 3, 1, x, y, r * 1.6);
    g.addColorStop(0, light); g.addColorStop(0.55, light); g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r * 1.6, 0, 2 * Math.PI); ctx.fill();
    ctx.fillStyle = dark; ctx.globalAlpha = 0.35; ctx.beginPath(); ctx.arc(x + r / 4, y + r / 4, r / 2, 0, 2 * Math.PI); ctx.fill(); ctx.globalAlpha = 1;
  }
  function star(x, y, r, color, a) {
    ctx.save(); ctx.globalAlpha = a; ctx.fillStyle = color; ctx.shadowColor = color; ctx.shadowBlur = 30;
    ctx.beginPath();
    for (var i = 0; i < 8; i++) { var ang = i * Math.PI / 4, rr = i % 2 ? r * 0.25 : r; ctx.lineTo(x + rr * Math.cos(ang), y + rr * Math.sin(ang)); }
    ctx.closePath(); ctx.fill(); ctx.restore();
  }
  function cracks(x, y) {
    ctx.strokeStyle = 'rgba(255,240,200,.9)'; ctx.lineWidth = 3;
    [[-60, -30], [55, -40], [-40, 50], [60, 45]].forEach(function (d) { ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + d[0] / 2, y + d[1] / 3); ctx.lineTo(x + d[0], y + d[1]); ctx.stroke(); });
  }
  function shield(x, y) {
    ctx.save(); ctx.fillStyle = 'rgba(111,217,176,.35)'; ctx.strokeStyle = '#A8F0D2'; ctx.lineWidth = 4;
    ctx.beginPath(); ctx.arc(x, y, 70, Math.PI * 1.1, Math.PI * 1.9); ctx.lineTo(x, y - 20); ctx.closePath(); ctx.fill(); ctx.stroke(); ctx.restore();
  }
  function label(text, y) {
    if (!text) return;
    ctx.font = '700 22px Inter, Arial, sans-serif'; ctx.textAlign = 'center';
    ctx.fillStyle = 'rgba(9,16,36,.6)'; ctx.fillText(text, W / 2 + 1, y + 1); ctx.fillStyle = '#F5E6C4'; ctx.fillText(text, W / 2, y);
  }

  // ── the loop ──
  function reset() {
    ['lgauge', 'lherbs', 'lclues', 'ldirs'].forEach(function (id) { show(id, false); });
    tap.hidden = true; tap.classList.remove('held');
    scene.classList.remove('storm', 'cold', 'zone', 'hot');
    stop(V.swirl); stop(V.cond); stop(V.storm);
    hint.classList.remove('warn');
    clear();
  }

  function apply(state) {
    if (!state || state.gone) { location.replace('/alchemy'); return; }
    track(state.points);
    setLog(state.log);
    if (state.done) { setTimeout(function () { location.replace('/alchemy/play'); }, 900); return; }
    if (!state.live) { setTimeout(function () { getState().then(apply); }, 500); return; }
    var L = state.live, def = S[L.stage];
    reset();
    fireNow = null;
    cur = {id: L.id, stage: L.stage, pub: L.pub, t0: null, st: {}};
    ending = false;
    kick.textContent = (L.no ? 'STAGE ' + L.no + ' OF ' + L.total + ' · ' : '') + def.title.toUpperCase();
    $('lkeys').textContent = def.keys;
    hint.textContent = def.hint || '';
    if (L.began) { cur.t0 = performance.now() - L.t * 1000; def.setup(cur); return; }    // a reload mid-stage
    var c = cur;
    var go = function () {
      if (cur !== c) return;
      def.setup(c);
      flash('Begin!', 'good', 600);
      c.t0 = performance.now();
      post('/alchemy/live/begin', {id: c.id}).catch(function () {});
    };
    flash(def.title, '', 1100);
    if (def.intro) def.intro(c, function () { setTimeout(go, 200); }); else setTimeout(go, 1200);
  }

  function finishStage(state) {
    if (ending) return;
    ending = true;
    var was = cur;
    cur = null;
    if (was && S[was.stage].up) tap.classList.remove('held');
    if (state && state.last && state.last.score !== undefined) flash(state.last.title + ': ' + Math.round(state.last.score * 100) + '%', state.last.score >= 0.7 ? 'good' : state.last.score < 0.4 ? 'bad' : '', 1300);
    setTimeout(function () { (state ? Promise.resolve(state) : getState()).then(apply); }, state && state.done ? 300 : 1400);
  }

  function loop() {
    frame = requestAnimationFrame(loop);
    if (!cur || cur.t0 === null || ending) return;
    var t = now(), def = S[cur.stage];
    def.tick(cur, t);
    fill.style.width = Math.max(0, 100 - 100 * t / cur.pub.length) + '%';
    if (t > cur.pub.length + 0.35 && !cur.polling && t >= (cur.nextPoll || 0)) {   // time is up: the server settles it
      var c = cur;
      c.polling = true; c.nextPoll = t + 0.4;
      getState().then(function (st) {
        c.polling = false;
        if (cur === c && st && (st.gone || st.done || !st.live || st.live.id !== c.id)) finishStage(st);
      }, function () { c.polling = false; });
    }
  }

  // ── hands ──
  function act(kind, arg) {
    if (!cur || cur.t0 === null || ending) return;
    var def = S[cur.stage];
    if (kind === 'down' && def.down) def.down(cur);
    if (kind === 'up' && def.up) def.up(cur);
    if (kind === 'key' && def.key) def.key(cur, arg);
    if (kind === 'dir' && def.dir) def.dir(cur, arg);
  }
  tap.addEventListener('pointerdown', function (e) { e.preventDefault(); tap.setPointerCapture && tap.setPointerCapture(e.pointerId); act('down'); });
  ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(function (n) { tap.addEventListener(n, function () { act('up'); }); });
  tap.addEventListener('contextmenu', function (e) { e.preventDefault(); });
  document.querySelectorAll('#ldirs .btn').forEach(function (b) {
    b.addEventListener('pointerdown', function (e) { e.preventDefault(); act('dir', b.dataset.dir); });
  });
  var DIRS = {ArrowLeft: 'left', ArrowUp: 'above', ArrowRight: 'right'};
  document.addEventListener('keydown', function (e) {
    if (e.repeat) { if (e.code === 'Space' || DIRS[e.key]) e.preventDefault(); return; }
    if (e.code === 'Space') { e.preventDefault(); act('down'); }
    else if (DIRS[e.key]) { e.preventDefault(); act('dir', DIRS[e.key]); }
    else if (/^[1-6]$/.test(e.key)) act('key', e.key);
  });
  document.addEventListener('keyup', function (e) { if (e.code === 'Space') { e.preventDefault(); act('up'); } });
  window.addEventListener('blur', function () { act('up'); });

  getState().then(apply).catch(function () { hint.textContent = 'Lost the connection to the cauldron. Reload the page.'; });
  loop();
})();
