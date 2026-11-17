/* The town hub (town.html, web/town.py, docs/town.md).

   Walk the cultivator about the town: W A S D / the arrow keys or the on-screen joystick, as on the hunting map
   (web/static/huntmap.js, whose walking this follows: the sheet row follows the direction, the frames advance with
   the distance walked, standing still holds each row's feet-together frame, or plays the look's idle sheet if it has
   one: `sheet.idle`, its frames looped over `idle.loop` seconds, each faded into the next).

   What makes the town feel big: the painting is drawn at full size (32 x 32 tiles of 128 x 64 px) and the camera
   is zoomed so a screen shows about VIEW tiles across, whatever its size, so you never see the whole town at once;
   the town is drawn K times bigger than the painting's own scale against you (cfg.scale: you, the townsfolk and
   your walking speed on screen stay the same, the streets get longer);
   the camera stops at the painting's edges; and a night vignette darkens everything away from you.

   The town is built from pieces (web/town.py): the ground, then each building and prop as its own picture, drawn in
   depth order with you and the townsfolk: you are hidden by a building when you stand behind it (beyond its
   footprint's back edges), and drawn over it in front; when something hides you, your silhouette shows through it.

   Walk up to someone and press E (or tap the button) to talk: a dialogue says who they are and offers the pages
   they send you to. Nothing here changes the game, so the server doesn't follow where you walk. */
(function () {
  'use strict';
  var cfg = JSON.parse(document.getElementById('mapdata').textContent);
  var SH = cfg.sheet, CELL = SH.cell, FEET_X = SH.feet[0], FEET_Y = SH.feet[1], STAND = SH.stand;
  var SIZE = cfg.size, AREA = cfg.area, BLOCKED = cfg.blocked || [], REACH = cfg.reach, NPCS = cfg.npcs;
  var PIECES = cfg.pieces || [], INSET = cfg.inset || 0;
  var TW = 128, TH = 64;                       // a tile, in the painting's pixels (the world)
  var SPEED = 150, STRIDE = 96, ZOOM = 1.2;     // world px/s; px per full stride (at 100%); character size
  var SLOW = 0.45, VIEW = 12;                   // Shift: a stroll; tiles across the screen (at K = 1)
  var K = cfg.scale || 1;                       // how much bigger the town is drawn than you

  function toScreen(x, y) { return {x: (x - y) * TW / 2, y: (x + y) * TH / 2}; }
  function inside(x, y) {                       // point in AREA (even-odd), as web/town.inside
    var hit = false;
    for (var i = 0, j = AREA.length - 1; i < AREA.length; j = i++) {
      var a = AREA[i], b = AREA[j];
      if ((a[1] > y) !== (b[1] > y) && x < a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])) hit = !hit;
    }
    return hit;
  }
  function walkable(x, y) {                     // the same test as web/town.walkable
    if (!(x > 0 && y > 0 && x < SIZE && y < SIZE) || !inside(x, y)) return false;
    for (var i = 0; i < BLOCKED.length; i++) { var c = BLOCKED[i]; if (Math.hypot(x - c[0], y - c[1]) <= c[2]) return false; }
    for (var j = 0; j < PIECES.length; j++) {
      var f = PIECES[j].fp; if (!f || PIECES[j].pass) continue;
      var e = Math.min(INSET, f[2] / 4, f[3] / 4);                // a small piece (a lantern) keeps most of its foot
      if (x > f[0] + e && x < f[0] + f[2] - e && y > f[1] + e && y < f[1] + f[3] - e) return false;
    }
    return true;
  }

  var cv = document.getElementById('map'), ctx = cv.getContext('2d'), W = 0, H = 0, DPR = 1, S = 1;
  function resize() {
    DPR = Math.min(window.devicePixelRatio || 1, 2); W = window.innerWidth; H = window.innerHeight;
    cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR);
    // VIEW tiles across a wide screen; a tall phone keeps the cultivator a readable size instead
    S = Math.min(1.6, Math.max(0.55, W / (VIEW * TW), H / (VIEW * TW * 0.72))) * K;
  }
  window.addEventListener('resize', resize); resize();
  window.addEventListener('townscale', function (e) { K = e.detail; resize(); });   // the demo's size buttons

  var painted = new Image(); painted.src = cfg.ground;
  PIECES.forEach(function (p) {
    p.img = new Image(); p.img.src = p.src;
    p.depth = p.fp ? p.fp[0] + p.fp[2] / 2 + p.fp[1] + p.fp[3] / 2 : p.at[0] + p.at[1];   // a footprint's middle
    p.order = p.z != null ? p.z : p.depth;        // a corner is drawn over the walls running in under its arms
  });
  PIECES.sort(function (a, b) { return a.order - b.order; });
  var sheet = new Image(); sheet.src = SH.src;
  var IDLE = SH.idle, idle = null;
  if (IDLE) { idle = new Image(); idle.src = IDLE.src; }
  NPCS.forEach(function (n) { if (n.src) { n.img = new Image(); n.img.src = n.src; } n.t = Math.random() * 6; });

  /* input: keyboard and joystick feed one movement vector (screen space, length 0..1) */
  var keys = {}, stickV = {x: 0, y: 0}, stickId = null;
  var KEYMAP = {KeyW: 'u', ArrowUp: 'u', KeyS: 'd', ArrowDown: 'd', KeyA: 'l', ArrowLeft: 'l', KeyD: 'r', ArrowRight: 'r'};
  var stick = document.getElementById('stick'), knob = document.getElementById('knob');
  function resetStick() { stickV = {x: 0, y: 0}; knob.style.transform = ''; }
  window.addEventListener('keydown', function (e) {
    if (e.target.tagName === 'INPUT') return;
    if (dlgOpen) { if (e.key === 'Escape') { closeTalk(); e.preventDefault(); } return; }
    if (KEYMAP[e.code]) { keys[KEYMAP[e.code]] = true; e.preventDefault(); }
    if (e.key === 'Shift') keys.slow = true;
    if ((e.code === 'KeyE' || e.code === 'Enter' || e.code === 'Space') && near) { openTalk(near); e.preventDefault(); }
    if (e.code === 'KeyG') debug = !debug;
  });
  window.addEventListener('keyup', function (e) { if (KEYMAP[e.code]) keys[KEYMAP[e.code]] = false; if (e.key === 'Shift') keys.slow = false; });
  window.addEventListener('blur', function () { keys = {}; resetStick(); });
  if (matchMedia('(pointer: coarse)').matches || 'ontouchstart' in window) {
    stick.classList.add('on'); document.getElementById('keys').style.display = 'none';
  }
  function stickMove(e) {
    var r = stick.getBoundingClientRect(), R = r.width / 2, lim = R - 10;
    var dx = e.clientX - (r.left + R), dy = e.clientY - (r.top + R), m = Math.hypot(dx, dy);
    if (m > lim) { dx *= lim / m; dy *= lim / m; m = lim; }
    knob.style.transform = 'translate(' + dx + 'px,' + dy + 'px)';
    var mag = m / lim, DEAD = 0.15;
    if (mag < DEAD) { stickV = {x: 0, y: 0}; return; }
    var k = (mag - DEAD) / (1 - DEAD) / mag;
    stickV = {x: dx / lim * k, y: dy / lim * k};
  }
  stick.addEventListener('pointerdown', function (e) { stickId = e.pointerId; stick.setPointerCapture(e.pointerId); stickMove(e); e.preventDefault(); });
  stick.addEventListener('pointermove', function (e) { if (e.pointerId === stickId) stickMove(e); });
  function stickUp(e) { if (e.pointerId === stickId) { stickId = null; resetStick(); } }
  stick.addEventListener('pointerup', stickUp); stick.addEventListener('pointercancel', stickUp);
  function inputVector() {
    if (dlgOpen) return {x: 0, y: 0};
    var x = (keys.r ? 1 : 0) - (keys.l ? 1 : 0), y = (keys.d ? 1 : 0) - (keys.u ? 1 : 0), m = Math.hypot(x, y);
    if (m) { var s = keys.slow ? SLOW : 1; return {x: x / m * s, y: y / m * s}; }
    return stickV;
  }

  /* the hero: at the gate, or in front of whoever you last left town through */
  var ROW_ANGLE = [90, 135, 180, 225, 270, 315, 0, 45];      // each row's facing, screen degrees (0 right, clockwise)
  function sectorRow(a) { var k = ((Math.round(a / (Math.PI / 4)) % 8) + 8) % 8; return (k + 6) % 8; }
  function angDiff(a, b) { return Math.abs(((a - b) % 360 + 540) % 360 - 180); }
  var hero = {x: cfg.hero.x, y: cfg.hero.y, dir: 4, frame: STAND[4], phase: 0, moving: false};
  var back = null;
  try { back = sessionStorage.getItem('town.from'); sessionStorage.removeItem('town.from'); } catch (e) {}
  NPCS.forEach(function (n) {                    // step back from them toward the gate until there is ground
    if (n.key !== back) return;
    for (var t = 0.08; t <= 1; t += 0.04) {
      var x = n.x + (cfg.hero.x - n.x) * t, y = n.y + (cfg.hero.y - n.y) * t;
      if (walkable(x, y) && Math.hypot(x - n.x, y - n.y) > 0.9) { hero.x = x; hero.y = y; break; }
    }
    var d = Math.atan2(toScreen(n.x, n.y).y - toScreen(hero.x, hero.y).y, toScreen(n.x, n.y).x - toScreen(hero.x, hero.y).x);
    hero.dir = sectorRow(d); hero.frame = STAND[hero.dir];
  });

  /* talking */
  var near = null, dlgOpen = false, prompt = document.getElementById('prompt'), dlg = document.getElementById('dlg');
  prompt.addEventListener('click', function () { if (near) openTalk(near); });
  function openTalk(n) {
    dlgOpen = true; keys = {}; resetStick(); prompt.classList.remove('on');
    document.getElementById('dlgName').textContent = n.name;
    document.getElementById('dlgTitle').textContent = n.title.toUpperCase();
    document.getElementById('dlgLine').textContent = n.line;
    var go = document.getElementById('dlgGo'); go.textContent = '';
    n.go.forEach(function (g, i) {
      var a = document.createElement('a'); a.className = 'hbtn small' + (i ? ' ghost' : ''); a.href = g[1]; a.textContent = g[0];
      a.addEventListener('click', function () { try { sessionStorage.setItem('town.from', n.key); } catch (e) {} });
      go.appendChild(a);
    });
    var bye = document.createElement('button'); bye.type = 'button'; bye.className = 'hbtn ghost small'; bye.textContent = n.go.length ? 'Leave' : 'Farewell';
    bye.addEventListener('click', closeTalk); go.appendChild(bye);
    dlg.hidden = false; (go.querySelector('a') || bye).focus();
  }
  function closeTalk() { dlgOpen = false; dlg.hidden = true; cv.focus(); }

  /* the loop: fixed 60 Hz steps, drawn every frame */
  var cam = {x: 0, y: 0}, last = 0, acc = 0, STEP = 1 / 60, debug = false, hiddenHero = false;
  function update(dt) {
    NPCS.forEach(function (n) { n.t += dt; });
    var v = inputVector(), m = Math.hypot(v.x, v.y), was = hero.moving;
    hero.moving = m > 0.01;
    if (hero.moving) {
      var ang = Math.atan2(v.y, v.x), deg = (ang * 180 / Math.PI + 360) % 360;
      if (angDiff(deg, ROW_ANGLE[hero.dir]) > 28.5) hero.dir = sectorRow(ang);         // 22.5° + a little hysteresis
      var sp = SPEED * m / K, vx = v.x / m * sp, vy = v.y / m * sp;
      var nx = hero.x + (vx / (TW / 2) + vy / (TH / 2)) / 2 * dt, ny = hero.y + (vy / (TH / 2) - vx / (TW / 2)) / 2 * dt;
      if (walkable(nx, hero.y)) hero.x = nx;
      if (walkable(hero.x, ny)) hero.y = ny;
      if (!was) hero.phase = STAND[hero.dir];
      hero.phase = (hero.phase + sp * dt / (STRIDE * ZOOM / K) * 8) % 8;
      hero.frame = Math.floor(hero.phase);
      hero.still = 0;
    } else { hero.frame = STAND[hero.dir]; hero.still = (hero.still || 0) + dt; }
    var best = null, bd = REACH;
    NPCS.forEach(function (n) { var d = Math.hypot(hero.x - n.x, hero.y - n.y); if (d < bd) { bd = d; best = n; } });
    if (best !== near) {
      near = best;
      if (near) { prompt.textContent = (near.prop ? 'Read the ' : 'Talk to ') + near.name + ' '; var k = document.createElement('b'); k.textContent = 'E'; prompt.appendChild(k); }
    }
    prompt.classList.toggle('on', !!near && !dlgOpen);
  }
  function shadow(x, y, rx, ry, a) { ctx.save(); ctx.fillStyle = 'rgba(0,0,0,' + a + ')'; ctx.beginPath(); ctx.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2); ctx.fill(); ctx.restore(); }
  function drawHero(x, y) {
    var s = 0.5 * ZOOM;
    shadow(x, y, 26 * ZOOM, 9 * ZOOM, .42);
    var dx = x - FEET_X * s, dy = y - FEET_Y * s, d = CELL * s;
    if (!hero.moving && idle && idle.complete && idle.naturalWidth) {
      var t = (hero.still / IDLE.loop * IDLE.cols) % IDLE.cols, a = Math.floor(t), b = (a + 1) % IDLE.cols;
      ctx.drawImage(idle, a * CELL, hero.dir * CELL, CELL, CELL, dx, dy, d, d);
      ctx.save(); ctx.globalAlpha *= t - a;                    // *=: also right when drawn faded through a wall
      ctx.drawImage(idle, b * CELL, hero.dir * CELL, CELL, CELL, dx, dy, d, d);
      ctx.restore();
    } else if (sheet.complete) ctx.drawImage(sheet, hero.frame * CELL, hero.dir * CELL, CELL, CELL, dx, dy, d, d);
  }
  function label(n, x, y, close) {
    ctx.save(); ctx.textAlign = 'center';
    ctx.font = '700 15px Cinzel, Georgia, serif';
    ctx.fillStyle = 'rgba(0,0,0,.65)'; ctx.fillText(n.name, x + 1, y + 1);
    ctx.fillStyle = close ? '#F6E2B0' : '#EBCB86'; ctx.fillText(n.name, x, y);
    ctx.font = '600 11px Inter, sans-serif'; ctx.fillStyle = 'rgba(0,0,0,.65)'; ctx.fillText(n.title, x + 1, y + 16);
    ctx.fillStyle = 'rgba(230,223,207,.85)'; ctx.fillText(n.title, x, y + 15);
    ctx.restore();
  }
  function drawNpc(n, x, y) {
    var close = n === near, bob = Math.sin(n.t * 2) * 1.5, h = n.h;
    if (n.img && n.img.complete && n.img.naturalWidth) {
      var w = h * n.img.naturalWidth / n.img.naturalHeight, face = (hero.x - hero.y < n.x - n.y ? -1 : 1) * (n.flip ? -1 : 1);
      shadow(x, y, 24, 8, .42);
      ctx.save(); ctx.translate(x, y); ctx.scale(face, 1); ctx.drawImage(n.img, -w / 2, -h, w, h); ctx.restore();
      label(n, x, y - h - 18, close);
      return;
    }
    // no picture yet: a lantern glow where they stand, a floating marker and their name
    var g = ctx.createRadialGradient(x, y - 30, 4, x, y - 30, 70);
    g.addColorStop(0, 'rgba(255,214,140,' + (close ? .42 : .26) + ')'); g.addColorStop(1, 'rgba(255,190,110,0)');
    ctx.fillStyle = g; ctx.fillRect(x - 70, y - 100, 140, 140);
    if (!n.prop) {
      ctx.save(); ctx.translate(x, y - 58 + bob); ctx.rotate(Math.PI / 4);
      ctx.fillStyle = close ? '#F6E2B0' : '#C9A45C'; ctx.strokeStyle = 'rgba(26,20,10,.8)'; ctx.lineWidth = 2;
      ctx.fillRect(-7, -7, 14, 14); ctx.strokeRect(-7, -7, 14, 14); ctx.restore();
    }
    label(n, x, y - (n.prop ? 120 : 78), close);
  }
  function draw() {
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0); ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high';
    ctx.fillStyle = '#0B0B0D'; ctx.fillRect(0, 0, W, H);
    var hp = toScreen(hero.x, hero.y), vw = W / S, vh = H / S, half = SIZE * TW / 2, full = SIZE * TH;
    var tx = hp.x, ty = hp.y - 50 / K;
    tx = vw >= SIZE * TW ? 0 : Math.max(-half + vw / 2, Math.min(half - vw / 2, tx));       // stop at the painting's edges
    ty = vh >= full ? full / 2 : Math.max(vh / 2, Math.min(full - vh / 2, ty));
    cam.x += (tx - cam.x) * 0.12; cam.y += (ty - cam.y) * 0.12;
    ctx.setTransform(DPR * S, 0, 0, DPR * S, DPR * (W / 2 - cam.x * S), DPR * (H / 2 - cam.y * S));
    if (painted.complete) ctx.drawImage(painted, -half, 0, SIZE * TW, full);
    if (debug) drawDebug();
    function at(x, y, f) { ctx.save(); ctx.translate(x, y); ctx.scale(1 / K, 1 / K); f(); ctx.restore(); }   // you and they at your size
    var movers = [{hero: true, x: hero.x, y: hero.y, h: 175, f: function () { at(hp.x, hp.y, function () { drawHero(0, 0); }); }}];
    NPCS.forEach(function (n) {
      var p = toScreen(n.x, n.y);
      movers.push({x: n.x, y: n.y, h: (n.h || 100) + 50, f: function () { at(p.x, p.y, function () { drawNpc(n, 0, 0); }); }});
    });
    layered(movers).forEach(function (f) { f(); });
    if (hiddenHero) {                                   // behind a wall or a building: your silhouette shows through
      ctx.save(); ctx.globalAlpha = 0.45; at(hp.x, hp.y, function () { drawHero(0, 0); }); ctx.restore();
    }
    // night: everything away from you sinks into the dark
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    var cx = W / 2 + (hp.x - cam.x) * S, cy = H / 2 + (hp.y - 60 / K - cam.y) * S, R = Math.max(W, H);
    var v = ctx.createRadialGradient(cx, cy, R * 0.12, cx, cy, R * 0.66);
    v.addColorStop(0, 'rgba(6,8,18,0)'); v.addColorStop(0.5, 'rgba(6,8,18,.45)'); v.addColorStop(1, 'rgba(4,5,12,.9)');
    ctx.fillStyle = v; ctx.fillRect(0, 0, W, H);
  }
  /* depth order: the pieces back to front; each person goes after every piece they overlap on screen and stand in
     front of (beyond a footprint's back edge, or nearer than a prop), so the rest are drawn over them */
  function layered(movers) {
    var off = {x: SIZE * TW / 2, y: 0};                  // pieces' rects are on the ground picture, its top-left corner at (-half, 0)
    movers.forEach(function (m) {
      var p = toScreen(m.x, m.y), w = 60 / K, top = p.y - m.h / K, slot = 0;
      PIECES.forEach(function (q, i) {
        var r = q.rect, left = r[0] - off.x;
        if (p.x + w < left || p.x - w > left + r[2] || p.y < r[1] || top > r[1] + r[3]) return;     // no overlap
        var front = q.fp ? (m.x >= q.fp[0] + q.fp[2] - 0.25 || m.y >= q.fp[1] + q.fp[3] - 0.25) : m.x + m.y > q.depth;
        if (front) slot = i + 1;
      });
      m.slot = slot;
      if (m.hero) hiddenHero = PIECES.some(function (q, i) {   // is anything drawn over you?
        var r = q.rect, left = r[0] - off.x;
        return i >= slot && !(p.x + w < left || p.x - w > left + r[2] || p.y < r[1] || top > r[1] + r[3]);
      });
    });
    movers.sort(function (a, b) { return a.slot - b.slot || (a.x + a.y) - (b.x + b.y); });
    var out = [], k = 0;
    for (var i = 0; i <= PIECES.length; i++) {
      while (k < movers.length && movers[k].slot === i) out.push(movers[k++].f);
      if (i < PIECES.length) out.push(drawPiece.bind(null, PIECES[i], off));
    }
    return out;
  }
  function drawPiece(q, off) {
    if (!q.img.complete || !q.img.naturalWidth) return;
    ctx.drawImage(q.img, q.rect[0] - off.x, q.rect[1], q.rect[2], q.rect[3]);
  }
  /* G: the tile grid, the walkable ground and what blocks the way (to check the town against its painting) */
  function drawDebug() {
    ctx.save(); ctx.lineWidth = 1; ctx.strokeStyle = 'rgba(235,203,134,.25)';
    for (var i = 0; i <= SIZE; i++) {
      var a = toScreen(i, 0), b = toScreen(i, SIZE), c = toScreen(0, i), d = toScreen(SIZE, i);
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.moveTo(c.x, c.y); ctx.lineTo(d.x, d.y); ctx.stroke();
    }
    ctx.strokeStyle = 'rgba(79,199,155,.9)'; ctx.lineWidth = 2; ctx.beginPath();
    AREA.forEach(function (q, i) { var p = toScreen(q[0], q[1]); ctx[i ? 'lineTo' : 'moveTo'](p.x, p.y); });
    ctx.closePath(); ctx.stroke();
    ctx.fillStyle = 'rgba(224,90,80,.35)'; ctx.strokeStyle = 'rgba(255,140,120,.9)';
    BLOCKED.forEach(function (c) {
      var p = toScreen(c[0], c[1]);
      ctx.beginPath(); ctx.ellipse(p.x, p.y, c[2] * TW / Math.SQRT2, c[2] * TH / Math.SQRT2, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    });
    ctx.strokeStyle = 'rgba(120,170,255,.9)';
    PIECES.forEach(function (q) {
      if (!q.fp) return; var f = q.fp; ctx.beginPath();
      [[f[0], f[1]], [f[0] + f[2], f[1]], [f[0] + f[2], f[1] + f[3]], [f[0], f[1] + f[3]]].forEach(function (c, i) {
        var p = toScreen(c[0], c[1]); ctx[i ? 'lineTo' : 'moveTo'](p.x, p.y); });
      ctx.closePath(); ctx.stroke();
    });
    var h = toScreen(hero.x, hero.y);
    ctx.fillStyle = '#F6E2B0'; ctx.font = '12px Inter, sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(hero.x.toFixed(1) + ', ' + hero.y.toFixed(1), h.x, h.y + 18);
    ctx.restore();
  }
  function frame(t) {
    var dt = Math.min(0.1, (t - last) / 1000 || 0); last = t;
    acc += dt; while (acc >= STEP) { update(STEP); acc -= STEP; }
    draw(); requestAnimationFrame(frame);
  }
  var p0 = toScreen(hero.x, hero.y); cam.x = p0.x; cam.y = p0.y - 50 / K;
  cv.addEventListener('pointerdown', function () { cv.focus(); });
  cv.focus();
  requestAnimationFrame(frame);
})();
