/* The Dantian (web/dantian_play.py, docs/web.md "The Dantian").
   The inner sea is a 1920x1080 stage that covers the screen; its glowing orb (at 960, 650) is your Dantian. Round
   it: a ring that fills with your Qi bar (gold when it presses against a gate), Qi drifting in as fast as you gather
   it, and dark wisps for toxicity. The numbers are the server's; between refreshes the Qi counts up at your rate.
   Eating a pill: the server eats it with the bot's rules, then the pill dissolves into the orb (the absorb video,
   tinted to the pill) and the numbers change as it lands. */
(function () {
  var S = JSON.parse(document.getElementById('dtstate').textContent), V = S.v, ART = S.art;
  function $(id) { return document.getElementById(id); }
  var reduced = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var soundOn = true, soundVol = 0.6;
  try {
    soundOn = localStorage.getItem('ma.sound') !== 'off';
    var v0 = parseFloat(localStorage.getItem('ma.vol')); if (v0 >= 0 && v0 <= 100) soundVol = v0 / 100;
  } catch (e0) {}
  function fs(name, arg, delay) { var F = window.FightSound; if (F) F.play(name, arg, delay); }
  function audio(url, vol, loop) {
    if (!soundOn || !url) return null;
    var a = new Audio(url); a.volume = Math.min(1, vol); a.loop = !!loop;
    var p = a.play(); if (p && p.catch) p.catch(function () {});
    return a;
  }
  var amb = null;
  function ambience() { if (!amb) amb = audio(ART.sea_sound, soundVol * 0.7, true); }
  ['pointerdown', 'keydown'].forEach(function (ev) { document.addEventListener(ev, ambience, {once: true, passive: true}); });
  function esc(t) { var d = document.createElement('div'); d.textContent = t == null ? '' : String(t); return d.innerHTML; }
  function say(t) { var el = $('dtsay'); el.textContent = t; el.classList.remove('go'); void el.offsetWidth; el.classList.add('go'); }

  /* ── the stage and the orb ─────────────────────────────────────── */
  var scene = $('dtscene'), stage = $('dtstage'), fxc = $('dtfx'), fx = fxc.getContext('2d'), ab = $('dtabsorb'), ax = ab.getContext('2d');
  var W = 0, H = 0, K = 1, OX = 0, OY = 0, DPR = 1, ORB = [960, 650], R0 = 70;
  function fit() {
    var r = scene.getBoundingClientRect(); W = r.width; H = r.height; DPR = Math.min(2, window.devicePixelRatio || 1);
    K = Math.max(W / 1920, H / 1080); OX = (W - 1920 * K) / 2; OY = (H - 1080 * K) / 2;
    stage.style.width = 1920 * K + 'px'; stage.style.height = 1080 * K + 'px'; stage.style.left = OX + 'px'; stage.style.top = OY + 'px';
    [fxc, ab].forEach(function (c) { c.width = Math.round(W * DPR); c.height = Math.round(H * DPR); c.style.width = W + 'px'; c.style.height = H + 'px'; });
  }
  window.addEventListener('resize', fit);
  function orb() { return [OX + ORB[0] * K, OY + ORB[1] * K, R0 * K]; }
  var motes = [], pulse = 0, shown = 0;
  function draw(now) {
    var o = orb(), x = o[0], y = o[1], r = o[2], pct = Math.min(1, live() / V.need), full = V.full;
    fx.setTransform(DPR, 0, 0, DPR, 0, 0); fx.clearRect(0, 0, W, H);
    /* toxicity: dark wisps circling the orb, more the higher it is */
    var tox = V.toxicity.n;
    if (tox > 0) {
      var n = Math.min(10, tox * 2);
      for (var i = 0; i < n; i++) {
        var a = now / (3200 + i * 300) + i * 1.9, rr = r * (1.25 + 0.35 * Math.sin(now / 1700 + i));
        var gx = x + Math.cos(a) * rr * 1.5, gy = y + Math.sin(a) * rr * 0.55;
        var g = fx.createRadialGradient(gx, gy, 0, gx, gy, r * 0.7);
        g.addColorStop(0, 'rgba(90,30,110,' + Math.min(0.55, 0.12 + tox * 0.07) + ')'); g.addColorStop(1, 'rgba(60,20,80,0)');
        fx.fillStyle = g; fx.fillRect(gx - r, gy - r, r * 2, r * 2);
      }
    }
    /* the ring: your bar, gold when it presses against a gate */
    var col = full ? '245,220,166' : '140,230,255';
    fx.lineCap = 'round';
    fx.strokeStyle = 'rgba(255,255,255,.12)'; fx.lineWidth = 3 * Math.max(1, K * 1.4);
    fx.beginPath(); fx.ellipse(x, y, r * 2.2, r * 0.85, 0, 0, 6.2832); fx.stroke();
    fx.strokeStyle = 'rgba(' + col + ',' + (0.75 + 0.25 * Math.sin(now / (full ? 400 : 900))) + ')';
    fx.lineWidth = 4 * Math.max(1, K * 1.4);
    fx.beginPath(); fx.ellipse(x, y, r * 2.2, r * 0.85, 0, -Math.PI / 2, -Math.PI / 2 + 6.2832 * pct); fx.stroke();
    /* the glow, and what drifts in */
    fx.globalCompositeOperation = 'lighter';
    var gl = 0.25 + pulse * 0.8 + (full ? 0.2 : 0);
    var g2 = fx.createRadialGradient(x, y, 0, x, y, r * (2.4 + pulse * 2));
    g2.addColorStop(0, 'rgba(' + col + ',' + gl + ')'); g2.addColorStop(1, 'rgba(' + col + ',0)');
    fx.fillStyle = g2; fx.fillRect(x - r * 5, y - r * 5, r * 10, r * 10);
    pulse = Math.max(0, pulse - 0.012);
    var want = reduced ? 8 : Math.max(6, Math.min(60, Math.round(8 + Math.log(1 + V.rate) * 9)));
    while (motes.length < want) motes.push({t: now - Math.random() * 3000, life: 2400 + Math.random() * 2600, a: Math.random() * 6.283, d: 0.3 + Math.random() * 0.55});
    motes = motes.filter(function (m) {
      var k = (now - m.t) / m.life; if (k >= 1) return false;
      var rr = Math.max(W, H) * m.d * (1 - k), mx = x + Math.cos(m.a + k * 1.6) * rr, my = y + Math.sin(m.a + k * 1.6) * rr * 0.45;
      fx.fillStyle = 'rgba(180,240,255,' + 0.85 * Math.sin(k * 3.14) + ')';
      fx.beginPath(); fx.arc(mx, my, (1.5 + 2 * k) * Math.max(0.7, K * 1.4), 0, 7); fx.fill();
      return true;
    });
    fx.globalCompositeOperation = 'source-over';
    absorbFrame(now);
    if (now - shown > 200) { shown = now; counter(); }
    requestAnimationFrame(draw);
  }

  /* ── the numbers: the Qi counts up at your rate between refreshes ─────── */
  var t0 = performance.now();
  function live() { return Math.min(V.need, V.qi + V.rate / 3600 * (performance.now() - t0) / 1000); }
  function counter() {
    var q = live();
    $('dtqin').textContent = q.toFixed(q >= 1000 ? 1 : 2);
    if (V.full) $('dteta').textContent = V.gate.kind === 'peak' ? 'The peak: no gate remains' : 'Full: it presses against the gate' + (V.waiting ? ' · ' + V.waiting.toLocaleString() + ' Qi waiting behind it' : '');
    else if (V.eta) {
      var left = Math.max(0, (V.need - q) / V.rate * 3600);
      $('dteta').textContent = 'Full in ' + span(left) + (V.gate.kind === 'layer' ? ' · the next layer opens on its own' : ' · then the ' + V.gate.target + ' gate');
    }
  }
  function span(s) {
    s = Math.round(s); var d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60);
    if (d) return d + 'd ' + h + 'h'; if (h) return h + 'h ' + m + 'm'; if (m) return m + 'm ' + (s % 60) + 's'; return (s % 60) + 's';
  }
  function render() {
    $('dtrate').textContent = V.rate_text; $('dtpm').textContent = V.per_min; $('dtps2').textContent = V.per_sec; $('dtps').textContent = '+' + V.per_sec;
    $('dtrows').innerHTML = V.ledger.map(function (r) {
      return '<li class="' + (r.on ? 'on' : 'off') + (r.mult ? ' mult' : '') + '"><span class="dtl"><b>' + esc(r.label) + '</b><small>' + esc(r.detail) + '</small>' +
        (r.how ? '<em>' + esc(r.how) + '</em>' : '') + '</span><i>' + esc(r.value) + '</i></li>';
    }).join('');
    $('dtformula').textContent = V.formula;
    var g = V.gate, gate = $('dtgate');
    gate.className = 'dtgate k-' + (g.look || 'none');
    gate.innerHTML = g.kind === 'layer' ? '<b>Next: the ' + esc(V.next_layer) + ' Layer</b><small>opens on its own when the bar fills</small>'
      : g.kind === 'peak' ? '<b>The Peak</b><small>no gate remains</small>'
      : '<b>Gate: ' + esc(g.target) + '</b><small>' + (V.plate.ready ? (g.kind === 'realm' ? 'Realm' : 'Phase') + ' · ' + esc(V.plate.chance) + ' chance' : V.plate.why ? esc(V.plate.why) : 'when the bar is full') + '</small>' +
        (V.plate.ready ? '<a class="dtbtn main" href="/breakthrough?from=/dantian">Break through</a>' : '');
    $('dtlayers').innerHTML = V.layers.map(function (l) {
      return '<i class="' + (l.done ? 'done' : '') + (l.now ? ' now' : '') + (l.gate ? ' g-' + l.gate : '') + '" title="Layer ' + l.n + (l.gate ? (l.gate === 'realm' ? ' · the realm gate' : ' · a phase bottleneck') : '') + '">' + l.n + '</i>';
    }).join('');
    var t = V.toxicity;
    $('dttoxn').textContent = t.n; $('dttoxz').textContent = ' · ' + t.text;
    $('dttox').className = 'dttox z-' + t.zone;
    $('dtmark').style.left = Math.min(100, t.n / 8 * 100) + '%';
    var lines = [];
    if (t.n) lines.push('−1 in ' + t.next + ' · clean in about ' + t.clean + '. One point fades every ' + t.every + ' hours.');
    else lines.push('Every pill but a Cleansing or Breakthrough pill adds 0 to 2 (fewer the more patterns it has). At 4 pills work at half strength, at 6 at a quarter.');
    if (t.cap != null) lines.push('Dao Heart: it can never go above ' + t.cap + '.');
    if (t.faster) lines.push('Your artifact makes it fade ' + t.faster + ' faster.');
    $('dttoxt').textContent = lines.join(' ');
    pills();
  }
  function pills() {
    var box = $('dtpills');
    if (!V.pills.length) { box.innerHTML = '<p class="sub">No pills in your bag. Refine them in the cauldron (Alchemy).</p>'; return; }
    box.innerHTML = '';
    V.pills.forEach(function (p) {
      var row = document.createElement('div'); row.className = 'dtpill' + (p.can ? '' : ' cant'); row.style.setProperty('--pc', p.color);
      row.innerHTML = '<img alt="" width="40" height="40"><span class="dtpn"><b></b><small></small><em></em></span>' + (p.can ? '<button class="dtbtn" type="button">Eat</button>' : '');
      if (p.picture) row.querySelector('img').src = p.picture; else row.querySelector('img').remove();
      row.querySelector('b').textContent = p.name + (p.qty > 1 ? ' ×' + p.qty : '');
      row.querySelector('small').textContent = p.kind_name + (p.patterns ? ' · ' + p.patterns + ' patterns' : '');
      row.querySelector('em').textContent = p.can ? (p.lines[0] || '') : p.why;
      if (p.can) row.querySelector('button').addEventListener('click', function () { ask(p); });
      box.appendChild(row);
    });
  }

  /* ── eating a pill ─────────────────────────────────────────────────── */
  var asking = null, busy = false;
  function ask(p) {
    asking = p;
    $('dtmimg').src = p.picture || ''; $('dtmk').textContent = p.kind_name.toUpperCase();
    $('dtmh').textContent = p.name;
    $('dtmlines').innerHTML = p.lines.map(function (l) { return '<li>' + esc(l) + '</li>'; }).join('');
    $('dtmwarn').innerHTML = p.warn.map(function (l) { return '<li>' + esc(l) + '</li>'; }).join('');
    $('dtpillcard').style.setProperty('--pc', p.color);
    $('dtmodal').hidden = false; $('dtmyes').focus(); fs('press');
  }
  $('dtmno').addEventListener('click', function () { $('dtmodal').hidden = true; asking = null; });
  $('dtmodal').addEventListener('click', function (e) { if (e.target.id === 'dtmodal') { $('dtmodal').hidden = true; asking = null; } });
  $('dtmyes').addEventListener('click', function () {
    if (!asking || busy) return;
    var p = asking; busy = true; $('dtmodal').hidden = true; ambience();
    fetch('/dantian/eat', {method: 'POST', headers: {'Content-Type': 'application/json'}, credentials: 'same-origin',
      body: JSON.stringify({item: p.id, nonce: Math.random().toString(36).slice(2)})})
      .then(function (r) { return r.json(); })
      .then(function (v) {
        if (v.gone) { location.href = '/'; return; }
        if (v.error || !v.result) { busy = false; say(v.error || 'Something went wrong.'); if (v.view) { V = v.view; t0 = performance.now(); render(); } return; }
        swallow(v.result);
      })
      .catch(function () { busy = false; say('The connection dropped. Look at your pills before you try again.'); });
  });
  /* the pill dissolves into the Dantian: the absorb video (light on black), tinted to the pill, its sound; the
     numbers change as the light sinks in */
  var absorbV = null, absorbAt = 0, absorbCol = [255, 220, 150];
  if (ART.absorb) { absorbV = document.createElement('video'); absorbV.muted = true; absorbV.playsInline = true; absorbV.setAttribute('playsinline', ''); absorbV.preload = 'auto'; absorbV.src = ART.absorb; }
  var tint = document.createElement('canvas'), tc = tint.getContext('2d');
  function rgb(hex) { var n = parseInt(hex.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
  function absorbFrame() {
    ax.setTransform(1, 0, 0, 1, 0, 0); ax.clearRect(0, 0, ab.width, ab.height);
    if (!absorbV || absorbV.paused || absorbV.ended || absorbV.readyState < 2) return;
    var o = orb(), k = K * DPR * 1.05, w = 1280 * k, h = 720 * k;
    var x = o[0] * DPR - 640 * k, y = o[1] * DPR - 610 * k;              // the light ends where it sinks: on the orb
    tint.width = 640; tint.height = 360; tc.globalCompositeOperation = 'source-over'; tc.drawImage(absorbV, 0, 0, 640, 360);
    tc.globalCompositeOperation = 'multiply'; tc.fillStyle = 'rgb(' + absorbCol.map(function (c) { return Math.min(255, Math.round(c * 0.7 + 90)); }) + ')'; tc.fillRect(0, 0, 640, 360);
    ax.drawImage(tint, x, y, w, h);
  }
  function swallow(r) {
    absorbCol = rgb(r.color);
    var lands = 3300;
    if (absorbV && !reduced) {
      try { absorbV.currentTime = 0; } catch (e) {}
      var pv = absorbV.play(); if (pv && pv.catch) pv.catch(function () {});
    } else lands = 600;
    audio(ART.absorb_sound, soundVol * 0.9);
    fs('gather');
    setTimeout(function () {
      pulse = 1; fs(r.kind === 'heaven' ? 'victory' : 'heal');
      V = r.view; t0 = performance.now(); render();
      var b = r.before, a = r.after, words = [];
      if (a.talent !== b.talent) title('TALENT RISES', b.talent + ' → ' + a.talent, 'Qi Rate ' + b.rate + ' → ' + a.rate + ' Qi/h');
      if (a.rate !== b.rate) words.push('Qi Rate ' + b.rate + ' → ' + a.rate + ' Qi/h');
      if (a.qi !== b.qi || a.layer !== b.layer) words.push(a.layer !== b.layer ? 'Your Qi floods in: ' + a.layer + ' Layer' : '+' + (a.qi - b.qi).toFixed(1) + ' Qi');
      if (a.tox !== b.tox) words.push('Toxicity ' + b.tox + ' → ' + a.tox);
      say(words.join(' · ') || r.name + ' swallowed');
      busy = false;
    }, lands);
  }
  function title(k, h, sub) {
    var t = $('dttitle'); $('dttk').textContent = k; $('dtth').textContent = h; $('dtts').textContent = sub;
    t.hidden = false; t.classList.remove('go'); void t.offsetWidth; t.classList.add('go');
    setTimeout(function () { t.hidden = true; }, 5200);
  }

  /* ── when the Qi is full: the Discord ping (the bot's own setting) and this browser ─────────────── */
  $('dtping').addEventListener('change', function () {
    var on = $('dtping').checked;
    fetch('/dantian/pings', {method: 'POST', headers: {'Content-Type': 'application/json'}, credentials: 'same-origin', body: JSON.stringify({on: on})})
      .then(function (r) { return r.json(); }).then(function (v) { $('dtping').checked = !!v.pings; say(v.pings ? 'Discord will ping you when your Qi is full' : 'No Discord pings'); });
  });
  var nb = $('dtnotify'), nw = $('dtnotifywhy');
  function notifyState() {
    var ok = 'Notification' in window, on = false;
    try { on = localStorage.getItem('ma.notify.qi') === '1'; } catch (e) {}
    nb.disabled = !ok; nb.checked = ok && on && Notification.permission === 'granted';
    nw.textContent = !ok ? 'This browser has no notifications.' : Notification.permission === 'denied' ? 'Notifications are blocked for this site in your browser settings.' : nb.checked ? 'A map page of the game must be open (a background tab is fine).' : '';
  }
  nb.addEventListener('change', function () {
    if (!nb.checked) { try { localStorage.setItem('ma.notify.qi', '0'); } catch (e) {} notifyState(); return; }
    Notification.requestPermission().then(function (p) {
      try { localStorage.setItem('ma.notify.qi', p === 'granted' ? '1' : '0'); } catch (e) {}
      notifyState();
    });
  });
  notifyState();

  setInterval(function () {                                          // the server's numbers again, now and then
    if (busy || !$('dtmodal').hidden) return;
    fetch('/dantian/view', {credentials: 'same-origin'}).then(function (r) { return r.json(); }).then(function (v) { if (v && !v.gone && !busy) { V = v; t0 = performance.now(); render(); } }).catch(function () {});
  }, 60000);

  fit(); render(); requestAnimationFrame(draw);
})();
