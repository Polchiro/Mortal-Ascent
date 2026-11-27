/* The Treasure Shelf and the vault (web/chest_play.py, docs/web.md "Opening a chest").
   The server opens (rolls and grants) the chest the moment you start breaking its seals; this page only shows what
   came out. The ceremony grows with the chest's tier (its seals, its light, a Mythic chest darkening the room and
   rising), which you knew before you opened it. What is inside lands as identical jade slips that turn over worst
   first; Epic and better rise to the middle, and Legendary and Mythical fill the screen. */
(function () {
  var S = JSON.parse(document.getElementById('chstate').textContent), ART = S.art, SHELF = S.shelf;
  function $(id) { return document.getElementById(id); }
  var main = $('ch');
  var reduced = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var soundOn = true, soundVol = 0.6, quick = false;
  try {
    soundOn = localStorage.getItem('ma.sound') !== 'off';
    var v0 = parseFloat(localStorage.getItem('ma.vol')); if (v0 >= 0 && v0 <= 100) soundVol = v0 / 100;
    quick = localStorage.getItem('ma.chest.quick') === '1';
  } catch (e0) {}
  function fs(name, arg, delay) { var F = window.FightSound; if (F) F.play(name, arg, delay); }
  function audio(url, vol, loop) {
    if (!soundOn || !url) return null;
    var a = new Audio(url); a.volume = Math.min(1, vol); a.loop = !!loop;
    var p = a.play(); if (p && p.catch) p.catch(function () {});
    return a;
  }
  var AC = null;
  function tone(freq, at, len, vol, type) {                       // the slips' tick and the coins' clink
    if (!soundOn) return;
    try {
      var C = window.AudioContext || window.webkitAudioContext; AC = AC || new C();
      var t = AC.currentTime + (at || 0), o = AC.createOscillator(), g = AC.createGain();
      o.type = type || 'triangle'; o.frequency.setValueAtTime(freq, t);
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime((vol || 0.25) * soundVol, t + 0.01);
      g.gain.exponentialRampToValueAtTime(0.0001, t + (len || 0.25));
      o.connect(g); g.connect(AC.destination); o.start(t); o.stop(t + (len || 0.25) + 0.05);
    } catch (e) {}
  }
  var RANK_NOTE = [523, 587, 659, 784, 880, 1047];                // Common .. Mythical: each a little higher
  function say(t) { $('chsay').textContent = t || ''; }
  function nonce() { return Math.random().toString(36).slice(2) + Date.now().toString(36); }

  /* ── stages: the shelf is shown whole (contain), the vault fills the window (cover) ───────────── */
  function fit() {
    [['chshelfstage', false], ['chvaultstage', true]].forEach(function (d) {
      var st = $(d[0]), box = st.parentElement.getBoundingClientRect(), W = box.width, H = box.height;
      if (!W || !H) return;
      var k = d[1] ? Math.max(W / 1920, H / 1080) : Math.min(W / 1920, H / 1080);
      st.style.width = 1920 * k + 'px'; st.style.height = 1080 * k + 'px';
      st.style.left = (W - 1920 * k) / 2 + 'px'; st.style.top = (H - 1080 * k) / 2 + 'px';
      st.style.setProperty('--k', k);
      if (d[1]) $('chaltar').style.width = Math.min(0.34 * 1920 * k, W * 0.8) + 'px';   // a phone: still within the screen
    });
    var c = $('chfx'), r = c.getBoundingClientRect(), dpr = Math.min(2, window.devicePixelRatio || 1);
    c.width = Math.round(r.width * dpr); c.height = Math.round(r.height * dpr);
  }
  window.addEventListener('resize', fit);

  /* ── the shelf: three shelves, the rarest at the top; only the chests you have glow ────────────── */
  var PLACE = {mythic: [38, 34.2], legendary: [62, 34.2], epic: [38, 61.2], rare: [62, 61.2], uncommon: [38, 86], common: [62, 86]};
  var picked = null;
  function drawShelf() {
    var box = $('chslots'); box.innerHTML = '';
    SHELF.tiers.forEach(function (t) {
      var at = PLACE[t.key], el = document.createElement(t.qty ? 'button' : 'div');
      el.className = 'cslot' + (t.qty ? '' : ' none') + (picked === t.key ? ' on' : '');
      el.style.left = at[0] + '%'; el.style.top = at[1] + '%'; el.style.setProperty('--rc', t.color);
      if (t.qty) { el.type = 'button'; el.setAttribute('aria-label', t.name + ', ' + t.qty); }
      el.innerHTML = '<span class="cglow"></span><img alt=""><b class="cqty"></b><span class="cname"></span>';
      el.querySelector('img').src = t.picture;
      el.querySelector('.cqty').textContent = t.qty ? '×' + t.qty : '';
      el.querySelector('.cname').textContent = t.qty ? t.name : '';
      if (t.qty) el.addEventListener('click', function () { pick(t.key); });
      box.appendChild(el);
    });
    $('chroom').textContent = 'Bag: ' + (SHELF.capacity - SHELF.room) + ' / ' + SHELF.capacity + ' slots used · ' + SHELF.total + ' chest' + (SHELF.total === 1 ? '' : 's');
    $('chwait').hidden = !SHELF.waiting.length;
    if (!picked || !tierOf(picked) || !tierOf(picked).qty) {
      var best = SHELF.tiers.slice().reverse().filter(function (t) { return t.qty; })[0];
      picked = best ? best.key : null;
    }
    drawPick();
  }
  function tierOf(key) { return SHELF.tiers.filter(function (t) { return t.key === key; })[0]; }
  function pick(key) { picked = key; fs('press'); drawShelf(); }
  function drawPick() {
    var box = $('chpick'), t = picked && tierOf(picked);
    Array.prototype.forEach.call(document.querySelectorAll('.cslot'), function (el, i) { el.classList.toggle('on', SHELF.tiers[i].key === picked); });
    if (!t) { box.innerHTML = '<p class="chempty">No chests yet. They drop from beasts, exploring and the daily tasks.</p>'; return; }
    var all = Math.min(t.qty, SHELF.max_all, t.fits);
    box.style.setProperty('--rc', t.color);
    box.innerHTML = '<div class="chpicked"><img alt=""><div><b></b><small></small></div></div>' +
      '<p class="chcan"></p><div class="chbtns"><button class="chbtn main" id="chopen" type="button">Open</button>' +
      (t.qty > 1 ? '<button class="chbtn" id="chall" type="button"></button>' : '') + '</div>';
    box.querySelector('img').src = t.picture;
    box.querySelector('b').textContent = t.name;
    box.querySelector('small').textContent = '×' + t.qty + ' · ' + (t.seals ? t.seals + ' seal' + (t.seals > 1 ? 's' : '') : 'no seal');
    var can = box.querySelector('.chcan');
    if (t.fits < 1) { can.className = 'chcan warn'; can.textContent = 'Needs ' + t.need + ' free bag slots to open (it can give up to ' + t.need + ' items). You have ' + SHELF.room + '.'; }
    else can.textContent = 'Can give up to ' + t.need + ' items that take a bag slot. Nothing is ever left behind.';
    $('chopen').disabled = t.fits < 1;
    if ($('chall')) {
      $('chall').textContent = 'Open ' + Math.max(1, all) + (all < t.qty ? ' of ' + t.qty : ' (all)');
      $('chall').disabled = all < 2;
      $('chall').addEventListener('click', function () { vault(t, all); });
    }
    $('chopen').addEventListener('click', function () { vault(t, 1); });
  }
  $('chcollect').addEventListener('click', function () {
    request('/chests/collect', {nonce: nonce()}, function (r) { vault({key: r.tier, name: r.name, color: r.color, seals: 0, picture: r.picture, item: null}, r.opened, r); });
  });
  var qbox = $('chquick');
  qbox.checked = quick;
  qbox.addEventListener('change', function () { quick = qbox.checked; try { localStorage.setItem('ma.chest.quick', quick ? '1' : '0'); } catch (e) {} });

  function request(url, body, ok, bad) {
    fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, credentials: 'same-origin', body: JSON.stringify(body)})
      .then(function (r) { return r.json(); })
      .then(function (v) {
        if (v.gone) { location.href = '/'; return; }
        if (v.shelf) SHELF = v.shelf;
        if (v.error || !v.result) { say(v.error || 'Something went wrong.'); drawShelf(); if (bad) bad(v.error); return; }
        ok(v.result);
      })
      .catch(function () { say('The connection dropped. Look at your bag before you try again.'); if (bad) bad(); });
  }

  /* ── the vault ──────────────────────────────────────────────────── */
  var vbg = $('chvbg'), vstill = $('chvstill'), amb = null, R = null, T = null, count = 1, timers = [], phase = '';
  var fxc = $('chfx'), fx = fxc.getContext('2d'), burstV = null, glowIn = null, glowV = null;
  if (ART.vault) vstill.src = ART.vault;
  function later(fn, ms) { timers.push(setTimeout(fn, ms)); }
  function video(src, loop) {
    if (!src) return null;
    var v = document.createElement('video'); v.muted = true; v.playsInline = true; v.setAttribute('playsinline', ''); v.preload = 'auto'; v.loop = !!loop; v.src = src;
    return v;
  }
  burstV = video(ART.burst); glowIn = video(ART.glow_in); glowV = video(ART.glow, true);

  function vault(t, n, already) {
    T = t; count = n; R = already || null; phase = 'seal'; timers.forEach(clearTimeout); timers = []; endRite();
    main.dataset.view = 'vault'; $('chvault').hidden = false; fit();
    main.style.setProperty('--rc', t.color);
    $('chvault').className = 'chvault tier-' + t.key;
    $('chvname').textContent = n > 1 ? t.name + ' ×' + n : t.name;
    $('chchest').src = t.picture; $('chopened').src = t.open || t.picture;
    $('chbox').className = 'chbox in';
    $('chcards').innerHTML = ''; $('chcards').className = 'chcards'; $('chsum').hidden = true; $('chspot').hidden = true; $('chcoins').hidden = true;
    $('chskip').hidden = true; $('chdark').className = 'chdark';
    if (ART.vault_video) {
      vbg.src = ART.vault_video; var p = vbg.play(); if (p && p.catch) p.catch(function () {});
      vbg.onplaying = function () { vstill.classList.add('off'); };
    }
    if (!amb) amb = audio(ART.vault_sound, soundVol * 0.7, true);
    fs('gather');
    seals(already ? 0 : t.seals);
    if (already) later(burst, 500);
  }
  /* the seals: hold to break them one after another (a tap breaks one); a chest without one opens with a tap */
  var left = 0, holding = null, holdAt = 0, HOLD = 520;
  function seals(n) {
    left = quick ? 0 : n;
    var box = $('chseals'); box.innerHTML = '';
    for (var i = 0; i < left; i++) {
      var s = document.createElement('span'); s.className = 'cseal'; s.style.setProperty('--i', i); s.style.setProperty('--n', left);
      if (ART.seal) s.style.backgroundImage = 'url(' + ART.seal + ')';
      box.appendChild(s);
    }
    $('chhint').textContent = R ? '' : left ? 'Hold to break the seal' + (left > 1 ? 's' : '') : 'Tap the chest to open it';
    $('chhint').classList.add('on');
  }
  var altar = $('chaltar');
  function commit() {                                            // the first touch opens it on the server
    if (R || phase !== 'seal' || commit.sent) return;
    commit.sent = true;
    request('/chests/open', {item: T.item, count: count, nonce: commit.nonce || (commit.nonce = nonce())}, function (r) {
      R = r; commit.nonce = null; commit.sent = false;
      if (left <= 0) burst();
    }, function () { commit.sent = false; commit.nonce = null; back(); });
  }
  function breakOne() {
    var box = $('chseals'), s = box.querySelector('.cseal:not(.gone)');
    if (s) { s.classList.add('gone'); if (ART.crack) s.style.backgroundImage = 'url(' + ART.crack + ')'; }
    left -= 1; fs('block'); fs('stun', null, 40);
    $('chbox').classList.remove('jolt'); void $('chbox').offsetWidth; $('chbox').classList.add('jolt');
    if (left <= 0) { stopHold(); $('chhint').classList.remove('on'); if (R) burst(); else $('chhint').textContent = ''; }
  }
  function startHold(e) {
    if (phase !== 'seal' || main.dataset.view !== 'vault') return;
    if (e) e.preventDefault();
    commit();
    if (left <= 0) { if (R) burst(); return; }
    breakOne();                                                  // a tap breaks one at once
    if (left <= 0) return;
    holdAt = performance.now();
    holding = setInterval(function () { if (performance.now() - holdAt >= HOLD) { holdAt = performance.now(); breakOne(); } }, 60);
  }
  function stopHold() { if (holding) { clearInterval(holding); holding = null; } }
  altar.addEventListener('pointerdown', startHold);
  ['pointerup', 'pointerleave', 'pointercancel'].forEach(function (ev) { altar.addEventListener(ev, stopHold); });
  document.addEventListener('keydown', function (e) { if ((e.key === ' ' || e.key === 'Enter') && !e.repeat && main.dataset.view === 'vault' && phase === 'seal') startHold(e); });
  document.addEventListener('keyup', function (e) { if (e.key === ' ' || e.key === 'Enter') stopHold(); });

  /* the burst: the chest shakes, light leaks out, then the burst of light (the chest's colour) and its sound */
  function burst() {
    if (phase !== 'seal' || !R) return;
    phase = 'burst';
    $('chhint').classList.remove('on'); $('chskip').hidden = false;
    var big = T.key === 'mythic' || T.key === 'legendary';
    var plan = quick ? null : RITES[T.key];                     // Epic, Legendary, Mythic: their own opening first
    if (T.key === 'mythic') $('chdark').className = 'chdark on';
    $('chbox').className = 'chbox shake' + (T.key === 'mythic' ? ' float' : '');
    var wait = quick ? 0 : plan ? plan.open : (big ? 1300 : 800);
    if (plan) rite = {key: T.key, t0: performance.now(), plan: plan}, plan.start();
    later(function () {
      flash(big ? 0.7 : 0.5);
      $('chbox').className = 'chbox open' + (T.key === 'mythic' ? ' floated' : '');      // the lid snaps open
      fs('block'); sparks(big ? 90 : 50);
      later(function () { $('chbox').classList.add('rest'); }, 1600);
      if (burstV && !quick) { try { burstV.currentTime = 0; } catch (e) {} var p = burstV.play(); if (p && p.catch) p.catch(function () {}); }
      audio(ART.burst_sound, soundVol * 0.9); fs('boom');
      if (plan && plan.opened) plan.opened();
      later(cards, quick ? 200 : plan ? plan.cards : 900);
    }, wait);
  }
  function flash(a) {
    var el = $('chflash'); el.style.background = 'radial-gradient(circle at 50% 58%, #fff, ' + T.color + ' 30%, transparent 70%)';
    el.style.transition = 'none'; el.style.opacity = reduced ? Math.min(a, 0.3) : a; void el.offsetWidth;
    el.style.transition = 'opacity 900ms ease-out'; el.style.opacity = 0;
  }
  /* the burst video is light on black: drawn added onto the scene and tinted to the chest's colour */
  var tintC = document.createElement('canvas'), tc = tintC.getContext('2d');
  function rgb(c) { var m = /(\d+)\D+(\d+)\D+(\d+)/.exec(c || ''); return m ? [+m[1], +m[2], +m[3]] : [255, 220, 150]; }
  /* where the light comes out: the open chest's mouth (its glowing inside, 53% down the chest picture) */
  var MOUTH = 0.53, BURST_FOOT = 0.985, BURST_WIDE = 2.8;
  function mouth() {
    var r = $('chbox').getBoundingClientRect(), dpr = fxc.width / Math.max(1, fxc.getBoundingClientRect().width);
    return {x: (r.left + r.width / 2) * dpr, y: (r.top + r.height * MOUTH) * dpr, w: r.width * dpr};
  }
  /* the burst video is a fountain of light rising from the middle of its bottom edge: that point is set on the
     chest's mouth, and the video sized to the chest, so the light pours out of the chest and nowhere else */
  function drawVideo(v, alpha) {
    var m = mouth(), w = Math.min(m.w * BURST_WIDE, fxc.width * 1.3), h = w * 720 / 1280, x = m.x - w / 2, y = m.y - h * BURST_FOOT;
    tintC.width = 640; tintC.height = 360;
    tc.globalCompositeOperation = 'source-over'; tc.drawImage(v, 0, 0, 640, 360);
    var c = rgb(T.color);
    tc.globalCompositeOperation = 'multiply'; tc.fillStyle = 'rgb(' + c.map(function (x) { return Math.min(255, Math.round(x * 0.6 + 110)); }) + ')'; tc.fillRect(0, 0, 640, 360);
    fx.globalCompositeOperation = 'lighter'; fx.globalAlpha = alpha; fx.drawImage(tintC, x, y, w, h); fx.globalAlpha = 1; fx.globalCompositeOperation = 'source-over';
  }
  /* sparks thrown up out of the open chest, in its colour, falling back as they fade */
  var motes = [];
  function sparks(n) {
    if (reduced) n = Math.round(n / 4);
    var m = mouth(), dpr = fxc.width / Math.max(1, fxc.getBoundingClientRect().width);
    var x = m.x, y = m.y, w = m.w * 0.32, t = performance.now();
    for (var i = 0; i < n; i++) motes.push({x: x + (Math.random() - 0.5) * w, y: y, vx: (Math.random() - 0.5) * 5 * dpr,
      vy: -(4 + Math.random() * 9) * dpr, t: t, life: 900 + Math.random() * 900, s: (1.5 + Math.random() * 2.5) * dpr});
  }
  /* ── Epic, Legendary and Mythic: their own opening (docs/web.md "Opening a chest") ──────────────
     SHOAIB's pictures (art/chest/rite, light on black, every edge faded) drawn added onto the scene round the chest's
     mouth, moved, turned and faded in code; the sounds are made here too. Each plan says when the lid opens (`open`
     ms after the start), when the rewards come (`cards` ms after the lid), and draws itself every frame (`draw(t)`).
     Skip ends it at once; Quick opening leaves it out. */
  var RITE = ART.rite || {}, rite = null, shards = [], rain = [];
  function pic(src) { if (!src) return null; var i = new Image(); i.decoding = 'async'; i.src = src; return i; }
  var P = {seal: pic(RITE.seal), dragon: pic(RITE.dragon), beam: pic(RITE.beam), crack: pic(RITE.crack), galaxy: pic(RITE.galaxy)};
  if (RITE.stamp) $('chbannerseal').src = RITE.stamp;
  if (RITE.ring) $('chring').src = RITE.ring;
  /* the rune circle on the altar: an image behind the chest (not on the canvas, which is in front of it), its middle
     on the chest's foot (86% down the chest picture), lying flat (squashed to `flat` of its height) and turning */
  function ring(size, lift, turn, alpha, flat) {
    var el = $('chring'), box = $('chbox');
    if (alpha <= 0.002) { el.style.opacity = 0; return; }
    var cx = box.offsetLeft + box.offsetWidth / 2, cy = box.offsetTop + box.offsetHeight * 0.86 - lift;
    el.style.width = size + 'px'; el.style.left = (cx - size / 2) + 'px'; el.style.top = (cy - size / 2) + 'px';
    el.style.transform = 'scaleY(' + flat + ') rotate(' + turn + 'rad)'; el.style.opacity = Math.min(1, alpha);
    el.style.filter = alpha > 1 ? 'brightness(' + alpha.toFixed(2) + ')' : '';
  }
  function ease(k) { k = Math.max(0, Math.min(1, k)); return k * k * (3 - 2 * k); }
  function span(t, a, b) { return Math.max(0, Math.min(1, (t - a) / (b - a))); }
  function ok(im) { return im && im.complete && im.naturalWidth; }
  function blit(im, x, y, w, h, alpha, turn, flat) {            // a light picture added onto the scene, round (x, y);
    if (!ok(im) || alpha <= 0.002 || w < 1) return;            // flat: lying on the floor, seen at a slant
    fx.save(); fx.globalCompositeOperation = 'lighter'; fx.globalAlpha = Math.min(1, alpha);
    fx.translate(x, y); if (flat) fx.scale(1, flat); if (turn) fx.rotate(turn); fx.drawImage(im, -w / 2, -h / 2, w, h); fx.restore();
  }
  function quake(on, hard) { $('chvaultstage').classList.toggle('chquake', !!on); $('chvaultstage').classList.toggle('hard', !!hard); }
  function banner(word, line, color) {
    var b = $('chbanner'); $('chbannerw').textContent = word; $('chbanners').textContent = line;
    b.style.setProperty('--bc', color); b.hidden = false; b.className = 'chbanner'; void b.offsetWidth; b.className = 'chbanner go';
    later(function () { b.className = 'chbanner go out'; }, 3400);
    later(function () { b.hidden = true; }, 4300);
  }
  function endRite() {
    rite = null; shards = []; rain = []; quake(false); $('chbanner').hidden = true; SFX.stop(); $('chring').style.opacity = 0;
    if (amb) amb.volume = Math.min(1, soundVol * 0.7);
  }

  /* sounds made in code: a hum, crackles, shattering glass, a whoosh, a roar, thunder, a choir and a deep boom */
  var SFX = (function () {
    var live = [];
    function ctx() { var C = window.AudioContext || window.webkitAudioContext; AC = AC || new C(); if (AC.state === 'suspended') AC.resume(); return AC; }
    function noise(sec) {
      var c = ctx(), b = c.createBuffer(1, Math.ceil(c.sampleRate * sec), c.sampleRate), d = b.getChannelData(0);
      for (var i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
      var s = c.createBufferSource(); s.buffer = b; return s;
    }
    function out(vol) { var c = ctx(), g = c.createGain(); g.gain.value = 0.0001; g.connect(c.destination); return g; }
    function env(g, at, peak, attack, hold, release) {
      var t = ctx().currentTime + at, v = Math.max(0.0001, peak * soundVol);
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(v, t + attack);
      g.gain.setValueAtTime(v, t + attack + hold); g.gain.exponentialRampToValueAtTime(0.0001, t + attack + hold + release);
      return t + attack + hold + release;
    }
    function play(src, at, end) { var t = ctx().currentTime + at; src.start(t); src.stop(end + 0.05); live.push(src); }
    function filt(type, f, q) { var x = ctx().createBiquadFilter(); x.type = type; x.frequency.value = f; if (q) x.Q.value = q; return x; }
    function go(fn) { if (!soundOn) return; try { fn(); } catch (e) {} }
    return {
      stop: function () { live.forEach(function (s) { try { s.stop(); } catch (e) {} }); live = []; },
      hum: function (at, dur, f0, f1, vol) { go(function () {          // a deep magical hum rising
        [1, 1.006, 2.001].forEach(function (m, i) {
          var o = ctx().createOscillator(), g = out(); o.type = i === 2 ? 'triangle' : 'sine';
          var t = ctx().currentTime + at; o.frequency.setValueAtTime(f0 * m, t); o.frequency.exponentialRampToValueAtTime(f1 * m, t + dur);
          o.connect(g); play(o, at, env(g, at, (vol || 0.12) / (i ? 2 : 1), dur * 0.7, dur * 0.25, 0.35));
        });
      }); },
      crackle: function (at, vol) { go(function () {
        var n = noise(0.08), f = filt('highpass', 2800), g = out(); n.connect(f); f.connect(g);
        play(n, at, env(g, at, vol || 0.18, 0.003, 0.01, 0.06));
      }); },
      shatter: function (at) { go(function () {                         // glass breaking: a bright burst and pings
        var n = noise(0.9), f = filt('bandpass', 4200, 0.8), g = out(); n.connect(f); f.connect(g); play(n, at, env(g, at, 0.35, 0.004, 0.03, 0.75));
        for (var i = 0; i < 9; i++) tone(2200 + Math.random() * 2600, at + Math.random() * 0.35, 0.5, 0.06, 'sine');
      }); },
      whoosh: function (at, dur, f0, f1, vol) { go(function () {
        var n = noise(dur + 0.3), f = filt('bandpass', f0, 1.2), g = out(), t = ctx().currentTime + at;
        f.frequency.setValueAtTime(f0, t); f.frequency.exponentialRampToValueAtTime(f1, t + dur);
        n.connect(f); f.connect(g); play(n, at, env(g, at, vol || 0.3, dur * 0.6, dur * 0.2, dur * 0.4));
      }); },
      roar: function (at) { go(function () {                            // a dragon's roar: a growl gliding down
        var o = ctx().createOscillator(), o2 = ctx().createOscillator(), f = filt('lowpass', 900, 3), g = out(), t = ctx().currentTime + at;
        o.type = 'sawtooth'; o2.type = 'sawtooth';
        o.frequency.setValueAtTime(150, t); o.frequency.exponentialRampToValueAtTime(70, t + 1.4);
        o2.frequency.setValueAtTime(153, t); o2.frequency.exponentialRampToValueAtTime(68, t + 1.4);
        var lfo = ctx().createOscillator(), lg = ctx().createGain(); lfo.frequency.value = 23; lg.gain.value = 30; lfo.connect(lg); lg.connect(o.frequency);
        o.connect(f); o2.connect(f); f.connect(g); var end = env(g, at, 0.3, 0.12, 0.7, 0.7);
        play(o, at, end); play(o2, at, end); play(lfo, at, end);
        var n = noise(1.6), nf = filt('bandpass', 700, 0.7), ng = out(); n.connect(nf); nf.connect(ng); play(n, at, env(ng, at, 0.22, 0.1, 0.6, 0.8));
      }); },
      boom: function (at, vol) { go(function () {                        // a deep impact
        var o = ctx().createOscillator(), g = out(), t = ctx().currentTime + at; o.type = 'sine';
        o.frequency.setValueAtTime(90, t); o.frequency.exponentialRampToValueAtTime(28, t + 1.6);
        o.connect(g); play(o, at, env(g, at, vol || 0.6, 0.01, 0.15, 1.6));
        var n = noise(2), f = filt('lowpass', 500), ng = out(); n.connect(f); f.connect(ng); play(n, at, env(ng, at, (vol || 0.6) * 0.5, 0.01, 0.1, 1.8));
      }); },
      rumble: function (at, dur, vol) { go(function () {
        var n = noise(dur + 1), f = filt('lowpass', 140), g = out(); n.connect(f); f.connect(g); play(n, at, env(g, at, vol || 0.35, dur * 0.5, dur * 0.3, dur * 0.4));
      }); },
      thunder: function (at) { go(function () {                         // a crack, then the roll
        var n = noise(0.3), f = filt('highpass', 1800), g = out(); n.connect(f); f.connect(g); play(n, at, env(g, at, 0.5, 0.002, 0.04, 0.25));
        var r = noise(3), rf = filt('lowpass', 600), rg = out(), t = ctx().currentTime + at; rf.frequency.setValueAtTime(1200, t); rf.frequency.exponentialRampToValueAtTime(120, t + 2.6);
        r.connect(rf); rf.connect(rg); play(r, at, env(rg, at + 0.05, 0.55, 0.03, 0.4, 2.3));
      }); },
      choir: function (at, dur) { go(function () {                      // a rising heavenly chord
        [220, 277.2, 329.6, 440, 554.4].forEach(function (f, i) {
          var o = ctx().createOscillator(), g = out(), v = ctx().createOscillator(), vg = ctx().createGain();
          o.type = 'sine'; o.frequency.value = f; v.frequency.value = 5 + i * 0.4; vg.gain.value = f * 0.006; v.connect(vg); vg.connect(o.frequency);
          o.connect(g); var end = env(g, at + i * 0.12, 0.05, dur * 0.8, dur * 0.1, 0.8); play(o, at + i * 0.12, end); play(v, at + i * 0.12, end);
        });
      }); },
      chimes: function (at) { go(function () { [1568, 1976, 2349, 3136].forEach(function (f, i) { tone(f, at + i * 0.11, 1.4, 0.08, 'sine'); }); }); }
    };
  })();

  /* Epic: a purple rune seal turns over the chest, fills with lightning and shatters */
  function epicPlan() {
    return {open: 3300, cards: 1100,
      start: function () {
        $('chdark').className = 'chdark on half';
        SFX.hum(0, 2.9, 70, 190, 0.14);
        for (var i = 0; i < 9; i++) SFX.crackle(1.0 + i * 0.2 + Math.random() * 0.1, 0.12 + i * 0.015);
        SFX.shatter(2.95); later(function () { quake(true); }, 1500); later(function () { quake(false); }, 2950);
        later(function () { flash(0.75); spawnShards(); }, 2950);
      },
      draw: function (t, m) {
        var k = t < 2950 ? ease(span(t, 0, 900)) : 1 - ease(span(t, 2950, 3500));
        var grow = t < 2950 ? 0.75 + 0.25 * ease(span(t, 0, 1200)) + 0.05 * Math.sin(t / 90) * span(t, 1500, 2950)
                            : 1.05 + 0.6 * ease(span(t, 2950, 3500));
        var spin = t / 1000 * (0.4 + 2.6 * span(t, 900, 2950) * span(t, 900, 2950));
        var bw = $('chbox').offsetWidth, glow = 0.85 + 0.35 * span(t, 1500, 2950) + 0.12 * Math.sin(t / 70) * span(t, 1500, 2950);
        var lift = bw * 0.5 * ease(span(t, 2950, 3500));          // the seal rises from the altar as it breaks
        ring(bw * 2.0 * grow, lift, spin, k * glow, 0.3);         // a magic circle on the altar, the chest standing on it
        if (t > 1500 && t < 2950 && Math.random() < 0.35) bolt(m, '#C9A3FF', m.w * 0.9);
      }
    };
  }
  /* Legendary: a golden dragon of light gathers round the chest, roars, and dives into it */
  function legendaryPlan() {
    return {open: 4300, cards: 1500,
      start: function () {
        $('chdark').className = 'chdark on half'; quake(true); later(function () { quake(false); }, 700);
        SFX.rumble(0, 1.2, 0.3); SFX.whoosh(0.5, 1.9, 220, 1400, 0.25);
        SFX.roar(2.3); later(function () { flash(0.55); quake(true, false); }, 2350); later(function () { quake(false); }, 3100);
        SFX.whoosh(3.3, 0.9, 1800, 160, 0.32); SFX.boom(4.25, 0.55); SFX.chimes(4.45);
      },
      opened: function () { goldRain(); },
      draw: function (t, m) {
        var come = ease(span(t, 500, 2300)), dive = ease(span(t, 3300, 4250));
        var roar = t > 2300 && t < 3300 ? Math.sin(span(t, 2300, 3300) * Math.PI) : 0;
        var size = Math.min(m.w * (2.0 + 0.2 * come + 0.15 * roar), fxc.height * 0.82) * (1 - 0.88 * dive);
        var turn = -0.9 * (1 - come) + 0.08 * Math.sin(t / 600) + 2.2 * dive;
        var y = Math.max(size * 0.48, m.y - m.w * 0.25 * (1 - dive)) * (1 - dive) + (m.y + m.w * 0.05) * dive;
        blit(P.dragon, m.x, y, size, size, come * (1 - dive * 0.7) * (1 + 0.5 * roar), turn);
        if (roar) blit(P.dragon, m.x, y, size * 1.12, size * 1.12, roar * 0.35, turn + 0.05);
      }
    };
  }
  /* Mythic: the room goes dark, the sky cracks open, a beam of heavenly light strikes the chest, it trembles, the
     heavens burst into a galaxy, the lid flies open, and the 天 seal stamps the moment */
  function mythicPlan() {
    return {open: 7600, cards: 4200,
      start: function () {
        $('chdark').className = 'chdark on deep'; if (amb) amb.volume = Math.min(1, soundVol * 0.12);
        SFX.rumble(0.9, 2.2, 0.45); later(function () { quake(true); }, 1000); later(function () { quake(false); }, 2600);
        SFX.thunder(2.75); later(function () { flash(0.9); quake(true, true); }, 2800); later(function () { quake(false); }, 3500);
        SFX.choir(3.2, 3.6); SFX.hum(3.2, 4.1, 55, 160, 0.16);
        later(function () { quake(true); }, 4600); later(function () { quake(true, true); }, 6200);
        SFX.boom(7.0, 0.8); SFX.whoosh(6.4, 0.6, 300, 3000, 0.3);
        later(function () { quake(false); flash(1); whiteout(); }, 7000);
      },
      opened: function () {
        later(function () { banner('MYTHIC', 'The heavens answer', '#FF6B4A'); SFX.boom(0, 0.55); SFX.chimes(0.15); }, 700);
      },
      draw: function (t, m) {
        var W = fxc.width, H = fxc.height;
        var crack = ease(span(t, 900, 2200)) * (1 - ease(span(t, 7000, 8200)));
        var cw = Math.min(Math.max(W * 0.9, Math.min(W * 1.6, m.w * 2.8)), m.w * 2.9), ch = cw * 480 / 1100;
        var cy = Math.min(ch * 0.42, m.y - m.w * 0.6 - ch * 0.28);      // high in the sky, above the chest, wider than a phone
        blit(P.crack, m.x, cy, cw, ch, crack * (0.9 + 0.1 * Math.sin(t / 50) * (t < 2200 ? 1 : 0.3)));
        var drop = ease(span(t, 2200, 2800)), fade = 1 - ease(span(t, 7000, 7900));
        if (drop > 0) {                                           // the beam, from the crack down onto the chest
          var top = cy + ch * 0.12, len = (m.y - top) * drop, bw = m.w * (1.5 + 0.15 * Math.sin(t / 60) * span(t, 2800, 7000));
          if (ok(P.beam) && len > 2) {
            fx.save(); fx.globalCompositeOperation = 'lighter'; fx.globalAlpha = fade * (0.9 + 0.1 * Math.sin(t / 37));
            fx.drawImage(P.beam, m.x - bw / 2, top, bw, len); fx.restore();
          }
          if (t > 2800 && t < 7000 && Math.random() < 0.25) bolt(m, '#FFD2A0', m.w * 0.7, top);
          if (t > 2800 && t < 7000 && Math.random() < 0.5) sparks(1);
        }
        var g = ease(span(t, 7000, 9400)), gf = t < 9400 ? 1 : 1 - 0.75 * ease(span(t, 9400, 11500));
        if (t > 7000) {                                           // the galaxy bursts out of the chest and stays, slowly
          var size = m.w * (0.4 + 3.4 * g), spin = (t - 7000) / 1000 * (0.9 - 0.6 * g);
          blit(P.galaxy, m.x, m.y - m.w * 0.15, size, size, (0.85 - 0.3 * g) * gf, spin);
        }
      }
    };
  }
  var RITES = {epic: epicPlan(), legendary: legendaryPlan(), mythic: mythicPlan()};
  if (reduced) RITES = {};                                     // reduced motion: the plain opening

  function bolt(m, color, reach, fromY) {                     // a short jagged lightning arc near the chest
    var x = m.x + (Math.random() - 0.5) * reach, y = fromY !== undefined ? fromY + Math.random() * (m.y - fromY) : m.y - Math.random() * reach * 0.5;
    fx.save(); fx.globalCompositeOperation = 'lighter'; fx.strokeStyle = color; fx.lineWidth = Math.max(1, m.w / 260); fx.globalAlpha = 0.85;
    fx.shadowColor = color; fx.shadowBlur = m.w / 30; fx.beginPath(); fx.moveTo(x, y);
    var a = Math.random() * Math.PI * 2, len = reach * (0.15 + Math.random() * 0.25);
    for (var i = 0; i < 6; i++) { x += Math.cos(a) * len / 6 + (Math.random() - 0.5) * len / 5; y += Math.sin(a) * len / 6 + (Math.random() - 0.5) * len / 5; fx.lineTo(x, y); }
    fx.stroke(); fx.restore();
  }
  function spawnShards() {                                    // the seal breaks into purple shards
    var m = mouth(), t = performance.now(), n = reduced ? 20 : 70;
    for (var i = 0; i < n; i++) {
      var a = Math.random() * Math.PI * 2, v = (0.4 + Math.random()) * m.w / 55;
      shards.push({x: m.x + Math.cos(a) * m.w * 0.9, y: m.y + m.w * 0.33 - m.w * 0.5 + Math.sin(a) * m.w * 0.27, vx: Math.cos(a) * v, vy: Math.sin(a) * v * 0.7 - m.w / 250,
                   s: m.w * (0.015 + Math.random() * 0.03), r: Math.random() * 6, vr: (Math.random() - 0.5) * 0.3, t: t, life: 900 + Math.random() * 700});
    }
  }
  function goldRain() {                                       // gold motes drifting down for a few seconds
    var W = fxc.width, t = performance.now(), m = mouth();
    for (var i = 0; i < (reduced ? 25 : 110); i++) rain.push({x: m.x + (Math.random() - 0.5) * m.w * 4, y: -Math.random() * fxc.height * 0.8,
      vy: (0.6 + Math.random() * 1.4) * W / 1400, s: (1 + Math.random() * 2.2) * W / 1400, t: t + Math.random() * 1800, life: 2600 + Math.random() * 1500, ph: Math.random() * 6});
  }
  function whiteout() { var el = $('chflash'); el.style.transition = 'none'; el.style.background = '#fff'; el.style.opacity = reduced ? 0.3 : 0.95; void el.offsetWidth; el.style.transition = 'opacity 1400ms ease-out'; el.style.opacity = 0; }
  function drawRite(now) {
    if (rite) rite.plan.draw(now - rite.t0, mouth());
    if (shards.length) {
      fx.save(); fx.globalCompositeOperation = 'lighter';
      shards = shards.filter(function (s) {
        var k = (now - s.t) / s.life; if (k >= 1) return false;
        s.x += s.vx; s.y += s.vy; s.vy += fxc.width / 9000; s.r += s.vr;
        fx.save(); fx.translate(s.x, s.y); fx.rotate(s.r); fx.globalAlpha = 1 - k; fx.fillStyle = k < 0.3 ? '#F2E4FF' : '#B67CFF';
        fx.beginPath(); fx.moveTo(0, -s.s); fx.lineTo(s.s * 0.6, s.s * 0.4); fx.lineTo(-s.s * 0.5, s.s * 0.7); fx.closePath(); fx.fill(); fx.restore();
        return true;
      });
      fx.restore();
    }
    if (rain.length) {
      fx.save(); fx.globalCompositeOperation = 'lighter';
      rain = rain.filter(function (d) {
        var k = (now - d.t) / d.life; if (k >= 1) return false; if (k < 0) return true;
        d.y += d.vy; var x = d.x + Math.sin(now / 500 + d.ph) * d.s * 4;
        fx.globalAlpha = Math.sin(k * Math.PI) * 0.9; fx.fillStyle = '#FFE39A';
        fx.beginPath(); fx.arc(x, d.y, d.s, 0, 7); fx.fill();
        return true;
      });
      fx.restore();
    }
  }

  function frame(now) {
    fx.setTransform(1, 0, 0, 1, 0, 0); fx.clearRect(0, 0, fxc.width, fxc.height);
    drawRite(now);
    if (burstV && !burstV.paused && !burstV.ended && burstV.readyState >= 2) drawVideo(burstV, 1);
    if (motes.length) {
      var c = rgb(T && T.color);
      fx.globalCompositeOperation = 'lighter';
      motes = motes.filter(function (m) {
        var k = (now - m.t) / m.life; if (k >= 1) return false;
        m.x += m.vx; m.y += m.vy; m.vy += 0.22 * (fxc.width / 1440); m.vx *= 0.985;
        fx.fillStyle = 'rgba(' + c.map(function (v) { return Math.min(255, v + 90); }) + ',' + (1 - k) + ')';
        fx.beginPath(); fx.arc(m.x, m.y, m.s * (1 - k * 0.5), 0, 7); fx.fill();
        return true;
      });
      fx.globalCompositeOperation = 'source-over';
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  /* the rewards: coins first, then a jade slip each, all alike, turning over worst first; Open all groups them */
  var queue = [], shown = [];
  function cards() {
    phase = 'cards';
    setTimeout(function () { $('chdark').className = 'chdark'; }, 1200);     // the Mythic chest's darkness lifts
    var list = count > 1 ? R.summary.slice().reverse() : R.chests[0].rewards;
    var box = $('chcards'); box.innerHTML = ''; box.className = 'chcards' + (list.length > 6 ? ' many' : '') + (list.length > 14 ? ' lots' : '');
    queue = list.map(function (r, i) { var el = card(r); el.style.setProperty('--i', i); box.appendChild(el); return {r: r, el: el}; });
    coins(R.coins);
    later(next, quick ? 150 : 650);
  }
  function card(r) {
    var el = document.createElement('div'); el.className = 'ccard r-' + r.rarity.toLowerCase();
    el.style.setProperty('--rc', r.color);
    el.innerHTML = '<div class="cin"><div class="cback"></div><div class="cfront"><span class="cband"></span><img alt=""><b></b><small class="ck"></small><small class="cl"></small><i class="cq"></i></div></div>';
    if (ART.slip) el.querySelector('.cback').style.backgroundImage = 'url(' + ART.slip + ')';
    var img = el.querySelector('img'); if (r.picture) img.src = r.picture; else img.remove();
    el.querySelector('b').textContent = r.name;
    el.querySelector('.ck').textContent = r.rarity + ' · ' + r.kind;
    el.querySelector('.cl').textContent = r.lost ? 'Left behind: the bag was full' : (r.line || '');
    el.querySelector('.cq').textContent = r.qty > 1 ? '×' + r.qty : '';
    el.title = r.name;
    return el;
  }
  function coins(n) {
    var box = $('chcoins'), b = $('chcoinsn'); box.hidden = false; box.classList.remove('go'); void box.offsetWidth; box.classList.add('go');
    var t0 = performance.now(), dur = quick ? 300 : Math.min(1400, 500 + n / 4);
    for (var i = 0; i < 6; i++) tone(1400 + i * 90, i * 0.09, 0.12, 0.12, 'sine');
    (function up() { var k = Math.min(1, (performance.now() - t0) / dur); b.textContent = Math.round(n * (1 - Math.pow(1 - k, 3))).toLocaleString(); if (k < 1) requestAnimationFrame(up); })();
  }
  function next() {
    if (phase !== 'cards') return;
    var q = queue.shift();
    if (!q) { later(summary, quick ? 200 : 900); return; }
    q.el.classList.add('flip'); shown.push(q);
    var rank = q.r.rank;
    tone(RANK_NOTE[rank] || 523, 0, 0.22, 0.2 + rank * 0.03);
    if (rank >= 3) tone((RANK_NOTE[rank] || 880) * 1.5, 0.08, 0.35, 0.15, 'sine');
    if (q.r.rarity === 'Mythical' && !reduced) { $('chvault').classList.remove('tremor'); void $('chvault').offsetWidth; $('chvault').classList.add('tremor'); }
    if (!quick && rank >= 3) { later(function () { spotlight(q.r); }, 520); return; }
    later(next, quick ? 60 : (count > 1 ? 160 : 430));
  }
  /* Epic and better: the card rises to the middle with its flavour line; Legendary and Mythical fill the screen,
     the ring of light turning behind them with its own sound */
  var spotOn = false, spotV = null, glowSnd = null;
  function spotlight(r) {
    phase = 'spot'; spotOn = true;
    var box = $('chspot'), big = r.rank >= 4;
    box.className = 'chspot r-' + r.rarity.toLowerCase() + (big ? ' big' : '');
    box.style.setProperty('--rc', r.color); box.hidden = false;
    var c = card(r); c.classList.add('flip');
    $('chspotcard').innerHTML = ''; $('chspotcard').appendChild(c);
    $('chflavor').textContent = r.flavor || '';
    if (big) {
      fs('victory'); glowSnd = audio(ART.glow_sound, soundVol * 0.9);
      spotV = glowIn; if (spotV) { try { spotV.currentTime = 0; } catch (e) {} var p = spotV.play(); if (p && p.catch) p.catch(function () {}); }
      spotGlow();
    } else { fs('heal'); tone(1175, 0.05, 0.6, 0.18, 'sine'); }
    later(endSpot, big ? 4200 : 2400);
  }
  function spotGlow() {                                             // the ring: once in, then its loop
    var cv = $('chspotglow'), x = cv.getContext('2d'), c = rgb(getComputedStyle($('chspot')).getPropertyValue('--rc'));
    (function draw() {
      if (!spotOn) { x.clearRect(0, 0, cv.width, cv.height); return; }
      var r = cv.getBoundingClientRect(); cv.width = r.width; cv.height = r.height;
      var v = spotV && spotV.ended && glowV ? glowV : spotV;
      if (spotV && spotV.ended && glowV && glowV.paused) { var p = glowV.play(); if (p && p.catch) p.catch(function () {}); }
      if (v && v.readyState >= 2) {
        var k = Math.max(r.width / 1280, r.height / 720), w = 1280 * k, h = 720 * k;
        tintC.width = 640; tintC.height = 360; tc.globalCompositeOperation = 'source-over'; tc.drawImage(v, 0, 0, 640, 360);
        tc.globalCompositeOperation = 'multiply'; tc.fillStyle = 'rgb(' + c.map(function (q) { return Math.min(255, Math.round(q * 0.55 + 120)); }) + ')'; tc.fillRect(0, 0, 640, 360);
        x.globalCompositeOperation = 'lighter'; x.drawImage(tintC, (r.width - w) / 2, (r.height - h) / 2, w, h);
      }
      requestAnimationFrame(draw);
    })();
  }
  function endSpot() {
    if (!spotOn) return;
    spotOn = false; $('chspot').hidden = true;
    if (glowV) glowV.pause(); if (glowSnd) glowSnd.pause();
    phase = 'cards'; later(next, 260);
  }
  $('chspot').addEventListener('click', function () { timers.forEach(clearTimeout); timers = []; endSpot(); });

  function skip() {
    timers.forEach(clearTimeout); timers = []; endRite();
    spotOn = false; $('chspot').hidden = true; if (glowSnd) glowSnd.pause();
    if (phase === 'seal' && R) { phase = 'cards'; }
    if (phase === 'burst') cards();
    queue.forEach(function (q) { q.el.classList.add('flip'); }); queue = [];
    summary();
  }
  $('chskip').addEventListener('click', function () { if (R) skip(); });

  function summary() {
    if (phase === 'summary') return;
    later(endRite, 400);
    phase = 'summary'; $('chskip').hidden = true;
    var best = R.best, word = ['', '', 'A fine find', 'A rare treasure', 'Golden radiance', 'The heavens tremble'][Math.max(0, best)] || '';
    $('chsumk').textContent = (R.opened > 1 ? R.opened + ' ' + R.name + 's opened' : R.name + ' opened').toUpperCase();
    $('chsumh').textContent = word || 'What was inside';
    var grid = $('chsumgrid'); grid.innerHTML = '';
    var coinRow = document.createElement('div'); coinRow.className = 'srow coin';
    coinRow.innerHTML = '<span class="sdot"></span><b>Lotus Coins</b><i></i>'; coinRow.querySelector('i').textContent = R.coins.toLocaleString();
    grid.appendChild(coinRow);
    R.summary.forEach(function (r) {
      var row = document.createElement('div'); row.className = 'srow r-' + r.rarity.toLowerCase() + (r.rank >= 3 ? ' top' : '') + (r.lost ? ' lost' : '');
      row.style.setProperty('--rc', r.color);
      row.innerHTML = '<img alt=""><b></b><small></small><i></i>';
      var im = row.querySelector('img'); if (r.picture) im.src = r.picture; else im.remove();
      row.querySelector('b').textContent = r.name; row.querySelector('small').textContent = r.rarity + (r.lost ? ' · left behind' : '');
      row.querySelector('i').textContent = r.qty > 1 ? '×' + r.qty : '';
      grid.appendChild(row);
    });
    var notes = [];
    R.chests.forEach(function (c) { c.notes.forEach(function (n) { if (notes.indexOf(n) < 0) notes.push(n); }); });
    if (R.opened < R.asked) notes.push('Opened ' + R.opened + ' of ' + R.asked + ': there was room in the bag for that many.');
    $('chnotes').innerHTML = notes.map(function (n) { return '<li>' + n + '</li>'; }).join('');   // the server escapes them
    var t = tierOf(R.tier);
    $('chnext').hidden = !(t && t.qty && t.fits >= 1);
    $('chnext').textContent = t && t.qty ? 'Open another (' + t.qty + ' left)' : 'Open another';
    $('chsum').hidden = false;
    fs(best >= 3 ? 'victory' : 'heal');
  }
  $('chnext').addEventListener('click', function () { var t = tierOf(R.tier); if (t && t.qty) vault(t, 1); });
  function back() {
    timers.forEach(clearTimeout); timers = []; phase = '';
    main.dataset.view = 'shelf'; $('chvault').hidden = true;
    if (amb) { amb.pause(); amb = null; }
    vbg.pause();
    drawShelf(); fit();
  }
  $('chdone').addEventListener('click', back);

  fit(); drawShelf();
  if (S.open) {                                                     // the bag's Open button: straight into the vault
    var want = SHELF.tiers.filter(function (t) { return t.item === S.open && t.qty; })[0];
    if (want) { picked = want.key; drawPick(); if (want.fits >= 1) vault(want, 1); }
  }
})();
