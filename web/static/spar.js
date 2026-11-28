/* The spar's fight screen (/spar): draws what web/spar_play.py says and acts each exchange out. It never decides
   anything: a move is sent, the server answers with what happened, and that is what is shown.

   Your cultivator plays the same frame-by-frame movements as in a beast fight (looks.py: the stance, Strike, Break,
   Guard, and the techniques' fist / palm / kick / finger / brace / deflect / sidestep), stepped by this file's own
   small player, so nothing in fight.js is touched. The Martial Master plays his own (web/spar_master.py: the stance
   he breathes in, Strike, Guard, Break, his stagger when he is hit, his bow, and the knee he takes when you beat him, each with the video's own sound), holds his tell's pose while you
   choose when he gives one, and steps to you and is knocked back in code. Without his sheets he is a still picture. */
(function () {
  var main = document.getElementById('spar');
  if (!main) return;
  var S = JSON.parse(document.getElementById('sstate').textContent);
  function $(id) { return document.getElementById(id); }
  function fs(name, arg, delay) { var F = window.FightSound; if (F) F.play(name, arg, delay); }
  if (window.FightSound) window.FightSound.voice = S.me.gender;          // his own takes of the sounds, where he has them

  var scene = main.querySelector('.bscene'), fme = $('fme'), poses = fme.querySelector('.poses');
  var fthem = $('fthem'), body = $('smbody');
  var sheets = {};
  fme.querySelectorAll('.ssheet').forEach(function (el) { sheets[el.dataset.name] = el; });
  var SPEC = S.me.sheets || {};
  var shownTurn = S.last ? S.last.turn : 0, sending = false, acting = false, wasOver = S.over;
  var left = S.left, leftAt = Date.now(), asked = 0;
  var MOVE_ICON = {strike: '/art/icons/actions/strike.webp', guard: '/art/icons/actions/guard.webp', 'break': '/art/icons/actions/break.webp'};

  (S.me.art || []).forEach(function (src) { new Image().src = src; });
  Object.keys(SPEC).forEach(function (k) { new Image().src = SPEC[k].src; });
  ['/art/fx/slash.webp', '/art/fx/break_burst.webp'].forEach(function (src) { new Image().src = src; });
  body.classList.add('breathe');

  /* ── the Master's movements, frame by frame ───────────────────── */
  var revealing = false;
  var MS = S.master.sheets ? S.master.sheets.sheets : null, msheets = {}, mMode = 'idle', mT0 = performance.now(), mPlay = null;
  fthem.querySelectorAll('.smsheet').forEach(function (el) { msheets[el.dataset.name] = el; });
  var LEAD = {strike: 800, guard: 650, 'break': 1200};           // ms he moves before his blow lands
  var soundOn = true, soundVol = 0.6;
  try {
    soundOn = localStorage.getItem('ma.sound') !== 'off';
    var v0 = parseFloat(localStorage.getItem('ma.vol')); if (v0 >= 0 && v0 <= 100) soundVol = v0 / 100;
  } catch (e0) {}
  if (MS) Object.keys(MS).forEach(function (k) { new Image().src = MS[k].src; });
  function LOUD() { return Math.min(1, soundVol * 1.6); }        // his sounds are meant to be heard over the music
  function mshow(name, f) {
    var sp = MS[name], el = msheets[name];
    f = Math.max(0, Math.min(sp.frames - 1, f));
    el.style.backgroundPosition = (sp.cols > 1 ? (f % sp.cols) / (sp.cols - 1) * 100 : 0) + '% ' +
      (sp.rows > 1 ? Math.floor(f / sp.cols) / (sp.rows - 1) * 100 : 0) + '%';
    Object.keys(msheets).forEach(function (k) { msheets[k].classList.toggle('on', k === name); });
  }
  function mframe(name, tm) {                                    // the frame at `tm` ms into the movement
    var at = MS[name].at, i = 0;
    while (i + 1 < at.length && at[i + 1] <= tm) i++;
    return i;
  }
  function mposed() {                                            // standing: breathing, or holding his tell's pose
    if (!MS) return;
    var pose = !S.over && S.tell_pose && MS[S.tell_pose] && MS[S.tell_pose].tell != null ? S.tell_pose : null;
    mMode = pose ? 'tell' : 'idle';
    if (pose) mshow(pose, MS[pose].tell);
  }
  function mloop(now) {
    if (MS) {
      if (mMode === 'idle') mshow('stance', mframe('stance', (now - mT0) % MS.stance.loop));
      else if (mMode === 'play' && mPlay) {
        var tm = (now - mPlay.t0) * mPlay.speed, last = MS[mPlay.name].at[MS[mPlay.name].frames - 1];
        mshow(mPlay.name, mframe(mPlay.name, tm));
        if (tm >= last + 120) { var cb = mPlay.done; mPlay = null; mposed(); if (cb) cb(); }
      }
    }
    requestAnimationFrame(mloop);
  }
  function mplay(name, speed, done) {                            // one movement through (his bow), then back to standing
    if (!MS || !MS[name]) { if (done) done(); return; }
    mMode = 'play'; mPlay = {name: name, speed: speed, t0: performance.now(), done: done};
    var snd = MS[name].sound;                                    // its own sound, kept in step at this speed
    if (snd && soundOn) {
      var a = new Audio(snd.src); a.volume = LOUD(); a.playbackRate = speed;
      setTimeout(function () { a.play().catch(function () {}); }, (snd.from || 0) / speed);
    }
  }
  function msound(move, HIT) {                                   // the video's own sound, its blow on the moment HIT
    var snd = MS && MS[move] && MS[move].sound;
    if (!snd || !soundOn) return false;
    var a = new Audio(snd.src), start = HIT - snd.lead;
    a.volume = LOUD();
    if (start < 0) { try { a.currentTime = -start / 1000; } catch (e1) {} }
    setTimeout(function () { a.play().catch(function () {}); }, Math.max(0, start));
    return a;
  }
  /* where he is in his movement, t ms into the exchange: he reaches `hit` exactly as the exchange is decided, and
     comes back to his stance faster than the video does */
  function mtime(move, t, HIT, soft, held, cut) {
    var sp = MS[move], x = t - HIT, tell = sp.at[sp.tell], lead = LEAD[move];
    if (cut) return Math.min(sp.hit - 330, x <= 0 ? mtime(move, t, HIT, false, held) : sp.hit);   // struck before it lands: he never lets it go
    if (soft) {                                                  // a Guard nothing lands on: up, held, down again
      if (x <= 0) return held ? tell : tell * Math.max(0, 1 + x / lead);
      return Math.max(0, tell - Math.max(0, x - 550) * 1.6);
    }
    if (x <= 0) {
      var run = lead - 250, from = Math.max(tell, sp.hit - run);
      if (x < -run) return held ? tell : tell * Math.max(0, Math.min(1, (x + lead) / 250));
      return from + (sp.hit - from) * (1 + x / run);
    }
    return sp.hit + (x < 450 ? x : 450 + (x - 450) * 2.4);
  }
  function mlength(move, soft) {                                 // ms after HIT until he is back in his stance
    var sp = MS[move];
    if (soft) return 550 + sp.at[sp.tell] / 1.6;
    return 450 + Math.max(0, sp.at[sp.frames - 1] - sp.hit - 450) / 2.4;
  }

  /* the yard alive: SHOAIB's video of it (petals falling, mist, the lanterns), behind the whole page on a wide screen
     and inside the scene on a narrow one (where the yard is drawn on the scene). Its own sound loops under the fight.
     Not with reduced motion or when the browser saves data: then the still shows, with petals made here. */
  var live = S.yard_video && !(navigator.connection && navigator.connection.saveData) &&
    !(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
  (function () {
    if (!live) return;
    var film = document.createElement('video'), narrow = window.matchMedia ? matchMedia('(max-width: 900px)') : null;
    film.muted = true; film.loop = true; film.autoplay = true; film.playsInline = true; film.preload = 'auto';
    film.setAttribute('muted', ''); film.setAttribute('playsinline', ''); film.setAttribute('aria-hidden', 'true');
    film.addEventListener('playing', function () { film.classList.add('on'); });
    film.addEventListener('error', function () { film.remove(); });
    function place() {
      if (narrow && narrow.matches) { film.className = 'sloop' + (film.classList.contains('on') ? ' on' : ''); scene.insertBefore(film, scene.firstChild); }
      else {
        film.className = 'bgloop' + (film.classList.contains('on') ? ' on' : ''); main.insertBefore(film, main.firstChild);
        if (!main.querySelector(':scope > .bgshade')) { var sh = document.createElement('div'); sh.className = 'bgshade'; main.insertBefore(sh, film.nextSibling); }
        main.classList.add('bglive');
      }
      var p = film.play(); if (p && p.catch) p.catch(function () {});
    }
    film.addEventListener('playing', function () { main.classList.add('yardlive'); });   // the video has lanterns of its own
    film.src = S.yard_video; place();
    if (narrow && narrow.addEventListener) narrow.addEventListener('change', place);
    if (S.yard_sound && window.SparMusic) window.SparMusic.ambience(S.yard_sound);
  })();

  /* petals on the wind, when the video isn't there to bring its own */
  (function () {
    var box = $('spetals');
    if (!box || S.trial || live) return;
    for (var i = 0; i < 16; i++) {
      var p = document.createElement('i'), sz = 7 + Math.random() * 7;
      p.style.left = (20 + Math.random() * 100) + '%'; p.style.width = sz + 'px'; p.style.height = sz * 0.7 + 'px';
      p.style.animationDuration = (9 + Math.random() * 9) + 's'; p.style.animationDelay = (-Math.random() * 18) + 's';
      box.appendChild(p);
    }
  })();

  /* ── small helpers ─────────────────────────────────────────────── */
  function ease(x) { return x < 0 ? 0 : x > 1 ? 1 : 1 - Math.pow(1 - x, 3); }
  function inout(x) { x = x < 0 ? 0 : x > 1 ? 1 : x; return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2; }
  function span(t, a, b) { return b <= a ? (t >= b ? 1 : 0) : Math.max(0, Math.min(1, (t - a) / (b - a))); }
  function again(el, text) { el.textContent = text; el.classList.remove('go'); void el.offsetWidth; el.classList.add('go'); }
  function info(m) { $('ititle').textContent = m.label + (m.state ? ' · ' + m.state : ''); $('itext').textContent = m.info; fitInfo(); }
  /* the panel keeps one size; when its text is longer than the panel, the bottom fades and the text scrolls */
  function fitInfo() {
    var b = document.querySelector('.sparfight .itbody'); if (!b) return;
    b.scrollTop = 0; b.classList.toggle('more', b.scrollHeight > b.clientHeight + 2);
  }
  if (window.MutationObserver) {
    var ib = document.querySelector('.sparfight .itbody');
    if (ib) new MutationObserver(fitInfo).observe(ib, {childList: true, subtree: true, characterData: true});
    window.addEventListener('resize', fitInfo);
  }
  function pct(a, b) { return Math.max(0, Math.min(100, 100 * a / (b || 1))); }

  /* ── drawing the state ─────────────────────────────────────────── */
  function bars(s) {
    $('mehp').style.width = pct(s.me.hp, s.me.max_hp) + '%';
    $('mehpv').textContent = s.me.hp.toLocaleString() + ' / ' + s.me.max_hp.toLocaleString();
    $('themhp').style.width = pct(s.master.hp, s.master.max_hp) + '%';
    $('themhpv').textContent = s.master.hp.toLocaleString() + ' / ' + s.master.max_hp.toLocaleString();
  }
  function beads(s, fresh) {
    var box = $('sbeads'); box.textContent = '';
    for (var i = 1; i <= s.max_turns; i++) {
      var li = document.createElement('li'), b = s.beads[i - 1];
      if (b) {
        li.className = b.outcome + (b.timed ? ' timed' : '') + (fresh === b.turn ? ' fresh' : '');
        li.title = 'Exchange ' + i + ': he chose ' + b.his + (b.outcome === 'win' ? ' · yours' : b.outcome === 'lose' ? ' · his' : ' · even');
        var im = document.createElement('img'); im.src = MOVE_ICON[b.his]; im.alt = b.his; li.appendChild(im);
      } else if (i === s.turn && !s.over) { li.className = 'now'; li.title = 'Exchange ' + i; }
      box.appendChild(li);
    }
  }
  function button(m, no) {
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'actbtn'; b.dataset.key = m.key;
    b.innerHTML = '<img alt="" width="104" height="104"><span class="alab"></span><span class="ast"></span><span class="ano"></span>';
    b.querySelector('img').src = m.icon; b.querySelector('.alab').textContent = m.label;
    b.querySelector('.ast').textContent = m.state || ''; b.querySelector('.ano').textContent = no;
    b.addEventListener('click', function () { pick(m.key); });
    b.addEventListener('mouseenter', function () { info(m); }); b.addEventListener('focus', function () { info(m); });
    return b;
  }
  function moves(s) {
    var bar = $('smoves'); bar.textContent = '';
    if (s.over) return;
    var by = {}; s.me.moves.forEach(function (m) { by[m.key] = m; });
    var techs = s.me.moves.filter(function (m) { return m.tech; });
    var ready = techs.filter(function (t) { return t.ready; });
    var open = s.opening && ready.some(function (t) { return t.type === 'attack'; });
    bar.appendChild(button(by.strike, 1));
    var menu = document.createElement('details');
    menu.className = 'techmenu' + (ready.length ? '' : ' off') + (open ? ' opening' : '');
    menu.innerHTML = '<summary class="actbtn"><img src="/art/icons/actions/techniques.webp" alt="" width="104" height="104">' +
      '<span class="alab">Techniques</span><span class="ast"></span><span class="ano">2</span></summary><div class="techpop" role="menu"></div>';
    menu.querySelector('.ast').textContent = techs.length ? (open ? 'Opening!' : ready.length ? ready.length + ' ready' : 'Resting') : 'None equipped';
    var about = {label: 'Techniques', state: '', info: 'An attack technique counts as a Strike, a defense technique as a Guard. ' +
      'Only a technique used at the right moment earns mastery EXP. Each rests a few exchanges after use.'};
    menu.querySelector('summary').addEventListener('mouseenter', function () { info(about); });
    menu.querySelector('summary').addEventListener('click', function (e) { if (!ready.length) e.preventDefault(); });
    techs.forEach(function (t) {
      var b = document.createElement('button');
      b.type = 'button'; b.className = 'techbtn' + (open && t.ready && t.type === 'attack' ? ' opening' : ''); b.disabled = !t.ready;
      b.innerHTML = '<img alt="" width="56" height="56"><span><span class="tkind"></span><b></b><span class="tstate"></span></span>';
      b.querySelector('img').src = t.icon; b.querySelector('.tkind').textContent = t.kind;
      b.querySelector('b').textContent = t.label;
      b.querySelector('.tstate').textContent = open && t.ready && t.type === 'attack' ? 'Perfect timing now!' : t.state;
      b.addEventListener('click', function () { menu.open = false; pick(t.key); });
      b.addEventListener('mouseenter', function () { info(t); });
      menu.querySelector('.techpop').appendChild(b);
    });
    bar.appendChild(menu);
    bar.appendChild(button(by.guard, 3));
    bar.appendChild(button(by['break'], 4));
    lock();
  }
  function lock() {
    var shut = sending || acting || S.over;
    main.dataset.phase = S.over ? 'finished' : shut ? 'submitting' : 'player_turn';
    main.classList.toggle('acting', acting);
    main.querySelectorAll('#smoves .actbtn, #smoves .techbtn').forEach(function (b) {
      if (b.tagName !== 'BUTTON') return;
      if (shut) { if (!b.disabled) { b.disabled = true; b.dataset.locked = '1'; } }
      else if (b.dataset.locked) { b.disabled = false; delete b.dataset.locked; }
    });
    main.querySelectorAll('#smoves details.techmenu').forEach(function (d) { d.classList.toggle('shut', shut); if (shut) d.open = false; });
    $('schip').textContent = S.over ? 'The spar is over' : acting ? 'The exchange' : sending ? 'Sending…' : 'Your turn';
  }
  function status(s) {
    $('swarn').textContent = s.over ? s.title : 'Exchange ' + s.shown_turn + ' / ' + s.max_turns;
    $('shint').textContent = s.over ? '' : s.master.staggered ? 'He is staggered: your next hit lands harder.' :
      s.opening ? 'An opening! Your attack technique now is perfect timing.' : s.title;
    $('hturn').textContent = 'Exchange ' + s.shown_turn;
    $('stimed').textContent = s.timed ? 'Well-timed: ' + s.timed + ' · +' + s.per_use + ' mastery EXP each, +' + s.win + ' on a win'
      : 'No well-timed technique yet';
    var tell = $('stell');
    tell.classList.toggle('blank', !s.has_tell);
    if (s.over) tell.textContent = ''; else again(tell, s.tell || '');
    if (!acting && mMode !== 'play') mposed();
  }
  function history(s) {
    var box = $('histbody'); box.textContent = '';
    var turns = (s.history || []).slice().reverse();
    if (!turns.length) { var p0 = document.createElement('p'); p0.className = 'li'; p0.textContent = 'The master bows. Begin.'; box.appendChild(p0); }
    turns.forEach(function (t) {
      var d = document.createElement('div'); d.className = 'hturn';
      var h = document.createElement('p'); h.className = 'hno'; h.textContent = 'Exchange ' + t.turn; d.appendChild(h);
      t.lines.forEach(function (l) { var p = document.createElement('p'); p.className = 'li'; p.textContent = l; d.appendChild(p); });
      box.appendChild(d);
    });
  }
  function result(s) {
    if (!s.over) { $('sresult').hidden = true; return; }
    var r = s.result, won = r.outcome === 'victory';
    $('rkick').textContent = s.trial ? 'MASTERY TRIAL' : 'SPARRING WITH THE MASTER';
    $('rtitle').textContent = won ? (s.trial ? 'Breakthrough!' : 'You win the spar!') : r.outcome === 'forfeit' ? 'You walked away' : 'The master wins this time';
    $('rsub').textContent = r.exchanges + ' exchange' + (r.exchanges === 1 ? '' : 's') + ' · spar again in ' + r.again;
    var g = $('sgains'); g.textContent = '';
    r.gains.forEach(function (t) {
      var row = document.createElement('div'); row.className = 'sgain';
      row.innerHTML = '<img alt=""><div><b></b><em></em><div class="ybar"><div></div></div><small></small></div>';
      row.querySelector('img').src = t.icon; row.querySelector('b').textContent = t.name;
      row.querySelector('em').textContent = '+' + t.gained.toLocaleString() + ' mastery EXP';
      var fill = row.querySelector('.ybar div'), before = t.cap ? pct(t.exp - t.gained, t.cap) : 100;
      row.querySelector('.ybar').classList.toggle('full', t.full);
      fill.style.width = before + '%';
      setTimeout(function () { fill.style.width = t.pct + '%'; }, 350);
      row.querySelector('small').textContent = t.stage + ' · ' + (t.cap ? t.exp.toLocaleString() + ' / ' + t.cap.toLocaleString() : 'final stage');
      g.appendChild(row);
    });
    var n = $('snotes'); n.textContent = '';
    r.notes.forEach(function (text) {
      var li = document.createElement('li'); li.textContent = text;
      if (/^Breakthrough/.test(text)) li.className = 'big';
      n.appendChild(li);
    });
    $('sresult').classList.toggle('won', won); $('semblem').hidden = !(r.trial && r.trial.passed);
    $('syield').hidden = true;
    if (window.SparMusic) window.SparMusic.stop();
    if (revealing) return;
    revealing = !wasOver;
    var reveal = function () { revealing = false; $('sresult').hidden = false; if (!wasOver) { wasOver = true; fs(won ? 'victory' : 'defeat'); } };
    if (wasOver || r.outcome === 'forfeit') reveal();
    else if (won && MS && MS.kneel) { mMode = 'idle'; mplay('kneel', 1); setTimeout(reveal, 2900); }   // beaten: down on one knee, at the video's own pace so its sound lands; the result comes while he kneels
    else { mMode = 'idle'; mplay('bow', 2.4, reveal); setTimeout(reveal, 4600); }
    $('ititle').textContent = won ? 'Well fought' : 'The master bows';
    $('itext').textContent = 'The master rests for ' + r.again + ' before he spars again.';
    body.classList.remove('breathe'); body.classList.toggle('down', won && !(MS && MS.kneel));
  }
  function draw(s, fresh) {
    S = s; bars(s); beads(s, fresh); status(s); moves(s); history(s); result(s); lock();
    left = s.left; leftAt = Date.now();
  }

  /* ── things that appear on the scene for a moment ─────────────── */
  function at(rect, fx, fy) {                                    // a point inside a box, as % of the scene
    var sr = scene.getBoundingClientRect();
    return [100 * (rect.left + rect.width * fx - sr.left) / sr.width, 100 * (rect.top + rect.height * fy - sr.top) / sr.height];
  }
  function fx(cls, p, life) {
    var n = document.createElement('span');
    n.className = 'sfx ' + cls; n.style.left = p[0] + '%'; n.style.top = p[1] + '%';
    scene.appendChild(n); setTimeout(function () { n.remove(); }, life || 900);
    return n;
  }
  function pic(src, p, widthPct, life, frames) {                 // one of the game's effect pictures, animated in code
    var n = document.createElement('img');
    n.className = 'sfx spic'; n.src = src; n.alt = ''; n.style.left = p[0] + '%'; n.style.top = p[1] + '%'; n.style.width = widthPct + '%';
    scene.appendChild(n);
    if (n.animate) n.animate(frames, {duration: life, easing: 'ease-out', fill: 'forwards'});
    setTimeout(function () { n.remove(); }, life + 40);
    return n;
  }
  function dust(p) {
    pic('/art/spar/dust.webp', p, 24, 900, [{opacity: 0, transform: 'translate(-50%,-70%) scale(.5)'}, {opacity: 0.8, transform: 'translate(-50%,-85%) scale(.9)', offset: 0.2},
      {opacity: 0, transform: 'translate(-50%,-105%) scale(1.25)'}]);
  }
  function pop(box, text, kind) {
    var el = document.createElement('p');
    el.className = 'dmg ' + kind; el.textContent = text; box.appendChild(el);
    setTimeout(function () { el.remove(); }, 1700);
  }

  /* ── your movements, frame by frame ───────────────────────────── */
  function show(name, f) {
    var sp = SPEC[name], el = sheets[name];
    f = Math.max(0, Math.min(sp.frames - 1, Math.round(f)));
    el.style.backgroundPosition = (sp.cols > 1 ? (f % sp.cols) / (sp.cols - 1) * 100 : 0) + '% ' +
      (sp.rows > 1 ? Math.floor(f / sp.cols) / (sp.rows - 1) * 100 : 0) + '%';
    Object.keys(sheets).forEach(function (k) { sheets[k].classList.toggle('on', k === name); });
    fme.dataset.pose = 'sheet';
  }
  function stand() { fme.dataset.pose = 'idle'; Object.keys(sheets).forEach(function (k) { sheets[k].classList.remove('on'); }); hero(0, 0); }
  function hero(x, y) { poses.style.transform = 'translate(' + x + 'px,' + y + 'px)'; }
  function keyed(keys, t) {                                      // [[ms, frame], ...] → the frame at t
    var f = keys[keys.length - 1][1];
    for (var j = 1; j < keys.length; j++) {
      if (t < keys[j][0]) { var a = keys[j - 1], b = keys[j]; f = a[1] + (b[1] - a[1]) * span(t, a[0], b[0]); break; }
    }
    return f;
  }

  /* What you do this exchange, as {hit, end, render(t), cues}. `hit` is the moment the exchange is decided on screen:
     your blade or fist arriving, or his blow reaching your guard. */
  function mine(e, G) {
    var me = e.me, X = me.fx, name, sp;
    if (X && SPEC[X.motion]) {                                   // a technique with its own movement
      name = X.motion; sp = SPEC[name];
      var n = sp.frames - 1, rel = Math.min(sp.release, n), back = Math.min(sp.back || rel, n);
      if (me.type === 'attack') {
        var T = Math.max(X.ms || 0, sp.ms || 0, 1600), wind = Math.min(sp.windup || sp.jab || rel, rel);
        var keys = [[0, 0], [T * 0.34, wind], [T * 0.44, rel], [T * 0.70, back], [T, n]];
        var hand = sp.hand || [0.72, 0.4];
        var reach = Math.max(0, G.mr.left - (G.fr.left + G.fr.width * hand[0]) - G.W * 0.012);
        return {hit: T * 0.44, end: T, cues: [[0, 'cast']], render: function (t) {
          show(name, keyed(keys, t));
          hero(reach * (inout(span(t, T * 0.12, T * 0.44)) - inout(span(t, T * 0.70, T * 0.96))), 0);
        }, art: X.art && X.art[0], mirror: X.mirror};
      }
      var H = 820, pace = sp.pace || 1;                          // a defense technique: set as his blow arrives, then held
      var dkeys = name === 'deflect'
        ? [[0, 0], [H - 260, sp.jab || 0], [H, rel], [H + 520 * pace, Math.min(sp.sweep || back, n)], [H + 700 * pace, back], [H + 1300 * pace, n]]
        : [[0, 0], [H - 420, sp.jab || 0], [H - 60, rel], [H + 520 * pace, back], [H + 520 * pace + Math.max(300, (n - back) * 70), n]];
      return {hit: H, end: dkeys[dkeys.length - 1][0], cues: [[0, 'cast']], render: function (t) { show(name, keyed(dkeys, t)); hero(0, 0); },
              art: X.art && X.art[0], own: true};
    }
    if (me.base !== 'guard' && SPEC[me.base]) {                  // Strike / Break (and a technique with no movement of its own)
      name = me.base; sp = SPEC[name];
      var R = sp.blade, began = false;
      var far = Math.max(0, G.mr.left - (G.fr.left + G.fr.width * (sp.tip || 0.8)) + G.mr.width * 0.18);
      return {hit: R.hit, end: R.end, slam: !!R.slam, cues: [[Math.max(0, R.swing - 90), 'swing', name]].concat(me.tech ? [[0, 'cast']] : []), render: function (t) {
        if (R.slam && !began) { began = true; fs('gather'); }
        show(name, keyed(R.keys, t));
        var x = far * inout(span(t, R.dash[0], R.dash[1]));
        if (t >= R.back[0]) x = far * (1 - inout(span(t, R.back[0], R.back[1])));
        hero(x, 0);
      }};
    }
    if (SPEC.guard) {                                            // Guard (and a defense technique with no movement of its own)
      sp = SPEC.guard;
      var GT = {ready: sp.ready || 320, first: sp.first || 4, ms: sp.ms || 34}, HG = GT.ready + 200;
      return {hit: HG, end: HG + Math.min(1500, (sp.frames - GT.first) * GT.ms), cues: [[0, me.tech ? 'cast' : 'guardup']], render: function (t) {
        var h = t - HG;
        var f = h < 0 ? Math.floor((GT.first - 1) * span(h, -GT.ready, 0)) : GT.first + Math.floor(h / GT.ms);
        if (h < -GT.ready || f >= sp.frames) stand(); else { show('guard', f); hero(0, 0); }
      }};
    }
    return {hit: 600, end: 1300, cues: [], render: function () {}};
  }

  /* The Master's side of the exchange, in code: [x, y, degrees, squash] for his painting at time t. */
  function his(e, G, HIT) {
    var move = e.master.move, close = e.me.base !== 'guard';     // you came to him: he only needs a short step
    var gap = Math.max(0, G.mr.left - (G.fr.left + G.fr.width * 0.6));
    var step = close ? G.W * 0.03 : Math.max(G.W * 0.03, gap - G.W * 0.012);
    var lost = e.master.lost > 0, knock = (MS && MS.hit ? 0.35 : 1) * G.W * (lost ? 0.022 + 0.03 * Math.min(1, e.master.lost / (S.master.max_hp * 0.3)) : 0);
    return function (t) {
      var x = 0, y = 0, rot = 0, sq = 1, h = t - HIT;
      if (move === 'strike') {
        x = G.W * 0.012 * ease(span(t, HIT - 460, HIT - 220)) - (step + G.W * 0.012) * ease(span(t, HIT - 200, HIT - 20)) + step * inout(span(t, HIT + 180, HIT + 620));
        rot = 3 * ease(span(t, HIT - 460, HIT - 220)) - 9 * ease(span(t, HIT - 200, HIT - 20)) + 6 * inout(span(t, HIT + 180, HIT + 620));
      } else if (move === 'break') {
        sq = 1 - 0.07 * (ease(span(t, HIT - 760, HIT - 380)) - ease(span(t, HIT - 240, HIT - 60)));
        x = -step * ease(span(t, HIT - 240, HIT - 20)) + step * inout(span(t, HIT + 260, HIT + 760));
        y = -G.W * 0.022 * Math.sin(Math.PI * span(t, HIT - 240, HIT - 20));
        rot = -12 * ease(span(t, HIT - 240, HIT - 20)) + 12 * inout(span(t, HIT + 260, HIT + 760));
      } else {
        x = G.W * 0.006 * (ease(span(t, HIT - 420, HIT - 160)) - inout(span(t, HIT + 320, HIT + 700)));
        rot = 2 * (ease(span(t, HIT - 420, HIT - 160)) - inout(span(t, HIT + 320, HIT + 700)));
      }
      if (MS) { rot = 0; sq = 1; if (move === 'guard') x = 0; if (move === 'break') y = 0; }
      if (h >= 0 && knock) { x += knock * (ease(span(h, 0, 80)) - ease(span(h, 140, 520))); rot += 5 * (ease(span(h, 0, 80)) - ease(span(h, 140, 520))); }
      return [x, y, rot, sq];
    };
  }

  /* the instant the exchange is decided: numbers, sparks, the word, the bars */
  function impact(e, next, plan, G) {
    var me = e.me, m = e.master, mr = body.getBoundingClientRect(), fr = poses.getBoundingClientRect();   // where each stands now
    var chest = at(mr, 0.42, 0.36), mine = at(fr, 0.46, 0.5);
    if (m.lost > 0) {
      var big = m.lost >= S.master.max_hp * 0.2;
      pop(fthem, '−' + m.lost.toLocaleString(), 'hit'); fx('sspark', chest, 450); if (!plan.hitSound) fs('hit', big ? 'big' : '');
      body.classList.remove('hit'); void body.offsetWidth; body.classList.add('hit');
      if (!me.tech && me.base === 'strike') pic('/art/fx/slash.webp', chest, 22, 420, [{opacity: 0, transform: 'translate(-70%,-50%) scale(.6)'},
        {opacity: 1, transform: 'translate(-50%,-50%) scale(1)', offset: 0.3}, {opacity: 0, transform: 'translate(-40%,-50%) scale(1.1)'}]);
      if (big || plan.slam) dust(at(mr, 0.5, 0.97));
      if (plan.slam) {
        fs('boom'); var feet = at(mr, 0.5, 0.97);
        pic('/art/fx/break_burst.webp', feet, 26, 800, [{opacity: 0, transform: 'translate(-50%,-70%) scale(.4)'},
          {opacity: 1, transform: 'translate(-50%,-85%) scale(1)', offset: 0.25}, {opacity: 0, transform: 'translate(-50%,-95%) scale(1.15)'}]);
      }
      if (big && scene.animate) scene.animate([{transform: 'none'}, {transform: 'translate(-7px,4px)'}, {transform: 'translate(7px,-4px)'},
        {transform: 'translate(-4px,2px)'}, {transform: 'none'}], {duration: 380});
    } else if (me.base !== 'guard') {
      if (m.move === 'guard') { pop(fthem, 'Blocked', 'hit'); fx('sring', chest, 520); if (!plan.hisSound) fs('block'); body.classList.add('guarding'); }
      else if (e.outcome === 'lose') { pop(fthem, 'Too slow', 'hit'); fs('miss'); }
    }
    if (me.lost > 0) {
      pop(poses, '−' + me.lost.toLocaleString(), 'hurt'); fx('sspark', mine, 450);
      fs('hurt', me.lost >= S.me.max_hp * 0.2 ? 'big' : '', 40);
      if (m.move === 'break') { if (!plan.hisSound) fs('boom', null, 60); dust(at(fr, 0.46, 0.93)); }
      if (m.move === 'strike') pic('/art/spar/ripple.webp', mine, 15, 520, [{opacity: 0.95, transform: 'translate(-50%,-50%) scale(.25)'}, {opacity: 0, transform: 'translate(-50%,-50%) scale(1.25)'}]);
      fme.classList.remove('hit'); void fme.offsetWidth; fme.classList.add('hit');
    } else if (me.lost < 0) { pop(poses, '+' + (-me.lost).toLocaleString(), 'heal'); fs('heal'); }
    else if (m.move !== 'guard') {
      if (me.base === 'guard' && e.outcome === 'win') { pop(poses, 'Blocked!', 'hit'); fx('sring', at(fr, 0.62, 0.45), 520); fs('block'); }
      else if (e.outcome !== 'win') { pop(poses, 'Dodged!', 'hit'); fs('miss'); }
    }
    if (e.outcome === 'win' && me.base === 'guard') { body.classList.remove('opened'); void body.offsetWidth; body.classList.add('opened'); }
    var word = $('sword'); word.className = 'sword ' + e.outcome; again(word, e.word);
    if (e.timed) {
      setTimeout(function () {
        again($('sperfect'), 'Perfect timing! ' + me.label + ' grows');
        fx('sseal', at(poses.getBoundingClientRect(), 0.44, 0.55), 950); fs('heal', null, 60);
      }, 380);
    }
    bars(next); beads(next, e.turn);
  }

  /* acting one exchange out, then drawing what comes next */
  function act(next, done) {
    var e = next.last;
    acting = true; lock();
    stand();
    var sr = scene.getBoundingClientRect();
    var G = {W: sr.width, fr: fme.getBoundingClientRect(), mr: body.getBoundingClientRect()};
    var plan = mine(e, G), mv = e.master.move;
    var held = S.tell_pose === mv;                              // he is already in this move's first pose
    var soft = mv === 'guard' && e.me.base === 'guard';
    var cut = mv === 'break' && e.outcome === 'win';            // your Strike lands first: his Break never comes
    var struck = !!(MS && MS.hit && e.master.lost > 0);        // your blow lands: his own stagger, from the moment it does         // nothing lands on his guard
    var D = MS ? Math.max(0, LEAD[mv] - plan.hit) : 0;          // you wait for him: both blows meet at HIT
    var HIT = plan.hit + D, END = Math.max(plan.end + D, HIT + (MS ? (struck ? 500 + Math.max(0, MS.hit.at[MS.hit.frames - 1] - 500) / 2.4 : cut ? 900 : mlength(mv, soft)) : 950)) + 120;
    var him = his(e, G, HIT), start = null, fired = false;
    var cues = (plan.cues || []).map(function (c) { return [c[0] + D, c[1], c[2]]; });
    body.classList.remove('breathe');
    if (MS) { mMode = 'act'; mPlay = null; plan.hisSound = !soft && !(struck && mv === 'guard') && msound(mv, HIT);
      plan.hitSound = struck && msound('hit', HIT);
      if (cut && plan.hisSound) setTimeout(function () { plan.hisSound.pause(); }, HIT + 40); }
    again($('sayme'), e.me.label + (e.timed_out ? ' (too slow)' : ''));
    again($('saythem'), e.master.label);
    if (e.line) again($('dtoast'), e.line);
    if (!MS) {
      if (mv === 'guard') fs('guardup', null, Math.max(0, HIT - 380));
      else cues.push([Math.max(0, HIT - 200), 'swing', mv]);
    }
    if (plan.art) {                                              // the technique's own picture: over you, or flying to him
      setTimeout(function () {
        var fr = fme.getBoundingClientRect(), mr = body.getBoundingClientRect();
        if (plan.own) pic(plan.art, at(fr, 0.5, 0.55), 24, 1300, [{opacity: 0, transform: 'translate(-50%,-50%) scale(.7)'},
          {opacity: 0.95, transform: 'translate(-50%,-50%) scale(1)', offset: 0.25}, {opacity: 0.9, offset: 0.7}, {opacity: 0, transform: 'translate(-50%,-50%) scale(1.08)'}]);
        else {
          var a = at(fr, 0.74, 0.4), b = at(mr, 0.4, 0.4), dx = (b[0] - a[0]) / 100 * G.W, flip = plan.mirror ? ' scaleX(-1)' : '';
          pic(plan.art, a, 15, 760, [{opacity: 0, transform: 'translate(-50%,-50%) scale(.4)' + flip},
            {opacity: 0.9, transform: 'translate(calc(-50% + ' + dx * 0.15 + 'px),-50%) scale(.7)' + flip, offset: 0.12},
            {opacity: 1, transform: 'translate(calc(-50% + ' + dx * 0.55 + 'px),-50%) scale(1)' + flip, offset: 0.35},
            {opacity: 1, transform: 'translate(calc(-50% + ' + dx + 'px),-50%) scale(1.15)' + flip, offset: 0.6},
            {opacity: 0, transform: 'translate(calc(-50% + ' + dx + 'px),-50%) scale(1.5)' + flip}]);
        }
      }, Math.max(0, HIT - (plan.own ? 420 : 300)));
    }
    function frame(now) {
      if (start === null) start = now;
      var t = now - start;
      while (cues.length && t >= cues[0][0]) { var c = cues.shift(); fs(c[1], c[2]); }
      plan.render(Math.max(0, Math.min(t - D, plan.end)));
      if (t - D >= plan.end) stand();
      if (MS) {
        var x = t - HIT;
        if (struck && x >= -MS.hit.hit) mshow('hit', mframe('hit', MS.hit.hit + (x < 500 ? x : 500 + (x - 500) * 2.4)));
        else if (cut && x > 520) mshow('stance', 0);
        else mshow(mv, mframe(mv, mtime(mv, t, HIT, soft, held, cut)));
      }
      var m = him(t);
      body.style.transform = 'translate(' + m[0] + 'px,' + m[1] + 'px) rotate(' + m[2] + 'deg) scaleY(' + m[3] + ')';
      if (t >= HIT && !fired) { fired = true; impact(e, next, plan, G); }
      if (t < END) { requestAnimationFrame(frame); return; }
      stand(); body.style.transform = '';
      body.classList.remove('guarding', 'gathering', 'hit', 'opened'); fme.classList.remove('hit');
      if (!next.over) body.classList.add('breathe');
      acting = false; S = next; mposed(); done();
    }
    cues.sort(function (a, b) { return a[0] - b[0]; });
    requestAnimationFrame(frame);
  }

  /* ── talking to the server ────────────────────────────────────── */
  function apply(s) {
    if (!s || s.gone) { location.href = '/training'; return; }
    if (acting) return;
    var turn = s.last ? s.last.turn : 0;
    if (turn > shownTurn) {
      var told = {text: S.tell, pose: S.tell_pose};               // the tell he showed before this exchange
      shownTurn = turn; act(s, function () { draw(s); explain(s.last, told); }); return;
    }
    draw(s);
  }

  /* ── learning: after each exchange, what happened and what would have won (How to play, "Explanations") ── */
  var BEATS = {strike: 'guard', guard: 'break', break: 'strike'}, explainOn = true;
  try { explainOn = localStorage.getItem('ma.spar.explain') !== 'off'; } catch (e5) {}
  function T(m) { return m.charAt(0).toUpperCase() + m.slice(1); }
  function explain(t, told) {
    var el = $('sexplain');
    if (!el) return;
    if (!explainOn || !t) { el.textContent = ''; return; }
    var his = t.master.move, mine = t.me.base, out = [];
    if (t.timed_out) out.push('Time ran out, so you raised your Guard.');
    if (t.outcome === 'win') out.push('You read him: your ' + T(mine) + ' beats his ' + T(his) + '.');
    else if (t.outcome === 'lose') out.push('His ' + T(his) + ' beat your ' + T(mine) + '. ' + T(BEATS[his]) + ' would have won.');
    else out.push('You both chose ' + T(his) + ': a clash. ' + T(BEATS[his]) + ' would have won.');
    if (told && told.pose) {
      out.push(told.pose === his ? 'His tell meant ' + T(his) + '.'
        : 'His tell was a feint: it showed ' + T(told.pose) + ', but the small sign in it gave away ' + T(his) + '.');
    } else out.push('No tell this time: read his rhythm in the beads.');
    if (t.me.tech) {
      if (t.timed) out.push('Well timed: your technique earns mastery EXP.');
      else out.push(t.me.type === 'attack' ? 'Attack techniques earn mastery right after you Guard his Strike.'
        : 'Defense techniques earn mastery when he Strikes.');
    }
    el.textContent = out.join(' ');
  }
  (function () {
    var box = $('showto'), check = $('sexplaincheck');
    if (!box) return;
    check.checked = explainOn;
    check.addEventListener('change', function () {
      explainOn = this.checked;
      try { localStorage.setItem('ma.spar.explain', explainOn ? 'on' : 'off'); } catch (e6) {}
      if (!explainOn) $('sexplain').textContent = '';
    });
    $('showbtn').addEventListener('click', function () { box.hidden = false; });
    $('showclose').addEventListener('click', function () { box.hidden = true; });
    box.addEventListener('click', function (e) { if (e.target === box) box.hidden = true; });
  })();
  function fetchState() {
    return fetch('/spar/state', {cache: 'no-store'}).then(function (r) { return r.json(); }).then(apply).catch(function () {});
  }
  function pick(key) {
    if (sending || acting || S.over) return;
    fs('press');
    sending = true; lock();
    var bodyq = new URLSearchParams({move: key, turn: S.turn});
    fetch('/spar/pick', {method: 'POST', body: bodyq, headers: {'Content-Type': 'application/x-www-form-urlencoded'}})
      .then(function (r) { return r.json(); })
      .then(function (r) {
        sending = false;
        if (r.error) { $('ititle').textContent = 'Not now'; $('itext').textContent = r.error; }
        apply(r.state);
        if (!acting) lock();
      })
      .catch(function () { sending = false; lock(); fetchState(); });
  }

  /* ── controls ─────────────────────────────────────────────────── */
  $('syield').addEventListener('click', function () {
    var b = $('syield');
    if (S.over || acting) return;
    if (b.dataset.sure) { fetch('/spar/yield', {method: 'POST'}).then(function (r) { return r.json(); }).then(apply); }
    else { b.dataset.sure = '1'; b.querySelector('span').textContent = 'Really? Nothing is earned'; setTimeout(function () { delete b.dataset.sure; b.querySelector('span').textContent = 'Yield'; }, 4000); }
  });
  $('syield').addEventListener('mouseenter', function () { info({label: 'Yield', state: '', info: 'Walk away from the spar. Nothing is earned, and the master still rests.'}); });
  var hist = main.querySelector('.bhist');
  main.querySelector('.histclose').addEventListener('click', function () { hist.open = false; });
  document.addEventListener('keydown', function (e) {
    if (e.target.tagName === 'INPUT' || e.ctrlKey || e.metaKey || e.altKey) return;
    var k = e.key.toLowerCase();
    if (k === '1') pick('strike');
    else if (k === '3') pick('guard');
    else if (k === '4') pick('break');
    else if (k === '2') { var m = main.querySelector('details.techmenu:not(.off):not(.shut)'); if (m) m.open = !m.open; }
    else if (k === 'f') $('syield').click();
    else if (k === 'h') hist.open = !hist.open;
    else if (k === 'g') $('showto').hidden = !$('showto').hidden;
    else if (k === 'escape') { hist.open = false; $('showto').hidden = true; main.querySelectorAll('details.techmenu[open]').forEach(function (d) { d.open = false; }); }
  });

  /* ── the exchange's countdown; when it runs out, the server has already played your Guard ── */
  setInterval(function () {
    if (S.over) { $('sleft').textContent = '0'; $('sbar').style.width = '0'; return; }
    var n = Math.max(0, left - (Date.now() - leftAt) / 1000);
    $('sleft').textContent = Math.ceil(n);
    $('sbar').style.width = Math.round(100 * n / S.seconds) + '%';
    $('sbar').style.background = n <= 5 ? '#E45B4C' : '';
    if (n <= 0 && !sending && !acting && Date.now() - asked > 1500) { asked = Date.now(); fetchState(); }
  }, 200);
  document.addEventListener('visibilitychange', function () { if (!document.hidden && !acting && !sending) fetchState(); });
  draw(S);
  requestAnimationFrame(mloop);
  if (!S.over && !S.last) mplay('bow', 2.0);
  if (!S.over && window.SparMusic) window.SparMusic.start(S.trial ? 'trial' : 'spar');
})();
