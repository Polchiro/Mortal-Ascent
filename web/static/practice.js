/* Practice with Senior Sister Xue (web/practice_play.py, docs/technique.md "Practice on the website"): the drill
   played in real time from the pattern the server made.

   Striking (attack techniques): targets light up on the dummy (the kicking post for kicks); hit each one in its lane
   as its ring closes. Defending (defense techniques): a sandbag (high), a staff (middle) or a log (low) comes at you;
   meet it in its lane as it lands, and hold a brace until it has passed. Space: a counter, or a breath.

   The page only keeps time: every press and let-go is written down as [ms since the drill began, lane, 'd' | 'u'] and
   sent when the drill ends. The server grades them itself and pays what the bot pays; what the page shows while you
   play ("Perfect", the score) is the same rules worked out here, for the feel of it.

   Her movements are cut from SHOAIB's videos (art/practice/instructor/, scripts/make_master_sheets.py --instructor)
   with their own sound, played loud over the music: she raises her hand and cuts the air to begin the drill, watches
   while you work, and approves or shakes her head at the end. The hall's own sound loops under the music. */
(function () {
  'use strict';
  var main = document.getElementById('practice');
  if (!main) return;
  var S = JSON.parse(document.getElementById('pstate').textContent);
  function $(id) { return document.getElementById(id); }
  function fs(name, arg, delay) { var F = window.FightSound; if (F) F.play(name, arg, delay); }
  if (window.FightSound) window.FightSound.voice = S.me.gender;

  var D = S.drill, W = S.w, P = S.prompts, STRIKE = D.mode === 'strike';
  var scene = $('pscene'), fme = $('fme'), poses = fme.querySelector('.poses');
  var reduced = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var soundOn = true, soundVol = 0.6;
  try {
    soundOn = localStorage.getItem('ma.sound') !== 'off';
    var v0 = parseFloat(localStorage.getItem('ma.vol')); if (v0 >= 0 && v0 <= 100) soundVol = v0 / 100;
  } catch (e0) {}
  function LOUD() { return Math.min(1, soundVol * 1.7); }        // her voice and the hall's blows are meant to be heard

  /* ── the lanes: which key, what it's called, where it lands ─────── */
  var LANES = STRIKE ? D.lanes : 4;
  /* Your own keys (the drill card's Settings): one per lane, kept in this browser for each kind of drill. The number
     keys (and the arrows when defending) work as well, unless you gave one of them to another lane. Guides: the key
     written on each target and a faint mark where targets appear; they can be turned off. */
  var DEFAULT = STRIKE ? ['d', 'f', 'j', 'k'] : ['w', 'd', 's', ' '];
  var ALT = STRIKE ? [['1'], ['2'], ['3'], ['4']] : [['1', 'arrowup'], ['2', 'arrowright'], ['3', 'arrowdown'], ['4']];
  var STORE = 'ma.practice.keys.' + D.mode, keys = DEFAULT.slice(), guides = true, LANE_OF = {}, capturing = null;
  function usable(k) { return typeof k === 'string' && (k.length === 1 || k.indexOf('arrow') === 0); }
  try {
    var saved = JSON.parse(localStorage.getItem(STORE) || 'null');
    if (Array.isArray(saved) && saved.length === 4 && saved.every(usable) &&
        saved.every(function (k, i) { return saved.indexOf(k) === i; })) keys = saved;
    guides = localStorage.getItem('ma.practice.guides') !== 'off';
  } catch (e2) {}
  function keyName(k) {
    return k === ' ' ? 'Space' : {arrowup: '↑', arrowdown: '↓', arrowleft: '←', arrowright: '→'}[k] || k.toUpperCase();
  }
  var LABEL = STRIKE
    ? (D.target === 'post' ? ['High', 'Middle', 'Low'] : ['Head', 'Upper arm', 'Lower arm', 'Leg'])
    : ['High', 'Middle', 'Low', D.effect === 'counter' ? 'Counter' : D.effect === 'recover' ? 'Breathe' : 'Space'];
  /* where each lane's target sits on the picture (fractions of its box), measured on SHOAIB's pictures */
  var SPOTS = D.target === 'post' ? [[0.5, 0.2], [0.5, 0.42], [0.5, 0.64]]
    : [[0.6, 0.1], [0.36, 0.29], [0.36, 0.46], [0.4, 0.7]];
  if (STRIKE) setTimeout(function () { gmarks.forEach(function (g, i) { g.style.left = SPOTS[i][0] * 100 + '%'; g.style.top = SPOTS[i][1] * 100 + '%'; }); bind(); }, 0);
  else setTimeout(bind, 0);
  var MARKS = [[0.5, 0.27], [0.5, 0.47], [0.5, 0.82]];          // high, middle, low on your body (fractions of the fighter box)
  var BLOW = [{img: '/art/practice/sandbag.webp', w: 0.09, cls: 'bag'}, {img: '/art/practice/staff.webp', w: 0.42, cls: 'staff'},
              {img: '/art/practice/log.webp', w: 0.3, cls: 'log'}];
  var WOOD = {straw: 1, dummy: 1, post: 1};

  (function keys() {
    var pads = $('ppads'), out = [];
    for (var i = 0; i < LANES; i++) {
      var b = document.createElement('button');
      b.type = 'button'; b.className = 'ppad' + (!STRIKE && i === 3 ? ' space' : ''); b.dataset.lane = i;
      b.innerHTML = '<b></b><small></small>';
      b.querySelector('b').textContent = LABEL[i];
      (function (lane) {
        b.addEventListener('pointerdown', function (e) { e.preventDefault(); down(lane); });
        ['pointerup', 'pointercancel', 'pointerleave'].forEach(function (ev) { b.addEventListener(ev, function () { up(lane); }); });
      })(i);
      pads.appendChild(b);
    }
  })();
  /* the faint marks where targets appear, and the Settings: a key for each lane, guides on or off */
  var gmarks = [];
  (function () {
    var box = STRIKE ? $('ptarget') : $('pmarks'), at = STRIKE ? null : [[0.5, 0.27], [0.5, 0.47], [0.5, 0.82]];
    for (var i = 0; i < (STRIKE ? LANES : 3); i++) {
      var g = document.createElement('div'); g.className = 'pguide'; g.innerHTML = '<b></b>'; g.dataset.lane = i;
      box.appendChild(g); gmarks.push(g);
      if (at) { g.style.left = at[i][0] * 100 + '%'; g.style.top = at[i][1] * 100 + '%'; }
    }
    var row = $('pkeyrow');
    for (var j = 0; j < LANES; j++) {
      var b = document.createElement('button');
      b.type = 'button'; b.className = 'pkeybtn'; b.dataset.lane = j; b.innerHTML = '<small></small><b></b>';
      b.querySelector('small').textContent = LABEL[j];
      (function (lane) { b.addEventListener('click', function () { capturing = capturing === lane ? null : lane; bind(); }); })(j);
      row.appendChild(b);
    }
    $('pguides').checked = guides;
    $('pguides').addEventListener('change', function () {
      guides = this.checked;
      try { localStorage.setItem('ma.practice.guides', guides ? 'on' : 'off'); } catch (e3) {}
      bind();
    });
    $('pkeyreset').addEventListener('click', function () { keys = DEFAULT.slice(); capturing = null; save(); bind(); });
  })();
  function save() { try { localStorage.setItem(STORE, JSON.stringify(keys)); } catch (e4) {} }
  function bind() {                                              // the keys as they stand now, everywhere they are shown
    LANE_OF = {};
    var i;
    for (i = 0; i < LANES; i++) LANE_OF[keys[i]] = i;
    ALT.forEach(function (ks, lane) { if (lane < LANES) ks.forEach(function (k) { if (LANE_OF[k] == null) LANE_OF[k] = lane; }); });
    var out = [];
    for (i = 0; i < LANES; i++) {
      var name = keyName(keys[i]);
      main.querySelector('.ppad[data-lane="' + i + '"] small').textContent = name;
      var kb = main.querySelector('.pkeybtn[data-lane="' + i + '"]');
      kb.querySelector('b').textContent = capturing === i ? 'Press a key…' : name; kb.classList.toggle('on', capturing === i);
      if (gmarks[i]) gmarks[i].querySelector('b').textContent = name;
      out.push(name + ' ' + LABEL[i].toLowerCase());
    }
    $('pkeys').textContent = 'Keys: ' + out.join(' · ') + '. Change them in Settings. On a phone, the pads below.';
    main.classList.toggle('noguide', !guides);
  }
  function capture(e) {                                          // Settings is waiting for a key for one lane
    var k = (e.key || '').toLowerCase();
    e.preventDefault();
    if (k === 'escape') { capturing = null; bind(); return; }
    if (!usable(k)) return;
    var other = keys.indexOf(k);
    if (other >= 0 && other !== capturing) keys[other] = keys[capturing];      // taken: the two lanes swap keys
    keys[capturing] = k; capturing = null; save(); bind();
  }

  /* ── preload: the art the drill shows ─────────────────────────── */
  ['/art/practice/plaque.webp', '/art/practice/sparks.webp', '/art/practice/splinters.webp', '/art/practice/flame.webp',
   '/art/practice/breath.webp', '/art/practice/aura.webp', '/art/practice/bell.webp', '/art/practice/broken.webp']
    .concat(STRIKE ? [] : BLOW.map(function (b) { return b.img; }))
    .forEach(function (src) { new Image().src = src; });

  function ease(x) { return x < 0 ? 0 : x > 1 ? 1 : 1 - Math.pow(1 - x, 3); }
  function span(t, a, b) { return b <= a ? (t >= b ? 1 : 0) : Math.max(0, Math.min(1, (t - a) / (b - a))); }
  function again(el, text, cls) { el.textContent = text; el.className = el.className.replace(/ (go|perfect|good|miss|warn)\b/g, ''); void el.offsetWidth; el.className += ' go' + (cls ? ' ' + cls : ''); }

  /* ── Senior Sister Xue, frame by frame ────────────────────────── */
  var I = S.instructor, MS = I.sheets ? I.sheets.sheets : null, tsheets = {}, tPlay = null, tT0 = performance.now();
  var teacher = $('pteacher');
  teacher.querySelectorAll('.ptsheet').forEach(function (el) { tsheets[el.dataset.name] = el; });
  if (MS) Object.keys(MS).forEach(function (k) { new Image().src = MS[k].src; });
  function tshow(name, f) {
    var sp = MS[name], el = tsheets[name];
    f = Math.max(0, Math.min(sp.frames - 1, f));
    el.style.backgroundPosition = (sp.cols > 1 ? (f % sp.cols) / (sp.cols - 1) * 100 : 0) + '% ' +
      (sp.rows > 1 ? Math.floor(f / sp.cols) / (sp.rows - 1) * 100 : 0) + '%';
    Object.keys(tsheets).forEach(function (k) { tsheets[k].classList.toggle('on', k === name); });
  }
  function tframe(name, tm) {
    var at = MS[name].at, i = 0;
    while (i + 1 < at.length && at[i + 1] <= tm) i++;
    return i;
  }
  /* she plays `name` from the start until `until` ms (her videos end standing as they began, so the rest is cut),
     her own sound with it, then watches again */
  var CUT = {begin: 5200, approve: 6200, disapprove: 7600};
  function tplay(name, done) {
    if (!MS || !MS[name]) { if (done) setTimeout(done, 1200); return; }
    var until = Math.min(CUT[name] || 1e9, MS[name].at[MS[name].frames - 1]), snd = MS[name].sound, a = null;
    if (snd && soundOn) {
      a = new Audio(snd.src); a.volume = LOUD();
      var go = function () { var p = a.play(); if (p && p.catch) p.catch(function () {}); };
      if (snd.from) setTimeout(go, snd.from); else go();
    }
    tPlay = {name: name, t0: performance.now(), until: until, done: done, audio: a};
  }
  function tloop(now) {
    if (MS) {
      if (tPlay) {
        var tm = now - tPlay.t0;
        tshow(tPlay.name, tframe(tPlay.name, tm));
        if (tm >= tPlay.until) {
          var cb = tPlay.done, a = tPlay.audio; tPlay = null; tT0 = now;
          if (a) fadeOut(a);
          if (cb) cb();
        }
      } else if (MS.watch) tshow('watch', tframe('watch', (now - tT0) % (MS.watch.loop || MS.watch.at[MS.watch.frames - 1] + 250)));
    }
    requestAnimationFrame(tloop);
  }
  function fadeOut(a) {
    var v = a.volume, k = setInterval(function () { v -= 0.08; if (v <= 0) { a.pause(); clearInterval(k); } else a.volume = v; }, 40);
  }
  requestAnimationFrame(tloop);
  function say(text) { again($('psay'), text); }

  /* ── the hall: dust in the sunlight ────────────────────────────── */
  (function () {
    var box = $('pmotes');
    if (!box || reduced) return;
    for (var i = 0; i < 26; i++) {
      var m = document.createElement('i'), sz = 2 + Math.random() * 3.5;
      m.style.left = (Math.random() * 100) + '%'; m.style.top = (Math.random() * 90) + '%';
      m.style.width = m.style.height = sz + 'px';
      m.style.animationDuration = (10 + Math.random() * 14) + 's'; m.style.animationDelay = (-Math.random() * 20) + 's';
      box.appendChild(m);
    }
  })();

  /* ── your movements ────────────────────────────────────────────── */
  var SPEC = S.me.sheets || {}, sheets = {}, anim = null;
  fme.querySelectorAll('.ssheet').forEach(function (el) { sheets[el.dataset.name] = el; });
  Object.keys(SPEC).forEach(function (k) { new Image().src = SPEC[k].src; });
  var MOVE = SPEC[D.motion] ? D.motion : (!STRIKE && SPEC.guard ? 'guard' : null);
  function show(name, f) {
    var sp = SPEC[name], el = sheets[name];
    f = Math.max(0, Math.min(sp.frames - 1, Math.round(f))); cur = f;
    el.style.backgroundPosition = (sp.cols > 1 ? (f % sp.cols) / (sp.cols - 1) * 100 : 0) + '% ' +
      (sp.rows > 1 ? Math.floor(f / sp.cols) / (sp.rows - 1) * 100 : 0) + '%';
    Object.keys(sheets).forEach(function (k) { sheets[k].classList.toggle('on', k === name); });
    clearTimeout(blendK); fme.classList.remove('blend');
    fme.dataset.pose = 'sheet';
  }
  var cur = 0, blendK = null;                                   // the frame shown now
  function hero(x) { poses.style.transform = x ? 'translateX(' + x.toFixed(1) + 'px)' : ''; }
  /* back to the stance: the movement's last frame fades out over the stance for a moment, instead of a jump */
  function stand() {
    anim = null; hero(0); fme.dataset.pose = 'idle'; fme.classList.add('blend');
    clearTimeout(blendK);
    blendK = setTimeout(function () { fme.classList.remove('blend'); Object.keys(sheets).forEach(function (k) { sheets[k].classList.remove('on'); }); }, 180);
  }
  function keyed(keys, t) {
    var f = keys[keys.length - 1][1];
    for (var j = 1; j < keys.length; j++) {
      if (t < keys[j][0]) { var a = keys[j - 1], b = keys[j]; f = a[1] + (b[1] - a[1]) * span(t, a[0], b[0]); break; }
    }
    return f;
  }
  function frames() {                                          // the movement's key frames: set, out, back, done
    var sp = SPEC[MOVE], n = sp.frames - 1;
    if (MOVE === 'guard') return {set: sp.first || 4, out: Math.min(n, (sp.first || 4) + 4), back: Math.min(n, (sp.first || 4) + 12), n: n};
    var rel = Math.min(sp.release || n, n);
    return {set: Math.min(sp.windup || sp.jab || 0, rel), out: rel, back: Math.min(sp.back || rel, n), n: n};
  }
  /* how far to step in so the hand meets the target of `lane` (striking only), px */
  function reach(lane) {
    if (!STRIKE || lane == null || !target || !SPEC[MOVE] || !SPOTS[lane]) return 0;
    var hand = SPEC[MOVE].hand || [0.72, 0.4], f = fme.getBoundingClientRect(), r = target.getBoundingClientRect();
    var dx = r.left + r.width * SPOTS[lane][0] - (f.left + f.width * hand[0]);
    return Math.max(0, Math.min(scene.clientWidth * 0.3, dx - r.width * 0.06));
  }
  /* one movement: 'strike' (out and back), 'hold' (out, held until let go), 'charge' (drawn back, held). A new one
     starts from the frame shown now, so quick blows flow into each other instead of snapping back to the start */
  function act(kind, lane) {
    if (!MOVE) {                                                // no movement of its own: the two still poses
      fme.dataset.pose = kind === 'charge' ? 'windup' : 'strike';
      if (kind === 'strike') { clearTimeout(act.k); act.k = setTimeout(function () { fme.dataset.pose = 'idle'; }, 260); }
      return;
    }
    var F = frames(), from = anim && fme.dataset.pose === 'sheet' ? Math.min(cur, F.out) : F.set;
    var go = reach(lane), x0 = anim ? (anim.x || 0) : 0;
    if (kind === 'charge') anim = {keys: [[0, anim ? cur : 0], [300, F.set]], t0: performance.now(), hold: true, dx: [[0, x0], [300, 0]]};
    else if (kind === 'hold') anim = {keys: [[0, from], [120, F.out]], t0: performance.now(), hold: true};
    else {
      var mid = Math.round((F.out + F.back) / 2);
      anim = {keys: [[0, from], [90, F.out], [210, F.out], [380, mid], [560, F.back], [760, F.n]], t0: performance.now(),
              dx: [[0, x0], [90, go], [230, go], [560, 0]]};
    }
  }
  function release() {                                          // let go of a charge or a brace
    if (!MOVE) { fme.dataset.pose = 'strike'; clearTimeout(act.k); act.k = setTimeout(function () { fme.dataset.pose = 'idle'; }, 260); return; }
    var F = frames(), go = reach(release.lane);
    anim = {keys: [[0, cur], [90, F.out], [240, F.out], [480, F.back], [700, F.n]], t0: performance.now(),
            dx: [[0, 0], [90, go], [260, go], [560, 0]]};
  }
  function animate(now) {
    if (anim) {
      var t = now - anim.t0, last = anim.keys[anim.keys.length - 1][0];
      show(MOVE, keyed(anim.keys, Math.min(t, last)));
      if (anim.dx) { anim.x = keyed(anim.dx, Math.min(t, anim.dx[anim.dx.length - 1][0])); hero(anim.x); }
      if (!anim.hold && t > last + 30) stand();
    }
  }

  /* ── effects ───────────────────────────────────────────────────── */
  function pt(el, fx, fy) {                                    // a point of an element, in px inside the scene
    var r = el.getBoundingClientRect(), s = scene.getBoundingClientRect();
    return [r.left - s.left + r.width * fx, r.top - s.top + r.height * fy];
  }
  function pic(src, p, wPct, life, cls) {
    var n = document.createElement('img');
    n.src = src; n.alt = ''; n.className = 'pfx ' + (cls || '');
    n.style.left = p[0] + 'px'; n.style.top = p[1] + 'px'; n.style.width = wPct + '%';
    n.style.animationDuration = (life || 600) + 'ms';
    scene.appendChild(n); setTimeout(function () { n.remove(); }, (life || 600) + 40);
    return n;
  }
  function pop(p, text, cls) {
    var n = document.createElement('p');
    n.className = 'ppop ' + (cls || ''); n.textContent = text; n.style.left = p[0] + 'px'; n.style.top = p[1] + 'px';
    scene.appendChild(n); setTimeout(function () { n.remove(); }, 900);
  }
  function shake(el) { el.classList.remove('shook'); void el.offsetWidth; el.classList.add('shook'); }

  /* ── the drill ─────────────────────────────────────────────────── */
  var t0 = null, running = false, ended = false, inputs = [], res = [], els = {}, held = {}, strays = 0, streak = 0;
  var target = $('ptarget'), blows = $('pblows'), marks = $('pmarks');
  var POINTS = {perfect: 1, good: 0.6, avoided: 1};
  function lead(p) { return W.approach + (p.kind === 'charge' ? S.charge_lead : 0); }
  function shows(p) { return p.at - lead(p) * (S.night ? S.night : 1); }
  function mark(p, t) { var off = Math.abs(t - p.at); return off <= W.perfect ? 'perfect' : off <= W.good ? 'good' : null; }
  function visible(p, t) { return p.at - lead(p) <= t && t <= p.at + W.good; }
  function now() { return performance.now() - t0; }

  function spawn(p) {
    var el;
    if (p.lane === 3 && !STRIKE) {                               // Space: a counter or a breath, at your feet
      el = document.createElement('div');
      el.className = 'pspace ' + (p.breath ? 'breath' : 'counter');
      el.innerHTML = '<img src="/art/practice/' + (p.breath ? 'breath' : 'flame') + '.webp" alt=""><i class="ring"></i><b></b>';
      el.querySelector('b').textContent = (p.breath ? 'Breathe' : 'Counter') + ' · ' + keyName(keys[3]);
      var q = pt(fme, 0.3, 0.55);
      el.style.left = q[0] + 'px'; el.style.top = q[1] + 'px';
      scene.appendChild(el);
    } else if (STRIKE) {
      el = document.createElement('div');
      el.className = 'pspot k-' + p.kind + (p.small ? ' small' : '') + (p.pair ? ' pair' : '') + (p.finish ? ' finish' : '') + (p.rival ? ' rival' : '');
      el.style.left = SPOTS[p.lane][0] * 100 + '%'; el.style.top = SPOTS[p.lane][1] * 100 + '%';
      el.innerHTML = (p.kind === 'charge' ? '<img class="flame" src="/art/practice/flame.webp" alt="">' : '') +
        '<img class="plq" src="/art/practice/plaque.webp" alt=""><i class="ring"></i>' +
        (p.chain ? '<b>' + p.chain + '</b>' : p.kind === 'charge' ? '<b>Hold</b>' : p.kind === 'feint' ? '<b>✕</b>' : '') +
        (p.kind === 'feint' ? '' : '<em class="pk"></em>');
      if (p.kind !== 'feint') el.querySelector('.pk').textContent = keyName(keys[p.lane]);
      target.appendChild(el);
    } else {                                                     // a blow coming at you, and its ring on your body
      var B = BLOW[p.lane];
      el = document.createElement('div');
      el.className = 'pblow ' + B.cls + ' k-' + p.kind + (p.finish ? ' finish' : '') + (p.rival ? ' rival' : '');
      el.innerHTML = '<img src="' + B.img + '" alt="">';
      el.style.width = B.w * 100 + '%';
      blows.appendChild(el);
      var m = document.createElement('div');
      m.className = 'pmark k-' + p.kind; m.innerHTML = '<i class="ring"></i><b></b>';
      m.querySelector('b').textContent = p.kind === 'feint' ? '✕' : keyName(keys[p.lane]);
      m.style.left = MARKS[p.lane][0] * 100 + '%'; m.style.top = MARKS[p.lane][1] * 100 + '%';
      marks.appendChild(m);
      el.mark = m;
    }
    els[p.i] = el;
    if (p.rival && !spawn.rival) { spawn.rival = true; again($('pbanner'), 'The rival disciple steps in! Beat three targets.', 'warn'); fs('cast'); }
    if (p.finish) again($('pbanner'), STRIKE ? 'Finishing blow: hold, and release on the mark!' : 'The heavy blow!', 'warn');
  }
  function place(p, t) {                                         // where a prompt is drawn at t
    var el = els[p.i]; if (!el) return;
    var x = (t - (p.at - lead(p))) / lead(p), ring = el.querySelector('.ring') || (el.mark && el.mark.querySelector('.ring'));
    var sc = 1 + 2.2 * Math.max(0, 1 - x);
    if (ring) ring.style.transform = 'translate(-50%,-50%) scale(' + sc.toFixed(3) + ')';
    if (el.classList.contains('pblow')) {
      var me = pt(fme, 0.6, MARKS[p.lane][1]), sw = scene.clientWidth, x0 = sw * 1.02, k = Math.pow(Math.min(1, x), 1.7);
      if (p.kind === 'feint' && x > 0.8) k = Math.pow(0.8, 1.7) * (1 - span(x, 0.8, 1.05) * 0.9);    // it pulls back
      var X = x0 + (me[0] - x0) * k, rot = p.lane === 0 ? -14 * (1 - k) : p.lane === 2 ? 10 * (1 - k) : 0;
      el.style.transform = 'translate(' + X.toFixed(1) + 'px,' + me[1].toFixed(1) + 'px) translateY(' + (p.lane === 0 ? -72 : -50) + '%) rotate(' + rot + 'deg)';
    }
  }
  function settle(p, r, t) {                                     // a prompt is decided: show it, sound it
    res[p.i] = r;
    var el = els[p.i], good = r === 'perfect' || r === 'good';
    var where = el ? (el.mark ? pt(el.mark, 0.5, 0.5) : pt(el, 0.5, 0.5)) : pt(fme, 0.6, 0.4);
    if (good || r === 'avoided') { streak++; } else streak = 0;
    $('pstreak').textContent = streak;
    var done = res.filter(function (x, i) { return x && !P[i].rival; });
    var got = done.reduce(function (s, x) { return s + (POINTS[x] || 0); }, 0) - 0.2 * strays;
    $('pscore').textContent = Math.max(0, Math.round(100 * got / Math.max(1, done.length))) + '%';
    if (r === 'avoided') { if (el) el.classList.add('gone'); pop(where, 'Left alone', 'good'); }
    else if (r === 'struck') { if (el) el.classList.add('bad'); pop(where, 'Feint!', 'miss'); fs('miss'); }
    else if (good) {
      pop(where, r === 'perfect' ? 'Perfect' : 'Good', r);
      if (el) el.classList.add('hit');
      if (STRIKE || p.lane === 3) {
        if (p.breath) { pic('/art/practice/breath.webp', pt(fme, 0.5, 0.45), 16, 900, 'soft'); fs('heal'); }
        else {
          pic(WOOD[D.target] && STRIKE ? '/art/practice/splinters.webp' : '/art/practice/sparks.webp', where, p.kind === 'charge' ? 20 : 11, 520);
          if (p.counter) fs('swing'); fs(p.kind === 'charge' ? 'boom' : 'hit');
          if (target) shake(target);
        }
      } else {
        pic('/art/practice/sparks.webp', where, 12, 480);
        fs(D.motion === 'sidestep' ? 'dodge' : 'block');
      }
      if (r === 'perfect' && streak && streak % 8 === 0) { pic('/art/practice/aura.webp', pt(fme, 0.5, 0.5), 18, 1100, 'soft'); again($('pcall'), streak + ' in a row!', 'perfect'); }
    } else {
      pop(where, 'Miss', 'miss');
      if (el) el.classList.add('missed');
      if (!STRIKE && p.lane < 3) { fme.classList.remove('hurt'); void fme.offsetWidth; fme.classList.add('hurt'); fs('hurt'); }
    }
    if (el) setTimeout(function () { el.remove(); if (el.mark) el.mark.remove(); }, good ? 260 : 380);
    if (el && el.classList.contains('pblow') && good) el.classList.add('back');
  }

  function down(lane) {
    if (!running) return;
    var t = now();
    if (held[lane]) return;
    inputs.push([Math.round(t), lane, 'd']);
    var c = P.filter(function (p) {
      return p.lane === lane && res[p.i] == null && p.kind !== 'feint' &&
        (p.kind === 'charge' ? visible(p, t) : Math.abs(t - p.at) <= W.good);
    }).sort(function (a, b) { return Math.abs(t - a.at) - Math.abs(t - b.at); })[0];
    if (c) {
      if (c.kind === 'tap') { act('strike', c.lane); settle(c, mark(c, t) || 'miss', t); }
      else if (c.kind === 'brace') {
        var m = mark(c, t); act('hold'); held[lane] = c; c.got = m;
        if (els[c.i]) els[c.i].classList.add('held');
        pop(els[c.i] ? pt(els[c.i].mark || els[c.i], 0.5, 0.5) : pt(fme, 0.6, 0.4), 'Hold…', 'good'); fs('guardup');
      } else { act('charge'); held[lane] = c; res[c.i] = 'holding'; if (els[c.i]) els[c.i].classList.add('held'); fme.classList.add('charging'); fs('gather'); }
      pad(lane, true);
      return;
    }
    var f = P.filter(function (p) { return p.lane === lane && p.kind === 'feint' && res[p.i] == null && visible(p, t); })[0];
    act('strike', lane);
    if (f) settle(f, 'struck', t);
    else { strays++; streak = 0; $('pstreak').textContent = 0; pop(pt(STRIKE ? target : fme, STRIKE ? SPOTS[lane][0] : 0.6, STRIKE ? SPOTS[lane][1] : (MARKS[lane] || [0, 0.9])[1]), '·', 'stray'); }
    pad(lane, true);
  }
  function up(lane) {
    pad(lane, false);
    if (!running) return;
    var c = held[lane];
    inputs.push([Math.round(now()), lane, 'u']);
    if (!c) return;
    delete held[lane];
    var t = now();
    fme.classList.remove('charging');
    release.lane = lane; release();
    if (c.kind === 'charge') { res[c.i] = null; settle(c, mark(c, t) || 'miss', t); }
    else if (t < c.at + c.hold - 90) { settle(c, c.got === 'perfect' ? 'good' : 'miss', t); if (c.got) pop(pt(fme, 0.5, 0.1), 'Let go too soon', 'miss'); }
    else settle(c, c.got || 'miss', t);
  }
  function pad(lane, on) { var b = main.querySelector('.ppad[data-lane="' + lane + '"]'); if (b) b.classList.toggle('on', on); }

  function frame(nowMs) {
    animate(nowMs);
    if (running) {
      var t = now();
      P.forEach(function (p) {
        if (res[p.i] != null && res[p.i] !== 'holding' && !(held[p.lane] === p)) return;
        if (!els[p.i] && t >= shows(p) && t < p.at + W.good + 50) spawn(p);
        if (els[p.i]) place(p, t);
        var h = held[p.lane] === p;
        if (p.kind === 'brace' && h && t >= p.at + p.hold) {          // held through: the blow has passed
          delete held[p.lane]; release(); pad(p.lane, false); settle(p, p.got || 'miss', t);
        } else if (!h && res[p.i] == null && t > p.at + W.good) settle(p, p.kind === 'feint' ? 'avoided' : 'miss', t);
      });
      var cur = P.filter(function (p) { return p.at >= t - 300; })[0];
      $('pphase').textContent = cur ? {form: 'Form', flow: 'Flow', finish: 'Finish', rival: 'Rival'}[cur.phase] : 'Done';
      $('pclock').style.width = Math.min(100, 100 * t / S.length) + '%';
      if (t >= S.length + 150) finish();
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  /* keys: each lane's own, held down and let go */
  document.addEventListener('keydown', function (e) {
    if (capturing != null) { capture(e); return; }
    var k = (e.key || '').toLowerCase(), lane = LANE_OF[k];
    if (lane == null || e.ctrlKey || e.metaKey || e.altKey) return;
    if (running || k === ' ' || k.indexOf('arrow') === 0) e.preventDefault();
    if (e.repeat) return;
    down(lane);
  });
  document.addEventListener('keyup', function (e) {
    var lane = LANE_OF[(e.key || '').toLowerCase()];
    if (lane != null) up(lane);
  });

  /* ── begin: she raises her hand and cuts the air; the drill starts on the cut ── */
  var BEGIN_AT = 4000;                                          // ms into her "begin" when her hand comes down
  function begin() {
    $('pbegin').disabled = true; capturing = null;
    main.dataset.phase = 'count';
    if (window.SparMusic) { window.SparMusic.start('practice'); if (S.hall.sound) window.SparMusic.ambience(S.hall.sound); }
    tplay('begin');
    say(I.line);
    var count = $('pcount');
    [[1200, '3'], [2100, '2'], [3000, '1']].forEach(function (c) { setTimeout(function () { again(count, c[1]); fs('press'); }, c[0]); });
    setTimeout(function () {
      again(count, 'Begin!', 'perfect');
      fetch('/practice/go', {method: 'POST'}).then(function (r) { return r.json(); }).then(function (j) {
        if (j.error || j.gone) { again($('pbanner'), j.error || 'The drill is over.', 'warn'); return; }
      }).catch(function () {});
      t0 = performance.now(); running = true; main.dataset.phase = 'drill';
    }, MS ? BEGIN_AT : 3800);
  }
  $('pbegin').addEventListener('click', begin);

  /* ── the end: send the presses, and hear her verdict ─────────── */
  function finish() {
    if (ended) return;
    ended = true; running = false; stand(); fme.classList.remove('charging');
    Object.keys(held).forEach(function (l) { inputs.push([Math.round(now()), +l, 'u']); });
    main.dataset.phase = 'wait';
    again($('pbanner'), 'She tallies your drill…');
    var send = function (tries) {
      fetch('/practice/submit', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({inputs: inputs})})
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if (j.result) return result(j.result, true);
          if (j.error && /isn't over/.test(j.error) && tries < 4) return setTimeout(function () { send(tries + 1); }, 900);
          again($('pbanner'), j.error || 'The drill is over.', 'warn');
          setTimeout(function () { location.href = '/training#practice'; }, 2500);
        })
        .catch(function () { if (tries < 4) setTimeout(function () { send(tries + 1); }, 1500); });
    };
    send(0);
  }
  function result(r, fresh) {
    main.dataset.phase = 'result';
    if (window.SparMusic && fresh) window.SparMusic.stop();
    $('pbanner').textContent = ''; $('pbanner').className = 'pbanner';
    var pctScore = Math.round(r.score * 100);
    $('rkick').textContent = {great: 'EXCELLENT', good: 'WELL DONE', poor: 'SLOPPY', bad: 'AGAIN, PROPERLY'}[r.verdict];
    $('rscore').textContent = pctScore + '%';
    $('rline').textContent = '"' + r.line + '"';
    var counts = [['Perfect', r.perfect], ['Good', r.good], ['Missed', r.miss]];
    if (r.avoided || r.struck) counts.push(['Feints left alone', r.avoided + ' / ' + (r.avoided + r.struck)]);
    counts.push(['Best run', r.best_run]);
    if (r.strays) counts.push(['Wasted presses', r.strays]);
    var ul = $('rcounts'); ul.innerHTML = '';
    counts.forEach(function (c) { var li = document.createElement('li'); li.innerHTML = '<span></span><b></b>'; li.firstChild.textContent = c[0]; li.lastChild.textContent = c[1]; ul.appendChild(li); });
    $('rexp').textContent = '+' + r.gained + ' mastery EXP · ' + r.bar.exp.toLocaleString() + ' / ' + (r.bar.cap || r.bar.exp).toLocaleString() + ' (' + r.bar.stage + ')';
    var notes = r.notes.slice();
    if (r.bar.full) notes.unshift('The mastery bar is full: take the trial with the Martial Master.');
    notes.push('Rest ' + r.again + ' before the next drill.');
    var nl = $('rnotes'); nl.innerHTML = '';
    notes.forEach(function (t) { var li = document.createElement('li'); li.textContent = t; nl.appendChild(li); });
    var fill = $('rbar'), cap = r.bar.cap || 1;
    fill.style.width = Math.min(100, 100 * r.bar.before / cap) + '%';
    var show = function () {
      $('presult').hidden = false;
      setTimeout(function () { fill.style.width = Math.min(100, 100 * r.bar.exp / cap) + '%'; }, 400);
    };
    if (!fresh) { show(); say(r.line); return; }
    if (target && r.verdict === 'great' && D.target === 'dummy') {    // the wooden dummy gives way
      setTimeout(function () {
        target.classList.add('broken'); fs('boom');
        pic('/art/practice/splinters.webp', pt(target, 0.55, 0.4), 30, 900);
      }, 300);
    }
    if (r.verdict === 'great') setTimeout(function () { pic('/art/practice/bell.webp', pt(teacher, 0.5, 0.05), 16, 1400, 'soft'); }, 500);
    setTimeout(function () {
      tplay(r.approve ? 'approve' : 'disapprove');
      say(r.line);
    }, 700);
    setTimeout(show, 2600);
  }

  /* Leave (the corner): walking away from a drill earns nothing and the rest stays, so it asks once; after the
     result it is simply the way back to the training yard */
  (function () {
    var form = $('pleave'), label = form.querySelector('span'), sure = false, k = null;
    form.addEventListener('submit', function (e) {
      if (main.dataset.phase === 'result') { form.action = '/practice/done'; return; }
      if (sure) return;
      e.preventDefault(); sure = true; label.textContent = 'Leave? No EXP'; form.classList.add('sure');
      clearTimeout(k); k = setTimeout(function () { sure = false; label.textContent = 'Leave'; form.classList.remove('sure'); }, 3500);
    });
  })();

  /* ── what the page opens on ────────────────────────────────────── */
  if (S.result) { $('pintro').hidden = true; result(S.result, false); }
  else if (S.begun) {                                            // reloaded in the middle: the drill's clock is lost
    $('pbegin').hidden = true;
    var lost = document.createElement('p'); lost.className = 'anotice'; lost.textContent = 'You left the drill in the middle. It can only be walked away from now.';
    $('pintro').insertBefore(lost, $('pintro').querySelector('.pbtns'));
  }
})();
