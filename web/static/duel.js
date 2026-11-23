/* A duel at the Arena (duel.html, web/duel_play.py), on the beast fight's screen.

   The server referees: this page only shows the state it is given and sends picks. It polls /arena/v about
   once a second; when the duel's version changes it fetches /duel/state and draws it. A newly resolved turn is
   acted out first: both fighters wind up, then each one's move plays (a Strike or Break lunges in, a Guard
   holds), the damage floats up over whoever took it, and the HP bars run down. */
(function () {
  'use strict';
  var S = JSON.parse(document.getElementById('dstate').textContent);
  var $ = function (id) { return document.getElementById(id); };
  var main = $('duel');
  var shownTurn = S.last ? S.last.turn : 0, sending = false, acting = false, leftAt = Date.now(), left = S.left;
  /* sound (web/static/fight_sound.js): told what just happened on screen; silent if it isn't there */
  function fs(name, arg, delay) { var F = window.FightSound; if (F) F.play(name, arg, delay); }
  var wasOver = !!S.over;                                      // the result's sound plays once, when the duel ends in front of you

  /* ── drawing the state ─────────────────────────────────────────── */
  function pct(side) { return Math.max(0, Math.round(100 * side.hp / side.max_hp)); }
  function bars(s) {
    $('mehp').style.width = pct(s.me) + '%';
    $('mehpv').textContent = s.me.hp.toLocaleString() + ' / ' + s.me.max_hp.toLocaleString();
    $('themhp').style.width = pct(s.them) + '%';
    $('themhpv').textContent = s.them.hp.toLocaleString() + ' / ' + s.them.max_hp.toLocaleString();
  }
  function info(m) {
    $('ititle').textContent = m.label + (m.state ? ' · ' + m.state : '');
    $('itext').textContent = m.info;
  }
  function button(m, no) {
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'actbtn' + (m.ready ? '' : ' off'); b.disabled = !m.ready;
    b.innerHTML = '<img alt="" width="104" height="104"><span class="alab"></span><span class="ano"></span>';
    b.querySelector('img').src = m.icon; b.querySelector('.alab').textContent = m.label;
    b.querySelector('.ano').textContent = no;
    b.addEventListener('click', function () { pick(m.key); });
    b.addEventListener('mouseenter', function () { info(m); }); b.addEventListener('focus', function () { info(m); });
    return b;
  }
  function moves(s) {
    var bar = $('dmoves'); bar.textContent = '';
    if (s.over) return;
    var by = {}; s.me.moves.forEach(function (m) { by[m.key] = m; });
    var techs = s.me.moves.filter(function (m) { return m.tech; });
    var ready = techs.filter(function (t) { return t.ready; });
    bar.appendChild(button(by.strike, 1));
    var menu = document.createElement('details');
    menu.className = 'techmenu' + (ready.length ? '' : ' off');
    menu.innerHTML = '<summary class="actbtn"><img src="/art/icons/actions/attack_tech.webp" alt="" width="104" height="104">' +
      '<span class="alab">Techniques</span><span class="ast"></span><span class="ano">2</span></summary><div class="techpop" role="menu"></div>';
    menu.querySelector('.ast').textContent = techs.length ? (ready.length ? ready.length + ' ready' : 'Recovering') : 'None equipped';
    var about = {label: 'Techniques', state: '', info: 'An attack technique counts as a Strike, a defense technique as a Guard. ' +
      'After use, each recovers for a few turns before you can play it again.'};
    menu.querySelector('summary').addEventListener('mouseenter', function () { info(about); });
    menu.querySelector('summary').addEventListener('click', function (e) { if (!ready.length) e.preventDefault(); });
    techs.forEach(function (t) {
      var b = document.createElement('button');
      b.type = 'button'; b.className = 'techbtn'; b.disabled = !t.ready;
      b.innerHTML = '<img alt="" width="56" height="56"><span><span class="tkind"></span><b></b><span class="tstate"></span></span>';
      b.querySelector('img').src = t.icon; b.querySelector('.tkind').textContent = t.kind;
      b.querySelector('b').textContent = t.label; b.querySelector('.tstate').textContent = t.state;
      b.addEventListener('click', function () { menu.open = false; pick(t.key); });
      b.addEventListener('mouseenter', function () { info(t); });
      menu.querySelector('.techpop').appendChild(b);
    });
    bar.appendChild(menu);
    bar.appendChild(button(by.guard, 3));
    bar.appendChild(button(by['break'], 4));
    lockButtons(s);
  }
  function lockButtons(s) {
    var shut = !!s.me.pick || acting || s.over;
    main.dataset.phase = s.over ? 'finished' : shut ? 'submitting' : 'player_turn';
    main.querySelectorAll('#dmoves .actbtn, #dmoves .techbtn').forEach(function (b) {
      if (b.tagName !== 'BUTTON') return;
      if (shut) { if (!b.disabled) { b.disabled = true; b.dataset.locked = '1'; } }
      else if (b.dataset.locked) { b.disabled = false; delete b.dataset.locked; }
    });
    main.querySelectorAll('#dmoves details.techmenu').forEach(function (d) { d.classList.toggle('shut', shut); if (shut) d.open = false; });
  }
  function status(s) {
    $('melock').textContent = s.over ? '' : s.me.pick ? 'Locked in: ' + s.me.pick : '';
    $('themlock').textContent = s.over ? '' : s.them.locked ? s.them.name + ' has locked in. Your move?' : s.them.name + ' is choosing…';
    $('dchip').textContent = s.over ? 'The duel is over' : s.me.pick ? (s.them.locked ? 'Revealing…' : 'Waiting for ' + s.them.name) : 'Your turn';
    $('dwarn').textContent = s.them.staggered ? s.them.name + ' is staggered!' : s.me.staggered ? 'You are staggered!' : 'Friendly duel · Turn ' + s.turn + ' / ' + s.max_turns;
    $('hturn').textContent = 'Turn ' + s.turn;
    $('dheat').hidden = !s.intensity;
    if (s.intensity) $('dheat').textContent = 'Rising intensity · all damage +' + Math.round(s.intensity * 100) + '%';
  }
  function history(s) {
    var box = $('histbody'); box.textContent = '';
    var turns = (s.history || []).slice().reverse();
    if (!turns.length) { var p0 = document.createElement('p'); p0.className = 'li'; p0.textContent = 'The duel begins.'; box.appendChild(p0); }
    turns.forEach(function (t) {
      var d = document.createElement('div'); d.className = 'hturn';
      var h = document.createElement('p'); h.className = 'hno'; h.textContent = 'Turn ' + t.turn; d.appendChild(h);
      t.lines.forEach(function (l) { var p = document.createElement('p'); p.className = 'li'; p.textContent = l; d.appendChild(p); });
      box.appendChild(d);
    });
  }
  function result(s) {
    if (!s.over) { $('dresult').hidden = true; return; }
    var r = s.result;
    $('rkick').textContent = r.draw ? 'NEITHER YIELDS' : r.won ? 'VICTORY' : 'DEFEAT';
    $('rtitle').textContent = r.draw ? 'A draw' : r.won ? 'You win!' : r.winner + ' wins';
    var how = {ko: 'by knock-out', time: 'on the turn limit', forfeit: 'by forfeit', timeouts: 'by forfeit (time ran out)'}[r.reason] || '';
    $('rsub').textContent = how + ' · ' + r.turns + ' turn' + (r.turns === 1 ? '' : 's');
    $('dresult').hidden = false;
    $('dflee').hidden = true;
    if (!wasOver) { wasOver = true; fs(r.won ? 'victory' : r.draw ? 'block' : 'defeat', null, 250); }
    $('fme').classList.toggle('down', !r.won && !r.draw);
    $('fthem').classList.toggle('down', !!r.won);
  }
  function draw(s) {
    S = s; bars(s); status(s); moves(s); history(s); result(s);
    left = s.left; leftAt = Date.now();
  }

  /* ── acting out a turn ─────────────────────────────────────────── */
  function again(el, text) { el.textContent = text; el.classList.remove('go'); void el.offsetWidth; el.classList.add('go'); }
  function pop(who, text, kind) {
    var el = document.createElement('p');
    el.className = 'dmg ' + kind; el.textContent = text; $('f' + who).appendChild(el);
    setTimeout(function () { el.remove(); }, 1700);
  }
  function act(s, done) {
    var t = s.last, mine = t && t.moves && t.moves[S.me.uid], theirs = t && t.moves && t.moves[S.them.uid];
    if (!mine || !theirs) { done(); return; }
    acting = true; lockButtons(S);
    var fme = $('fme'), fthem = $('fthem');
    if (t.lines && t.lines[0]) again($('dtoast'), t.lines[0]);
    again($('sayme'), mine.label + (mine.timed_out ? ' (too slow)' : ''));
    again($('saythem'), theirs.label + (theirs.timed_out ? ' (too slow)' : ''));
    [mine, theirs].forEach(function (m, i) {                     // each side's move: a guard goes up, Qi gathers, a blade is drawn
      if (/_tech$/.test(m.move)) fs('cast', 1, i * 60);
      else if (m.base === 'guard') fs('guardup', null, i * 60);
      else if (m.base === 'break') fs('gather', null, i * 60);
    });
    [[fme, mine], [fthem, theirs]].forEach(function (p) {
      p[0].classList.add('acting');
      p[0].dataset.pose = p[1].base === 'guard' ? 'idle' : 'windup';
      p[0].classList.toggle('guarding', p[1].base === 'guard');
    });
    setTimeout(function () {
      [[fme, mine], [fthem, theirs]].forEach(function (p) {
        if (p[1].base !== 'guard') { p[0].dataset.pose = 'strike'; p[0].classList.add('lunge'); }
      });
      [mine, theirs].forEach(function (m, i) { if (m.base !== 'guard' && !/_tech$/.test(m.move)) fs('swing', m.base, i * 70); });
      setTimeout(function () {
        [['me', fme, mine, theirs], ['them', fthem, theirs, mine]].forEach(function (p) {
          var lost = p[2].lost, max = (p[0] === 'me' ? S.me : S.them).max_hp, big = lost >= max * 0.2 ? 'big' : '';
          if (lost > 0) {
            p[1].classList.add('hit'); pop(p[0], '−' + lost.toLocaleString(), 'hurt');
            fs(p[0] === 'me' ? 'hurt' : 'hit', big, p[0] === 'me' ? 0 : 60);          // you are hurt; your blow lands on them
            if (p[3].base === 'break') fs('boom', null, 40);
          }
          else if (lost < 0) { pop(p[0], '+' + (-lost).toLocaleString(), 'heal'); fs('heal'); }
          else if (p[3].base !== 'guard') { pop(p[0], p[2].base === 'guard' ? 'Blocked!' : 'Missed!', 'hit'); fs(p[2].base === 'guard' ? 'block' : 'miss'); }
        });
        bars(s);
        setTimeout(function () {
          [fme, fthem].forEach(function (f) { f.classList.remove('lunge', 'hit', 'guarding', 'acting'); f.dataset.pose = 'idle'; });
          acting = false; done();
        }, 700);
      }, 280);
    }, 420);
  }
  function apply(s) {
    if (s.gone) { location.href = '/arena'; return; }
    var turn = s.last ? s.last.turn : 0;
    if (turn > shownTurn && s.last.moves) {          // a new turn: act it out on the old bars, then draw the rest
      shownTurn = turn;
      $('melock').textContent = $('themlock').textContent = '';
      act(s, function () { draw(s); });
      return;
    }
    shownTurn = turn;
    if (!acting) draw(s);
  }
  function fetchState() {
    return fetch('/duel/state', {cache: 'no-store'}).then(function (r) { return r.json(); }).then(apply);
  }
  function pick(key) {
    fs('press');
    if (sending || acting || S.over || S.me.pick) return;
    sending = true;
    var body = new URLSearchParams({move: key, turn: S.turn});
    fetch('/duel/pick', {method: 'POST', body: body, headers: {'Content-Type': 'application/x-www-form-urlencoded'}})
      .then(function (r) { return r.json(); })
      .then(function (r) { if (r.error) { $('ititle').textContent = 'Not now'; $('itext').textContent = r.error; } return fetchState(); })
      .catch(function () {}).then(function () { sending = false; });
  }

  /* ── controls ──────────────────────────────────────────────────── */
  $('dflee').addEventListener('click', function () {
    var b = $('dflee');
    if (b.dataset.sure) { fetch('/duel/flee', {method: 'POST'}).then(fetchState); }
    else { b.dataset.sure = '1'; b.querySelector('span').textContent = 'Really? You lose'; }
  });
  $('dflee').addEventListener('mouseenter', function () { info({label: 'Flee', state: '', info: 'Leave the duel. It counts as a loss.'}); });
  var hist = main.querySelector('.bhist');
  main.querySelector('.histclose').addEventListener('click', function () { hist.open = false; });
  document.addEventListener('keydown', function (e) {
    if (e.target.tagName === 'INPUT' || e.ctrlKey || e.metaKey || e.altKey) return;
    var k = e.key.toLowerCase();
    if (k === '1') pick('strike');
    else if (k === '3') pick('guard');
    else if (k === '4') pick('break');
    else if (k === '2') { var m = main.querySelector('details.techmenu:not(.off):not(.shut)'); if (m) m.open = !m.open; }
    else if (k === 'f') $('dflee').click();
    else if (k === 'h') hist.open = !hist.open;
    else if (k === 'escape') { hist.open = false; main.querySelectorAll('details.techmenu[open]').forEach(function (d) { d.open = false; }); }
  });

  /* ── polling, and the turn's countdown ─────────────────────────── */
  var seenV = S.v;
  function poll() {
    fetch('/arena/v', {cache: 'no-store'}).then(function (r) { return r.json(); }).then(function (v) {
      if (v.gone || v.d === null) { if (!S.over) location.href = '/arena'; return; }
      if (v.d !== seenV) { seenV = v.d; return fetchState(); }
    }).catch(function () {}).then(function () { setTimeout(poll, S.over ? 4000 : 900); });
  }
  setInterval(function () {
    if (S.over) { $('dleft').textContent = '0'; $('dbar').style.width = '0'; return; }
    var n = Math.max(0, left - (Date.now() - leftAt) / 1000);
    $('dleft').textContent = Math.ceil(n);
    $('dbar').style.width = Math.round(100 * n / S.seconds) + '%';
    $('dbar').style.background = n <= 5 ? '#E45B4C' : '';
  }, 200);
  draw(S);
  poll();
})();
