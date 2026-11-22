/* The fight's background, alive (docs/web.md "Living backgrounds"): mist, leaves, snow, sand, rain, lightning,
   fireflies, drawn on one canvas at the back of the scene, behind the fighters and the beast, so nothing in front of
   it changes. Which weather plays is read off the fight's background picture (--arena on main.battle:
   art/scenes/battle_<region>.jpg, or the Arena's ruins for duels). Nothing here touches the fight: it only draws.

   The beast fight's page is replaced every turn (fight.js `show`); the same canvas is moved into the new scene, so the
   leaves keep falling instead of starting over. It stops while the tab is hidden, and with reduced motion it isn't
   drawn at all. Sizes are shares of the scene, so it looks the same on a phone and on a wide screen. */
(function () {
  'use strict';
  if (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  // ── what each place does ───────────────────────────────────────────────────────────────────────────
  // mist: soft banks drifting sideways (how many, how high as shares of the scene, how strong, which tint)
  // fall: falling things (kind, how many per 1000 px of width, speed, wind), motes: glowing specks, flash: lightning
  var PLACES = {
    bamboo_forest: {mist: {n: 4, y: [0.55, 0.85], a: 0.10, c: '214,224,206'},
                    fall: {kind: 'leaf', n: 9, speed: 0.06, wind: 0.015, colors: ['#C8792E', '#A85A22', '#D9A441', '#8C6A2E']},
                    motes: {n: 10, y: [0.15, 0.6], c: '255,236,190', a: 0.5}},
    misty_pine_valley: {mist: {n: 9, y: [0.25, 0.85], a: 0.24, c: '214,222,230', speed: 1.2},
                        motes: {n: 8, y: [0.3, 0.8], c: '220,232,240', a: 0.35}},
    northern_sea_wilds: {aurora: {y: 0.12, c: '90,255,200'},
                         fall: {kind: 'snow', n: 34, speed: 0.05, wind: 0.03},
                         mist: {n: 3, y: [0.6, 0.9], a: 0.09, c: '200,230,255', speed: 1.6}},
    red_cliff_gorge: {fall: {kind: 'sand', n: 55, speed: 0.0, wind: 0.32, colors: ['#F2C28A', '#E0A060', '#FFD9A8']},
                      gust: {c: '226,160,100'}},
    thunder_peaks: {fall: {kind: 'rain', n: 70, speed: 0.9, wind: 0.12},
                    flash: {every: [5, 11]},
                    mist: {n: 4, y: [0.6, 0.92], a: 0.10, c: '170,170,200'}},
    arena_ruins: {mist: {n: 3, y: [0.7, 0.95], a: 0.08, c: '170,190,230'},
                  motes: {n: 30, y: [0.2, 0.85], c: '200,230,255', a: 0.8, glow: true, big: 1.5}}
  };
  var DEFAULT = {motes: {n: 10, y: [0.2, 0.8], c: '255,240,210', a: 0.4}};

  var canvas = null, ctx = null, place = null, key = null, W = 0, H = 0, dpr = 1, items = [], last = 0, flash = 0,
      nextFlash = 0, bolt = null, gust = 0, nextGust = 0, mistSprite = null;
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
    var r = canvas.parentNode.getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, 1.5);
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
    if (!attach()) return;
    var dt = Math.min(0.05, (now - (last || now)) / 1000); last = now;
    var t = now / 1000, p = place, sc = Math.min(W, H * 1.8);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);

    if (p.aurora) {                                            // the aurora breathes: a soft band that brightens and fades
      var a = 0.05 + 0.05 * Math.sin(t * 0.5) + 0.03 * Math.sin(t * 1.3);
      var g = ctx.createLinearGradient(0, 0, 0, H * 0.5);
      g.addColorStop(0, 'rgba(' + p.aurora.c + ',0)'); g.addColorStop(p.aurora.y + 0.1, 'rgba(' + p.aurora.c + ',' + a.toFixed(3) + ')'); g.addColorStop(1, 'rgba(' + p.aurora.c + ',0)');
      ctx.fillStyle = g; ctx.fillRect(0, 0, W, H * 0.5);
    }

    if (p.flash) {                                             // lightning now and then: the sky lights up, a bolt, gone
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

    if (p.gust) {                                              // the gorge's wind lifts a veil of dust now and then
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

    for (var i = 0; i < items.length; i++) {
      var it = items[i];
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

  window.addEventListener('resize', function () { if (canvas && canvas.parentNode && resize()) seed(); });
  requestAnimationFrame(frame);
})();
