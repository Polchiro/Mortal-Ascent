/* The open world's map (town.html, place.html; web/overworld.py, docs/world.md, docs/town.md).

   Every walkable place is walked here: Azure Cloud Town, the Crossroads outside its gate, and the wilds (Moon
   Forest). W A S D / the arrow keys or the on-screen joystick move the cultivator; his sheet row follows the
   direction, the frames advance with the distance walked, standing still holds each row's feet-together frame, or
   plays the look's idle sheet if it has one (`sheet.idle`, its frames looped over `idle.loop` seconds, each faded
   into the next).

   A place is built from pieces: the ground, then each building, tree, rock and log as its own picture, drawn in
   depth order with you, the townsfolk and the beasts: you are hidden by a piece when you stand behind it, and your
   silhouette shows through it. A place can be drawn bigger than you (cfg.scale: the town's streets feel grand); the
   camera shows about VIEW tiles across, stops at the painting's edges, and the night darkens the edges of the view.
   The wilds' pieces (web/env.py) take the place's light (cfg.tone) once per picture, and cast soft shadows; painted
   lamps and glowing mushrooms glow, fireflies drift.

   Walk into a gate or a path (an exit with `walk`) and you go through it: the screen fades, the server checks you
   were there (/world/move) and answers the next place, which is swapped in here without a reload. The page tells
   the server where you are a few times a second (/world/pos); if it disagrees you are put back.

   What is out there is the server's (/world/state, polled): herbs glowing in the grass (E: a round of the gathering
   game in a panel over the map, /world/gather), beasts that wander, notice you and charge (meeting one is the fight,
   /world/engage, then /hunt), and things that glint (E: /world/discover). With the trip's encounters spent, or while
   resting or injured, the beasts keep their distance and nothing glints. While a panel is open nothing moves.
   Walk up to someone and press E to talk: a dialogue offers the pages they send you to. */
(function () {
  'use strict';
  var TW = 128, TH = 64;                       // a tile, in the painting's pixels (the world)
  var SPEED = 150, STRIDE = 96, ZOOM = 1.2;     // world px/s; px per full stride (at 100%); character size
  var SLOW = 0.45, VIEW = 12;                   // Shift: a stroll; tiles across the screen (at K = 1)
  var CALM = matchMedia('(prefers-reduced-motion: reduce)').matches;

  var cfg = JSON.parse(document.getElementById('mapdata').textContent);
  var SH = cfg.sheet, CELL = SH.cell, FEET_X = SH.feet[0], FEET_Y = SH.feet[1], STAND = SH.stand;
  var sheet = new Image(); sheet.src = SH.src;
  var IDLE = SH.idle, idle = null;
  if (IDLE) { idle = new Image(); idle.src = IDLE.src; }

  // this place (load() sets them; a new place swaps them all)
  var PLACE, SIZE, AREA, BLOCKED, REACH, NPCS, PIECES, INSET, EXITS, SPOTS, K = 1, painted, TONE, LIGHTS, ATMOS, TRIGGER;
  var HERBS = [], FINDS = [], BEASTS = [], WORLD = {}, IMGS = {};

  function toScreen(x, y) { return {x: (x - y) * TW / 2, y: (x + y) * TH / 2}; }
  function inside(x, y) {                       // point in AREA (even-odd), as web/town.inside
    var hit = false;
    for (var i = 0, j = AREA.length - 1; i < AREA.length; j = i++) {
      var a = AREA[i], b = AREA[j];
      if ((a[1] > y) !== (b[1] > y) && x < a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])) hit = !hit;
    }
    return hit;
  }
  function walkable(x, y) {                     // the same test as the server's (web/overworld.walkable)
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
  window.addEventListener('resize', resize);
  window.addEventListener('townscale', function (e) { K = e.detail; resize(); });   // the demo's size buttons

  /* a picture in this place's light, made once per file (the wilds' pieces: painted in daylight, placed at night) */
  function toned(src, lit) {
    var key = src + (TONE ? '#' + TONE.join(',') : '') + (lit ? '#lit' : ''), c = IMGS[key];
    if (c) return c;
    c = IMGS[key] = {ready: null};
    var im = new Image();
    im.onload = function () {
      if (!TONE) { c.ready = im; return; }
      var cv2 = document.createElement('canvas'); cv2.width = im.naturalWidth; cv2.height = im.naturalHeight;
      var g = cv2.getContext('2d'); g.drawImage(im, 0, 0);
      var k = lit ? TONE.map(function (v) { return (1 + v) / 2; }) : TONE;   // glowing pieces keep more colour
      g.globalCompositeOperation = 'multiply';
      g.fillStyle = 'rgb(' + k.map(function (v) { return Math.round(v * 255); }).join(',') + ')';
      g.fillRect(0, 0, cv2.width, cv2.height);
      g.globalCompositeOperation = 'destination-in'; g.drawImage(im, 0, 0);
      c.ready = cv2;
    };
    im.src = src;
    return c;
  }
  function plain(src) { var c = IMGS[src]; if (c) return c; var im = new Image(); im.src = src; return (IMGS[src] = {img: im}); }
  function ready(c) { return c.ready || (c.img && c.img.complete && c.img.naturalWidth ? c.img : null); }

  /* the hero */
  var ROW_ANGLE = [90, 135, 180, 225, 270, 315, 0, 45];      // each row's facing, screen degrees (0 right, clockwise)
  function sectorRow(a) { var k = ((Math.round(a / (Math.PI / 4)) % 8) + 8) % 8; return (k + 6) % 8; }
  function angDiff(a, b) { return Math.abs(((a - b) % 360 + 540) % 360 - 180); }
  var hero = {x: 0, y: 0, dir: 4, frame: STAND[4], phase: 0, moving: false, still: 0};
  if (window.__spy) window.__hero = hero;       // the headless-browser checks follow him
  function face(tx, ty) {
    var a = toScreen(hero.x, hero.y), b = toScreen(tx, ty);
    hero.dir = sectorRow(Math.atan2(b.y - a.y, b.x - a.x)); hero.frame = STAND[hero.dir];
  }

  var cam = {x: 0, y: 0}, armed = {}, through = false;
  function load(c, swapped) {
    cfg = c;
    PLACE = c.place; SIZE = c.size; AREA = c.area; BLOCKED = c.blocked || []; REACH = c.reach; NPCS = c.npcs || [];
    PIECES = c.pieces || []; INSET = c.inset || 0; EXITS = c.exits || []; K = c.scale || 1; TONE = c.tone || null;
    LIGHTS = c.lights || []; ATMOS = !!c.atmos; TRIGGER = c.trigger || 0.75;
    SPOTS = NPCS.concat(EXITS.filter(function (e) { return !e.walk; }));
    resize();
    painted = new Image(); painted.src = c.ground;
    PIECES.forEach(function (p) {
      p.pic = p.env ? toned(p.src, p.lit) : plain(p.src);
      p.depth = p.fp ? p.fp[0] + p.fp[2] / 2 + p.fp[1] + p.fp[3] / 2 : p.at[0] + p.at[1];   // a footprint's middle
      p.order = p.z != null ? p.z : p.depth;      // a corner is drawn over the walls running in under its arms
      p.tall = !p.env || p.rect[3] > 56;          // tall enough that you'd lose sight of yourself behind it
    });
    PIECES.sort(function (a, b) { return a.order - b.order; });
    NPCS.forEach(function (n) { if (n.src) n.pic = plain(n.src); n.t = Math.random() * 6; });
    hero.x = c.hero.x; hero.y = c.hero.y; hero.moving = false; hero.still = 0;
    // back from someone's page: in front of them; just through an exit: facing away from it
    var back = null;
    try { back = sessionStorage.getItem('town.from'); sessionStorage.removeItem('town.from'); } catch (e) {}
    if (c.near) back = c.near;
    var stood = false;
    NPCS.forEach(function (n) {                   // step back from them toward the gate until there is ground
      if (n.key !== back || swapped) return;
      for (var t = 0.04; t <= 1; t += 0.02) {
        var x = n.x + (c.hero.x - n.x) * t, y = n.y + (c.hero.y - n.y) * t;
        if (walkable(x, y) && Math.hypot(x - n.x, y - n.y) > 0.9) { hero.x = x; hero.y = y; break; }
      }
      face(n.x, n.y); stood = true;
    });
    armed = {};
    EXITS.forEach(function (e) {
      var d = Math.hypot(hero.x - e.x, hero.y - e.y);
      armed[e.key] = d > 2.6;                      // just came out of it: it waits until you have walked away
      if (!stood && d < 3.2) { face(hero.x + (hero.x - e.x), hero.y + (hero.y - e.y)); stood = true; }
    });
    BEASTS = []; HERBS = []; FINDS = [];
    world(c.world || {});
    var t = document.getElementById('placeTitle'), k = document.getElementById('placeKicker');
    if (t && c.title) t.textContent = c.title;
    if (k && c.kicker) k.textContent = c.kicker;
    if (c.title) document.title = c.title + ' · Mortal Ascent';
    if (swapped && c.url) try { history.replaceState(null, '', c.url); } catch (e) {}
    cv.setAttribute('aria-label', (c.title || 'The map') + '. Walk with W A S D or the arrow keys, or the joystick; '
      + 'press E by someone, a herb or a glint; walk into a gate or a path to go through it.');
    var p0 = toScreen(hero.x, hero.y); cam.x = p0.x; cam.y = p0.y - 50 / K;
    seedAtmosphere();
    near = null; through = false;
  }

  /* input: keyboard and joystick feed one movement vector (screen space, length 0..1) */
  var keys = {}, stickV = {x: 0, y: 0}, stickId = null;
  var KEYMAP = {KeyW: 'u', ArrowUp: 'u', KeyS: 'd', ArrowDown: 'd', KeyA: 'l', ArrowLeft: 'l', KeyD: 'r', ArrowRight: 'r'};
  var stick = document.getElementById('stick'), knob = document.getElementById('knob');
  function resetStick() { stickV = {x: 0, y: 0}; knob.style.transform = ''; }
  function busy() { return dlgOpen || gOpen || fOpen || through || engaging; }
  window.addEventListener('keydown', function (e) {
    if (e.target.tagName === 'INPUT') return;
    if (gOpen) { gatherKey(e); return; }
    if (fOpen) { if (e.key === 'Escape' || e.key === 'Enter') { closeFind(); e.preventDefault(); } return; }
    if (dlgOpen) { if (e.key === 'Escape') { closeTalk(); e.preventDefault(); } return; }
    if (KEYMAP[e.code]) { keys[KEYMAP[e.code]] = true; e.preventDefault(); }
    if (e.key === 'Shift') keys.slow = true;
    if ((e.code === 'KeyE' || e.code === 'Enter' || e.code === 'Space') && near) { act(near); e.preventDefault(); }
    if (e.code === 'KeyG') debug = !debug;
    if (e.code === 'KeyM') location.href = '/world';             // the World Map (Back or M brings you back here)
  });
  window.addEventListener('keyup', function (e) { if (KEYMAP[e.code]) keys[KEYMAP[e.code]] = false; if (e.key === 'Shift') keys.slow = false; });
  window.addEventListener('blur', function () { keys = {}; resetStick(); });
  if (matchMedia('(pointer: coarse)').matches || 'ontouchstart' in window) {
    stick.classList.add('on'); var kk = document.getElementById('keys'); if (kk) kk.style.display = 'none';
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
    if (busy()) return {x: 0, y: 0};
    var x = (keys.r ? 1 : 0) - (keys.l ? 1 : 0), y = (keys.d ? 1 : 0) - (keys.u ? 1 : 0), m = Math.hypot(x, y);
    if (m) { var s = keys.slow ? SLOW : 1; return {x: x / m * s, y: y / m * s}; }
    return stickV;
  }

  /* talking to the server */
  function post(url, data) {
    return fetch(url, {method: 'POST', body: new URLSearchParams(data), credentials: 'same-origin',
                       headers: {'Accept': 'application/json'}}).then(function (r) { return r.json(); });
  }
  var sentAt = 0;
  function report(force) {
    var now = performance.now();
    if (!force && now - sentAt < 300) return;
    sentAt = now;
    var at = PLACE;
    post('/world/pos', {place: PLACE, x: hero.x.toFixed(3), y: hero.y.toFixed(3)}).then(function (v) {
      if (v.gone) { location.replace('/'); return; }
      if (v.url && !through) { location.replace(v.url); return; }               // the server has you elsewhere
      if (at === PLACE && v.x != null && Math.hypot(v.x - hero.x, v.y - hero.y) > 1.2) { hero.x = v.x; hero.y = v.y; }
    }).catch(function () {});
  }
  function poll() {
    if (busy()) return;
    var at = PLACE;
    post('/world/state', {place: PLACE}).then(function (v) { if (!v.gone && at === PLACE) world(v); }).catch(function () {});
  }
  setInterval(poll, 10000);

  /* through a gate or down a path: the next place, without a reload */
  var fade = document.getElementById('fade');
  function goThrough(e) {
    if (through) return;
    through = true; keys = {}; resetStick(); prompt.classList.remove('on');
    fade.classList.add('on');
    var t0 = performance.now();
    post('/world/move', {place: PLACE, key: e.key, x: hero.x.toFixed(3), y: hero.y.toFixed(3)}).then(function (v) {
      setTimeout(function () {
        if (v.to && v.data) {
          load(v.data, true);
          if (v.notice) say(v.notice, true);
        } else {
          through = false;
          if (v.x != null) { hero.x = v.x; hero.y = v.y; }
          armed[e.key] = false;
        }
        fade.classList.remove('on');
      }, Math.max(0, 320 - (performance.now() - t0)));
    }).catch(function () { through = false; fade.classList.remove('on'); armed[e.key] = false; });
  }

  /* what the server says is out there */
  var tripEl = document.getElementById('trip');
  function world(v) {
    WORLD = v;
    HERBS = (v.herbs || []).map(function (h) {
      var old = HERBS.find && HERBS.find(function (o) { return o.id === h.id; });
      h.t = old ? old.t : Math.random() * 6; h.pic = plain(h.picture); return h;
    });
    FINDS = (v.finds || []).map(function (f) { f.t = Math.random() * 6; return f; });
    var keep = {};
    BEASTS.forEach(function (b) { keep[b.id] = b; });
    BEASTS = (v.beasts || []).map(function (b) {
      var o = keep[b.id];
      if (o) return o;                                              // the one already out there: as it is
      b.pic = plain(b.src); b.w = b.tier === 'beast_king' ? 195 : b.tier === 'elite' ? 155 : 125;
      b.home = {x: b.x, y: b.y}; b.state = 'idle'; b.timer = 0.8 + Math.random() * 1.5; b.face = 1; b.moving = 0; b.t = 0;
      return b;
    });
    var lines = [];
    if (v.trip) {
      lines.push(v.trip.spent ? 'Trip: all ' + v.trip.steps + ' encounters met. Walk back to town to bank your finds.'
        : 'Trip: encounter ' + v.trip.step + ' of ' + v.trip.steps + ' · HP ' + v.trip.hp + ' / ' + v.trip.max_hp
          + ' · walk back to town to bank what you carry');
    } else if (v.quiet) lines.push(v.quiet);
    if (tripEl) { tripEl.textContent = lines.join(' '); tripEl.hidden = !lines.length; }
  }
  var sayEl = document.getElementById('say'), sayT = null;
  function say(text, html) {
    if (!sayEl) return;
    if (html) sayEl.innerHTML = text; else sayEl.textContent = text;
    sayEl.hidden = false; clearTimeout(sayT); sayT = setTimeout(function () { sayEl.hidden = true; }, 7000);
  }

  /* the beasts: each wanders about the spot the server put it on, notices you (a "!"), charges, and the fight
     starts when it reaches you (or when you walk up and press E). How far it roams and sees comes from the server
     (hunt_map.WANDER / NOTICE), which only starts the fight where such a charge could have met you. With nothing
     left to meet (wary), they keep away from you instead. */
  var RUN = {normal: 4.4, elite: 4.8, beast_king: 5.2}, STROLL = {normal: 0.9, elite: 1.0, beast_king: 1.1};
  var engaging = false, bt = 0;
  function beastStep(b, dt) {
    var wd = (WORLD.wander || {})[b.tier], nt = (WORLD.notice || {})[b.tier];
    var WANDER = wd != null ? wd : 1.6, NOTICE = nt != null ? nt : 3.2;
    var d = Math.hypot(hero.x - b.x, hero.y - b.y);
    var leash = Math.hypot(hero.x - b.home.x, hero.y - b.home.y) <= WANDER + NOTICE;
    b.timer -= dt; b.moving = 0; b.t += dt;
    if (WORLD.wary) {                                               // nothing to meet: it shies away from you
      if (d < 2.6) {
        var ax = b.x - hero.x, ay = b.y - hero.y, m = Math.hypot(ax, ay) || 1;
        moveBeast(b, b.x + ax / m, b.y + ay / m, STROLL[b.tier] * 1.8, dt);
        b.state = 'idle'; b.timer = 1;
        return;
      }
      if (b.state === 'alert' || b.state === 'charge') { b.state = 'return'; b.timer = 8; }
    } else if ((b.state === 'idle' || b.state === 'wander') && d < NOTICE && leash) {
      b.state = 'alert'; b.timer = b.tier === 'beast_king' ? 0.4 : 0.55; b.alertAt = bt;
    }
    if (b.state === 'idle' && b.timer <= 0) {
      for (var i = 0; i < 8; i++) {                                 // somewhere to sniff about, near its spot
        var a = Math.random() * Math.PI * 2, r = Math.random() * WANDER;
        var tx = b.home.x + Math.cos(a) * r, ty = b.home.y + Math.sin(a) * r;
        if (walkable(tx, ty)) { b.tx = tx; b.ty = ty; b.state = 'wander'; b.timer = 6; break; }
      }
      if (b.state === 'idle') b.timer = 1;
    }
    if (b.state === 'wander' || b.state === 'return') {
      var gx = b.state === 'return' ? b.home.x : b.tx, gy = b.state === 'return' ? b.home.y : b.ty;
      if (!moveBeast(b, gx, gy, STROLL[b.tier] * (b.state === 'return' ? 1.4 : 1), dt) || b.timer <= 0) {
        b.state = 'idle'; b.timer = 1.2 + Math.random() * 2.5;
      }
    }
    if (b.state === 'alert') { b.face = hero.x - hero.y > b.x - b.y ? 1 : -1; if (b.timer <= 0) { b.state = 'charge'; b.timer = 4; } }
    if (b.state === 'charge') {
      if (!leash || b.timer <= 0) { b.state = 'return'; b.timer = 8; return; }     // you got away
      moveBeast(b, hero.x, hero.y, RUN[b.tier], dt);
      if (Math.random() < 0.5) puff(b.x, b.y, 0.6);
      if (Math.hypot(hero.x - b.x, hero.y - b.y) < (WORLD.beastReach || 1.6) * 0.8) engage(b);
    }
  }
  function moveBeast(b, gx, gy, speed, dt) {                       // false once it has arrived (or is stuck)
    var dx = gx - b.x, dy = gy - b.y, m = Math.hypot(dx, dy);
    if (m < 0.08) return false;
    var step = Math.min(m, speed * dt), nx = b.x + dx / m * step, ny = b.y + dy / m * step, ok = false;
    if (walkable(nx, ny)) { b.x = nx; b.y = ny; ok = true; }
    else if (walkable(nx, b.y)) { b.x = nx; ok = true; }
    else if (walkable(b.x, ny)) { b.y = ny; ok = true; }
    if (ok) { b.moving = speed; var s = (dx - dy); if (Math.abs(s) > 0.02) b.face = s > 0 ? 1 : -1; }
    return ok;
  }
  function engage(b) {
    if (engaging) return;
    engaging = true; keys = {}; resetStick();
    prompt.textContent = 'The ' + b.name + ' turns on you…'; prompt.classList.add('on');
    post('/world/engage', {place: PLACE, id: b.id, x: hero.x.toFixed(3), y: hero.y.toFixed(3)}).then(function (v) {
      if (v.fight) { location.href = v.fight; return; }
      engaging = false; prompt.classList.remove('on');
      b.state = 'return'; b.timer = 8;
      if (v.error) say(v.error, true);
      if (v.world) world(v.world);
    }).catch(function () { engaging = false; prompt.classList.remove('on'); });
  }

  /* what you can do where you stand: talk, gather, look, fight */
  var near = null, prompt = document.getElementById('prompt');
  prompt.addEventListener('click', function () { if (near) act(near); });
  function nearest() {
    var best = null, bd = 99;
    function consider(o, d, lim) { if (d < lim && d < bd) { bd = d; best = o; } }
    SPOTS.forEach(function (n) { consider({kind: n.exit ? 'exit' : 'npc', o: n}, Math.hypot(hero.x - n.x, hero.y - n.y), REACH); });
    HERBS.forEach(function (h) { consider({kind: 'herb', o: h}, Math.hypot(hero.x - h.x, hero.y - h.y), (WORLD.reach || 1.6) * 0.9); });
    FINDS.forEach(function (f) { consider({kind: 'find', o: f}, Math.hypot(hero.x - f.x, hero.y - f.y), (WORLD.reach || 1.6) * 0.9); });
    if (!WORLD.wary) BEASTS.forEach(function (b) { consider({kind: 'beast', o: b}, Math.hypot(hero.x - b.x, hero.y - b.y), 1.35); });
    return best;
  }
  function promptText(n) {
    var o = n.o;
    if (n.kind === 'herb') return 'Gather the ' + o.name;
    if (n.kind === 'find') return o.secret ? 'Something stirs here: look' : 'Something glints: look';
    if (n.kind === 'beast') return 'Fight the ' + (o.tier === 'normal' ? '' : o.tierName + ' ') + o.name;
    if (o.kind === 'road') return (o.state === 'open' ? 'The road to ' : '') + o.name;
    return o.exit ? o.title : (o.prop ? 'Read the ' : 'Talk to ') + o.name;
  }
  function act(n) {
    if (n.kind === 'herb') gather(n.o);
    else if (n.kind === 'find') discover(n.o);
    else if (n.kind === 'beast') engage(n.o);
    else openTalk(n.o);
  }

  /* talking */
  var dlgOpen = false, dlg = document.getElementById('dlg');
  function openTalk(n) {
    dlgOpen = true; keys = {}; resetStick(); prompt.classList.remove('on');
    document.getElementById('dlgName').textContent = n.name;
    document.getElementById('dlgTitle').textContent = n.title.toUpperCase();
    document.getElementById('dlgLine').textContent = n.line;
    var go = document.getElementById('dlgGo'); go.textContent = '';
    n.go.forEach(function (g, i) {
      var cls = 'hbtn small' + (i ? ' ghost' : '');
      if (g[2] === 'post') {                       // setting out: a form, so the server checks and starts it
        var f = document.createElement('form'); f.method = 'post'; f.action = g[1];
        var sb = document.createElement('button'); sb.type = 'submit'; sb.className = cls; sb.textContent = g[0];
        f.appendChild(sb); go.appendChild(f); return;
      }
      var a = document.createElement('a'); a.className = cls; a.href = g[1]; a.textContent = g[0];
      if (!n.exit) a.addEventListener('click', function () { try { sessionStorage.setItem('town.from', n.key); } catch (e) {} });
      go.appendChild(a);
    });
    var bye = document.createElement('button'); bye.type = 'button'; bye.className = 'hbtn ghost small';
    bye.textContent = n.exit ? (n.go.length ? 'Stay' : 'Turn back') : n.go.length ? 'Leave' : 'Farewell';
    bye.addEventListener('click', closeTalk); go.appendChild(bye);
    dlg.hidden = false; (go.querySelector('a, form button') || bye).focus();
  }
  function closeTalk() { dlgOpen = false; dlg.hidden = true; cv.focus(); }

  /* gathering: kneel at a herb and play its round in the panel (web/gather_play.py decides everything) */
  var gOpen = false, gp = document.getElementById('gpanel'), gBody = document.getElementById('gBody'), gView = null, gTimer = null;
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function htmlLine(tag, cls, html) { var e = el(tag, cls); e.innerHTML = html; return e; }   // the server's own lines
  function gather(h) {
    if (gOpen) return;
    gOpen = true; keys = {}; resetStick(); prompt.classList.remove('on');
    face(h.x, h.y);
    gBody.textContent = ''; gBody.appendChild(el('p', 'pline', 'You kneel in the grass…'));
    gp.hidden = false;
    post('/world/gather', {place: PLACE, id: h.id, x: hero.x.toFixed(3), y: hero.y.toFixed(3)}).then(function (g) {
      if (g.error || !g.mode) { closeGather(); say(g.error || 'The herb is gone.', true); poll(); return; }
      showRound(g);
    }).catch(closeGather);
  }
  function showRound(g) {
    gView = g; clearInterval(gTimer);
    document.getElementById('gKicker').textContent = (g.place || 'the wilds').toUpperCase();
    gBody.textContent = '';
    if (g.mode === 'round') (g.prompt || []).forEach(function (l, i, all) { gBody.appendChild(htmlLine('p', 'pline' + (i === all.length - 1 && g.target ? ' desc' : ''), l)); });
    if (g.target) {
      var t = g.target, tb = el('div', 'target'); tb.style.borderColor = t.color;
      if (t.picture) { var ti = el('img'); ti.src = t.picture; ti.alt = ''; ti.width = 56; ti.height = 56; tb.appendChild(ti); }
      var ts = el('span'); ts.appendChild(el('span', 'sub', 'You are looking for'));
      var tn = el('b', null, (t.age ? t.age + '-year ' : '') + t.name); tn.style.color = t.color; ts.appendChild(tn);
      ts.appendChild(el('span', 'sub', t.grade + ' · ' + t.rarity + ' · ' + t.emoji + ' ' + t.type + ' herb'));
      tb.appendChild(ts); gBody.appendChild(tb);
      var grid = el('div', 'plants' + (g.wide ? ' wide' : ''));
      (g.choices || []).forEach(function (c) {
        var b = el('button', 'plantcard ' + (c.state || '')); b.type = 'button'; b.disabled = g.mode !== 'round';
        b.appendChild(el('span', 'no', String(c.no)));
        var im = el('img'); im.src = c.picture; im.alt = ''; im.width = 240; im.height = 170; b.appendChild(im);
        if (c.name) b.appendChild(el('b', null, c.name));
        b.appendChild(el('span', 'look', c.look));
        b.addEventListener('click', function () { pick(c.key); });
        grid.appendChild(b);
      });
      gBody.appendChild(grid);
    }
    if (g.spirit) {
      var art = el('img', 'stageart'); art.src = g.spirit.art; art.alt = ''; art.width = 150; art.height = 150; gBody.appendChild(art);
      if (g.spirit.signs && g.spirit.signs.length) {
        var row = el('div', 'choices');
        g.spirit.signs.forEach(function (s) {
          var b = el('button', 'btn btn-gold sign', s.emoji); b.type = 'button'; b.setAttribute('aria-label', s.key);
          b.addEventListener('click', function () { pick(s.key); }); row.appendChild(b);
        });
        gBody.appendChild(row);
      }
    }
    if (g.mode === 'round') {
      var tm = el('div', 'timer'), bar = el('div', 'tbar'), fill = el('div'), left = el('span', null, g.left + 's');
      bar.appendChild(fill); tm.appendChild(bar); tm.appendChild(left); gBody.appendChild(tm);
      var away = el('button', 'link', 'Walk away (this herb counts as missed)'); away.type = 'button';
      away.addEventListener('click', walkAway); gBody.appendChild(away);
      var end = Date.now() + g.left * 1000;
      gTimer = setInterval(function () {
        var l = Math.max(0, (end - Date.now()) / 1000), f = l / g.seconds;
        fill.style.width = (f * 100) + '%'; left.textContent = l.toFixed(1) + 's';
        fill.style.background = f > 0.5 ? '#6FD9B0' : f > 0.25 ? '#E8C27A' : '#E05A4F';
        if (l <= 0) { clearInterval(gTimer); setTimeout(walkAway, 900); }
      }, 100);
      var first = gBody.querySelector('.plantcard, .sign'); if (first) first.focus();
    } else {
      (g.result || []).forEach(function (l) { gBody.appendChild(htmlLine('p', 'pline big2', l)); });
      var row2 = el('div', 'choices'), ok = el('button', 'btn btn-jade', 'Walk on'); ok.type = 'button';
      ok.addEventListener('click', closeGather); row2.appendChild(ok); gBody.appendChild(row2); ok.focus();
    }
  }
  function pick(key) {
    if (!gView || gView.mode !== 'round') return;
    clearInterval(gTimer);
    var turn = gView.turn; gView = null;
    post('/world/gather/pick', {key: key, turn: turn}).then(after).catch(closeGather);
  }
  function walkAway() {
    if (!gView || gView.mode !== 'round') { closeGather(); return; }
    clearInterval(gTimer);
    var turn = gView.turn; gView = null;
    post('/world/gather/away', {turn: turn}).then(after).catch(closeGather);
  }
  function after(g) { if (g.world) world(g.world); if (g.mode) showRound(g); else closeGather(); }
  function closeGather() { clearInterval(gTimer); gOpen = false; gView = null; gp.hidden = true; cv.focus(); }
  function gatherKey(e) {
    if (e.key === 'Escape') { walkAway(); e.preventDefault(); return; }
    var n = parseInt(e.key, 10);
    if (gView && gView.mode === 'round' && n >= 1) {
      var bs = gBody.querySelectorAll('.plantcard, .sign'); if (bs[n - 1]) { bs[n - 1].click(); e.preventDefault(); }
    }
  }

  /* something glints: look (one of /explore's finds; the server decides) */
  var fOpen = false, fp = document.getElementById('fpanel'), fBody = document.getElementById('fBody');
  document.getElementById('fClose').addEventListener('click', closeFind);
  function discover(f) {
    if (fOpen) return;
    fOpen = true; keys = {}; resetStick(); prompt.classList.remove('on'); face(f.x, f.y);
    document.getElementById('fName').textContent = f.secret ? 'A hidden place' : 'Something glints';
    fBody.textContent = ''; fBody.appendChild(el('p', 'tline', 'You look closer…'));
    fp.hidden = false;
    post('/world/discover', {place: PLACE, id: f.id, x: hero.x.toFixed(3), y: hero.y.toFixed(3)}).then(function (v) {
      if (v.world) world(v.world);
      fBody.textContent = '';
      if (v.error) { closeFind(); say(v.error, true); return; }
      (v.lines || []).forEach(function (l) { fBody.appendChild(htmlLine('p', 'tline', l)); });
      document.getElementById('fClose').focus();
    }).catch(closeFind);
  }
  function closeFind() { fOpen = false; fp.hidden = true; cv.focus(); }

  /* the loop: fixed 60 Hz steps, drawn every frame */
  var last = 0, acc = 0, STEP = 1 / 60, debug = false, hiddenHero = false, glowT = 0;
  function update(dt) {
    NPCS.forEach(function (n) { n.t += dt; }); glowT += dt; bt += dt;
    HERBS.forEach(function (h) { h.t += dt; }); FINDS.forEach(function (f) { f.t += dt; });
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
      var before = hero.phase;
      hero.phase = (hero.phase + sp * dt / (STRIDE * ZOOM / K) * 8) % 8;
      if (ATMOS && ((before < 4 && hero.phase >= 4) || hero.phase < before)) puff(hero.x, hero.y, 0.45);
      hero.frame = Math.floor(hero.phase);
      hero.still = 0;
      report(false);
    } else {
      if (was) report(true);
      hero.frame = STAND[hero.dir]; hero.still = (hero.still || 0) + dt;
    }
    if (!busy()) {
      BEASTS.forEach(function (b) { beastStep(b, dt); });
      EXITS.forEach(function (e) {                                // walk into a gate or a path: through it
        if (!e.walk) return;
        var d = Math.hypot(hero.x - e.x, hero.y - e.y);
        if (d > 2.6) armed[e.key] = true;
        if (armed[e.key] && d < TRIGGER) goThrough(e);
      });
    }
    stepAtmosphere(dt);
    var n = busy() ? null : nearest(), msg = null;
    BEASTS.forEach(function (b) {
      if (b.state === 'charge') msg = 'The ' + b.name + ' charges!';
      else if (b.state === 'alert' && !msg) msg = 'The ' + b.name + ' has seen you…';
    });
    if (engaging) return;
    if (msg && !busy()) { if (prompt.textContent !== msg) prompt.textContent = msg; prompt.classList.add('on'); near = null; return; }
    var same = n && near && n.kind === near.kind && n.o === near.o;
    if (!same) {
      near = n;
      if (near) {
        prompt.textContent = promptText(near) + ' ';
        var k = document.createElement('b'); k.textContent = 'E'; prompt.appendChild(k);
      }
    }
    prompt.classList.toggle('on', !!near && !busy());
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
  function isNear(o) { return near && near.o === o; }
  function drawNpc(n, x, y) {
    var close = isNear(n), bob = Math.sin(n.t * 2) * 1.5, h = n.h, img = n.pic && ready(n.pic);
    if (img) {
      var w = h * img.naturalWidth / img.naturalHeight, f = (hero.x - hero.y < n.x - n.y ? -1 : 1) * (n.flip ? -1 : 1);
      shadow(x, y, 24, 8, .42);
      ctx.save(); ctx.translate(x, y); ctx.scale(f, 1); ctx.drawImage(img, -w / 2, -h, w, h); ctx.restore();
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

  /* a herb: its picture small in the grass, glowing in its grade's colour (brighter, with motes, the rarer it is) */
  function drawHerb(h, x, y) {
    var close = isNear(h), b = CALM ? 0.5 : (Math.sin(h.t * 2.4) + 1) / 2, rare = h.rank, img = ready(h.pic);
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    var R = 34 + rare * 10, g = ctx.createRadialGradient(x, y - 10, 2, x, y - 10, R * (1 + 0.15 * b));
    g.addColorStop(0, hexA(h.color, 0.35 + 0.1 * b + (close ? 0.15 : 0))); g.addColorStop(1, hexA(h.color, 0));
    ctx.fillStyle = g; ctx.fillRect(x - R * 1.3, y - 10 - R * 1.3, R * 2.6, R * 2.6);
    if (rare >= 1 && !CALM) for (var i = 0; i < 2 + rare * 2; i++) {             // motes rising from a rarer herb
      var t = (h.t * 0.4 + i / (2 + rare * 2)) % 1, a = i * 2.39, mx = x + Math.cos(a) * 14, my = y - 8 - t * (40 + rare * 12);
      ctx.fillStyle = hexA(h.color, 0.8 * Math.sin(Math.PI * t)); ctx.beginPath(); ctx.arc(mx, my, 1.8, 0, Math.PI * 2); ctx.fill();
    }
    ctx.restore();
    shadow(x, y, 13, 4, .3);
    if (img) { var s = 38 + (close ? 4 : 0); ctx.drawImage(img, x - s / 2, y - s + 4 + Math.sin(h.t * 1.3) * 1, s, s); }
  }
  /* a find: a glint of light that turns and breathes (a secret spot: violet) */
  function drawFind(f, x, y) {
    var close = isNear(f), b = CALM ? 0.5 : (Math.sin(f.t * 3) + 1) / 2, col = f.secret ? '#C9A2FF' : '#FFE3A0';
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    var g = ctx.createRadialGradient(x, y - 14, 1, x, y - 14, 40);
    g.addColorStop(0, hexA(col, 0.45 + 0.3 * b + (close ? .2 : 0))); g.addColorStop(1, hexA(col, 0));
    ctx.fillStyle = g; ctx.fillRect(x - 44, y - 58, 88, 88);
    ctx.translate(x, y - 14); ctx.rotate(CALM ? 0 : f.t * 0.6);
    ctx.fillStyle = hexA(col, 0.7 + 0.3 * b);
    for (var i = 0; i < 4; i++) { ctx.rotate(Math.PI / 2); ctx.beginPath(); ctx.moveTo(0, -3); ctx.lineTo(2, 0); ctx.lineTo(0, -10 - 6 * b); ctx.lineTo(-2, 0); ctx.closePath(); ctx.fill(); }
    ctx.restore();
  }
  function drawBeast(b, x, y) {
    var img = ready(b.pic); if (!img) return;
    var f = -b.face;                                              // the paintings face left
    var run = b.moving > 2, walk = b.moving > 0;
    var w = b.w, h = w * img.naturalHeight / img.naturalWidth;
    var bob = run ? -Math.abs(Math.sin(b.t * 14)) * 7 : walk ? -Math.abs(Math.sin(b.t * 6)) * 2.5 : Math.sin(b.t * 2.2) * 1.5;
    var glow = b.tier === 'beast_king' ? 'rgba(255,80,70,' : b.tier === 'elite' ? 'rgba(240,150,80,' : null;
    if (glow) { var gg = ctx.createRadialGradient(x, y - h * .35, 10, x, y - h * .35, w * .75);
      gg.addColorStop(0, glow + '.28)'); gg.addColorStop(1, glow + '0)'); ctx.fillStyle = gg; ctx.fillRect(x - w, y - h * 1.2, w * 2, h * 1.6); }
    shadow(x, y, w * .38, w * .1, .45);
    ctx.save(); if (WORLD.wary) ctx.globalAlpha = 0.85;
    ctx.translate(x, y + bob); ctx.scale(f, 1); if (run) ctx.rotate(-0.06);
    ctx.drawImage(img, -w / 2, -h * .96, w, h); ctx.restore();
    if (b.state === 'alert' || b.state === 'charge') {            // it has seen you
      var age = bt - (b.alertAt || 0), pop = Math.min(1, age / 0.15), sz = 26 * (0.6 + 0.4 * pop) * (age < 0.25 ? 1.2 - age * .8 : 1);
      var col = b.tier === 'beast_king' ? '#FF6B5E' : b.tier === 'elite' ? '#FFA45C' : '#F6E2B0';
      ctx.save(); ctx.font = '800 ' + Math.round(sz) + 'px Cinzel, Georgia, serif'; ctx.textAlign = 'center';
      ctx.lineWidth = 4; ctx.strokeStyle = 'rgba(0,0,0,.7)'; ctx.strokeText('!', x, y - h - 22);
      ctx.fillStyle = col; ctx.fillText('!', x, y - h - 22); ctx.restore();
    }
    ctx.save(); ctx.font = '700 12px Cinzel, Georgia, serif'; ctx.textAlign = 'center';
    var lab = (b.tier === 'normal' ? '' : b.tierName + ' · ') + b.name;
    ctx.fillStyle = 'rgba(0,0,0,.6)'; ctx.fillText(lab, x + 1, y - h - 5);
    ctx.fillStyle = b.tier === 'normal' ? '#EBCB86' : b.tier === 'elite' ? '#FFC69A' : '#FFB0A8'; ctx.fillText(lab, x, y - h - 6);
    ctx.restore();
  }

  /* a way out: a gate's doorway (e.glow: the foot of the door, outside) lit with pale blue Qi that breathes, motes
     rising from it, drawn over the gate; a road's end (drawRoad); a path out of the wilds (a ring on the ground) */
  function drawExit(e) {
    if (e.kind === 'road') { drawRoad(e); return; }
    var p = toScreen(e.glow[0], e.glow[1]), close = isNear(e), b = CALM ? 0.5 : (Math.sin(glowT * 2.2) + 1) / 2;
    if (e.kind === 'path') {
      ctx.save(); ctx.globalCompositeOperation = 'lighter';
      var rg = ctx.createRadialGradient(p.x, p.y, 3, p.x, p.y, 70);
      rg.addColorStop(0, 'rgba(150,210,255,' + (0.22 + 0.1 * b) + ')'); rg.addColorStop(1, 'rgba(110,180,255,0)');
      ctx.fillStyle = rg; ctx.beginPath(); ctx.ellipse(p.x, p.y, 72, 36, 0, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = 'rgba(190,230,255,' + (0.3 + 0.25 * b) + ')'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.ellipse(p.x, p.y, 52, 26, 0, 0, Math.PI * 2); ctx.stroke();
      ctx.restore();
      roadLabel(e, {x: p.x, y: p.y + 40}, close);
      return;
    }
    var k = (close ? 1.25 : 1) * (0.85 + 0.15 * b);
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    var pool = ctx.createRadialGradient(p.x, p.y, 4, p.x, p.y, 110);          // a pool of light on the road
    pool.addColorStop(0, 'rgba(140,200,255,' + 0.30 * k + ')'); pool.addColorStop(1, 'rgba(110,180,255,0)');
    ctx.fillStyle = pool; ctx.beginPath(); ctx.ellipse(p.x, p.y, 110, 46, 0, 0, Math.PI * 2); ctx.fill();
    ctx.save(); ctx.translate(p.x, p.y - 70); ctx.scale(0.62, 1);                 // light spilling from the doorway
    var door = ctx.createRadialGradient(0, 0, 6, 0, 0, 110);
    door.addColorStop(0, 'rgba(170,220,255,' + 0.34 * k + ')'); door.addColorStop(0.55, 'rgba(120,185,255,' + 0.12 * k + ')');
    door.addColorStop(1, 'rgba(110,180,255,0)');
    ctx.fillStyle = door; ctx.beginPath(); ctx.arc(0, 0, 110, 0, Math.PI * 2); ctx.fill(); ctx.restore();
    if (!CALM) for (var i = 0; i < 9; i++) {                                     // motes drifting up and out
      var t = (glowT * 0.3 + i / 9) % 1, a = i * 2.39, mx = p.x + Math.cos(a) * 46 + Math.sin(glowT + i) * 6, my = p.y - 10 - t * 150;
      ctx.fillStyle = 'rgba(205,238,255,' + (0.75 * Math.sin(Math.PI * t)) + ')'; ctx.beginPath(); ctx.arc(mx, my, 2.1, 0, Math.PI * 2); ctx.fill();
    }
    ctx.restore();
  }
  /* a road's end: open, a ring of warm light on the road; resting, a bank of grey mist; sealed, a disc of golden runes
     standing across it. Its name floats above. */
  function drawRoad(e) {
    var p = toScreen(e.glow[0], e.glow[1]), close = isNear(e), b = CALM ? 0.5 : (Math.sin(glowT * 2.2 + e.x) + 1) / 2;
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    if (e.state === 'open' || e.walk) {
      var g = ctx.createRadialGradient(p.x, p.y, 4, p.x, p.y, 95);
      g.addColorStop(0, 'rgba(255,214,150,' + (0.26 + 0.1 * b + (close ? .12 : 0)) + ')'); g.addColorStop(1, 'rgba(255,190,110,0)');
      ctx.fillStyle = g; ctx.beginPath(); ctx.ellipse(p.x, p.y, 95, 44, 0, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = 'rgba(255,226,170,' + (0.3 + 0.25 * b) + ')'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.ellipse(p.x, p.y, 66, 31, 0, 0, Math.PI * 2); ctx.stroke();
    } else if (e.state === 'waiting') {
      ctx.globalCompositeOperation = 'source-over';
      for (var i = 0; i < 6; i++) {
        var a = glowT * 0.25 + i * 1.05, mx = p.x + Math.cos(a) * 40, my = p.y - 30 + Math.sin(a * 1.3) * 12;
        var m = ctx.createRadialGradient(mx, my, 4, mx, my, 70);
        m.addColorStop(0, 'rgba(190,200,215,.22)'); m.addColorStop(1, 'rgba(190,200,215,0)');
        ctx.fillStyle = m; ctx.fillRect(mx - 70, my - 70, 140, 140);
      }
    } else {                                                        // sealed
      ctx.translate(p.x, p.y - 62);
      var halo = ctx.createRadialGradient(0, 0, 8, 0, 0, 80);
      halo.addColorStop(0, 'rgba(255,200,110,' + (0.28 + 0.12 * b) + ')'); halo.addColorStop(1, 'rgba(255,170,80,0)');
      ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(0, 0, 80, 0, Math.PI * 2); ctx.fill();
      ctx.scale(0.55, 1); ctx.rotate(CALM ? 0 : glowT * 0.35);
      ctx.strokeStyle = 'rgba(255,214,140,' + (0.55 + 0.3 * b) + ')'; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(0, 0, 52, 0, Math.PI * 2); ctx.stroke();
      ctx.lineWidth = 1.6; ctx.beginPath(); ctx.arc(0, 0, 40, 0, Math.PI * 2); ctx.stroke();
      for (var r = 0; r < 8; r++) {                                 // rune strokes round the ring
        ctx.rotate(Math.PI / 4); ctx.beginPath(); ctx.moveTo(0, -48); ctx.lineTo(0, -42); ctx.moveTo(-4, -46); ctx.lineTo(4, -44); ctx.stroke();
      }
      ctx.beginPath(); for (var k = 0; k < 6; k++) { var q = k * Math.PI / 3; ctx[k ? 'lineTo' : 'moveTo'](Math.cos(q) * 26, Math.sin(q) * 26); }
      ctx.closePath(); ctx.stroke();
    }
    ctx.restore();
    roadLabel(e, p, close);
  }
  function roadLabel(e, p, close) {
    var y = p.y - (e.state === 'locked' ? 148 : 70);
    ctx.save(); ctx.textAlign = 'center';
    ctx.font = '700 17px Cinzel, Georgia, serif';
    ctx.fillStyle = 'rgba(0,0,0,.7)'; ctx.fillText(e.name, p.x + 1, y + 1);
    ctx.fillStyle = e.state === 'locked' ? '#C9B79A' : close ? '#F6E2B0' : '#EBCB86'; ctx.fillText(e.name, p.x, y);
    ctx.font = '600 12px Inter, sans-serif'; ctx.fillStyle = 'rgba(0,0,0,.7)'; ctx.fillText(e.title, p.x + 1, y + 18);
    ctx.fillStyle = e.state === 'locked' ? '#E8968C' : e.state === 'waiting' ? '#EBCB86' : 'rgba(230,223,207,.85)';
    ctx.fillText(e.title, p.x, y + 17);
    ctx.restore();
  }

  /* the wilds at night: painted lamps and glowing mushrooms, fireflies, dust where feet land, mist */
  var puffs = [], flies = [], mists = [];
  function rnd(seed) { return function () { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; }; }
  function seedAtmosphere() {
    puffs = []; flies = []; mists = [];
    if (!ATMOS) return;
    var r = rnd(42), lo = 2, hi = SIZE - 2;
    for (var i = 0; i < (CALM ? 14 : 38); i++) {
      var x, y, k = 0;
      do { x = lo + r() * (hi - lo); y = lo + r() * (hi - lo); } while (!walkable(x, y) && ++k < 20);
      flies.push({x: x, y: y, z: 18 + r() * 50, ph: r() * 6.3, sp: .25 + r() * .35, hue: r()});
    }
    for (var j = 0; j < 7; j++) mists.push({x: lo + r() * (hi - lo), y: lo + r() * (hi - lo), r: 260 + r() * 320,
      vx: (r() - .5) * .18, vy: (r() - .5) * .12, a: .05 + r() * .05});
  }
  function puff(x, y, size) {
    if (CALM || puffs.length > 60) return;
    for (var i = 0; i < 3; i++) puffs.push({x: x + (Math.random() - .5) * .25, y: y + (Math.random() - .5) * .25,
      t: 0, life: .45 + Math.random() * .3, s: size * (0.7 + Math.random() * .6), dx: (Math.random() - .5) * 16});
  }
  function stepAtmosphere(dt) {
    for (var i = puffs.length - 1; i >= 0; i--) { puffs[i].t += dt; if (puffs[i].t > puffs[i].life) puffs.splice(i, 1); }
    flies.forEach(function (f) { f.ph += dt * f.sp; f.x += Math.cos(f.ph * 1.3) * dt * .25; f.y += Math.sin(f.ph) * dt * .25; });
    mists.forEach(function (m) {
      m.x += m.vx * dt; m.y += m.vy * dt;
      if (m.x < 2 || m.x > SIZE - 2) m.vx *= -1;
      if (m.y < 2 || m.y > SIZE - 2) m.vy *= -1;
    });
  }
  function drawPuffs() {                                       // on the ground, under the walkers
    puffs.forEach(function (p) {
      var q = toScreen(p.x, p.y), k = p.t / p.life, r = (6 + 14 * k) * p.s;
      ctx.fillStyle = 'rgba(190,180,150,' + (0.28 * (1 - k)) + ')';
      ctx.beginPath(); ctx.ellipse(q.x + p.dx * k, q.y - 3 - 8 * k, r, r * .55, 0, 0, Math.PI * 2); ctx.fill();
    });
  }
  function drawLights() {
    if (!LIGHTS.length && !flies.length) return;
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    LIGHTS.forEach(function (l, i) {
      var q = toScreen(l[0], l[1]), fl = .85 + Math.sin(glowT * 3.1 + i * 1.7) * .08 + Math.sin(glowT * 7.3 + i) * .05;
      var R = l[3] || 120, cy = q.y - (l[3] ? R * 0.3 : 0);         // a small light (a glowing mushroom): round its caps
      var g = ctx.createRadialGradient(q.x, cy, 2, q.x, cy, R * fl);
      g.addColorStop(0, hexA(l[2], .55 * fl)); g.addColorStop(.25, hexA(l[2], .18 * fl)); g.addColorStop(1, hexA(l[2], 0));
      ctx.fillStyle = g; ctx.fillRect(q.x - R * 1.1, cy - R * 1.1, R * 2.2, R * 2.2);
    });
    flies.forEach(function (f) {
      var q = toScreen(f.x, f.y), x = q.x, y = q.y - f.z - Math.sin(f.ph * 2) * 6;
      var on = Math.max(0, Math.sin(f.ph * 2.4 + f.hue * 6)) * .9 + .1;
      var g = ctx.createRadialGradient(x, y, 0, x, y, 14);
      g.addColorStop(0, 'rgba(232,247,160,' + (.75 * on) + ')'); g.addColorStop(.3, 'rgba(190,240,120,' + (.25 * on) + ')');
      g.addColorStop(1, 'rgba(190,240,120,0)');
      ctx.fillStyle = g; ctx.fillRect(x - 14, y - 14, 28, 28);
    });
    ctx.globalCompositeOperation = 'source-over';
    mists.forEach(function (m) {
      var q = toScreen(m.x, m.y), g = ctx.createRadialGradient(q.x, q.y, 0, q.x, q.y, m.r);
      g.addColorStop(0, 'rgba(190,210,235,' + m.a + ')'); g.addColorStop(1, 'rgba(190,210,235,0)');
      ctx.fillStyle = g; ctx.save(); ctx.translate(q.x, q.y); ctx.scale(1, .5); ctx.translate(-q.x, -q.y);
      ctx.fillRect(q.x - m.r, q.y - m.r, m.r * 2, m.r * 2); ctx.restore();
    });
    ctx.restore();
  }
  function hexA(hex, a) {
    var n = parseInt(hex.slice(1), 16);
    return 'rgba(' + (n >> 16 & 255) + ',' + (n >> 8 & 255) + ',' + (n & 255) + ',' + a + ')';
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
    drawShadows();
    drawPuffs();
    function at(x, y, f) { ctx.save(); ctx.translate(x, y); ctx.scale(1 / K, 1 / K); f(); ctx.restore(); }   // drawn at your size
    EXITS.forEach(function (e) { if (e.kind === 'path') drawExit(e); });   // a path out lies on the ground
    HERBS.forEach(function (h) { var p = toScreen(h.x, h.y); at(p.x, p.y, function () { drawHerb(h, 0, 0); }); });
    FINDS.forEach(function (f) { var p = toScreen(f.x, f.y); at(p.x, p.y, function () { drawFind(f, 0, 0); }); });
    var movers = [{hero: true, x: hero.x, y: hero.y, h: 175, f: function () { at(hp.x, hp.y, function () { drawHero(0, 0); }); }}];
    NPCS.forEach(function (n) {
      var p = toScreen(n.x, n.y);
      movers.push({x: n.x, y: n.y, h: (n.h || 100) + 50, f: function () { at(p.x, p.y, function () { drawNpc(n, 0, 0); }); }});
    });
    BEASTS.forEach(function (b) {
      var p = toScreen(b.x, b.y);
      movers.push({x: b.x, y: b.y, h: b.w, f: function () { at(p.x, p.y, function () { drawBeast(b, 0, 0); }); }});
    });
    layered(movers).forEach(function (f) { f(); });
    EXITS.forEach(function (e) { if (e.kind !== 'path') drawExit(e); });   // over the gate: its doorway lit
    if (hiddenHero) {                                   // behind a wall or a building: your silhouette shows through
      ctx.save(); ctx.globalAlpha = 0.45; at(hp.x, hp.y, function () { drawHero(0, 0); }); ctx.restore();
    }
    drawLights();
    // night: everything away from you sinks into the dark
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    var cx = W / 2 + (hp.x - cam.x) * S, cy = H / 2 + (hp.y - 60 / K - cam.y) * S, R = Math.max(W, H);
    var v = ctx.createRadialGradient(cx, cy, R * 0.12, cx, cy, R * 0.66);
    v.addColorStop(0, 'rgba(6,8,18,0)'); v.addColorStop(0.5, 'rgba(6,8,18,.45)'); v.addColorStop(1, 'rgba(4,5,12,.9)');
    ctx.fillStyle = v; ctx.fillRect(0, 0, W, H);
  }
  function onScreen(r) {                                // a piece's rect against the view (world px, ground image space)
    var half = SIZE * TW / 2, vw = W / S, vh = H / S, l = r[0] - half;
    return l < cam.x + vw / 2 && l + r[2] > cam.x - vw / 2 && r[1] < cam.y + vh / 2 && r[1] + r[3] > cam.y - vh / 2;
  }
  function drawShadows() {                              // the wilds' pieces cast a soft shadow (a log's lies along it)
    var half = SIZE * TW / 2;
    PIECES.forEach(function (q) {
      if (!q.shadow || !onScreen(q.rect)) return;
      var p = toScreen(q.at[0], q.at[1]), s = q.shadow;
      ctx.save(); ctx.translate(p.x, p.y); ctx.fillStyle = 'rgba(0,0,0,.34)'; ctx.beginPath();
      if (s.len) { ctx.rotate(Math.atan2(TH / 2, s.axis === 'x' ? TW / 2 : -TW / 2)); ctx.ellipse(0, 0, s.len, s.wide, 0, 0, Math.PI * 2); }
      else ctx.ellipse(0, 0, s.rx || 10, s.ry || 4, 0, 0, Math.PI * 2);
      ctx.fill(); ctx.restore();
    });
    return half;
  }
  /* depth order: the pieces back to front; each walker goes after every piece they overlap on screen and stand in
     front of (beyond a footprint's back edge, or nearer than a point), so the rest are drawn over them */
  function layered(movers) {
    var off = {x: SIZE * TW / 2, y: 0};                  // pieces' rects are on the ground picture, its top-left corner at (-half, 0)
    movers.forEach(function (m) {
      var p = toScreen(m.x, m.y), w = 60 / K, top = p.y - m.h / K, slot = 0;
      function over(q) { var r = q.rect, left = r[0] - off.x;
        return !(p.x + w < left || p.x - w > left + r[2] || p.y < r[1] || top > r[1] + r[3]); }
      PIECES.forEach(function (q, i) {
        if (!over(q)) return;
        var front = q.fp ? (m.x >= q.fp[0] + q.fp[2] - 0.25 || m.y >= q.fp[1] + q.fp[3] - 0.25) : m.x + m.y > q.depth;
        if (front) slot = i + 1;
      });
      m.slot = slot;
      if (m.hero) hiddenHero = PIECES.some(function (q, i) { return i >= slot && q.tall && over(q); });
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
    var img = ready(q.pic);
    if (!img || !onScreen(q.rect)) return;
    var r = q.rect;
    if (q.flip) { ctx.save(); ctx.translate(r[0] - off.x + r[2], r[1]); ctx.scale(-1, 1); ctx.drawImage(img, 0, 0, r[2], r[3]); ctx.restore(); }
    else ctx.drawImage(img, r[0] - off.x, r[1], r[2], r[3]);
  }
  /* G: the tile grid, the walkable ground and what blocks the way (to check a place against its painting) */
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
      if (!q.fp || q.pass) return; var f = q.fp; ctx.beginPath();
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
  load(cfg, false);
  cv.addEventListener('pointerdown', function () { cv.focus(); });
  cv.focus();
  requestAnimationFrame(frame);
})();
