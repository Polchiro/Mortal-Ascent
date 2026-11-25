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
    T = t; count = n; R = already || null; phase = 'seal'; timers.forEach(clearTimeout); timers = [];
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
    if (T.key === 'mythic') $('chdark').className = 'chdark on';
    $('chbox').className = 'chbox shake' + (T.key === 'mythic' ? ' float' : '');
    var wait = quick ? 0 : (big ? 1300 : 800);
    later(function () {
      flash(big ? 0.7 : 0.5);
      $('chbox').className = 'chbox open' + (T.key === 'mythic' ? ' floated' : '');      // the lid snaps open
      fs('block'); sparks(big ? 90 : 50);
      later(function () { $('chbox').classList.add('rest'); }, 1600);
      if (burstV && !quick) { try { burstV.currentTime = 0; } catch (e) {} var p = burstV.play(); if (p && p.catch) p.catch(function () {}); }
      audio(ART.burst_sound, soundVol * 0.9); fs('boom');
      later(cards, quick ? 200 : 900);
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
  function drawVideo(v, alpha) {
    var W = fxc.width, H = fxc.height, k = Math.max(W / 1280, H / 720), w = 1280 * k, h = 720 * k, x = (W - w) / 2, y = (H - h) / 2 - H * 0.05;
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
    var r = $('chbox').getBoundingClientRect(), dpr = fxc.width / Math.max(1, fxc.getBoundingClientRect().width);
    var x = (r.left + r.width / 2) * dpr, y = (r.top + r.height * 0.42) * dpr, w = r.width * 0.32 * dpr, t = performance.now();
    for (var i = 0; i < n; i++) motes.push({x: x + (Math.random() - 0.5) * w, y: y, vx: (Math.random() - 0.5) * 5 * dpr,
      vy: -(4 + Math.random() * 9) * dpr, t: t, life: 900 + Math.random() * 900, s: (1.5 + Math.random() * 2.5) * dpr});
  }
  function frame(now) {
    fx.setTransform(1, 0, 0, 1, 0, 0); fx.clearRect(0, 0, fxc.width, fxc.height);
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
    timers.forEach(clearTimeout); timers = [];
    spotOn = false; $('chspot').hidden = true; if (glowSnd) glowSnd.pause();
    if (phase === 'seal' && R) { phase = 'cards'; }
    if (phase === 'burst') cards();
    queue.forEach(function (q) { q.el.classList.add('flip'); }); queue = [];
    summary();
  }
  $('chskip').addEventListener('click', function () { if (R) skip(); });

  function summary() {
    if (phase === 'summary') return;
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
