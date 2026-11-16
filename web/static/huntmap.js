/* The hunting-ground map (hunt_map.html, web/hunt_map.py, docs/hunting.md "The map").

   Walk the cultivator about a 2:1 isometric map with W A S D / the arrow keys or the on-screen joystick: both feed
   one movement vector, in screen space. He is drawn from his walking sheet (looks.WALK_SHEETS: 8 rows S SW W NW N NE
   E SE x 8 frames, feet at a fixed point in each 256 px cell); the row follows the direction he moves in, and the
   frames advance with the distance walked, one stride per `STRIDE` px, so his feet never slide. Standing still holds
   each row's feet-together frame.

   The server decides everything that matters: which beast is out there and where (it is already rolled), whether
   you are where you say (the page reports its position a few times a second and is put back if the server
   disagrees), and when the fight starts (walk up to the beast: the page asks, the server checks how close you are,
   then /hunt shows the ordinary fight screen). */
(function () {
  'use strict';
  var cfg = JSON.parse(document.getElementById('mapdata').textContent);
  var SH = cfg.sheet, CELL = SH.cell, FEET_X = SH.feet[0], FEET_Y = SH.feet[1], STAND = SH.stand;
  var SIZE = cfg.size, EDGE = cfg.edge, REACH = cfg.reach, BLOCKED = cfg.blocked || [];
  var TW = 128, TH = 64;                       // a tile on screen
  var SPEED = 150, STRIDE = 96, ZOOM = 1.2;     // px/s on screen; px per full stride (at 100%); character size
  var SLOW = 0.45;                              // Shift: a stroll

  function toScreen(x, y) { return {x: (x - y) * TW / 2, y: (x + y) * TH / 2}; }
  function walkable(x, y) {                     // the same test as web/hunt_map.walkable: the edge, then rocks, trees, water
    if (!(x > EDGE && y > EDGE && x < SIZE - EDGE && y < SIZE - EDGE)) return false;
    for (var i = 0; i < BLOCKED.length; i++) { var c = BLOCKED[i]; if (Math.hypot(x - c[0], y - c[1]) <= c[2]) return false; }
    return true;
  }

  var cv = document.getElementById('map'), ctx = cv.getContext('2d'), W = 0, H = 0, DPR = 1;
  function resize() {
    DPR = Math.min(window.devicePixelRatio || 1, 2); W = window.innerWidth; H = window.innerHeight;
    cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR);
  }
  window.addEventListener('resize', resize); resize();

  /* the ground: the location's painting (art/maps, its diamond's corners on the image's edges), or drawn in code */
  function rnd(seed) { return function () { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; }; }
  var ground = document.createElement('canvas'), gx0, gy0, painted = null;
  if (cfg.ground) { painted = new Image(); painted.src = cfg.ground; }
  else (function bake() {
    var r = rnd(7), pad = 160, w = SIZE * TW, h = SIZE * TH;
    ground.width = w + pad * 2; ground.height = h + pad * 2; gx0 = -w / 2 - pad; gy0 = -pad;
    var g = ground.getContext('2d');
    g.fillStyle = '#0D1410'; g.fillRect(0, 0, ground.width, ground.height);
    for (var y = 0; y < SIZE; y++) for (var x = 0; x < SIZE; x++) {
      var p = toScreen(x, y), cx = p.x - gx0, cy = p.y - gy0, edge = !walkable(x + .5, y + .5);
      var path = Math.abs((x - y) + Math.sin(y * 0.55) * 1.6) < 1.35 && !edge;
      var wave = Math.sin(x * .45 + y * .3) * .5 + Math.sin(y * .7 - x * .2) * .5, l = r() * .35 + (wave + 1) * .3;
      var c = edge ? [18 + l * 8, 30 + l * 10, 24 + l * 8] : path ? [90 + l * 12, 78 + l * 10, 56 + l * 8] : [42 + l * 12, 70 + l * 16, 48 + l * 10];
      g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx + TW / 2, cy + TH / 2); g.lineTo(cx, cy + TH); g.lineTo(cx - TW / 2, cy + TH / 2); g.closePath();
      g.fillStyle = 'rgb(' + c.map(Math.round).join(',') + ')'; g.fill(); g.strokeStyle = g.fillStyle; g.lineWidth = 1; g.stroke();
      for (var k = 0; k < (edge ? 2 : 6); k++) {
        var u = r() - .5, v = r() - .5;
        g.fillStyle = path ? 'rgba(40,30,20,.35)' : 'rgba(150,190,120,' + (0.10 + r() * 0.15) + ')';
        g.fillRect(cx + (u - v) * TW / 2 * .9, cy + TH / 2 + (u + v) * TH / 2 * .9, path ? 3 : 1.5, path ? 2 : 4);
      }
    }
    var mid = toScreen(SIZE / 2, SIZE / 2), lg = g.createRadialGradient(mid.x - gx0, mid.y - gy0, 60, mid.x - gx0, mid.y - gy0, w * .62);
    lg.addColorStop(0, 'rgba(210,225,255,.10)'); lg.addColorStop(.6, 'rgba(0,0,0,0)'); lg.addColorStop(1, 'rgba(0,0,0,.55)');
    g.fillStyle = lg; g.fillRect(0, 0, ground.width, ground.height);
    for (var t = 0; t < 140; t++) {
      var a = r() * SIZE, b = r() * SIZE;
      if (walkable(a, b)) continue;
      var q = toScreen(a, b), rr = 26 + r() * 30;
      var tg = g.createRadialGradient(q.x - gx0, q.y - gy0 - rr * .6, 4, q.x - gx0, q.y - gy0 - rr * .4, rr);
      tg.addColorStop(0, 'rgba(46,74,52,.95)'); tg.addColorStop(1, 'rgba(10,18,12,0)');
      g.fillStyle = tg; g.beginPath(); g.arc(q.x - gx0, q.y - gy0 - rr * .5, rr, 0, Math.PI * 2); g.fill();
    }
  })();

  /* input: keyboard and joystick feed one movement vector (screen space, length 0..1) */
  var keys = {}, stickV = {x: 0, y: 0}, stickId = null;
  var KEYMAP = {KeyW: 'u', ArrowUp: 'u', KeyS: 'd', ArrowDown: 'd', KeyA: 'l', ArrowLeft: 'l', KeyD: 'r', ArrowRight: 'r'};
  window.addEventListener('keydown', function (e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'BUTTON') return;
    if (KEYMAP[e.code]) { keys[KEYMAP[e.code]] = true; e.preventDefault(); }
    if (e.key === 'Shift') keys.slow = true;
  });
  window.addEventListener('keyup', function (e) { if (KEYMAP[e.code]) keys[KEYMAP[e.code]] = false; if (e.key === 'Shift') keys.slow = false; });
  var stick = document.getElementById('stick'), knob = document.getElementById('knob');
  function resetStick() { stickV = {x: 0, y: 0}; knob.style.transform = ''; }
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
    var x = (keys.r ? 1 : 0) - (keys.l ? 1 : 0), y = (keys.d ? 1 : 0) - (keys.u ? 1 : 0), m = Math.hypot(x, y);
    if (m) { var s = keys.slow ? SLOW : 1; return {x: x / m * s, y: y / m * s}; }
    return stickV;
  }

  /* the journal button */
  var logBtn = document.getElementById('logBtn'), log = document.getElementById('log');
  logBtn.addEventListener('click', function () { var o = log.classList.toggle('open'); logBtn.setAttribute('aria-expanded', o); cv.focus(); });
  if (cfg.step > 1 || !cfg.beast) { log.classList.add('open'); logBtn.setAttribute('aria-expanded', 'true');
    setTimeout(function () { log.classList.remove('open'); logBtn.setAttribute('aria-expanded', 'false'); }, 6000); }

  /* the hero */
  var ROW_ANGLE = [90, 135, 180, 225, 270, 315, 0, 45];      // each row's facing, screen degrees (0 right, clockwise)
  function sectorRow(a) { var k = ((Math.round(a / (Math.PI / 4)) % 8) + 8) % 8; return (k + 6) % 8; }
  function angDiff(a, b) { return Math.abs(((a - b) % 360 + 540) % 360 - 180); }
  var hero = {x: cfg.hero.x, y: cfg.hero.y, dir: 4, frame: STAND[4], phase: 0, moving: false};

  /* the beast */
  var beast = cfg.beast, bimg = null, bt = 0;
  if (beast) { bimg = new Image(); bimg.src = beast.src; beast.w = beast.tier === 'beast_king' ? 195 : beast.tier === 'elite' ? 155 : 125; }
  var prompt = document.getElementById('prompt');

  /* talking to the server: where we are, and the fight */
  var sentAt = 0, engaging = false;
  function post(url, data) {
    var body = new URLSearchParams(data);
    return fetch(url, {method: 'POST', body: body, credentials: 'same-origin', headers: {'Accept': 'application/json'}});
  }
  function report(force) {
    var now = performance.now();
    if (!force && now - sentAt < 300) return;
    sentAt = now;
    post('/hunt/pos', {x: hero.x.toFixed(3), y: hero.y.toFixed(3)}).then(function (r) { return r.json(); }).then(function (v) {
      if (v.gone) { location.replace('/hunt'); return; }
      if (Math.hypot(v.x - hero.x, v.y - hero.y) > 1.2) { hero.x = v.x; hero.y = v.y; }     // the server disagreed: back there
    }).catch(function () {});
  }
  function engage() {
    if (engaging) return;
    engaging = true; keys = {}; resetStick();
    prompt.textContent = 'The ' + beast.name + ' turns on you…'; prompt.classList.add('on');
    document.getElementById('engageAt').value = hero.x.toFixed(3) + ',' + hero.y.toFixed(3);
    post('/hunt/act', new FormData(document.getElementById('engage'))).then(function () { location.replace('/hunt'); })
      .catch(function () { engaging = false; prompt.classList.remove('on'); });
  }

  /* the loop: fixed 60 Hz steps, drawn every frame */
  var sheet = new Image(); sheet.src = SH.src;
  var cam = {x: 0, y: 0}, last = 0, acc = 0, STEP = 1 / 60;
  function update(dt) {
    if (engaging) return;
    var v = inputVector(), m = Math.hypot(v.x, v.y), was = hero.moving;
    hero.moving = m > 0.01;
    if (hero.moving) {
      var ang = Math.atan2(v.y, v.x), deg = (ang * 180 / Math.PI + 360) % 360;
      if (angDiff(deg, ROW_ANGLE[hero.dir]) > 28.5) hero.dir = sectorRow(ang);         // 22.5° + a little hysteresis
      var sp = SPEED * m, vx = v.x / m * sp, vy = v.y / m * sp;
      var nx = hero.x + (vx / (TW / 2) + vy / (TH / 2)) / 2 * dt, ny = hero.y + (vy / (TH / 2) - vx / (TW / 2)) / 2 * dt;
      if (walkable(nx, hero.y)) hero.x = nx;
      if (walkable(hero.x, ny)) hero.y = ny;
      if (!was) hero.phase = STAND[hero.dir];
      hero.phase = (hero.phase + sp * dt / (STRIDE * ZOOM) * 8) % 8;
      hero.frame = Math.floor(hero.phase);
      report(false);
    } else {
      if (was) report(true);
      hero.frame = STAND[hero.dir];
    }
    if (beast) {
      bt += dt;
      var d = Math.hypot(hero.x - beast.x, hero.y - beast.y);
      if (d < REACH * 0.85) engage();
      else if (d < REACH * 2.2) { prompt.textContent = 'Close in on the ' + beast.name + '…'; prompt.classList.add('on'); }
      else prompt.classList.remove('on');
    }
  }
  function shadow(x, y, rx, ry, a) { ctx.save(); ctx.fillStyle = 'rgba(0,0,0,' + a + ')'; ctx.beginPath(); ctx.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2); ctx.fill(); ctx.restore(); }
  function drawHero(x, y) {
    var s = 0.5 * ZOOM;
    shadow(x, y, 26 * ZOOM, 9 * ZOOM, .42);
    if (sheet.complete) ctx.drawImage(sheet, hero.frame * CELL, hero.dir * CELL, CELL, CELL, x - FEET_X * s, y - FEET_Y * s, CELL * s, CELL * s);
  }
  function drawBeast(x, y, face) {
    if (!bimg.complete || !bimg.naturalWidth) return;
    var w = beast.w, h = w * bimg.naturalHeight / bimg.naturalWidth, bob = Math.sin(bt * 2.2) * 1.5;
    var glow = beast.tier === 'beast_king' ? 'rgba(255,80,70,' : beast.tier === 'elite' ? 'rgba(240,150,80,' : null;
    if (glow) { var gg = ctx.createRadialGradient(x, y - h * .35, 10, x, y - h * .35, w * .75);
      gg.addColorStop(0, glow + '.28)'); gg.addColorStop(1, glow + '0)'); ctx.fillStyle = gg; ctx.fillRect(x - w, y - h * 1.2, w * 2, h * 1.6); }
    shadow(x, y, w * .38, w * .1, .45);
    ctx.save(); ctx.translate(x, y + bob); ctx.scale(face, 1); ctx.drawImage(bimg, -w / 2, -h * .96, w, h); ctx.restore();
    ctx.font = '700 12px Cinzel, Georgia, serif'; ctx.textAlign = 'center';
    var label = (beast.tier === 'normal' ? '' : beast.tierName + ' · ') + beast.name;
    ctx.fillStyle = 'rgba(0,0,0,.6)'; ctx.fillText(label, x + 1, y - h - 5);
    ctx.fillStyle = beast.tier === 'normal' ? '#EBCB86' : beast.tier === 'elite' ? '#FFC69A' : '#FFB0A8'; ctx.fillText(label, x, y - h - 6);
  }
  function pointer(ox, oy, bp) {                 // an arrow at the screen's edge toward a beast you can't see
    var sx = ox + bp.x, sy = oy + bp.y - 40, M = 46;
    if (sx > M && sx < W - M && sy > M && sy < H - M) return;
    var cx = W / 2, cy = H / 2, a = Math.atan2(sy - cy, sx - cx);
    var t = Math.min((W / 2 - M) / Math.abs(Math.cos(a) || 1e-6), (H / 2 - M) / Math.abs(Math.sin(a) || 1e-6));
    var px = cx + Math.cos(a) * t, py = cy + Math.sin(a) * t;
    ctx.save(); ctx.translate(px, py); ctx.rotate(a);
    ctx.fillStyle = 'rgba(235,203,134,.9)'; ctx.beginPath(); ctx.moveTo(14, 0); ctx.lineTo(-8, -9); ctx.lineTo(-4, 0); ctx.lineTo(-8, 9); ctx.closePath(); ctx.fill();
    ctx.restore();
  }
  function draw() {
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0); ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high';
    var hp = toScreen(hero.x, hero.y);
    cam.x += (hp.x - cam.x) * 0.12; cam.y += (hp.y - 60 - cam.y) * 0.12;
    var ox = Math.round(W / 2 - cam.x), oy = Math.round(H / 2 - cam.y);
    ctx.fillStyle = '#0B0B0D'; ctx.fillRect(0, 0, W, H);
    if (painted) { if (painted.complete) ctx.drawImage(painted, ox - SIZE * TW / 2, oy, SIZE * TW, SIZE * TH); }
    else ctx.drawImage(ground, ox + gx0, oy + gy0);
    if (debug) drawDebug(ox, oy);
    var list = [{y: hp.y, f: function () { drawHero(ox + hp.x, oy + hp.y); }}], bp = null;
    if (beast) { bp = toScreen(beast.x, beast.y); list.push({y: bp.y, f: function () { drawBeast(ox + bp.x, oy + bp.y, hp.x < bp.x ? -1 : 1); }}); }
    list.sort(function (a, b) { return a.y - b.y; }).forEach(function (o) { o.f(); });
    if (bp) pointer(ox, oy, bp);
  }
  /* G: the tile grid, the walkable edge and what blocks the way (to check a map against its painting) */
  var debug = false;
  window.addEventListener('keydown', function (e) { if (e.code === 'KeyG' && e.target.tagName !== 'INPUT') debug = !debug; });
  function drawDebug(ox, oy) {
    ctx.save(); ctx.lineWidth = 1; ctx.strokeStyle = 'rgba(235,203,134,.25)';
    for (var i = 0; i <= SIZE; i++) {
      var a = toScreen(i, 0), b = toScreen(i, SIZE), c = toScreen(0, i), d = toScreen(SIZE, i);
      ctx.beginPath(); ctx.moveTo(ox + a.x, oy + a.y); ctx.lineTo(ox + b.x, oy + b.y); ctx.moveTo(ox + c.x, oy + c.y); ctx.lineTo(ox + d.x, oy + d.y); ctx.stroke();
    }
    ctx.strokeStyle = 'rgba(79,199,155,.9)'; ctx.lineWidth = 2; ctx.beginPath();
    [[EDGE, EDGE], [SIZE - EDGE, EDGE], [SIZE - EDGE, SIZE - EDGE], [EDGE, SIZE - EDGE]].forEach(function (q, i) {
      var p = toScreen(q[0], q[1]); ctx[i ? 'lineTo' : 'moveTo'](ox + p.x, oy + p.y); });
    ctx.closePath(); ctx.stroke();
    ctx.fillStyle = 'rgba(224,90,80,.35)'; ctx.strokeStyle = 'rgba(255,140,120,.9)';
    BLOCKED.forEach(function (c) {                     // a circle on the ground is an ellipse on screen
      var p = toScreen(c[0], c[1]);
      ctx.beginPath(); ctx.ellipse(ox + p.x, oy + p.y, c[2] * TW / Math.SQRT2, c[2] * TH / Math.SQRT2, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    });
    var h = toScreen(hero.x, hero.y);
    ctx.fillStyle = '#F6E2B0'; ctx.font = '12px Inter, sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(hero.x.toFixed(1) + ', ' + hero.y.toFixed(1), ox + h.x, oy + h.y + 18);
    ctx.restore();
  }
  function frame(t) {
    var dt = Math.min(0.1, (t - last) / 1000 || 0); last = t;
    acc += dt; while (acc >= STEP) { update(STEP); acc -= STEP; }
    draw(); requestAnimationFrame(frame);
  }
  var p0 = toScreen(hero.x, hero.y); cam.x = p0.x; cam.y = p0.y - 60;
  cv.addEventListener('pointerdown', function () { cv.focus(); });
  cv.focus();
  requestAnimationFrame(frame);
})();
