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

  /* the beast: it wanders about the spot the server put it on, notices you (a "!"), charges, and the fight starts
     when it reaches you. How far it roams and sees comes from the server (hunt_map.WANDER / NOTICE), which only
     starts the fight where such a charge could have met you. Elites and Beast Kings roam wider and see further. */
  var beast = cfg.beast, bimg = null, bt = 0;
  var WANDER = (cfg.wander || {})[beast && beast.tier] || 0, NOTICE = (cfg.notice || {})[beast && beast.tier] || 0;
  var RUN = {normal: 4.4, elite: 4.8, beast_king: 5.2}, STROLL = {normal: 0.9, elite: 1.0, beast_king: 1.1};
  if (beast) {
    bimg = new Image(); bimg.src = beast.src; beast.w = beast.tier === 'beast_king' ? 195 : beast.tier === 'elite' ? 155 : 125;
    beast.home = {x: beast.x, y: beast.y}; beast.state = 'idle'; beast.timer = 0.8 + Math.random() * 1.5; beast.face = 1;
    beast.moving = 0;
  }
  var prompt = document.getElementById('prompt');
  function beastStep(dt) {
    var b = beast, d = Math.hypot(hero.x - b.x, hero.y - b.y);
    var leash = Math.hypot(hero.x - b.home.x, hero.y - b.home.y) <= WANDER + NOTICE;   // where the server allows a meeting
    b.timer -= dt; b.moving = 0;
    if ((b.state === 'idle' || b.state === 'wander') && d < NOTICE && leash) {
      b.state = 'alert'; b.timer = b.tier === 'beast_king' ? 0.4 : 0.55; b.alertAt = bt;
    }
    if (b.state === 'idle' && b.timer <= 0) {
      for (var i = 0; i < 8; i++) {                               // somewhere to sniff about, near its spot
        var a = Math.random() * Math.PI * 2, r = Math.random() * WANDER;
        var tx = b.home.x + Math.cos(a) * r, ty = b.home.y + Math.sin(a) * r;
        if (walkable(tx, ty)) { b.tx = tx; b.ty = ty; b.state = 'wander'; b.timer = 6; break; }
      }
      if (b.state === 'idle') b.timer = 1;
    }
    if (b.state === 'wander' || b.state === 'return') {
      var gx = b.state === 'return' ? b.home.x : b.tx, gy = b.state === 'return' ? b.home.y : b.ty;
      if (!moveBeast(gx, gy, STROLL[b.tier] * (b.state === 'return' ? 1.4 : 1), dt) || b.timer <= 0) {
        b.state = 'idle'; b.timer = 1.2 + Math.random() * 2.5;
      }
    }
    if (b.state === 'alert') { b.face = hero.x - hero.y > b.x - b.y ? 1 : -1; if (b.timer <= 0) { b.state = 'charge'; b.timer = 4; } }
    if (b.state === 'charge') {
      if (!leash || b.timer <= 0) { b.state = 'return'; b.timer = 8; b.lost = bt; return; }     // you got away
      moveBeast(hero.x, hero.y, RUN[b.tier], dt);
      if (Math.random() < 0.5) puff(b.x, b.y, 0.6);
      if (Math.hypot(hero.x - b.x, hero.y - b.y) < REACH * 0.8) engage();
    }
  }
  function moveBeast(gx, gy, speed, dt) {                         // false once it has arrived (or is stuck)
    var b = beast, dx = gx - b.x, dy = gy - b.y, m = Math.hypot(dx, dy);
    if (m < 0.08) return false;
    var step = Math.min(m, speed * dt), nx = b.x + dx / m * step, ny = b.y + dy / m * step, ok = false;
    if (walkable(nx, ny)) { b.x = nx; b.y = ny; ok = true; }
    else if (walkable(nx, b.y)) { b.x = nx; ok = true; }
    else if (walkable(b.x, ny)) { b.y = ny; ok = true; }
    if (ok) { b.moving = speed; var s = (dx - dy); if (Math.abs(s) > 0.02) b.face = s > 0 ? 1 : -1; }
    return ok;
  }

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

  /* the night: fireflies and mist over the clearing, bamboo leaves falling, the painted lamps glowing, dust where
     feet land, the edges of the view in shadow. Calmer when the player asks for reduced motion. */
  var CALM = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var LIGHTS = cfg.lights || [], puffs = [], flies = [], mists = [], leaves = [], night = 0;
  (function seed() {
    var r = rnd(42);
    for (var i = 0; i < (CALM ? 14 : 38); i++) {
      var x, y, k = 0;
      do { x = EDGE + r() * (SIZE - 2 * EDGE); y = EDGE + r() * (SIZE - 2 * EDGE); } while (!walkable(x, y) && ++k < 20);
      flies.push({x: x, y: y, z: 18 + r() * 50, ph: r() * 6.3, sp: .25 + r() * .35, hue: r()});
    }
    for (var j = 0; j < 7; j++) mists.push({x: EDGE + r() * (SIZE - 2 * EDGE), y: EDGE + r() * (SIZE - 2 * EDGE), r: 260 + r() * 320,
      vx: (r() - .5) * .18, vy: (r() - .5) * .12, a: .05 + r() * .05});
    for (var k2 = 0; k2 < (CALM ? 0 : 16); k2++) leaves.push(newLeaf(r, true));
  })();
  function newLeaf(r, anywhere) {
    r = r || Math.random;
    return {x: r() * (W + 200) - 100, y: anywhere ? r() * H : -20 - r() * 80, vx: 12 + r() * 18, vy: 22 + r() * 22,
            rot: r() * 6.3, spin: (r() - .5) * 3, sway: r() * 6.3, s: .7 + r() * .6, c: r() < .6 ? '#8FB35A' : '#C9B45A'};
  }
  function puff(x, y, size) {
    if (CALM || puffs.length > 60) return;
    for (var i = 0; i < 3; i++) puffs.push({x: x + (Math.random() - .5) * .25, y: y + (Math.random() - .5) * .25,
      t: 0, life: .45 + Math.random() * .3, s: size * (0.7 + Math.random() * .6), dx: (Math.random() - .5) * 16});
  }
  function stepAtmosphere(dt) {
    night += dt;
    for (var i = puffs.length - 1; i >= 0; i--) { puffs[i].t += dt; if (puffs[i].t > puffs[i].life) puffs.splice(i, 1); }
    flies.forEach(function (f) { f.ph += dt * f.sp; f.x += Math.cos(f.ph * 1.3) * dt * .25; f.y += Math.sin(f.ph) * dt * .25; });
    mists.forEach(function (m) {
      m.x += m.vx * dt; m.y += m.vy * dt;
      if (m.x < EDGE || m.x > SIZE - EDGE) m.vx *= -1;
      if (m.y < EDGE || m.y > SIZE - EDGE) m.vy *= -1;
    });
    leaves.forEach(function (l, i) {
      l.sway += dt * 1.6; l.rot += l.spin * dt;
      l.x += (l.vx + Math.sin(l.sway) * 14) * dt; l.y += l.vy * dt;
      if (l.y > H + 30 || l.x > W + 120) leaves[i] = newLeaf();
    });
  }
  function drawPuffs(ox, oy) {                                   // on the ground, under the walkers
    puffs.forEach(function (p) {
      var q = toScreen(p.x, p.y), k = p.t / p.life, r = (6 + 14 * k) * p.s;
      ctx.fillStyle = 'rgba(190,180,150,' + (0.28 * (1 - k)) + ')';
      ctx.beginPath(); ctx.ellipse(ox + q.x + p.dx * k, oy + q.y - 3 - 8 * k, r, r * .55, 0, 0, Math.PI * 2); ctx.fill();
    });
  }
  function drawAtmosphere(ox, oy) {
    ctx.save();
    // lamps painted on the map: a warm or cold glow that breathes a little
    ctx.globalCompositeOperation = 'lighter';
    LIGHTS.forEach(function (l, i) {
      var q = toScreen(l[0], l[1]), fl = .85 + Math.sin(night * 3.1 + i * 1.7) * .08 + Math.sin(night * 7.3 + i) * .05;
      var g = ctx.createRadialGradient(ox + q.x, oy + q.y, 2, ox + q.x, oy + q.y, 120 * fl);
      g.addColorStop(0, hexA(l[2], .55 * fl)); g.addColorStop(.25, hexA(l[2], .18 * fl)); g.addColorStop(1, hexA(l[2], 0));
      ctx.fillStyle = g; ctx.fillRect(ox + q.x - 130, oy + q.y - 130, 260, 260);
    });
    // fireflies
    flies.forEach(function (f) {
      var q = toScreen(f.x, f.y), x = ox + q.x, y = oy + q.y - f.z - Math.sin(f.ph * 2) * 6;
      if (x < -20 || y < -20 || x > W + 20 || y > H + 20) return;
      var on = Math.max(0, Math.sin(f.ph * 2.4 + f.hue * 6)) * .9 + .1;
      var g = ctx.createRadialGradient(x, y, 0, x, y, 14);
      g.addColorStop(0, 'rgba(232,247,160,' + (.75 * on) + ')'); g.addColorStop(.3, 'rgba(190,240,120,' + (.25 * on) + ')');
      g.addColorStop(1, 'rgba(190,240,120,0)');
      ctx.fillStyle = g; ctx.fillRect(x - 14, y - 14, 28, 28);
    });
    ctx.globalCompositeOperation = 'source-over';
    // mist drifting across the clearing
    mists.forEach(function (m) {
      var q = toScreen(m.x, m.y), x = ox + q.x, y = oy + q.y;
      var g = ctx.createRadialGradient(x, y, 0, x, y, m.r);
      g.addColorStop(0, 'rgba(190,210,235,' + m.a + ')'); g.addColorStop(1, 'rgba(190,210,235,0)');
      ctx.fillStyle = g; ctx.save(); ctx.translate(x, y); ctx.scale(1, .5); ctx.translate(-x, -y);
      ctx.fillRect(x - m.r, y - m.r, m.r * 2, m.r * 2); ctx.restore();
    });
    // bamboo leaves falling
    leaves.forEach(function (l) {
      ctx.save(); ctx.translate(l.x, l.y); ctx.rotate(l.rot); ctx.scale(l.s, l.s * Math.max(.25, Math.abs(Math.cos(l.sway))));
      ctx.fillStyle = l.c; ctx.globalAlpha = .75; ctx.beginPath(); ctx.ellipse(0, 0, 7, 2.2, 0, 0, Math.PI * 2); ctx.fill(); ctx.restore();
    });
    // moonlight: the edges of the view in shadow
    var v = ctx.createRadialGradient(W / 2, H / 2, Math.min(W, H) * .35, W / 2, H / 2, Math.max(W, H) * .75);
    v.addColorStop(0, 'rgba(6,10,20,0)'); v.addColorStop(1, 'rgba(6,10,20,.55)');
    ctx.fillStyle = v; ctx.fillRect(0, 0, W, H);
    ctx.restore();
  }
  function hexA(hex, a) {
    var n = parseInt(hex.slice(1), 16);
    return 'rgba(' + (n >> 16 & 255) + ',' + (n >> 8 & 255) + ',' + (n & 255) + ',' + a + ')';
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
      var before = hero.phase;
      hero.phase = (hero.phase + sp * dt / (STRIDE * ZOOM) * 8) % 8;
      if ((before < 4 && hero.phase >= 4) || hero.phase < before) puff(hero.x, hero.y, 0.45);   // a foot comes down
      hero.frame = Math.floor(hero.phase);
      report(false);
    } else {
      if (was) report(true);
      hero.frame = STAND[hero.dir];
    }
    if (beast) {
      bt += dt;
      beastStep(dt);
      if (beast.state === 'charge') { prompt.textContent = 'The ' + beast.name + ' charges!'; prompt.classList.add('on'); }
      else if (beast.state === 'alert') { prompt.textContent = 'The ' + beast.name + ' has seen you…'; prompt.classList.add('on'); }
      else prompt.classList.remove('on');
    }
    stepAtmosphere(dt);
  }
  function shadow(x, y, rx, ry, a) { ctx.save(); ctx.fillStyle = 'rgba(0,0,0,' + a + ')'; ctx.beginPath(); ctx.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2); ctx.fill(); ctx.restore(); }
  function drawHero(x, y) {
    var s = 0.5 * ZOOM;
    shadow(x, y, 26 * ZOOM, 9 * ZOOM, .42);
    if (sheet.complete) ctx.drawImage(sheet, hero.frame * CELL, hero.dir * CELL, CELL, CELL, x - FEET_X * s, y - FEET_Y * s, CELL * s, CELL * s);
  }
  function drawBeast(x, y) {
    if (!bimg.complete || !bimg.naturalWidth) return;
    var face = -beast.face;                                       // the paintings face left
    var run = beast.moving > 2, walk = beast.moving > 0;
    var w = beast.w, h = w * bimg.naturalHeight / bimg.naturalWidth;
    var bob = run ? -Math.abs(Math.sin(bt * 14)) * 7 : walk ? -Math.abs(Math.sin(bt * 6)) * 2.5 : Math.sin(bt * 2.2) * 1.5;
    var glow = beast.tier === 'beast_king' ? 'rgba(255,80,70,' : beast.tier === 'elite' ? 'rgba(240,150,80,' : null;
    if (glow) { var gg = ctx.createRadialGradient(x, y - h * .35, 10, x, y - h * .35, w * .75);
      gg.addColorStop(0, glow + '.28)'); gg.addColorStop(1, glow + '0)'); ctx.fillStyle = gg; ctx.fillRect(x - w, y - h * 1.2, w * 2, h * 1.6); }
    shadow(x, y, w * .38, w * .1, .45);
    ctx.save(); ctx.translate(x, y + bob); ctx.scale(face, 1); if (run) ctx.rotate(-0.06);
    ctx.drawImage(bimg, -w / 2, -h * .96, w, h); ctx.restore();
    if (beast.state === 'alert' || beast.state === 'charge') {      // it has seen you
      var age = bt - (beast.alertAt || 0), pop = Math.min(1, age / 0.15), sz = 26 * (0.6 + 0.4 * pop) * (age < 0.25 ? 1.2 - age * .8 : 1);
      var col = beast.tier === 'beast_king' ? '#FF6B5E' : beast.tier === 'elite' ? '#FFA45C' : '#F6E2B0';
      ctx.save(); ctx.font = '800 ' + Math.round(sz) + 'px Cinzel, Georgia, serif'; ctx.textAlign = 'center';
      ctx.lineWidth = 4; ctx.strokeStyle = 'rgba(0,0,0,.7)'; ctx.strokeText('!', x, y - h - 22);
      ctx.fillStyle = col; ctx.fillText('!', x, y - h - 22); ctx.restore();
    }
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
    if (beast) { bp = toScreen(beast.x, beast.y); list.push({y: bp.y, f: function () { drawBeast(ox + bp.x, oy + bp.y); }}); }
    drawPuffs(ox, oy);
    list.sort(function (a, b) { return a.y - b.y; }).forEach(function (o) { o.f(); });
    drawAtmosphere(ox, oy);
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
    if (beast) {                                       // how far it roams (dashed) and sees (gold), around its spot
      var hb = toScreen(beast.home.x, beast.home.y);
      ctx.setLineDash([6, 6]); ctx.strokeStyle = 'rgba(255,255,255,.5)';
      ctx.beginPath(); ctx.ellipse(ox + hb.x, oy + hb.y, WANDER * TW / Math.SQRT2, WANDER * TH / Math.SQRT2, 0, 0, Math.PI * 2); ctx.stroke();
      ctx.setLineDash([]); ctx.strokeStyle = 'rgba(235,203,134,.8)';
      var bq = toScreen(beast.x, beast.y);
      ctx.beginPath(); ctx.ellipse(ox + bq.x, oy + bq.y, NOTICE * TW / Math.SQRT2, NOTICE * TH / Math.SQRT2, 0, 0, Math.PI * 2); ctx.stroke();
    }
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
