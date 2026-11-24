/* Train: Meridian Circulation (web/train_play.py, docs/training.md "Train on the website"). PROTOTYPE (PR 1): the
   body and its meridians are drawn in code on one canvas over the hall picture; the art comes later.

   The server sent the whole session (the map of each cycle and every pulse). This page runs it with the same rules
   the server uses (train_sim.js), tick by tick, and records what you do as [ms since the Qi began to move, what,
   which]: "j" a junction turned, "g" a gate opened or closed, "b" / "B" breath held / let go. At the end it sends
   that list; the server replays it and scores it. What this page shows (the score, the Stability) is for the feel.

   Controls: click a junction or press its number to turn it; click a gate or press Shift + its number to open or
   close it; hold Space (or the Breathe button) to slow all Qi to 40% while your Breath lasts. */
(function () {
  'use strict';
  var main = document.getElementById('train');
  if (!main || !window.TrainSim) return;
  var S = JSON.parse(document.getElementById('tstate').textContent), PLAN = S.plan, SIM = window.TrainSim, TICK = SIM.TICK;
  function $(id) { return document.getElementById(id); }
  function fs(name, arg, delay) { var F = window.FightSound; if (F) F.play(name, arg, delay); }
  if (window.FightSound) window.FightSound.voice = S.me.gender;
  var reduced = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var canvas = $('tmap'), cx = canvas.getContext('2d'), scene = $('tscene');
  var charC = $('tchar'), cc = charC.getContext('2d');
  var W = 0, H = 0, DPR = 1, BOX = {x: 0, y: 0, s: 1};
  var soundOn = true, soundVol = 0.6;
  try {
    soundOn = localStorage.getItem('ma.sound') !== 'off';
    var v0 = parseFloat(localStorage.getItem('ma.vol')); if (v0 >= 0 && v0 <= 100) soundVol = v0 / 100;
  } catch (e0) {}
  function LOUD() { return Math.min(1, soundVol * 1.7); }        // the endings' own sounds are meant to be heard
  /* the art (scripts/make_train_art.py): you meditating, the effects' pictures; without it, drawn in code */
  var HERO = S.hero, FIT = HERO ? HERO.fit : null, FXI = {};
  Object.keys(S.fx || {}).forEach(function (k) { if (S.fx[k]) { FXI[k] = new Image(); FXI[k].src = S.fx[k]; } });
  function fxok(k) { return FXI[k] && FXI[k].complete && FXI[k].naturalWidth > 0; }
  function fxdraw(k, x, y, w, alpha, rot) {                    // an effect's picture, `w` wide, its middle at x, y
    var im = FXI[k], h = w * im.naturalHeight / im.naturalWidth;
    cx.save(); cx.translate(x, y); if (rot) cx.rotate(rot);
    cx.globalAlpha *= alpha == null ? 1 : alpha;
    cx.drawImage(im, -w / 2, -h / 2, w, h); cx.restore();
  }
  var SEAT_Y = 84, SEAT_W = 46;                                  // the cushion under you, in body units

  function again(el, text, cls) { el.textContent = text; el.className = el.className.replace(/ (go|perfect|good|miss|warn)\b/g, ''); void el.offsetWidth; el.className += ' go' + (cls ? ' ' + cls : ''); }
  function say(text) { again($('tsay'), text); }

  /* ── the canvas: the body sits in a square box in the middle of the scene ─────────────── */
  function resize() {
    var r = scene.getBoundingClientRect();
    DPR = Math.min(2, window.devicePixelRatio || 1);
    W = r.width; H = r.height;
    canvas.width = Math.round(W * DPR); canvas.height = Math.round(H * DPR);
    canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
    var s = Math.min(W * (W < 700 ? 0.96 : 0.7), H * 0.86);
    BOX = {x: (W - s) / 2, y: H * 0.11 + (H * 0.86 - s) / 2, s: s};
    charC.width = canvas.width; charC.height = canvas.height;
    charC.style.width = W + 'px'; charC.style.height = H + 'px';
    charDrawn = null;
    if (typeof rivC !== 'undefined' && rivC && rivOn) { rivC.width = canvas.width; rivC.height = canvas.height; rivC.style.width = W + 'px'; rivC.style.height = H + 'px'; rivSeen = -1; }
    /* the place: its cushion goes under you, at your size; then it is grown until it covers the scene */
    var bg = $('tbg'), seat = S.chamber.seat;
    if (bg && seat) {
      var u = s / 100, px = BOX.x + s / 2, py = BOX.y + SEAT_Y * u, w = SEAT_W * u / seat.w, h = w * 9 / 16;
      var grow = Math.max(1, px / (seat.x * w), (W - px) / ((1 - seat.x) * w), py / (seat.y * h), (H - py) / ((1 - seat.y) * h));
      w *= grow; h *= grow;
      bg.style.width = w + 'px'; bg.style.height = h + 'px';
      bg.style.left = (px - seat.x * w) + 'px'; bg.style.top = (py - seat.y * h) + 'px';
    }
  }
  var charDrawn = null;
  window.addEventListener('resize', resize);
  resize();
  function X(x) { return BOX.x + BOX.s * x / 100; }
  function Y(y) { return BOX.y + BOX.s * y / 100; }
  function U() { return BOX.s / 100; }                         // one box unit in px

  /* ── the session ──────────────────────────────────────────────────── */
  var st = SIM.start(PLAN), actions = [], queue = [], t0 = null, running = false, ended = false, settled = false;
  var mapDim = 1, endAt = 0;
  var flashes = [], shake = 0, glow = 0, trav = {}, lastPos = {}, numbers = {}, gateNumbers = {};
  /* the map's points are laid on your own body: each of the figure's acupoints (HERO.fit.points, measured on the
     picture) pulls the map's points near it to where it really is. Only where things are drawn: the rules go by
     each line's length, which the server set. */
  if (FIT) {
    var ANCH = Object.keys(S.body).filter(function (n) { return FIT.points[n]; })
      .map(function (n) { return [S.body[n][0], S.body[n][1], FIT.points[n][0] - S.body[n][0], FIT.points[n][1] - S.body[n][1]]; });
    PLAN.cycles.forEach(function (c) {
      Object.keys(c.nodes).forEach(function (id) {
        var n = c.nodes[id], sw = 0, dx = 0, dy = 0;
        ANCH.forEach(function (a) {
          var d2 = (n.x - a[0]) * (n.x - a[0]) + (n.y - a[1]) * (n.y - a[1]), w = 1 / (d2 * d2 + 0.5);
          sw += w; dx += w * a[2]; dy += w * a[3];
        });
        n.x += dx / sw; n.y += dy / sw;
      });
    });
  }
  function cyc() { return PLAN.cycles[Math.min(st.cycle, PLAN.cycles.length - 1)]; }
  function upcoming() { return st.pause_until != null && st.cycle + 1 < PLAN.cycles.length ? PLAN.cycles[st.cycle + 1] : cyc(); }
  function number() {                                          // junctions 1..n and gates 1..n, top to bottom, left to right
    var c = upcoming(), js = [], gs = [];
    Object.keys(c.nodes).forEach(function (id) {
      var n = c.nodes[id];
      if (n.type === 'junction') js.push(id); else if (n.type === 'gate') gs.push(id);
    });
    var by = function (a, b) { var A = c.nodes[a], B = c.nodes[b]; return A.y - B.y || A.x - B.x; };
    js.sort(by); gs.sort(by);
    numbers = {}; gateNumbers = {};
    js.forEach(function (id, i) { numbers[id] = i + 1; });
    gs.forEach(function (id, i) { gateNumbers[id] = i + 1; });
    number.js = js; number.gs = gs;
  }
  number();
  /* the shortest way (units) from each source to the Dantian: Night Training shows a colour for the last 40% of it */
  var reach = {};
  PLAN.cycles.forEach(function (c, ci) {
    reach[ci] = {};
    Object.keys(c.nodes).forEach(function (id) {
      if (c.nodes[id].type !== 'source') return;
      var best = {}, todo = [[id, 0]];
      best[id] = 0;
      while (todo.length) {
        todo.sort(function (a, b) { return a[1] - b[1]; });
        var cur = todo.shift(), n = c.nodes[cur[0]];
        if (n.type === 'dantian') { reach[ci][id] = cur[1]; break; }
        if (n.type === 'knot' || n.type === 'exit') continue;
        n.out.forEach(function (o) {
          var d = cur[1] + c.lens[cur[0] + '>' + o];
          if (best[o] == null || d < best[o]) { best[o] = d; todo.push([o, d]); }
        });
      }
    });
  });

  function act(what, which) {                                  // one of your actions, recorded and queued for its tick
    if (!running || ended) return;
    var t = Math.max(0, Math.round(performance.now() - t0 - S.settle));
    var a = [t, what, which || ''];
    actions.push(a); queue.push(a);
    if (what === 'j') { fs('press'); }
    if (what === 'g') { fs('guardup'); }
  }
  function turn(id) { if (st.junctions[id] != null) act('j', id); }
  function gate(id) { if (st.gates[id]) act('g', id); }
  var breathing = false;
  function breathe(on) {
    if (on === breathing || (on && !running)) return;
    breathing = on;
    $('tbreathe').classList.toggle('on', on);
    act(on ? 'b' : 'B');
    if (on && running) fs('gather');
  }

  /* ── one tick at a time, as the server will ───────────────────────── */
  function advance(elapsed) {
    var target = Math.floor(elapsed / TICK);
    while (!st.over && st.tick < target) {
      var mine = [];
      while (queue.length && Math.floor(queue[0][0] / TICK) <= st.tick) mine.push(queue.shift());
      var before = {};
      st.pulses.forEach(function (p) { before[p.id] = {edge: p.edge, pos: p.pos}; });
      var wasCycle = st.cycle, wasPause = st.pause_until;
      SIM.step(PLAN, st, mine);
      if (st.cycle !== wasCycle) { number(); onCycle(); }
      if (wasPause == null && st.pause_until != null) number();
      st.pulses.forEach(function (p) {                         // how far each pulse has come (Night Training)
        var b = before[p.id], c = cyc();
        if (!b) { trav[p.id] = Math.max(0, p.pos); return; }
        trav[p.id] = (trav[p.id] || 0) + (b.edge === p.edge ? p.pos - b.pos : (c.lens[b.edge] || 0) - b.pos + Math.max(0, p.pos));
      });
      st.events.forEach(onEvent);
      seenTips();
    }
    if (breathing && !st.breathing && st.breath === 0) { breathing = false; $('tbreathe').classList.remove('on'); act('B'); }
  }

  /* ── what happens, seen and heard ─────────────────────────────────── */
  function nodeAt(id) { var n = cyc().nodes[id]; return n ? [X(n.x), Y(n.y)] : [W / 2, H / 2]; }
  function flash(at, kind) { flashes.push({x: at[0], y: at[1], kind: kind, t: performance.now()}); }
  function pulseNode(pid) {                                    // where a finished pulse ended: its last line's end
    var p = st.pulses.filter(function (q) { return q.id === pid; })[0];
    if (!p) return [W / 2, H / 2];
    return nodeAt(p.wait || p.edge.split('>')[1]);
  }
  function onEvent(e) {
    var how = e[1], at = pulseNode(e[2]);
    if (how === 'in') {
      if (e[3]) { flash(at, 'bad'); shake = 8; fs('hurt'); again($('tcall'), 'Dark Qi in the Dantian!', 'miss'); }
      else { flash(at, 'gold'); glow = 1; fs('heal'); }
    } else if (how === 'out') { flash(at, e[3] ? 'puff' : 'bad'); fs(e[3] ? 'dodge' : 'miss'); }
    else if (how === 'wrong') { flash(at, 'bad'); fs('miss'); again($('tcall'), 'Gold lost through an exit', 'miss'); }
    else if (how === 'knot') { flash(at, 'bad'); fs('block'); again($('tcall'), e[3] ? 'Stuck in the knot' : 'Gold lost in the knot', 'miss'); }
    else if (how === 'gate_burst') { flash(nodeAt(e[2]), 'bad'); shake = 10; fs('boom'); again($('tcall'), 'The gate bursts!', 'miss'); }
    else if (how === 'deviation') { shake = 22; fs('stun'); again($('tbanner'), 'Qi deviation!', 'warn'); }
    else if (how === 'resonance') {                              // ten clean in a row: the Breath is full again
      var dn = cyc().nodes.dantian;
      again($('tcall'), 'Qi Resonance! ' + e[2] + ' in a row: Breath restored', 'perfect');
      fs('heal'); fs('cast', null, 120); glow = 1.4;
      if (dn) flashes.push({pic: 'bloom', x: X(dn.x), y: Y(dn.y), size: 26, life: 1200, t: performance.now()});
      var bb2 = $('tbreath'); bb2.classList.remove('full'); void bb2.offsetWidth; bb2.classList.add('full');
    }
    else if (how === 'boon') {
      var B = S.boon_text[e[2]];
      again($('tbanner'), B.name + ': ' + B.text); fs('heal');
    }
    else if (how === 'cycle_done' && e[2] === 'cycle') {
      glow = 1.6; fs('cast');
      var dn = cyc().nodes.dantian; if (dn) flashes.push({pic: 'bloom', x: X(dn.x), y: Y(dn.y), size: 34, life: 1500, t: performance.now()});
      if (PLAN.cycles[e[3] + 1] && PLAN.cycles[e[3] + 1].kind === 'rival') rivalIn();   // he steps in, laughing
      again($('tbanner'), e[3] + 1 < 3 ? 'Cycle ' + (e[3] + 1) + ' complete. The Dantian compresses…' : 'Third cycle complete.');
    }
  }
  function seenTips() {                                         // what has just appeared for the first time
    var c = cyc();
    if (st.pulses.some(function (p) { return p.dark && p.done == null; }))
      tip('dark', 'Dark Qi! Turn the junctions so it leaves by a white lotus (a palm or a sole), never into the Dantian.');
    if (Object.keys(c.nodes).some(function (id) { return c.nodes[id].type === 'knot'; }))
      tip('knot', 'A knot blocks a channel: Qi that reaches it is lost. Send the gold round it.');
    Object.keys(st.gates).forEach(function (g) {
      if (!st.gates[g].open && st.pulses.some(function (p) { return p.wait === g && p.done == null; }))
        tip('gate', 'Held at the gate. Open it again (Shift + its number) before the red ring fills, or it bursts.');
    });
    if (st.choosing != null) tip('boon', 'Open a meridian: pick a blessing (1 or 2). It lasts the rest of the session.');
    if (st.harmony >= 3) tip('harmony', 'Harmony ' + st.harmony + ': keep it clean. Every ' + PLAN.harmony + ' in a row refills your Breath.');
  }
  function onCycle() {
    var c = cyc();
    if (c.kind === 'rival') {
      again($('tbanner'), 'The rival disciple pushes dark Qi into your meridians! Expel it.', 'warn'); fs('roar');
      rivalIn();
    }
    else if (st.cycle === 1 && S.hints.length) say(S.hints[1]);
    else if (st.cycle === 1 && PLAN.tier >= 2) say('A knot blocks a line. Send the gold round it.');
  }

  /* ── you: the meditation loop, and the three endings ───────────────
     The loop is a sprite sheet played forwards then backwards (it never jumps). An ending (surge, deviation,
     scatter) is a small video whose top half is the picture and bottom half its mask (white = solid): each frame
     is put together here and drawn over the chamber, its own sound with it; then the loop again. */
  var loopImg = null, ENDS = {}, endNow = null, endBuf = null;
  if (HERO) {
    loopImg = new Image(); loopImg.src = HERO.loop.src;
    Object.keys(HERO.ends || {}).forEach(function (k) {
      var v = document.createElement('video');
      v.muted = true; v.playsInline = true; v.setAttribute('playsinline', ''); v.preload = 'auto'; v.src = HERO.ends[k].src;
      ENDS[k] = v;
    });
  }
  function onBody(box) {                                       // a box in the video's px, on the screen
    var k = U() / FIT.k;
    return [BOX.x + (box[0] - FIT.x0) * k, BOX.y + (box[1] - FIT.y0) * k, box[2] * k, box[3] * k];
  }
  function playEnd(name) {
    var v = ENDS[name]; if (!v) return false;
    try { v.currentTime = 0; } catch (e) {}
    var p = v.play(); if (p && p.catch) p.catch(function () {});
    endNow = {name: name, v: v, spec: HERO.ends[name], t0: performance.now(), seen: -1, ready: false};
    if (soundOn && endNow.spec.sound) {
      var a = new Audio(endNow.spec.sound); a.volume = LOUD();
      var q = a.play(); if (q && q.catch) q.catch(function () {});
    }
    return true;
  }
  function endFrame() { if (!endBuf) endBuf = {}; return unmask(endBuf, endNow.v, endNow.spec.w, endNow.spec.h); }
  /* a stacked-alpha video's frame now (picture on top, its mask below) as a see-through picture */
  function unmask(buf, v, w, h) {
    var endBuf = buf;
    if (!endBuf.raw || endBuf.raw.width !== w || endBuf.raw.height !== h * 2) {
      endBuf.raw = document.createElement('canvas'); endBuf.raw.width = w; endBuf.raw.height = h * 2;
      endBuf.rc = endBuf.raw.getContext('2d', {willReadFrequently: true});
      endBuf.out = document.createElement('canvas'); endBuf.out.width = w; endBuf.out.height = h;
      endBuf.oc = endBuf.out.getContext('2d');
    }
    endBuf.rc.drawImage(v, 0, 0, w, h * 2);
    var px = endBuf.rc.getImageData(0, 0, w, h * 2), d = px.data, n = w * h * 4, i, a;
    for (i = 0; i < n; i += 4) {
      a = d[i + n];
      if (a > 3) { d[i] = Math.min(255, d[i] * 255 / a); d[i + 1] = Math.min(255, d[i + 1] * 255 / a); d[i + 2] = Math.min(255, d[i + 2] * 255 / a); d[i + 3] = a; }
      else d[i + 3] = 0;
    }
    endBuf.oc.putImageData(px, 0, 0, 0, 0, w, h);
    endBuf.oc.clearRect(0, 0, w, 3); endBuf.oc.clearRect(0, h - 3, w, 3);     // where picture and mask meet, they bleed
    endBuf.oc.clearRect(0, 0, 3, h); endBuf.oc.clearRect(w - 3, 0, 3, h);
    return endBuf.out;
  }
  function drawChar(now) {
    if (!HERO || !loopImg.complete || !loopImg.naturalWidth) return;
    var L = HERO.loop, n = L.frames, span = Math.max(1, 2 * n - 2), i = Math.floor(now * L.fps / 1000) % span, f = i < n ? i : span - i;
    var key = 'L' + f, pic = null, blend = 0;
    if (endNow) {
      var e = endNow;
      if (e.v.ended || now - e.t0 > e.spec.ms + 1500) endNow = null;
      else if (e.v.readyState >= 2 && e.v.currentTime > 0) {
        if (!e.ready) { e.ready = true; e.t1 = now; }
        blend = Math.max(0, 1 - (now - e.t1) / 350);             // the loop fades out over the ending's first moment
        key = 'E' + e.name + e.v.currentTime + (blend ? 'b' + f : '');
        pic = e;
      }
    }
    if (key === charDrawn) return;
    charDrawn = key;
    cc.setTransform(DPR, 0, 0, DPR, 0, 0);
    cc.clearRect(0, 0, W, H);
    var r;
    if (pic) { r = onBody(pic.spec.box); try { cc.drawImage(endFrame(), r[0], r[1], r[2], r[3]); } catch (err) { endNow = null; } }
    if (!pic || blend) {
      r = onBody(L.box);
      cc.globalAlpha = pic ? blend : 1;
      cc.drawImage(loopImg, (f % L.cols) * L.fw, Math.floor(f / L.cols) * L.fh, L.fw, L.fh, r[0], r[1], r[2], r[3]);
      cc.globalAlpha = 1;
    }
  }

  /* ── the Rival Disciple's attack (art/train/rival.mp4 and its sound): he steps in at the right as the third cycle
     ends, laughs, and blasts dark Qi across at you just as his round begins; then he stands, arms folded, and
     watches until the end. He is drawn at a fixed size by his body in the first frame (`body`), whatever his blast
     does. Without the video, his picture slides in instead. ── */
  var RIV = S.rival && S.rival.attack, rivC = $('trivalc'), rivX = rivC ? rivC.getContext('2d') : null;
  var rivV = null, rivBuf = {}, rivSeen = -1, rivOn = false;
  if (RIV) {
    rivV = document.createElement('video');
    rivV.muted = true; rivV.playsInline = true; rivV.setAttribute('playsinline', ''); rivV.preload = 'auto'; rivV.src = RIV.src;
  }
  function rivalIn() {
    if (rivOn) return;
    rivOn = true;
    if (!RIV) { if ($('trival')) $('trival').classList.add('on'); return; }
    rivC.width = canvas.width; rivC.height = canvas.height; rivC.style.width = W + 'px'; rivC.style.height = H + 'px';
    rivC.classList.add('on');
    try { rivV.currentTime = 0; } catch (e) {}
    var p = rivV.play(); if (p && p.catch) p.catch(function () {});
    if (soundOn) { var a = new Audio(RIV.sound); a.volume = LOUD(); var q = a.play(); if (q && q.catch) q.catch(function () {}); }
  }
  function rivalOut() {
    if (!rivOn) return;
    if (rivC) rivC.classList.remove('on');
    if ($('trival')) $('trival').classList.remove('on');
  }
  function drawRival() {
    if (!rivOn || !RIV || rivV.readyState < 2 || rivV.currentTime === rivSeen) return;
    rivSeen = rivV.currentTime;
    var b = RIV.body, bx = RIV.box, k = H * (W < 700 ? 0.34 : 0.5) / b[3];
    var right = W * (W < 700 ? 1.02 : 0.99), x0 = right - (b[0] + b[2] - bx[0]) * k, y0 = H - (b[1] + b[3] - bx[1]) * k;
    rivX.setTransform(DPR, 0, 0, DPR, 0, 0); rivX.clearRect(0, 0, W, H);
    try { rivX.drawImage(unmask(rivBuf, rivV, RIV.w, RIV.h), x0, y0, bx[2] * k, bx[3] * k); } catch (e) {}
  }

  /* ── drawing ──────────────────────────────────────────────────────── */
  var GOLD = '#ffd66b', DARK = '#9a5cff', JADE = 'rgba(120,235,190,', INK = 'rgba(190,215,255,';
  /* the seated figure facing you, in ink wash (a stand-in until the painted meditation video): head and bun, the
     robe falling from the shoulders to the knees in a wide triangle, sleeves, the sash, hands on the knees */
  function body(alpha) {
    var u = U();
    cx.save();
    cx.globalAlpha = alpha;
    var g = cx.createRadialGradient(X(50), Y(50), u * 6, X(50), Y(56), u * 58);
    g.addColorStop(0, INK + '0.22)'); g.addColorStop(1, INK + '0.05)');
    var aura = cx.createRadialGradient(X(50), Y(55), u * 10, X(50), Y(55), u * 62);
    aura.addColorStop(0, 'rgba(120,235,190,.07)'); aura.addColorStop(1, 'rgba(120,235,190,0)');
    cx.fillStyle = aura; cx.fillRect(X(-15), Y(-10), u * 130, u * 120);
    cx.fillStyle = g; cx.strokeStyle = INK + '0.38)'; cx.lineWidth = Math.max(1, u * 0.35);
    cx.lineJoin = 'round'; cx.lineCap = 'round';
    cx.beginPath();                                                       // robe: shoulders to knees to lap
    cx.moveTo(X(45.5), Y(20));
    cx.quadraticCurveTo(X(38), Y(24.5), X(33), Y(28));
    cx.bezierCurveTo(X(25), Y(34), X(20), Y(50), X(17), Y(64));
    cx.quadraticCurveTo(X(10), Y(74), X(9), Y(82));
    cx.bezierCurveTo(X(10), Y(92), X(32), Y(95), X(50), Y(94));
    cx.bezierCurveTo(X(68), Y(95), X(90), Y(92), X(91), Y(82));
    cx.quadraticCurveTo(X(90), Y(74), X(83), Y(64));
    cx.bezierCurveTo(X(80), Y(50), X(75), Y(34), X(67), Y(28));
    cx.quadraticCurveTo(X(62), Y(24.5), X(54.5), Y(20));
    cx.closePath(); cx.fill(); cx.stroke();
    cx.beginPath(); cx.ellipse(X(50), Y(12.5), u * 6.8, u * 8.2, 0, 0, Math.PI * 2); cx.fill(); cx.stroke();   // head
    cx.beginPath(); cx.arc(X(50), Y(3.6), u * 2.8, 0, Math.PI * 2); cx.fill(); cx.stroke();                  // the bun
    cx.strokeStyle = INK + '0.24)';
    [[[44, 21], [50, 36], [56, 21]],                                     // the collar
     [[36, 33], [30, 52], [24, 70]], [[64, 33], [70, 52], [76, 70]],     // the sleeves' inner edges
     [[36, 54], [50, 57], [64, 54]],                                     // the sash
     [[18, 79], [50, 72], [82, 79]], [[24, 86], [50, 80], [76, 86]]]    // the crossed legs
      .forEach(function (c) {
        cx.beginPath(); cx.moveTo(X(c[0][0]), Y(c[0][1])); cx.quadraticCurveTo(X(c[1][0]), Y(c[1][1]), X(c[2][0]), Y(c[2][1])); cx.stroke();
      });
    cx.fillStyle = INK + '0.20)';
    [[22, 72], [78, 72]].forEach(function (h) { cx.beginPath(); cx.ellipse(X(h[0]), Y(h[1]), u * 4, u * 2.6, 0, 0, Math.PI * 2); cx.fill(); cx.stroke(); });
    cx.restore();
  }
  /* the channels: each runs from one acupoint (or gate, or knot) through its path points to the next, drawn as one
     smooth curve; a slow dash flowing along it shows which way the Qi goes */
  function channels(c) {
    var out = [];
    Object.keys(c.nodes).forEach(function (a) {
      if (a.indexOf('~') >= 0) return;
      c.nodes[a].out.forEach(function (o) {
        var pts = [a], keys = [], cur = o, prev = a;
        while (true) {
          keys.push(prev + '>' + cur); pts.push(cur);
          if (cur.indexOf('~') < 0) break;
          prev = cur; cur = c.nodes[cur].out[0];
        }
        out.push({pts: pts, keys: keys});
      });
    });
    return out;
  }
  var CHAN = {};
  function chans(c) { var i = PLAN.cycles.indexOf(c); if (!CHAN[i]) CHAN[i] = channels(c); return CHAN[i]; }
  function curve(c, pts) {
    var P = pts.map(function (id) { var n = c.nodes[id]; return [X(n.x), Y(n.y)]; });
    cx.beginPath(); cx.moveTo(P[0][0], P[0][1]);
    for (var i = 1; i < P.length - 1; i++) cx.quadraticCurveTo(P[i][0], P[i][1], (P[i][0] + P[i + 1][0]) / 2, (P[i][1] + P[i + 1][1]) / 2);
    cx.lineTo(P[P.length - 1][0], P[P.length - 1][1]);
  }
  function line(c, ch, alpha, now) {
    var u = U(), hurt = ch.keys.some(function (k) { return PLAN.injured.indexOf(k) >= 0; });
    cx.save();
    cx.globalAlpha = alpha; cx.lineCap = 'round'; cx.lineJoin = 'round';
    curve(c, ch.pts);
    cx.strokeStyle = hurt ? 'rgba(255,110,90,.16)' : JADE + '0.13)'; cx.lineWidth = u * 2.8; cx.stroke();
    var lift = Math.min(1, (st.harmony % PLAN.harmony) / PLAN.harmony);         // Harmony brightens the channels
    cx.strokeStyle = hurt ? 'rgba(255,140,120,.8)' : 'rgba(' + Math.round(120 + 100 * lift) + ',235,' + Math.round(190 - 40 * lift) + ',' + (0.7 + 0.25 * lift) + ')';
    cx.lineWidth = Math.max(1.4, u * (0.42 + 0.18 * lift)); cx.stroke();
    if (!reduced) {                                                    // the flow
      cx.setLineDash([u * 1.2, u * 4.5]); cx.lineDashOffset = -now / 60;
      cx.strokeStyle = hurt ? 'rgba(255,190,170,.75)' : 'rgba(225,255,240,.75)'; cx.lineWidth = Math.max(1.6, u * 0.5); cx.stroke();
    }
    cx.restore();
  }
  var NAMES = {crown: 'Baihui', heart: 'Tanzhong', dantian: 'Dantian', l_palm: 'Laogong', r_palm: 'Laogong',
               l_sole: 'Yongquan', r_sole: 'Yongquan', throat: 'Tiantu'};
  function labels(c, alpha) {                                         // the chart's names, beside their points
    if (W < 700) return;
    var u = U();
    cx.save(); cx.globalAlpha = alpha * 0.6; cx.fillStyle = '#f5dca6';
    cx.font = 'italic ' + Math.round(Math.max(11, u * 1.7)) + 'px Georgia, serif'; cx.textBaseline = 'middle';
    Object.keys(NAMES).forEach(function (id) {
      var n = c.nodes[id]; if (!n) return;
      if (id === 'dantian') { cx.textAlign = 'center'; cx.fillText(NAMES[id], X(n.x), Y(n.y) + u * 9.5); return; }
      var left = n.x < 50, dx = (n.type === 'junction' ? 4.6 : 3.4) * u;
      cx.textAlign = left ? 'right' : 'left';
      cx.fillText(NAMES[id], X(n.x) + (left ? -dx : dx), Y(n.y));
    });
    cx.restore();
  }
  function acupoints(c, alpha) {                                      // the small dots of the chart along the channels
    var u = U();
    cx.save(); cx.globalAlpha = alpha; cx.fillStyle = 'rgba(200,255,230,.55)';
    Object.keys(c.nodes).forEach(function (id) {
      if (id.indexOf('~') < 0 && c.nodes[id].type !== 'path') return;
      var n = c.nodes[id]; cx.beginPath(); cx.arc(X(n.x), Y(n.y), Math.max(1.3, u * 0.38), 0, Math.PI * 2); cx.fill();
    });
    cx.restore();
  }
  function arrowTo(x1, y1, x2, y2, r) {
    var a = Math.atan2(y2 - y1, x2 - x1), tx = x1 + Math.cos(a) * r, ty = y1 + Math.sin(a) * r, s = r * 0.55;
    cx.beginPath();
    cx.moveTo(tx + Math.cos(a) * s * 0.7, ty + Math.sin(a) * s * 0.7);
    cx.lineTo(tx + Math.cos(a + 2.4) * s, ty + Math.sin(a + 2.4) * s);
    cx.lineTo(tx + Math.cos(a - 2.4) * s, ty + Math.sin(a - 2.4) * s);
    cx.closePath(); cx.fill();
  }
  function radius() { return Math.max(22, U() * 3.6); }        // a junction or gate: at least 44 px across
  function node(c, id, alpha, now) {
    var n = c.nodes[id], x = X(n.x), y = Y(n.y), u = U(), r = radius();
    cx.save(); cx.globalAlpha = alpha;
    if (n.type === 'junction') {
      var way = st.junctions[id] != null ? st.junctions[id] : (n.way || 0), to = c.nodes[n.out[way]];
      cx.fillStyle = 'rgba(6,22,18,.88)'; cx.strokeStyle = JADE + '0.95)'; cx.lineWidth = Math.max(2, u * 0.45);
      cx.beginPath(); cx.arc(x, y, r * 0.62, 0, Math.PI * 2); cx.fill(); cx.stroke();
      cx.strokeStyle = JADE + '0.35)'; cx.lineWidth = 1;
      cx.beginPath(); cx.arc(x, y, r * 0.8, 0, Math.PI * 2); cx.stroke();
      cx.fillStyle = '#d9fff0'; arrowTo(x, y, X(to.x), Y(to.y), r * 0.86);
      cx.fillStyle = '#eafff6'; cx.font = '700 ' + Math.round(r * 0.56) + 'px Cinzel, Georgia, serif';
      cx.textAlign = 'center'; cx.textBaseline = 'middle'; cx.fillText(numbers[id] || '', x, y + 1);
    } else if (n.type === 'gate') {                                // a paper talisman seal: red when closed
      var g = st.gates[id], open = !g || g.open;
      var waiting = st.pulses.filter(function (p) { return p.wait === id && p.done == null; });
      var oldest = waiting.length ? Math.min.apply(null, waiting.map(function (p) { return p.waited; })) : null;
      var strain = waiting.length ? Math.max(waiting.length / st.gate_most, (st.tick - oldest) / st.gate_hold) : 0;
      var w = r * 0.62, h = r * 0.9, wob = open ? 0 : 0.06 * Math.sin(now / 80) * strain;
      cx.translate(x, y); cx.rotate(wob);
      if (fxok('seal')) {                                          // the jade seal: whole when shut, a ghost when open
        w = r * 0.7; h = r * 1.05;
        fxdraw('seal', 0, r * 0.06, r * 1.35, open ? 0.3 : 1);
        if (!open) { cx.strokeStyle = 'rgba(255,217,168,.9)'; cx.lineWidth = Math.max(1.5, u * 0.3); cx.beginPath(); cx.arc(0, r * 0.18, r * 0.78, 0, Math.PI * 2); cx.stroke(); }
      } else {
      cx.fillStyle = open ? 'rgba(120,30,24,.35)' : '#b3261e';
      cx.strokeStyle = open ? 'rgba(255,200,160,.45)' : '#ffd9a8'; cx.lineWidth = Math.max(1.5, u * 0.35);
      cx.fillRect(-w, -h, w * 2, h * 2); cx.strokeRect(-w, -h, w * 2, h * 2);
      cx.strokeStyle = open ? 'rgba(255,220,190,.5)' : '#2a0806'; cx.lineWidth = Math.max(1.2, u * 0.3);   // the rune
      cx.beginPath(); cx.moveTo(-w * 0.5, -h * 0.6); cx.lineTo(w * 0.5, -h * 0.6); cx.moveTo(0, -h * 0.75); cx.lineTo(0, h * 0.6);
      cx.moveTo(-w * 0.45, -h * 0.1); cx.quadraticCurveTo(0, h * 0.15, w * 0.45, -h * 0.1); cx.moveTo(-w * 0.5, h * 0.45); cx.lineTo(w * 0.5, h * 0.45); cx.stroke();
      }
      cx.rotate(-wob);
      cx.fillStyle = 'rgba(10,6,6,.8)'; cx.fillRect(w + 3, -r * 0.28, r * 0.95, r * 0.56);    // its key, beside it
      cx.fillStyle = open ? 'rgba(255,220,190,.8)' : '#fff1d6'; cx.font = '700 ' + Math.round(r * 0.42) + 'px Cinzel, Georgia, serif';
      cx.textAlign = 'center'; cx.textBaseline = 'middle'; cx.fillText('⇧' + (gateNumbers[id] || ''), w + 3 + r * 0.475, 1);
      if (!open && strain) {                                       // how close it is to bursting
        cx.strokeStyle = 'rgba(255,90,60,.95)'; cx.lineWidth = Math.max(2, u * 0.55);
        cx.beginPath(); cx.arc(0, 0, h * 1.25, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * Math.min(1, strain)); cx.stroke();
      }
    } else if (n.type === 'exit' && fxok('lotus')) {
      fxdraw('lotus', x, y - r * 0.1, r * 1.9);
    } else if (n.type === 'knot' && fxok('knot')) {
      fxdraw('knot', x, y, r * 2.1, 1, now / 1800);
    } else if (n.type === 'exit') {
      cx.translate(x, y);
      for (var i = 0; i < 5; i++) {
        cx.rotate(Math.PI * 2 / 5);
        cx.fillStyle = 'rgba(255,255,255,.78)';
        cx.beginPath(); cx.ellipse(0, -r * 0.42, r * 0.2, r * 0.38, 0, 0, Math.PI * 2); cx.fill();
      }
      cx.fillStyle = '#ffe9b0'; cx.beginPath(); cx.arc(0, 0, r * 0.16, 0, Math.PI * 2); cx.fill();
    } else if (n.type === 'knot') {
      cx.translate(x, y); cx.strokeStyle = '#2a0f22'; cx.lineWidth = Math.max(3, u * 0.9);
      cx.fillStyle = 'rgba(60,10,40,.9)'; cx.beginPath(); cx.arc(0, 0, r * 0.55, 0, Math.PI * 2); cx.fill();
      cx.strokeStyle = '#d07ab0'; cx.lineWidth = Math.max(2, u * 0.4);
      for (var k = 0; k < 3; k++) { cx.rotate(1.05); cx.beginPath(); cx.ellipse(0, 0, r * 0.55, r * 0.2, 0, 0, Math.PI * 2); cx.stroke(); }
    } else if (n.type === 'source') {
      var pulse = 0.5 + 0.5 * Math.sin(now / 300);
      cx.fillStyle = 'rgba(255,240,200,' + (0.35 + 0.4 * pulse) + ')';
      cx.beginPath(); cx.arc(x, y, r * 0.35 + pulse * r * 0.1, 0, Math.PI * 2); cx.fill();
    } else if (n.type === 'dantian') dantian(x, y, r, now);
    cx.restore();
  }
  function cycleGold() {                                       // this cycle's gold so far, for the Dantian's ring
    var c = cyc(), total = 0, inn = 0;
    if (c.kind !== 'cycle') return 0;
    c.pulses.forEach(function (q) { if (!q.dark) total++; });
    st.pulses.forEach(function (p) { if (!p.dark && p.done === 'in') inn++; });
    return total ? inn / total : 0;
  }
  function dantian(x, y, r, now) {
    var u = U(), R = Math.max(13, u * 4.2) * (1 + 0.15 * glow);
    if (fxok('dantian')) fxdraw('dantian', x, y, R * 4.6, 1, now / 2400);              // the golden orb, turning slowly
    else {
    var g = cx.createRadialGradient(x, y, 0, x, y, R * 2.2);
    g.addColorStop(0, 'rgba(255,240,180,' + (0.95) + ')'); g.addColorStop(0.35, 'rgba(255,196,80,.85)');
    g.addColorStop(1, 'rgba(255,170,40,0)');
    cx.fillStyle = g; cx.beginPath(); cx.arc(x, y, R * 2.2, 0, Math.PI * 2); cx.fill();
    cx.save(); cx.translate(x, y); cx.rotate(now / 2400);                            // a faint taiji swirl
    cx.strokeStyle = 'rgba(140,80,10,.5)'; cx.lineWidth = Math.max(1.5, u * 0.35);
    cx.beginPath(); cx.arc(0, 0, R * 0.62, 0, Math.PI * 2); cx.stroke();
    cx.beginPath(); cx.arc(0, -R * 0.31, R * 0.31, -Math.PI / 2, Math.PI / 2); cx.arc(0, R * 0.31, R * 0.31, -Math.PI / 2, Math.PI / 2, true); cx.stroke();
    cx.restore();
    }
    cx.lineWidth = Math.max(3, u * 0.8);                                             // the cycle filling
    cx.strokeStyle = 'rgba(255,214,107,.25)'; cx.beginPath(); cx.arc(x, y, R * 1.35, 0, Math.PI * 2); cx.stroke();
    cx.strokeStyle = GOLD; cx.beginPath(); cx.arc(x, y, R * 1.35, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * cycleGold()); cx.stroke();
    var s = st.stability / 100;                                                      // Stability, round it
    cx.strokeStyle = 'rgba(120,235,190,.18)'; cx.beginPath(); cx.arc(x, y, R * 1.7, 0, Math.PI * 2); cx.stroke();
    cx.strokeStyle = s > 0.5 ? '#7debc0' : s > 0.25 ? '#ffc46b' : '#ff6a55';
    cx.beginPath(); cx.arc(x, y, R * 1.7, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * s); cx.stroke();
  }
  function shownDark(p) {                                     // what colour the pulse shows now (Night Training)
    if (!S.night) return p.dark ? 1 : 0;
    var full = reach[st.cycle] ? reach[st.cycle][srcOf(p)] : 0;
    return (trav[p.id] || 0) >= (1 - S.night) * (full || 1) ? (p.dark ? 1 : 0) : -1;
  }
  var SRC = {};
  PLAN.cycles.forEach(function (c) { c.pulses.forEach(function (q) { SRC[q.id] = q.src; }); });
  function srcOf(p) { return SRC[p.id]; }
  function pulses(frac, now) {
    var c = cyc(), u = U();
    st.pulses.forEach(function (p) {
      if (p.done != null) return;
      var a, b, f, x, y;
      if (p.wait) { var n = c.nodes[p.wait]; x = X(n.x); y = Y(n.y); a = null; }
      else {
        var ab = p.edge.split('>'), A = c.nodes[ab[0]], B = c.nodes[ab[1]], L = c.lens[p.edge];
        var sp = PLAN.speed * (st.slow ? 0.85 : 1) * (PLAN.injured.indexOf(p.edge) >= 0 ? 0.6 : 1) * (st.breathing ? 0.4 : 1);
        f = Math.max(0, Math.min(1, (p.pos + sp * frac) / L));
        x = X(A.x + (B.x - A.x) * f); y = Y(A.y + (B.y - A.y) * f); a = A; b = B;
      }
      var col = shownDark(p), R = Math.max(5, u * 1.5);
      if (a) {                                                 // a short tail behind it
        var tx = X(a.x) - x, ty = Y(a.y) - y, d = Math.hypot(tx, ty) || 1, len = Math.min(d, u * 6);
        var g = cx.createLinearGradient(x, y, x + tx / d * len, y + ty / d * len);
        var c0 = col === 1 ? 'rgba(154,92,255,.75)' : col === 0 ? 'rgba(255,214,107,.85)' : 'rgba(200,200,210,.5)';
        g.addColorStop(0, c0); g.addColorStop(1, 'rgba(0,0,0,0)');
        cx.strokeStyle = g; cx.lineWidth = R * 1.3; cx.lineCap = 'round';
        cx.beginPath(); cx.moveTo(x, y); cx.lineTo(x + tx / d * len, y + ty / d * len); cx.stroke();
      }
      var gl = cx.createRadialGradient(x, y, 0, x, y, R * 2.6);
      if (col === 1) { gl.addColorStop(0, 'rgba(60,20,90,1)'); gl.addColorStop(0.4, 'rgba(154,92,255,.8)'); gl.addColorStop(1, 'rgba(90,40,160,0)'); }
      else if (col === 0) { gl.addColorStop(0, '#fffbe8'); gl.addColorStop(0.35, 'rgba(255,214,107,.95)'); gl.addColorStop(1, 'rgba(255,170,40,0)'); }
      else { gl.addColorStop(0, 'rgba(230,230,240,.9)'); gl.addColorStop(1, 'rgba(200,200,210,0)'); }
      cx.fillStyle = gl; cx.beginPath(); cx.arc(x, y, R * 2.6, 0, Math.PI * 2); cx.fill();
      if (col === 1 && !reduced) {                              // smoke
        cx.fillStyle = 'rgba(80,40,110,.35)';
        cx.beginPath(); cx.arc(x + Math.sin(now / 130 + p.id) * R, y - R * 1.4, R * 0.9, 0, Math.PI * 2); cx.fill();
      }
    });
  }
  function effects(now) {
    flashes = flashes.filter(function (f) { return now - f.t < (f.life || (f.kind === 'bloom' ? 1500 : 700)); });
    flashes.forEach(function (f) {
      if (f.pic) {                                                 // a painted effect: it opens out and fades
        if (now < f.t || !fxok(f.pic)) return;
        var q = (now - f.t) / f.life, sz = U() * f.size * (0.55 + 0.45 * Math.min(1, q * 3)) * (1 + 0.12 * q);
        fxdraw(f.pic, f.x, f.y - (f.rise || 0) * U() * q, sz, Math.min(1, q * 6) * Math.min(1, (1 - q) * 2.2));
        return;
      }
      if (f.kind === 'bloom') {                                    // a ring of gold opening out of the Dantian
        var b = (now - f.t) / 1500, R = U() * (6 + b * 48);
        cx.strokeStyle = 'rgba(255,214,107,' + (0.85 * (1 - b)) + ')'; cx.lineWidth = Math.max(2, U() * 1.2 * (1 - b) + 1);
        cx.beginPath(); cx.arc(f.x, f.y, R, 0, Math.PI * 2); cx.stroke();
        cx.fillStyle = 'rgba(255,236,170,' + (0.18 * (1 - b)) + ')'; cx.fill();
        return;
      }
      var k = (now - f.t) / 700, r = radius() * (0.8 + k * 2.2);
      var c = f.kind === 'gold' ? '255,214,107' : f.kind === 'puff' ? '220,200,255' : '255,80,60';
      cx.fillStyle = 'rgba(' + c + ',' + (0.55 * (1 - k)) + ')';
      cx.beginPath(); cx.arc(f.x, f.y, r, 0, Math.PI * 2); cx.fill();
    });
  }

  function draw(now) {
    var elapsed = running ? now - t0 - S.settle : -1, frac = 0;
    if (running && elapsed >= 0) {
      if (!settled) {
        settled = true; main.dataset.phase = 'flow';
        /* this session's conditions and event, every time (they change from session to session) */
        S.conditions.forEach(function (c) { tipQ.push(c.name + ': ' + c.text + '.'); });
        if (S.event) tipQ.push(S.event.text);
        if (S.hints.length) tipQ.unshift(S.hints[0]);
      }
      advance(elapsed);
      frac = st.over ? 0 : Math.max(0, Math.min(1, (elapsed - st.tick * TICK) / TICK));
      if (S.hints.length && st.cycle === 0 && elapsed > 12000 && !draw.hint3) { draw.hint3 = true; say(S.hints[2]); }
      if (st.over && !ended) finish();
    }
    cx.setTransform(DPR, 0, 0, DPR, 0, 0);
    cx.clearRect(0, 0, W, H);
    var sx = 0, sy = 0;
    if (shake > 0 && !reduced) { sx = (Math.random() - 0.5) * shake; sy = (Math.random() - 0.5) * shake; shake *= 0.88; if (shake < 0.5) shake = 0; }
    cx.translate(sx, sy);
    var mapIn = main.dataset.phase === 'ready' ? 0.35 : running ? Math.min(1, (now - t0) / S.settle) : 1;
    if (running) tips(now);
    drawRival();
    if (HERO) drawChar(now); else body(0.55 + 0.45 * mapIn);
    mapIn *= mapDim;
    var c = st.pause_until != null ? upcoming() : cyc();
    if (st.pause_until != null) { var k = (st.pause_until - st.tick) / PLAN.pause; mapIn *= 0.35 + 0.65 * Math.abs(k * 2 - 1); }
    chans(c).forEach(function (ch) { line(c, ch, mapIn, now); });
    acupoints(c, mapIn);
    labels(c, mapIn);
    Object.keys(c.nodes).forEach(function (id) { if (c.nodes[id].type !== 'path') node(c, id, mapIn, now); });
    if (c === cyc() && !ended) pulses(frac, now);
    effects(now);
    glow *= 0.96;
    hud();
    requestAnimationFrame(draw);
  }

  /* ── the HUD: next pulses, cycle, score, Breath ───────────────────── */
  var nextEl = $('tnext');
  function hud() {
    var c = cyc(), out = [];
    if (st.pause_until == null) for (var i = st.spawned; i < c.pulses.length && out.length < 3; i++) out.push(c.pulses[i]);
    else if (st.cycle + 1 < PLAN.cycles.length) out = PLAN.cycles[st.cycle + 1].pulses.slice(0, 3);
    var html = out.map(function (q) {
      var dark = PLAN.shown[q.id], cls = S.night ? 'hid' : dark ? 'dk' : 'gd';
      return '<i class="' + cls + '"></i>';
    }).join('');
    if (nextEl.innerHTML !== html) nextEl.innerHTML = html;
    $('tcycle').textContent = c.kind === 'rival' ? 'Rival round' : 'Cycle ' + Math.min(3, st.cycle + 1) + ' / 3';
    $('tscore').textContent = running && st.gold + st.dark ? Math.round(100 * soFar()) + '%' : '–';
    $('tbreathfill').style.height = (100 * st.breath / st.breath_max) + '%';
    var hm = $('tharm');
    hm.textContent = running && st.harmony ? 'Harmony ' + st.harmony : '';
    hm.classList.toggle('hot', st.harmony >= PLAN.harmony - 3 && st.harmony % PLAN.harmony >= PLAN.harmony - 3);
    boonCard();
    $('tbreath').classList.toggle('on', st.breathing);
  }

  /* the score of the pulses sent so far (the server's counts every pulse, sent or not) */
  function soFar() {
    var g = st.gold ? st.gold_in / st.gold : 1, stab = st.deviation ? 0 : st.stability / 100;
    return st.dark ? 0.6 * g + 0.25 * st.dark_out / st.dark + 0.15 * stab : 0.85 * g + 0.15 * stab;
  }

  /* ── open a meridian: the blessing card while one is being chosen ── */
  var boonFor = null;
  function boonCard() {
    var card = $('tboon');
    if (!running || st.choosing == null) { if (!card.hidden) card.hidden = true; boonFor = null; return; }
    if (boonFor !== st.choosing) {
      boonFor = st.choosing;
      var box = $('tboons'); box.innerHTML = '';
      PLAN.boons[st.choosing].forEach(function (k, i) {
        var B = S.boon_text[k], b = document.createElement('button');
        b.type = 'button'; b.innerHTML = '<b></b><small></small><i></i>';
        b.children[0].textContent = B.name; b.children[1].textContent = B.text; b.children[2].textContent = 'Press ' + (i + 1);
        b.addEventListener('click', function () { choose(i); });
        box.appendChild(b);
      });
      card.hidden = false; fs('cast');
    }
    var left = Math.max(0, st.choose_until - st.tick) / PLAN.choose;
    $('tboonclock').style.width = (100 * left) + '%';
  }
  function choose(i) {
    if (st.choosing == null || choose.sent === st.choosing) return;
    choose.sent = st.choosing;
    act('o', PLAN.boons[st.choosing][i]);
  }

  /* ── input: the map, the keys, the Breathe button ─────────────────── */
  function pick(ev) {
    var r = canvas.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top, c = cyc(), best = null, bd = 1e9;
    Object.keys(c.nodes).forEach(function (id) {
      var n = c.nodes[id];
      if (n.type !== 'junction' && n.type !== 'gate') return;
      var d = Math.hypot(X(n.x) - x, Y(n.y) - y);
      if (d < bd) { bd = d; best = id; }
    });
    if (best && bd <= radius() * 1.25) {
      ev.preventDefault();
      if (c.nodes[best].type === 'junction') turn(best); else gate(best);
    }
  }
  canvas.addEventListener('pointerdown', pick);
  var bb = $('tbreathe');
  bb.addEventListener('pointerdown', function (e) { e.preventDefault(); breathe(true); });
  ['pointerup', 'pointercancel', 'pointerleave'].forEach(function (n) { bb.addEventListener(n, function () { breathe(false); }); });
  document.addEventListener('keydown', function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.code === 'Space' || e.key === ' ') { e.preventDefault(); if (!e.repeat) breathe(true); return; }
    var m = /^(?:Digit|Numpad)([1-8])$/.exec(e.code || '');
    if (!m || e.repeat) return;
    var i = +m[1] - 1;
    if (st.choosing != null) { if (i < 2) { e.preventDefault(); choose(i); } return; }
    if (e.shiftKey) { if (number.gs[i]) { e.preventDefault(); gate(number.gs[i]); } }
    else if (number.js[i]) { e.preventDefault(); turn(number.js[i]); }
  });
  document.addEventListener('keyup', function (e) { if (e.code === 'Space' || e.key === ' ') breathe(false); });
  window.addEventListener('blur', function () { breathe(false); });

  /* ── begin, and the end ───────────────────────────────────────────── */
  function begin() {
    $('tbegin').disabled = true;
    main.dataset.phase = 'settle';
    if (window.SparMusic) { window.SparMusic.start('meditation'); if (S.chamber.sound) window.SparMusic.ambience(S.chamber.sound); }
    var bgv = $('tbg'); if (bgv && bgv.play) { var bp = bgv.play(); if (bp && bp.catch) bp.catch(function () {}); }
    say(S.begin);
    fetch('/train/go', {method: 'POST'}).then(function (r) { return r.json(); }).then(function (j) {
      if (j.error || j.gone) again($('tbanner'), j.error || 'The meditation is over.', 'warn');
    }).catch(function () {});
    t0 = performance.now(); running = true;
    again($('tbanner'), 'Your body grows still. The meridians glow…');
  }
  $('tbegin').addEventListener('click', begin);

  function finish() {
    if (ended) return;
    ended = true; breathe(false); running = false;
    main.dataset.phase = 'wait';
    rivalOut();
    ending();
    var send = function (tries) {
      fetch('/train/submit', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({actions: actions})})
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if (j.result) return result(j.result, true);
          if (j.error && /isn't over/.test(j.error) && tries < 5) return setTimeout(function () { send(tries + 1); }, 1000);
          again($('tbanner'), j.error || 'The meditation is over.', 'warn');
          setTimeout(function () { location.href = '/town?near=keeper'; }, 2500);
        })
        .catch(function () { if (tries < 5) setTimeout(function () { send(tries + 1); }, 1500); });
    };
    setTimeout(function () { send(0); }, st.deviation ? 1200 : 600);
  }
  function result(r, fresh) {
    main.dataset.phase = 'result';
    if (window.SparMusic && fresh) window.SparMusic.stop();
    $('tbanner').textContent = ''; $('tbanner').className = 'pbanner';
    $('rkick').textContent = {great: 'MERIDIANS CLEAR', good: 'WELL GUIDED', poor: 'THE QI DRIFTS', bad: 'THE QI SCATTERS',
                              deviation: 'QI DEVIATION'}[r.verdict];
    $('rscore').textContent = Math.round(r.score * 100) + '%';
    $('rline').textContent = '"' + r.line + '"';
    var counts = [['Gold delivered', r.gold_in + ' / ' + r.gold]];
    if (r.dark) counts.push(['Dark expelled', r.dark_out + ' / ' + r.dark]);
    counts.push(['Stability', r.stability]);
    if (r.dark_in) counts.push(['Dark in the Dantian', r.dark_in]);
    if (r.bursts) counts.push(['Gates burst', r.bursts]);
    if (r.best_harmony) counts.push(['Best Harmony', r.best_harmony]);
    if (r.boon_names && r.boon_names.length) counts.push(['Blessings', r.boon_names.join(', ')]);
    var ul = $('rcounts'); ul.innerHTML = '';
    counts.forEach(function (c) { var li = document.createElement('li'); li.innerHTML = '<span></span><b></b>'; li.firstChild.textContent = c[0]; li.lastChild.textContent = c[1]; ul.appendChild(li); });
    $('rexp').textContent = '+' + r.gained.toLocaleString() + ' Qi · ' + r.bar.qi.toLocaleString() + ' / ' + r.bar.need.toLocaleString() + ' (' + r.bar.where + ')';
    var notes = r.notes.slice();
    notes.push('Rest ' + r.again + ' before you train again.');
    var nl = $('rnotes'); nl.innerHTML = '';
    notes.forEach(function (t) { var li = document.createElement('li'); li.textContent = t; nl.appendChild(li); });
    var fill = $('rbar'), cap = r.bar.need || 1;
    fill.style.width = Math.min(100, 100 * r.bar.before / cap) + '%';
    var show = function () { $('tresult').hidden = false; setTimeout(function () { fill.style.width = Math.min(100, 100 * r.bar.qi / cap) + '%'; }, 400); };
    if (!fresh) { show(); return; }
    setTimeout(show, Math.max(400, endAt - performance.now()));       // after the ending has played
  }

  /* How the session ends, from this page's own count (the server's will agree): your character answers, with the
     ending's video and its sound when the art is there.
       85%+  Meridians clear: the Qi surge, the golden bloom, a chime        70%+  Well guided: the same, smaller
       50%+  The Qi drifts: the map dims, a low note                         under 50%  The Qi scatters: grey mist
       Stability 0  Qi deviation: dark Qi tears loose, the crack */
  function ending() {
    var score = SIM.score(PLAN, st), d = cyc().nodes.dantian || PLAN.cycles[0].nodes.dantian, at = [X(d.x), Y(d.y)];
    var t = performance.now(), wait = 1400;
    function pic(name, size, life, delay, rise) { flashes.push({pic: name, x: at[0], y: at[1], size: size, life: life, t: t + (delay || 0), rise: rise}); }
    function words(title, line, sad, delay) {
      setTimeout(function () {
        var el = $('tcheer'); el.innerHTML = '<span></span><small></small>';
        el.firstChild.textContent = title; el.lastChild.textContent = line;
        el.className = 'tcheer' + (sad ? ' sad' : ''); void el.offsetWidth; el.className += ' go';
      }, delay || 0);
    }
    if (st.deviation) {
      var dv = playEnd('deviation');
      pic('crack', 62, 2600, 0); mapDim = 0.35;
      words('Qi deviation!', 'The Qi tears loose', true, 300);
      wait = dv ? 5600 : 2400;
    } else if (score >= 0.7) {
      var big = score >= 0.85, sv = playEnd('surge'), peak = sv ? 3300 : 0;
      setTimeout(function () { cheer(big ? 'Meridians clear!' : 'Well guided', big ? 'Clear as spring water' : 'The Qi listened to you'); }, peak);
      pic('bloom', big ? 60 : 40, 2800, peak);
      wait = sv ? 6600 : 2600;
    } else if (score >= 0.5) {
      mapDim = 0.4; fs('defeat');
      words('The Qi drifts', 'You chased it instead of guiding it', true, 200);
      wait = 2600;
    } else {
      var sc = playEnd('scatter');
      mapDim = 0.3; pic('scatter', 70, 3200, sc ? 2300 : 200, 10);
      if (!sc) fs('defeat');
      words('The Qi scatters', 'Breathe first, then steer', true, sc ? 2200 : 300);
      wait = sc ? 5800 : 2600;
    }
    endAt = t + wait;
  }

  /* the celebration (no teacher: the meditation itself answers). Gold rings bloom out of the Dantian, the body
     glows, a chime; a great session (85%+) gets the full bloom */
  function cheer(title, line) {
    var c = cyc().nodes.dantian || PLAN.cycles[0].nodes.dantian, at = [X(c.x), Y(c.y)], big = title === 'Meridians clear!';
    glow = big ? 2.4 : 1.6; fs('victory');
    for (var i = 0; i < (big ? 5 : 2); i++) setTimeout(function () { flashes.push({x: at[0], y: at[1], kind: 'bloom', t: performance.now()}); fs('heal'); }, i * 260);
    var el = $('tcheer'); el.innerHTML = '<span></span><small></small>';
    el.firstChild.textContent = title; el.lastChild.textContent = line;
    el.className = 'tcheer'; void el.offsetWidth; el.className = 'tcheer go';
  }

  /* ── How to play: the guide. It opens by itself the first time; then from the start card or the ? button. It
     never pauses the meditation (the Qi keeps flowing), so the first time it shows before you begin. ── */
  var GUIDE_SEEN = 'ma.train.guide.seen', pages = [], page = 0;
  (function () {
    var box = $('tguide'), nav = $('tgnav');
    box.querySelectorAll('.tgbody section').forEach(function (sec) { pages.push(sec.dataset.p); });
    function go(i) {
      page = Math.max(0, Math.min(pages.length - 1, i));
      box.querySelectorAll('.tgbody section').forEach(function (sec, j) { sec.classList.toggle('on', j === page); });
      nav.querySelectorAll('button').forEach(function (b) { b.classList.toggle('on', b.dataset.p === pages[page]); });
      $('tgpage').textContent = (page + 1) + ' / ' + pages.length;
      $('tgprev').style.visibility = page ? 'visible' : 'hidden';
      $('tgnext').textContent = page < pages.length - 1 ? 'Next →' : 'Done';
      box.querySelector('.tgbody').scrollTop = 0;
      var on = nav.querySelector('button.on'); if (on && on.scrollIntoView && window.innerWidth < 900) on.scrollIntoView({block: 'nearest', inline: 'center'});
    }
    window.trainGuide = function (open, at) {
      if (!open) { box.hidden = true; return; }
      $('tglive').hidden = !running;
      box.hidden = false; go(at == null ? page : pages.indexOf(at) >= 0 ? pages.indexOf(at) : at);
      try { localStorage.setItem(GUIDE_SEEN, '1'); } catch (e) {}
    };
    nav.querySelectorAll('button').forEach(function (b) { b.addEventListener('click', function () { go(pages.indexOf(b.dataset.p)); }); });
    $('tgprev').addEventListener('click', function () { go(page - 1); });
    $('tgnext').addEventListener('click', function () { if (page < pages.length - 1) go(page + 1); else trainGuide(false); });
    $('tgclose').addEventListener('click', function () { trainGuide(false); });
    $('tguidebtn').addEventListener('click', function () { trainGuide(true, 0); });
    $('tqbtn').addEventListener('click', function () { trainGuide(box.hidden, running ? 'controls' : null); });
    document.addEventListener('keydown', function (e) {
      if (box.hidden) return;
      if (e.key === 'Escape') { e.preventDefault(); trainGuide(false); }
      else if (e.key === 'ArrowRight') go(page + 1);
      else if (e.key === 'ArrowLeft') go(page - 1);
    }, true);
    var seen = false;
    try { seen = localStorage.getItem(GUIDE_SEEN) === '1'; } catch (e) {}
    if (!seen && !S.result && !S.begun) trainGuide(true, 0);
  })();

  /* first-time tips: the moment something new appears, one line says what to do (each once per browser) */
  var tipQ = [], tipT = 0;
  function tip(key, text) {
    var k = 'ma.train.tip.' + key;
    try { if (localStorage.getItem(k) === '1') return; localStorage.setItem(k, '1'); } catch (e) {}
    tipQ.push(text);
  }
  function tips(now) {
    if (!tipQ.length || now < tipT) return;
    say(tipQ.shift()); tipT = now + 5200;
  }

  /* Leave: walking away earns nothing and the rest stays, so it asks once; after the result it goes back */
  (function () {
    var form = $('tleave'), label = form.querySelector('span'), sure = false, k = null;
    form.addEventListener('submit', function (e) {
      if (main.dataset.phase === 'result') { form.action = '/train/done'; return; }
      if (sure) return;
      e.preventDefault(); sure = true; label.textContent = 'Leave? No Qi'; form.classList.add('sure');
      clearTimeout(k); k = setTimeout(function () { sure = false; label.textContent = 'Leave'; form.classList.remove('sure'); }, 3500);
    });
  })();

  if (S.result) { $('tintro').hidden = true; result(S.result, false); }
  else if (S.begun) {
    $('tbegin').hidden = true;
    var lost = document.createElement('p'); lost.className = 'anotice'; lost.textContent = 'You left the meditation in the middle. It can only be walked away from now.';
    $('tintro').insertBefore(lost, $('tintro').querySelector('.pbtns'));
  }
  requestAnimationFrame(draw);
})();
