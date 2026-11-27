/* The fight's background, alive (docs/web.md "Living backgrounds"): mist, leaves, snow, sand, rain, lightning,
   fireflies, drawn on one canvas at the back of the scene, behind the fighters and the beast, so nothing in front of
   it changes. Which weather plays is read off the fight's background picture (--arena on main.battle:
   art/scenes/battle_<region>.jpg, or the Arena's ruins for duels). Nothing here touches the fight: it only draws.

   The beast fight's page is replaced every turn (fight.js `show`); the same canvas is moved into the new scene, so the
   leaves keep falling instead of starting over. It stops while the tab is hidden, and with reduced motion it isn't
   drawn at all. Sizes are shares of the scene, so it looks the same on a phone and on a wide screen.

   A place may also have a video of its painting coming alive (`video`: art/scenes/<scene>.mp4, made by
   scripts/make_background_loop.py): it loops behind the whole fight page, under the page's own shading, fading in
   over the painting once it plays (until then, or if it can't play, the painting shows). Like the canvas it moves into
   each turn's new page and carries on. Not with reduced motion, nor when the browser asks to save data. Where the
   video already shows something (the aurora, falling leaves, mist, lightning), the canvas leaves it out (`skip`).

   The place's own sound (`sound`: art/scenes/<scene>.m4a, the video's ambience looped by the same script: wind,
   rain, thunder, crickets; the bamboo's and the gorge's made by scripts/make_ambience.py) plays quietly under the fight while the video does, at a third of the Settings volume.
   It follows Settings (Sound Off or Music Off: none), pauses while the tab is hidden, and starts on the first tap
   or key if the browser didn't let it start by itself. */
(function () {
  'use strict';
  if (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  // ── what each place does ───────────────────────────────────────────────────────────────────────────
  // mist: soft banks drifting sideways (how many, how high as shares of the scene, how strong, which tint)
  // fall: falling things (kind, how many per 1000 px of width, speed, wind), motes: glowing specks, flash: lightning
  var V = '/art/scenes/', PLACES = {
    bamboo_forest: {video: V + 'battle_bamboo_forest.mp4', sound: V + 'battle_bamboo_forest.m4a', skip: ['fall', 'mist'],
                    mist: {n: 4, y: [0.55, 0.85], a: 0.10, c: '214,224,206'},
                    fall: {kind: 'leaf', n: 9, speed: 0.06, wind: 0.015, colors: ['#C8792E', '#A85A22', '#D9A441', '#8C6A2E']},
                    motes: {n: 10, y: [0.15, 0.6], c: '255,236,190', a: 0.5}},
    misty_pine_valley: {video: V + 'battle_misty_pine_valley.mp4', sound: V + 'battle_misty_pine_valley.m4a', skip: ['mist'],
                        mist: {n: 9, y: [0.25, 0.85], a: 0.24, c: '214,222,230', speed: 1.2},
                        motes: {n: 8, y: [0.3, 0.8], c: '220,232,240', a: 0.35}},
    northern_sea_wilds: {aurora: {y: 0.12, c: '90,255,200'}, video: V + 'battle_northern_sea_wilds.mp4',
                         sound: V + 'battle_northern_sea_wilds.m4a', skip: ['aurora'],
                         fall: {kind: 'snow', n: 34, speed: 0.05, wind: 0.03},
                         mist: {n: 3, y: [0.6, 0.9], a: 0.09, c: '200,230,255', speed: 1.6}},
    red_cliff_gorge: {video: V + 'battle_red_cliff_gorge.mp4', sound: V + 'battle_red_cliff_gorge.m4a', skip: ['gust'],
                      fall: {kind: 'sand', n: 55, speed: 0.0, wind: 0.32, colors: ['#F2C28A', '#E0A060', '#FFD9A8']},
                      gust: {c: '226,160,100'}},
    thunder_peaks: {video: V + 'battle_thunder_peaks.mp4', sound: V + 'battle_thunder_peaks.m4a', skip: ['flash'],
                    fall: {kind: 'rain', n: 70, speed: 0.9, wind: 0.12},
                    flash: {every: [5, 11]},
                    mist: {n: 4, y: [0.6, 0.92], a: 0.10, c: '170,170,200'}},
    arena_ruins: {video: V + 'arena_ruins.mp4', sound: V + 'arena_ruins.m4a', skip: ['motes'],
                  mist: {n: 3, y: [0.7, 0.95], a: 0.08, c: '170,190,230'},
                  motes: {n: 30, y: [0.2, 0.85], c: '200,230,255', a: 0.8, glow: true, big: 1.5}}
  };
  var DEFAULT = {motes: {n: 10, y: [0.2, 0.8], c: '255,240,210', a: 0.4}};

  var saveData = !!(navigator.connection && navigator.connection.saveData), film = null, filmSrc = null;
  function shown(kind) { return !(film && place && place.skip && place.skip.indexOf(kind) >= 0); }   // the video shows it

  var amb = null, ambSrc = null, ambVol = 0.6, ambOn = true;
  try {
    ambOn = localStorage.getItem('ma.sound') !== 'off' && localStorage.getItem('ma.music') !== 'off';
    var v0 = parseFloat(localStorage.getItem('ma.vol')); if (v0 >= 0 && v0 <= 100) ambVol = v0 / 100;
  } catch (e) {}
  function sound_(src) {                                       // the place's ambience, quiet under the fight
    if (!src || !ambOn || saveData) { if (amb) { amb.pause(); amb = null; ambSrc = null; } return; }
    if (amb && ambSrc === src) return;
    if (amb) amb.pause();
    amb = new Audio(src); ambSrc = src; amb.loop = true; amb.volume = Math.min(1, ambVol * 0.33); amb.preload = 'auto';
    var p = amb.play(); if (p && p.catch) p.catch(function () {});
  }
  function wake() { if (amb && amb.paused && !document.hidden) { var p = amb.play(); if (p && p.catch) p.catch(function () {}); } }
  ['pointerdown', 'keydown', 'touchstart'].forEach(function (e) { document.addEventListener(e, wake, {passive: true}); });
  document.addEventListener('visibilitychange', function () { if (!amb) return; if (document.hidden) amb.pause(); else wake(); });
  /* The video plays as two copies taking turns, not with `loop`: a browser jumping a looping video back to its start
     freezes or flashes for a moment on some machines (SHOAIB's PC: "the screen refreshes every 8 seconds"). Just
     before the shown copy ends, the other starts from the beginning under it and the top copy fades (SEAM s); the
     jump back to the start then happens on the hidden copy. The video's own end already flows into its start
     (scripts/make_background_loop.py), so the two match where they cross. `film` is the top copy (the page's
     shading follows it), `twin` the one under it. */
  var twin = null, front = null, SEAM = 0.6;
  function copy_(src) {
    var v = document.createElement('video');
    v.className = 'bgloop'; v.muted = true; v.autoplay = false; v.playsInline = true;
    v.setAttribute('muted', ''); v.setAttribute('playsinline', ''); v.setAttribute('aria-hidden', 'true');
    v.preload = 'auto'; v.src = src;
    v.addEventListener('timeupdate', function () { if (v === front && v.duration && v.currentTime >= v.duration - SEAM - 0.25) swap(); });
    v.addEventListener('ended', function () { if (v === front) swap(); v.pause(); v.currentTime = 0; });   // (a late timeupdate)
    v.addEventListener('error', function () { if (film) { film.remove(); film = null; } if (twin) { twin.remove(); twin = null; } });
    return v;
  }
  function play_(v) { var p = v.play(); if (p && p.catch) p.catch(function () {}); }
  function swap() {                                            // the other copy takes over from its first frame
    var next = front === film ? twin : film, prev = front;
    if (!next || !prev) return;
    front = next;
    next.currentTime = 0; play_(next);
    film.style.transition = 'opacity ' + SEAM + 's linear';
    film.style.opacity = next === film ? '' : '0';             // the top copy fades in or out over the one under it
    setTimeout(function () { if (front !== prev) { prev.pause(); prev.currentTime = 0; } }, SEAM * 1000 + 200);
  }
  function film_(main, src) {                                  // the place's video, at the back of the whole fight page
    if (!src || saveData) {
      if (film) { film.remove(); film = null; filmSrc = null; }
      if (twin) { twin.remove(); twin = null; }
      main.classList.remove('bglive'); return;
    }
    if (!film || filmSrc !== src) {
      if (film) film.remove();
      if (twin) twin.remove();
      film = copy_(src); twin = copy_(src); filmSrc = src; front = film;
      film.addEventListener('playing', function () { if (film) film.classList.add('on'); if (twin) twin.classList.add('on'); }, {once: true});
    }
    if (film.parentNode !== main) {
      main.insertBefore(film, main.firstChild);
      main.insertBefore(twin, film);                           // under the top copy; the shading stays right after it
      var shade = main.querySelector(':scope > .bgshade');      // the page's own shading, kept over the video
      if (!shade) { shade = document.createElement('div'); shade.className = 'bgshade'; main.insertBefore(shade, film.nextSibling); }
      main.classList.add('bglive');
      play_(front);
    }
  }

  var canvas = null, ctx = null, place = null, key = null, W = 0, H = 0, dpr = 1, items = [], last = 0, flash = 0,
      nextFlash = 0, bolt = null, gust = 0, nextGust = 0, mistSprite = null;
  /* Smoothness: measuring the page makes the browser work the whole layout out again, which is costly while a fight is
     animating. So the canvas is measured only when its box may have changed (a new scene, the screen resized or turned,
     or at most once a second where the browser can't tell us), not on every frame. On phones (LITE, as in fight.js)
     the drifting snow, rain and mist is drawn at screen sharpness 1 and about 30 times a second: on a small screen it
     looks the same and costs half. */
  var LITE = !!(window.matchMedia && matchMedia('(max-width: 700px)').matches), STEP = LITE ? 30 : 0, drawn = 0;
  var dirty = true, sized = null, checked = 0,
      watch = window.ResizeObserver ? new ResizeObserver(function () { dirty = true; }) : null;
  function rand(a, b) { return a + Math.random() * (b - a); }

  function sceneKey(main) {
    var url = main.style.getPropertyValue('--arena') || getComputedStyle(main).getPropertyValue('--arena') || '';
    var m = url.match(/(?:battle_)?([a-z_]+)\.(?:jpg|png|webp)/);
    return m ? m[1] : '';
  }

  function sprite(rgb) {                                       // one soft round puff in the place's tint, stretched into banks
    var c = document.createElement('canvas'); c.width = c.height = 128;
    var g = c.getContext('2d'), r = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    r.addColorStop(0, 'rgba(' + rgb + ',1)'); r.addColorStop(0.5, 'rgba(' + rgb + ',.45)'); r.addColorStop(1, 'rgba(' + rgb + ',0)');
    g.fillStyle = r; g.fillRect(0, 0, 128, 128);
    return c;
  }

  function seed() {
    items = [];
    var p = place, per = Math.max(0.5, W / 1000);
    if (p.mist) for (var i = 0; i < p.mist.n; i++) items.push({t: 'mist', x: rand(-0.3, 1.1), y: rand(p.mist.y[0], p.mist.y[1]),
      w: rand(0.35, 0.7), h: rand(0.12, 0.22), v: rand(0.004, 0.012) * (p.mist.speed || 1) * (Math.random() < 0.5 ? 1 : -0.6), ph: rand(0, 6)});
    if (p.fall) for (var j = 0; j < Math.round(p.fall.n * per); j++) items.push(faller(true));
    if (p.motes) for (var k = 0; k < Math.round(p.motes.n * Math.min(per, 1.6)); k++) items.push({t: 'mote', x: Math.random(), y: rand(p.motes.y[0], p.motes.y[1]),
      vx: rand(-0.006, 0.006), vy: rand(-0.008, -0.002), r: rand(0.8, 2.2) * (p.motes.big || 1), ph: rand(0, 6), sp: rand(0.6, 1.6)});
  }

  function faller(anywhere) {
    var f = place.fall, it = {t: f.kind, x: rand(-0.1, 1.1), y: anywhere ? Math.random() : rand(-0.15, -0.02)};
    if (f.kind === 'leaf') { it.vy = rand(0.6, 1.1) * f.speed; it.s = rand(5, 9); it.rot = rand(0, 6.3); it.spin = rand(-1.6, 1.6); it.sw = rand(0.6, 1.4); it.ph = rand(0, 6); it.col = f.colors[Math.floor(Math.random() * f.colors.length)]; }
    if (f.kind === 'snow') { it.vy = rand(0.6, 1.3) * f.speed; it.r = rand(0.7, 2.1); it.ph = rand(0, 6); }
    if (f.kind === 'rain') { it.vy = rand(0.85, 1.15) * f.speed; it.l = rand(0.025, 0.05); }
    if (f.kind === 'sand') { it.x = anywhere ? Math.random() : rand(1.0, 1.2); it.y = rand(0.45, 0.98); it.vx = -rand(0.6, 1.3) * f.wind; it.l = rand(8, 24); it.a = rand(0.3, 0.65); it.col = f.colors[Math.floor(Math.random() * f.colors.length)]; }
    return it;
  }

  function resize() {
    var box = canvas.parentNode, now = performance.now();
    if (!dirty && box === sized && (watch || now - checked < 1000)) return false;
    if (watch && box !== sized) { watch.disconnect(); watch.observe(box); }
    sized = box; dirty = false; checked = now;
    var r = box.getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, LITE ? 1 : 1.5);
    if (Math.round(r.width) === W && Math.round(r.height) === H) return false;
    W = Math.round(r.width); H = Math.round(r.height);
    canvas.width = Math.max(1, Math.round(W * dpr)); canvas.height = Math.max(1, Math.round(H * dpr));
    return true;
  }

  function attach() {                                          // the current scene: the canvas at its back
    var main = document.querySelector('main.battle'), scene = main && main.querySelector('.bscene');
    if (!scene) return false;
    var k = sceneKey(main);
    if (!canvas) {
      canvas = document.createElement('canvas'); canvas.className = 'ambient'; canvas.setAttribute('aria-hidden', 'true');
      ctx = canvas.getContext('2d');
    }
    if (canvas.parentNode !== scene) scene.insertBefore(canvas, scene.firstChild);
    var grown = resize();
    if (k !== key) { key = k; place = PLACES[k] || DEFAULT; mistSprite = place.mist ? sprite(place.mist.c) : null; seed(); nextFlash = 0; nextGust = 0; }
    else if (grown) seed();
    film_(main, place.video);
    sound_(place.video && film ? place.sound : null);
    return true;
  }

  function drawBolt(x) {                                       // a jagged bolt in the sky, top third
    var pts = [[x, 0]], y = 0, cx = x;
    while (y < 0.32) { y += rand(0.03, 0.06); cx += rand(-0.03, 0.03); pts.push([cx, y]); }
    return pts;
  }

  function frame(now) {
    requestAnimationFrame(frame);
    if (document.hidden) { last = now; return; }
    if (STEP && now - drawn < STEP) return;                    // phones: every other frame
    drawn = now;
    if (!attach()) return;
    var dt = Math.min(0.05, (now - (last || now)) / 1000); last = now;
    var t = now / 1000, p = place, sc = Math.min(W, H * 1.8);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);

    if (p.aurora && shown('aurora')) {                                            // the aurora breathes: a soft band that brightens and fades
      var a = 0.05 + 0.05 * Math.sin(t * 0.5) + 0.03 * Math.sin(t * 1.3);
      var g = ctx.createLinearGradient(0, 0, 0, H * 0.5);
      g.addColorStop(0, 'rgba(' + p.aurora.c + ',0)'); g.addColorStop(p.aurora.y + 0.1, 'rgba(' + p.aurora.c + ',' + a.toFixed(3) + ')'); g.addColorStop(1, 'rgba(' + p.aurora.c + ',0)');
      ctx.fillStyle = g; ctx.fillRect(0, 0, W, H * 0.5);
    }

    if (p.flash && shown('flash')) {                           // lightning now and then: the sky lights up, a bolt, gone
      if (!nextFlash) nextFlash = t + rand(1.5, 4);
      if (t >= nextFlash) { flash = 1; bolt = drawBolt(rand(0.15, 0.85)); nextFlash = t + rand(p.flash.every[0], p.flash.every[1]); }
      if (flash > 0) {
        var f = flash * (0.6 + 0.4 * Math.sin(t * 60) * Math.sin(t * 60));    // it flickers as it fades
        var sky = ctx.createLinearGradient(0, 0, 0, H * 0.75);
        sky.addColorStop(0, 'rgba(215,220,255,' + (0.55 * f).toFixed(3) + ')'); sky.addColorStop(1, 'rgba(215,220,255,0)');
        ctx.fillStyle = sky; ctx.fillRect(0, 0, W, H * 0.75);
        if (bolt && flash > 0.3) {
          ctx.strokeStyle = 'rgba(240,240,255,' + Math.min(1, 1.2 * f).toFixed(3) + ')'; ctx.lineWidth = 3; ctx.shadowColor = 'rgba(190,190,255,1)'; ctx.shadowBlur = 16;
          ctx.beginPath(); bolt.forEach(function (q, n) { ctx[n ? 'lineTo' : 'moveTo'](q[0] * W, q[1] * H); }); ctx.stroke(); ctx.shadowBlur = 0;
        }
        flash = Math.max(0, flash - dt * 1.6);
      }
    }

    if (p.gust && shown('gust')) {                             // the gorge's wind lifts a veil of dust now and then
      if (!nextGust) nextGust = t + rand(2, 5);
      if (t >= nextGust) { gust = 1; nextGust = t + rand(6, 11); }
      if (gust > 0) {
        var gx = (1 - gust) * 1.4 - 0.2, gg = ctx.createLinearGradient(gx * W - W * 0.4, 0, gx * W + W * 0.4, 0);
        var ga = Math.sin(Math.PI * gust) * 0.14;
        gg.addColorStop(0, 'rgba(' + p.gust.c + ',0)'); gg.addColorStop(0.5, 'rgba(' + p.gust.c + ',' + ga.toFixed(3) + ')'); gg.addColorStop(1, 'rgba(' + p.gust.c + ',0)');
        ctx.fillStyle = gg; ctx.fillRect(0, H * 0.45, W, H * 0.55);
        gust = Math.max(0, gust - dt * 0.35);
      }
    }

    var showMist = shown('mist'), showMotes = shown('motes'), showFall = shown('fall');
    for (var i = 0; i < items.length; i++) {
      var it = items[i];
      if (!(it.t === 'mist' ? showMist : it.t === 'mote' ? showMotes : showFall)) continue;
      if (it.t === 'mist') {
        it.x += it.v * dt; if (it.x > 1.25) it.x = -0.45; if (it.x < -0.45) it.x = 1.25;
        var al = p.mist.a * (0.7 + 0.3 * Math.sin(t * 0.3 + it.ph));
        ctx.globalAlpha = al;
        ctx.drawImage(mistSprite, (it.x - it.w / 2) * W, (it.y - it.h / 2) * H, it.w * W, it.h * H);
        ctx.globalAlpha = 1;
      } else if (it.t === 'mote') {
        it.x += (it.vx + 0.004 * Math.sin(t * it.sp + it.ph)) * dt; it.y += it.vy * dt;
        if (it.y < p.motes.y[0] - 0.05) { it.y = p.motes.y[1]; it.x = Math.random(); }
        if (it.x < -0.02) it.x = 1.02; if (it.x > 1.02) it.x = -0.02;
        var ma = p.motes.a * (0.35 + 0.65 * Math.abs(Math.sin(t * it.sp * 0.8 + it.ph)));
        if (p.motes.glow) { ctx.shadowColor = 'rgba(' + p.motes.c + ',1)'; ctx.shadowBlur = 12; }
        ctx.fillStyle = 'rgba(' + p.motes.c + ',' + ma.toFixed(3) + ')';
        ctx.beginPath(); ctx.arc(it.x * W, it.y * H, it.r, 0, 6.283); ctx.fill(); ctx.shadowBlur = 0;
      } else if (it.t === 'leaf') {                            // it sways and turns as it falls (its width shows its spin)
        it.y += it.vy * dt; it.x += (place.fall.wind + 0.03 * Math.sin(t * it.sw + it.ph)) * dt; it.rot += it.spin * dt;
        if (it.y > 1.05) items[i] = faller(false);
        ctx.save(); ctx.translate(it.x * W, it.y * H); ctx.rotate(it.rot); ctx.scale(Math.max(0.15, Math.abs(Math.cos(t * it.sw * 1.7 + it.ph))), 1);
        ctx.fillStyle = it.col; ctx.globalAlpha = 0.85;
        ctx.beginPath(); ctx.ellipse(0, 0, it.s * 0.45, it.s, 0, 0, 6.283); ctx.fill();
        ctx.restore(); ctx.globalAlpha = 1;
      } else if (it.t === 'snow') {
        it.y += it.vy * dt; it.x += (place.fall.wind + 0.012 * Math.sin(t * 1.1 + it.ph)) * dt;
        if (it.y > 1.02 || it.x > 1.05) { items[i] = faller(false); items[i].x = rand(-0.2, 1); }
        ctx.fillStyle = 'rgba(240,248,255,' + (0.45 + 0.35 * (it.r / 2.1)).toFixed(3) + ')';
        ctx.beginPath(); ctx.arc(it.x * W, it.y * H, it.r, 0, 6.283); ctx.fill();
      } else if (it.t === 'rain') {
        it.y += it.vy * dt; it.x += place.fall.wind * dt;
        if (it.y > 1.02) { items[i] = faller(false); }
        var x0 = it.x * W, y0 = it.y * H, len = it.l * sc;
        ctx.strokeStyle = 'rgba(205,215,240,.42)'; ctx.lineWidth = 1.2;
        ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x0 - place.fall.wind / place.fall.speed * len, y0 - len); ctx.stroke();
      } else if (it.t === 'sand') {
        it.x += it.vx * (1 + 1.5 * gust) * dt; it.y += 0.01 * Math.sin(t * 2 + it.x * 9) * dt;
        if (it.x < -0.05) { items[i] = faller(false); }
        var sx = it.x * W, sy = it.y * H, sl = it.l * (1 + gust), sg = ctx.createLinearGradient(sx, 0, sx + sl, 0);
        sg.addColorStop(0, it.col); sg.addColorStop(1, 'rgba(0,0,0,0)');   // bright at its head, fading along its tail
        ctx.strokeStyle = sg; ctx.globalAlpha = it.a; ctx.lineWidth = 1.6; ctx.lineCap = 'round';
        ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(sx + sl, sy); ctx.stroke(); ctx.globalAlpha = 1;
      }
    }
  }

  window.addEventListener('resize', function () { dirty = true; if (canvas && canvas.parentNode && resize()) seed(); });
  window.addEventListener('orientationchange', function () { dirty = true; });
  requestAnimationFrame(frame);
})();


/* Standing on the ground (docs/web.md "Living backgrounds"): each place's painting has its open floor at a known
   height (GROUND: the share of the picture's height, down from its top, where feet look right). The fighters' feet
   sit at a fixed spot of the page, so the painting and its video are moved (and, if they must, enlarged a little,
   at most MAX_ZOOM) until that row of the painting lies under their feet, whatever the screen's shape. Beast fights and
   hunts only (a duel keeps its own framing). It runs with reduced motion too: only the still picture is moved then. */
(function () {
  'use strict';
  var GROUND = {bamboo_forest: 0.78, misty_pine_valley: 0.78, red_cliff_gorge: 0.80, thunder_peaks: 0.76,
                arena_ruins: 0.76, northern_sea_wilds: 0.76};
  var ASPECT = 16 / 9, MAX_ZOOM = 1.35, HERO_FEET = 0.936;     // the hero's soles: 93.6% down the fight picture
  var last = '';
  function key(main) {
    var url = main.style.getPropertyValue('--arena') || '';
    var m = url.match(/(?:battle_)?([a-z_]+)\.(?:jpg|png|webp)/);
    return m ? m[1] : '';
  }
  function fit() {
    var main = document.querySelector('main.battle'), G = main && GROUND[key(main)];
    var hero = main && main.querySelector('.bscene .fighter'), beast = main && main.querySelector('.bscene .beast');
    if (!G || !hero || !beast) return;                         // beast fights and hunts (a duel keeps its own framing)
    var mr = main.getBoundingClientRect(), hr = hero.getBoundingClientRect(), br = beast.getBoundingClientRect();
    var feet = hr.top + hr.height * HERO_FEET - mr.top;
    if (br.height) feet = (feet + (br.bottom - mr.top)) / 2;                    // between the hero's and the beast's
    var W = mr.width, H = mr.height, sig = [W, H, Math.round(feet), G, main.dataset.turn].join();
    var vs = main.querySelectorAll(':scope > video.bgloop'), v = vs[vs.length - 1];   // both copies of the video
    if (sig === last && main.style.getPropertyValue('--arena-size') && (!v || v.style.width)) return;
    last = sig;
    var cover = Math.max(H, W / ASPECT);
    var h = Math.min(Math.max(cover, (H - feet) / (1 - G), feet / G), cover * MAX_ZOOM), w = h * ASPECT;
    var y = Math.max(0, Math.min(G * h - feet, h - H)), x = (w - W) / 2;
    main.style.setProperty('--arena-size', w.toFixed(0) + 'px ' + h.toFixed(0) + 'px');
    main.style.setProperty('--arena-pos', (-x).toFixed(0) + 'px ' + (-y).toFixed(0) + 'px');
    Array.prototype.forEach.call(vs, function (v) {
      v.style.inset = 'auto'; v.style.objectFit = 'fill';
      v.style.left = (-x).toFixed(0) + 'px'; v.style.top = (-y).toFixed(0) + 'px';
      v.style.width = w.toFixed(0) + 'px'; v.style.height = h.toFixed(0) + 'px';
    });
  }
  /* fit() measures the page, so it runs when something that moves the feet may have changed (a new page or turn, the
     window's size, a picture finishing loading) and otherwise a few times a second, not on every frame. */
  var fitAt = 0, fitMain = null, fitTurn = null, fitWin = '';
  document.addEventListener('load', function () { fitAt = 0; }, true);
  function tick(now) {
    requestAnimationFrame(tick);
    if (document.hidden) return;
    var main = document.querySelector('main.battle'), turn = main && main.dataset.turn, win = innerWidth + 'x' + innerHeight;
    if (main === fitMain && turn === fitTurn && win === fitWin && now - fitAt < 400) return;
    fitMain = main; fitTurn = turn; fitWin = win; fitAt = now;
    fit();
  }
  requestAnimationFrame(tick);
})();
