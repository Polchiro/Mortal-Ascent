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
        var tt = s.k * p.tick, want = s.pumping ? p.up * (flaring(p, tt) ? p.flarepump : 1) : -p.down;
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
  function bandLo(p, t) {
    var jump = 0;
    (p.jumps || []).forEach(function (j) { if (t >= j[0]) jump += j[1]; });
    return p.lo + jump + p.sway * Math.sin(2 * Math.PI * t / p.period + p.phase);
  }
  function flaring(p, t) { return (p.flares || []).some(function (f) { return f[0] <= t && t < f[0] + f[1]; }); }
  function gustAt(p, t) {                  // the same as alchemy_live.gust_at
    var push = flaring(p, t) ? p.flarepush : 0;
    for (var i = 0; i < p.gusts.length; i++) if (p.gusts[i][0] <= t && t < p.gusts[i][0] + p.gust) return push + p.gusts[i][1] * p.push;
    return push;
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
    var ghost = null;
    (p.jumps || []).forEach(function (j) {
      if (t >= j[0] - p.jumpwarn && t < j[0]) { omen = '⚠️ The fire\'s heart shifts! The band jumps ' + (j[1] > 0 ? 'HOTTER' : 'COOLER') + '…'; ghost = lo + j[1]; }
      else if (t >= j[0] && t < j[0] + 0.8) omen = '⚠️ The band has jumped! Follow it!';
    });
    (p.flares || []).forEach(function (f) {
      if (t >= f[0] - p.flareomen && t < f[0]) omen = '🔥 A flare-up is coming! Stop pumping!';
      else if (t >= f[0] && t < f[0] + f[1]) omen = '🔥 FLARE-UP! Let go of the bellows!';
    });
    var gb = $('lghost');
    if (gb) { gb.hidden = ghost === null; if (ghost !== null) { gb.style.left = Math.max(0, ghost) + '%'; gb.style.width = p.width + '%'; } }
    if (omen && omen !== c.st.lastOmen && /flare|shifts|gust/.test(omen)) Snd('warn');
    c.st.lastOmen = omen;
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
    title: 'Add the Herbs', keys: 'Tap a herb (or press 1-4) as the ring swells to its fullest. A volatile herb (blue ring) goes in when it is at its smallest.',
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
      var b = breathAt(p, t), phase = b[0], swell = Math.sin(Math.PI * phase), out = p.volatile === s.placed;
      var off = out ? Math.min(phase, 1 - phase) : Math.abs(phase - 0.5), on = off <= p.window;
      clear();
      var col = out ? '140,200,255' : '245,205,120';
      ring(W / 2, H * 0.52, 70 + 55 * swell, on ? 'rgba(168,240,210,.95)' : 'rgba(' + col + ',' + (0.3 + 0.4 * (out ? 1 - swell : swell)) + ')', on ? 9 : 4);
      if (on) ring(W / 2, H * 0.52, 70 + 55 * swell + 14, 'rgba(168,240,210,.35)', 4);
      if (p.shift && t >= p.shift[0] - 0.6 && t < p.shift[0] + 0.8) label('The breathing quickens!', H * 0.1);
      hint.innerHTML = s.placed < p.count ? 'Herb ' + (s.placed + 1) + ' of ' + p.count + ': which goes in ' + ['first', 'second', 'third', 'fourth', 'fifth', 'sixth'][s.placed] + '?'
        + (out ? ' <b class="volatile">💧 Volatile: add it on the OUT-breath (smallest ring)!</b>' : '') : 'The herbs settle…';
      label(on ? (out ? 'breathe out: now!' : 'breathe in: now!') : '', H * 0.94);
    },
    key: function (c, k) { var h = c.pub.herbs[+k - 1]; if (h) herb(c, h.key); }
  };
  function herb(c, key) {
    var p = c.pub, s = c.st, t = now();
    if (s.placed >= p.count) return;
    var b = breathAt(p, t), phase = b[0], out = p.volatile === s.placed;
    var how = rate(out ? Math.min(phase, 1 - phase) : Math.abs(phase - 0.5), p.window);
    s.placed++; s.since = t;
    once(V.splash);
    flash(WORD[how], how === 'rough' ? '' : 'good', 700);
    Snd(how === 'precise' ? 'chime' : how === 'good' ? 'good' : 'tick');
    press({herb: key}).then(function (r) {
      if (!r || !r.marks) return;
      var m = r.marks[r.marks.length - 1];
      s.placed = r.placed;
      if (m && m.how.indexOf('wrong') === 0) {
        backlash(); Snd('bad');
        flash(m.how === 'wrong-forgiven' ? 'Backlash! (forgiven)' : 'Backlash! It wanted ' + m.want, 'bad', 1400);
      }
    });
  }

  function breathAt(p, t) {                 // the same as alchemy_live.breath_at
    if (p.shift && t >= p.shift[0]) { var b2 = p.shift[1]; return [((t - p.shift[0]) % b2) / b2, b2]; }
    return [(t % p.breath) / p.breath, p.breath];
  }
  function rate(off, window) { return off <= window / 2 ? 'precise' : off <= window ? 'good' : 'rough'; }
  var WORD = {precise: '✨ Precise!', good: 'Good', rough: 'Rough…'};

  // ☯️ Fuse / 🔒 Seal: tap when the orbs meet
  function fuseStage(seal) {
    return {
      title: seal ? 'Seal the Core' : 'Fuse the Essences', keys: seal ? 'Press Space (or the button) the moment Yin and Yang meet.' : 'Press Space the moment Yin and Yang meet. Every meeting counts: a missed one scores nothing.',
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
        var left = Math.max(0, (next - t) / Math.max(0.2, next - prev));
        if (p.rush) left = left * left;                    // Heaven: slow drift, then a rush together
        var sep = 2 * Math.PI * left;
        var dir = 1, cx = W / 2, cy = H * 0.36, rx = 170, ry = 70;
        (p.reverse || []).forEach(function (k) { if (t >= m[k]) dir = -dir; });
        var base = dir * t * 1.1;
        sep = dir * sep;
        clear();
        ctx.strokeStyle = 'rgba(232,194,122,.25)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.ellipse(cx, cy, rx, ry, 0, 0, 2 * Math.PI); ctx.stroke();
        if (seal) {                         // the Beast Core, restless above the cauldron
          var j = s.unsteady * 3, r = 22 + 4 * Math.sin(t * 7);
          orb(cx + (Math.random() - .5) * j, cy + (Math.random() - .5) * j, r, '#E05A4F', '#5A0F0A');
        }
        orb(cx + rx * Math.cos(base), cy + ry * Math.sin(base), 20, '#DCE6FF', '#1B2850');
        orb(cx + rx * Math.cos(base + sep), cy + ry * Math.sin(base + sep), 20, '#FFE2A0', '#8A5A10');
        if (near) ring(cx + rx * Math.cos(base), cy + ry * Math.sin(base), 34, 'rgba(255,255,255,.8)', 4);
        (p.chaos || []).forEach(function (x) {                // the chaos orb streaks through the meeting place
          var k = (t - x) / 0.6;
          if (k < -1 || k > 1) return;
          var ax = cx + rx * Math.cos(base) + k * 260, ay = cy + ry * Math.sin(base) - k * 40;
          orb(ax, ay, 18, '#B57BFF', '#2A0A3A');
          if (Math.abs(t - x) <= p.chaoshalf) ring(ax, ay, 30, 'rgba(224,90,79,.9)', 4);
        });
        if (t - s.lastHit < 0.5) ring(cx + rx * Math.cos(base), cy + ry * Math.sin(base), 30 + 80 * (t - s.lastHit), 'rgba(168,240,210,' + (1 - 2 * (t - s.lastHit)) + ')', 6);
        scene.style.setProperty('--calm', (0.35 + 0.6 * s.fused / p.need) * Math.max(0.2, 1 - 0.25 * s.unsteady));
        var missed = seal ? 0 : m.filter(function (x, k) { return t > x + p.window * p.reach && !s.used[k]; }).length;
        if (missed > (s.missed || 0)) { s.missed = missed; flash('Missed!', 'bad', 600); Snd('bad'); }
        hint.textContent = (seal ? 'Seal the Beast Core: ' : 'Fuse Yin and Yang: ') + s.fused + ' of ' + p.need + (missed ? ' · ' + missed + ' missed' : '')
          + (s.unsteady ? ' · ' + s.unsteady + ' unsteady' : '') + (seal && p.allowed ? ' · ' + p.allowed + ' miss allowed' : '');
      },
      down: function (c) {
        var p = c.pub, s = c.st, t = now(), hit = -1;
        var chaos = (p.chaos || []).some(function (x) { return Math.abs(t - x) <= p.chaoshalf; });
        p.meet.forEach(function (x, i) { if (hit < 0 && !s.used[i] && Math.abs(t - x) <= p.window * p.reach) hit = i; });
        if (chaos) hit = -1;
        if (hit >= 0) {
          var how = rate(Math.abs(t - p.meet[hit]), p.window);
          s.used[hit] = 1; s.fused++; s.lastHit = t;
          flash((seal ? 'Sealed · ' : 'Fused · ') + WORD[how], how === 'rough' ? '' : 'good', 650); Snd(how === 'precise' ? 'chime' : 'good');
        } else { flash(chaos ? 'The chaos orb! Unsteady!' : 'Unsteady!', 'bad', 700); backlash(); Snd('bad'); }
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

  // 💊 Condense: a ring closes in on the golden outline every beat; on the ready beat, press as it lands
  S[4] = {
    title: 'Condense the Pill', keys: 'Press Space (or the button) the moment the thick gold ring lands on the outline.',
    hint: '',
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
      var p = c.pub, pa = pulseAt(p, t), level = pa[0], ph = pa[1], beat = level - p.start;
      var cx = W / 2, cy = H * 0.33, R = 62, far = 210;
      scene.style.setProperty('--glow', Math.min(1, level / 4));
      V.cond.style.setProperty('--glow', Math.min(1, level / 4));
      clear();
      // the target: a fixed golden outline around the pill
      ctx.save(); ctx.setLineDash([10, 8]); ring(cx, cy, R, 'rgba(255,236,180,.85)', 4); ctx.restore();
      if (level < 5) {
        // this beat's ring: from far outside, landing on the outline at mid-beat, then passing inside
        var r = R + (far - R) * (1 - 2 * ph), ready = level === 4, decoy = p.decoy === level;
        var col = ready ? 'rgba(255,214,102,1)' : decoy ? (ph > 0.25 ? 'rgba(235,80,70,.95)' : 'rgba(255,214,102,1)')
          : 'rgba(200,215,255,.45)';
        ring(cx, cy, Math.max(4, r), col, ready || decoy ? 10 : 3);
        if (ready && Math.abs(ph - 0.5) <= p.glint) star(cx, cy, Math.abs(ph - 0.5) <= p.glint / 2 ? 56 : 40, '#FFF3C4', 0.9);
      } else cracks(cx, cy);
      // the beats, counted: dim dots for the warm-up, the gold one is the beat to press on
      var n = 5 - p.start, x0 = cx - (n - 1) * 18;
      for (var i = 0; i < n; i++) {
        var lv = p.start + i, x = x0 + i * 36, y = H * 0.93;
        ctx.beginPath(); ctx.arc(x, y, lv === 4 ? 11 : 7, 0, 2 * Math.PI);
        ctx.fillStyle = lv < level ? 'rgba(200,215,255,.25)' : lv === level ? (lv === 4 ? '#FFD666' : '#DCE6FF') : lv === 4 ? 'rgba(255,214,102,.45)' : 'rgba(200,215,255,.55)';
        ctx.fill();
      }
      hint.textContent = level >= 5 ? 'Too late: cracks of light race across the pill!'
        : level === 4 ? 'The GOLD ring! Press as it lands on the outline!'
        : p.decoy === level ? 'A bright ring… watch: does it turn red?'
        : 'Watch the rhythm… beat ' + (beat + 1) + ' of ' + n + '. Press on the gold ring.';
    },
    down: function (c) {
      if (c.st.pressed) return;
      c.st.pressed = true;
      var p = c.pub, t = now(), pa = pulseAt(p, t), level = pa[0], ph = pa[1];
      var glint = level === 4 && Math.abs(ph - 0.5) <= p.glint, how = glint ? rate(Math.abs(ph - 0.5), p.glint) : null;
      flash(glint ? (how === 'precise' ? '✨ Precise: a perfect pulse!' : 'Good: in the glint') : level === 4 ? (ph < 0.5 ? 'Rough: a little early' : 'Rough: a little late') : level >= 5 ? 'Cracked!' : 'Too early',
            glint ? 'good' : level === 4 ? '' : 'bad', 1200);
      Snd(glint ? 'chime' : level >= 5 || level < 4 ? 'bad' : 'good');
      press({});
    }
  };

  function pulseAt(p, t) {                 // the same as alchemy_live.pulse_at
    var b = p.beats, i = 0;
    while (i + 1 < b.length && b[i + 1] <= t) i++;
    if (i >= b.length - 1) return [5, 0, p.pulse];
    var len = b[i + 1] - b[i];
    return [p.start + i, (t - b[i]) / len, len];
  }

  // ⚡ Tribulation: 🔵 blue bolts → Protect as the ring closes; 🔴 red bolts → Dodge to the SAFE side
  var HELP_KEY = 'ma-trib-help';
  S[6] = {
    title: 'Pill Tribulation', keys: 'Space / ↑ = Protect · ← → = Dodge',
    hint: 'The heavens test a nine-pattern pill with lightning. Weather all three strikes!',
    intro: function (c, go) {
      scene.classList.add('storm');
      play(V.storm); fire('low');
      var seen = false;
      try { seen = localStorage.getItem(HELP_KEY) === '1'; } catch (e) {}
      if (seen) return setTimeout(go, 1300);
      var box = $('lhelp');
      box.innerHTML = '<h3>⚡ Pill Tribulation</h3>'
        + '<p><b class="blue">🔵 Blue bolt</b> → <b>PROTECT</b> (Space). Raise the shield as the ring closes on the cauldron: too early and it fades.</p>'
        + '<p><b class="red">🔴 Red bolt</b> is too strong to block → <b>DODGE</b> (← or →) toward the side marked <b class="safe">SAFE</b>. Watch out: the safe side can change!</p>'
        + '<p>Weather all 3 strikes for a nine-pattern pill.</p><button type="button" class="btn btn-gold">Got it</button>';
      box.hidden = false;
      var b = box.querySelector('button'), done = function () {
        box.hidden = true;
        try { localStorage.setItem(HELP_KEY, '1'); } catch (e) {}
        document.removeEventListener('keydown', onKey, true);
        go();
      }, onKey = function (e) { if (e.code === 'Space' || e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); done(); } };
      b.addEventListener('click', done, {once: true});
      document.addEventListener('keydown', onKey, true);
    },
    setup: function (c) {
      c.st = {info: {}, asked: {}, acts: {}, landed: {}, marks: [], warned: {}, ticks: {}};
      scene.classList.add('storm');
      show('ldirs', true); show('ltrib', true);
      tribRow(c);
    },
    tick: function (c, t) {
      var p = c.pub, s = c.st, bolts = p.bolts, cx = W / 2, cy = H * 0.62;
      // landings
      bolts.forEach(function (b, i) {
        if (s.landed[i] || t < b.hit) return;
        s.landed[i] = 1;
        var ok = boltOk(c, i, b);
        s.acts[i] = s.acts[i] || null;
        once(V.light);
        Snd(ok ? 'shield' : 'thunder');
        if (!ok) { Snd('bad'); backlash(); }
        flash(ok ? (b.kind === 'blue' ? '🛡️ Blocked!' : '💨 Dodged!') : (b.kind === 'blue' ? (s.acts[i] ? '⚡ The shield faded too soon!' : '⚡ Struck! Protect!') : '⚡ Struck! Dodge to the SAFE side!'), ok ? 'good' : 'bad', 1100);
        setTimeout(function () { scene.classList.remove('goleft', 'goright'); }, 650);
        p.rounds.forEach(function (r, k) {
          if (r[r.length - 1] === i) { s.marks[k] = r.every(function (j) { return boltOk(c, j, bolts[j]); }); tribRow(c); }
        });
      });
      clear();
      var i = 0; while (i < bolts.length && s.landed[i]) i++;
      if (i >= bolts.length) { hint.textContent = 'The clouds part…'; return; }
      var b = bolts[i], info = s.info[i];
      if (t >= b.warn - 0.25 && !s.asked[i]) {
        s.asked[i] = 1;
        press({bolt: i, omen: '1'}).then(function (r) { if (r && r.bolt === i) s.info[i] = r; });
      }
      if (t < b.warn || !info) {
        hint.textContent = 'The clouds churn… get ready.';
        return;
      }
      if (!s.warned[i]) { s.warned[i] = 1; Snd('warn'); }
      var left = b.hit - t, f = Math.max(0, Math.min(1, (t - b.warn) / (b.hit - b.warn)));
      var red = info.kind === 'red', safe = red ? safeNow(info, t) : null;
      // the bolt gathering in the clouds above
      ctx.fillStyle = red ? 'rgba(255,90,80,' + (0.2 + 0.45 * f * Math.abs(Math.sin(t * 25))) + ')' : 'rgba(120,180,255,' + (0.2 + 0.45 * f * Math.abs(Math.sin(t * 25))) + ')';
      ctx.beginPath(); ctx.ellipse(cx, H * 0.12, 200, 70, 0, 0, 2 * Math.PI); ctx.fill();
      // the timing ring closing on the cauldron (lands at its edge when the bolt does)
      var R = 120, r = R + 200 * (1 - f);
      ring(cx, cy, R, 'rgba(255,255,255,.35)', 3);
      ring(cx, cy, r, red ? 'rgba(255,110,100,.95)' : 'rgba(140,200,255,.95)', 8);
      if (!red && left <= p.protect) ring(cx, cy, R + 4, 'rgba(255,255,255,.9)', 6);             // now: protect!
      if (red) {                                                                                // the SAFE side
        var sx = safe === 'left' ? W * 0.13 : W * 0.87;
        ctx.save(); ctx.fillStyle = 'rgba(111,217,176,.9)'; ctx.font = '800 30px Cinzel, Georgia, serif'; ctx.textAlign = 'center';
        ctx.fillText('SAFE', sx, cy - 10); ctx.font = '800 52px Arial'; ctx.fillText(safe === 'left' ? '⇦' : '⇨', sx, cy + 44); ctx.restore();
        if (info.flip && Math.abs(t - info.flip) < 0.25) flash('The clouds shift!', 'bad', 500);
      }
      var mine = s.acts[i];
      if (mine && mine[0] === 'protect' && t - mine[1] <= p.protect + 0.05) shieldDome(cx, cy, 1 - (t - mine[1]) / (p.protect + 0.05));
      if (b.warn + 0.05 > 0 && b.hit - b.warn >= 1.6) {                                           // 3, 2, 1
        var n = Math.ceil(left);
        if (n >= 1 && n <= 3) { label(String(n), H * 0.36); if (!s.ticks[i + ':' + n]) { s.ticks[i + ':' + n] = 1; Snd('tick'); } }
      }
      hint.innerHTML = red ? '🔴 <b>Red bolt!</b> Too strong to block. <b>DODGE ' + (safe === 'left' ? '← LEFT' : 'RIGHT →') + '</b> to the safe side!'
        : '🔵 <b>Blue bolt!</b> <b>PROTECT</b> (Space) as the ring closes on the cauldron!';
    },
    dir: function (c, d) {
      var p = c.pub, s = c.st, t = now(), i = 0;
      while (i < p.bolts.length && s.landed[i]) i++;
      if (i >= p.bolts.length || s.acts[i] || t < p.bolts[i].warn - 0.25) return;
      s.acts[i] = [d, t];
      if (d === 'protect') Snd('whoosh');
      else { scene.classList.remove('goleft', 'goright'); scene.classList.add(d === 'left' ? 'goleft' : 'goright'); Snd('whoosh'); }
      document.querySelectorAll('#ldirs .btn').forEach(function (b) { b.classList.toggle('chosen', b.dataset.dir === d); });
      setTimeout(function () { document.querySelectorAll('#ldirs .btn').forEach(function (b) { b.classList.remove('chosen'); }); }, 600);
      press({bolt: i, act: d});
    }
  };
  function safeNow(info, t) { return info.flip && t >= info.flip ? (info.safe === 'left' ? 'right' : 'left') : info.safe; }
  function boltOk(c, i, b) {
    var a = c.st.acts[i], info = c.st.info[i];
    if (!a || !info) return false;
    if (b.kind === 'blue') return a[0] === 'protect' && a[1] >= b.hit - c.pub.protect - c.pub.grace && a[1] <= b.hit + c.pub.grace;
    return a[0] === (info.flip ? (info.safe === 'left' ? 'right' : 'left') : info.safe);
  }
  function tribRow(c) {
    var html = c.pub.rounds.map(function (r, k) {
      var m = c.st.marks[k], kinds = r.map(function (i) { return c.pub.bolts[i].kind === 'red' ? '🔴' : '🔵'; }).join('');
      return '<span class="tround' + (m === true ? ' ok' : m === false ? ' bad' : '') + '">' + (m === true ? '🛡️' : m === false ? '⚡' : '○') + ' <small>' + kinds + '</small></span>';
    }).join('');
    $('ltrib').innerHTML = html;
  }
  function shieldDome(x, y, a) {
    ctx.save(); ctx.globalAlpha = Math.max(0.15, a);
    var g = ctx.createRadialGradient(x, y, 40, x, y, 170);
    g.addColorStop(0, 'rgba(111,217,176,0)'); g.addColorStop(0.8, 'rgba(111,217,176,.35)'); g.addColorStop(1, 'rgba(168,240,210,.9)');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, 170, Math.PI, 2 * Math.PI); ctx.closePath(); ctx.fill();
    ctx.strokeStyle = '#A8F0D2'; ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(x, y, 170, Math.PI, 2 * Math.PI); ctx.stroke();
    ctx.restore();
  }
  function Snd(n) { if (window.AlchemySound) window.AlchemySound.play(n); }

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
    scene.classList.remove('storm', 'cold', 'zone', 'hot', 'goleft', 'goright');
    ['ltrib'].forEach(function (id) { show(id, false); });
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
    if (kind === 'down' && !def.down && def.dir) def.dir(cur, 'protect');
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
  var DIRS = {ArrowLeft: 'left', ArrowUp: 'protect', ArrowRight: 'right'};
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
