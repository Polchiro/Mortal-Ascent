/* The fight screen: send a move without leaving the page (no jump to the top), then swap in the next turn. */
(function () {
  var playing = null;

  /* ── The combat action state ────────────────────────────────────────────────────────────────────────
     One place decides whether a move may be sent (docs/web.md, "One action per turn"). The phases have the
     same names as web/explore_play.py:

       player_turn    the buttons work: pick a move
       submitting     the move is on its way to the server; everything is locked
       player_acting  your action is being acted out
       beast_acting   the beast is acting, or reacting to your Guard
       dying          the loser is going down (a death animation sets this; nothing can be pressed)
       finished       the fight is over

     Only player_turn lets a move through: buttons, hotkeys and the techniques menu all ask Combat.can().
     The server has already resolved the turn before anything is acted out, so the phases only pace what is
     shown; they never decide damage or rewards. Other scripts can read window.MACombat.phase, call
     MACombat.set('dying'), or listen for the "combat:phase" event on document. */
  var Combat = {
    phase: 'player_turn',
    token: 0,                                                   // goes up with every move sent: late answers are dropped
    can: function () { return Combat.phase === 'player_turn'; },
    set: function (phase) {
      if (Combat.phase === phase) return;
      Combat.phase = phase;
      Combat.paint();
      document.dispatchEvent(new CustomEvent('combat:phase', {detail: {phase: phase}}));
    },
    /* show the phase on whatever fight is on the page now: the lock, the dimmed buttons, whose turn it is */
    paint: function () {
      var main = document.querySelector('main.battle');
      if (!main) return;
      var open = Combat.can();
      main.dataset.phase = Combat.phase;
      main.querySelectorAll('.fightform button').forEach(function (b) {
        if (open) { if (b.dataset.locked) { b.disabled = false; delete b.dataset.locked; } }
        else if (!b.disabled) { b.disabled = true; b.dataset.locked = '1'; }      // ones the server greyed out stay as they are
      });
      if (!open) main.querySelectorAll('details.techmenu[open]').forEach(function (d) { d.open = false; });
      var chip = main.querySelector('.turnchip');
      if (chip) chip.textContent = TURN_TEXT[Combat.phase] || '';
    }
  };
  var TURN_TEXT = {player_turn: 'Your turn', submitting: 'Sending…', player_acting: 'You act', beast_acting: 'The beast acts',
                   dying: '', finished: 'The fight is over'};
  var SETTLE = 220;            // ms a turn with nothing to act out stays locked: one press is one turn, never two
  var ANSWER_LIMIT = 12000;    // ms to wait for the server before asking it what happened
  window.MACombat = Combat;

  function init() {
    var main = document.querySelector('main.battle');
    if (!main) return;
    var title = main.querySelector('.ititle'), text = main.querySelector('.itext');
    main.querySelectorAll('[data-info]').forEach(function (el) {
      var target = el.tagName === 'DETAILS' ? el.querySelector('summary') : el;
      function show() {
        title.textContent = el.dataset.label + (el.dataset.state ? ' · ' + el.dataset.state : '');
        text.textContent = el.dataset.info;
      }
      target.addEventListener('mouseenter', show);
      target.addEventListener('focus', show);
    });
    var posed = main.querySelector('.beast.posed');             // load every pose picture now, so swaps are instant
    if (posed) { try { var ps = JSON.parse(posed.dataset.poses); Object.keys(ps).forEach(function (k) { new Image().src = ps[k].src; }); } catch (e) {} }
    ['/art/fx/break_burst.webp', '/art/fx/break_crater.webp'].forEach(function (src) { new Image().src = src; });   // Break's slam
    var hist = main.querySelector('.bhist'), close = main.querySelector('.histclose');
    if (hist && close) close.addEventListener('click', function () { hist.open = false; hist.querySelector('summary').focus(); });
    drawDeath(main);                                           // a won fight on a fresh page: the body already down
    if (main.classList.contains('slain')) { Combat.set('finished'); showVictory(main); }      // a won fight: nothing to act in
    main.querySelectorAll('form.fightform').forEach(function (form) {
      form.addEventListener('submit', function (ev) {
        ev.preventDefault();
        var button = ev.submitter;
        if (!Combat.can() || !button || button.disabled) return;
        send(form, button);
      });
    });
    main.querySelectorAll('details.techmenu').forEach(function (d) {        // the menu can't be opened while locked
      d.addEventListener('toggle', function () { if (d.open && !Combat.can()) d.open = false; });
    });
    Combat.paint();
  }

  function showVictory(main) {                                 // the panel is up: Continue is in reach (and on screen on a phone)
    var go = main.querySelector('.vgo'), card = main.querySelector('.vcard');
    if (go) go.focus({preventScroll: true});
    if (card && card.scrollIntoView) card.scrollIntoView({block: 'nearest', behavior: 'smooth'});
  }
  function endOf(main) { try { return JSON.parse(main.dataset.end || 'null'); } catch (e) { return null; } }

  /* A beaten beast goes down as ITSELF. Its body category has one shared movement (beasts.DEATH_ANIMATIONS: per
     frame, how wide the body lies and how high its back stands at points from tail to head, measured from SHOAIB's
     reference sheet) and no artwork. Here the beast's own picture is drawn on the .deathfx canvas in thin upright
     strips, each one lowered to the height the movement gives that part of the body at time t (ms; frames are
     blended, so it moves smoothly): the legs fold first, then the body above them comes down with a little squash,
     the head end lowest. Enemies face left, so the head is the left end. With no t it redraws where it was (the
     finished picture on a fresh page, or after the window changes size). */
  var LEGS = 0.42, LEGS_MIN = 0.14, BODY_MIN = 0.7;            // the legs' share of the body's height; how far each part gives
  function drawDeath(main, t) {
    var box = main && main.querySelector('.beast'), cv = box && box.querySelector('canvas.deathfx'), img = box && box.querySelector('img');
    var d = main && endOf(main);
    if (!cv || !img || !d || d.kind !== 'warp' || !cv.getContext) return;
    if (t === undefined) t = cv._t === undefined ? Infinity : cv._t;
    cv._t = t;
    if (!(img.complete && img.naturalWidth)) { img.addEventListener('load', function () { drawDeath(main); }, {once: true}); return; }
    var W = box.clientWidth, H = box.clientHeight, w = img.offsetWidth, h = img.offsetHeight, x = img.offsetLeft, y = img.offsetTop;
    if (!W || !H || !w || !h) return;
    if (!box.classList.contains('posed')) {                    // a painting is fitted inside its box, feet down
      var sc = Math.min(w / img.naturalWidth, h / img.naturalHeight), fw = img.naturalWidth * sc, fh = img.naturalHeight * sc;
      x += (w - fw) / 2; y += h - fh; w = fw; h = fh;
    }
    var dpr = Math.min(window.devicePixelRatio || 1, 2), M = 0.1;                       // the canvas overhangs the box by M all round
    var cw = Math.round(W * (1 + 2 * M) * dpr), ch = Math.round(H * (1 + 2 * M) * dpr);
    if (cv.width !== cw || cv.height !== ch) { cv.width = cw; cv.height = ch; }
    var ctx = cv.getContext('2d');
    ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, cw, ch);
    ctx.setTransform(dpr, 0, 0, dpr, W * M * dpr, H * M * dpr);
    var n = d.motion.length, f = n - 1, k = 0, acc = 0;
    for (var i = 0; i < n - 1; i++) { if (t < acc + d.ms[i]) { f = i; k = Math.max(0, (t - acc) / d.ms[i]); break; } acc += d.ms[i]; }
    var A = d.motion[f], B = d.motion[Math.min(n - 1, f + 1)], cols = A.h.length;
    function mix(a, b, q) { return a + (b - a) * q; }
    function high(u) {                                         // the back's height at u (0 tail .. 1 head), as a share of standing
      var p = Math.max(0, Math.min(1, u)) * (cols - 1), a = Math.floor(p), b = Math.min(cols - 1, a + 1), q = p - a;
      return mix(mix(A.h[a], A.h[b], q), mix(B.h[a], B.h[b], q), k);
    }
    var wide = mix(A.w, B.w, k);
    var x0 = x + d.box[0] * w, x1 = x + d.box[2] * w, top = y + d.box[1] * h, ground = y + d.box[3] * h, mid = (x0 + x1) / 2;
    var tall = ground - top, legs = tall * LEGS, knee = ground - legs;                   // above the knee line: the body
    var S = Math.max(24, Math.min(96, Math.round(w / 3))), nw = img.naturalWidth, nh = img.naturalHeight, kneeSrc = (knee - y) / h * nh;
    for (var s = 0; s < S; s++) {
      var a0 = x + w * s / S, a1 = x + w * (s + 1) / S;
      var r = high(1 - ((a0 + a1) / 2 - x0) / (x1 - x0));
      var give = (1 - r) * tall;                               // how far this part of the back has come down
      var lg = Math.max(LEGS_MIN, 1 - give / legs);            // the legs fold first ...
      var bd = Math.max(BODY_MIN, 1 - Math.max(0, give - legs * (1 - lg)) / (tall - legs));   // ... then the body gives a little
      var d0 = mid + (a0 - mid) * wide, dw = (a1 - a0) * wide + 0.7, kneeTo = ground - legs * lg;
      ctx.drawImage(img, nw * s / S, 0, nw / S, kneeSrc, d0, kneeTo - (knee - y) * bd, dw, (knee - y) * bd);
      ctx.drawImage(img, nw * s / S, kneeSrc, nw / S, nh - kneeSrc, d0, kneeTo, dw, (y + h - knee) * lg);
    }
  }
  window.addEventListener('resize', function () { drawDeath(document.querySelector('main.battle')); });

  function send(form, button) {
    Combat.set('submitting');                                   // before anything else: a second press finds the lock
    var token = ++Combat.token, sent = +document.querySelector('main.battle').dataset.turn;
    var data = new FormData(form);
    data.set(button.name, button.value);
    load(form.action, {method: 'POST', body: new URLSearchParams(data)})
      .then(function (html) { if (token === Combat.token) show(html, sent); })
      .catch(function () {
        /* No answer (connection dropped, timed out). The move may or may not have reached the server, and
           sending it again could never play it twice (the server takes one action per turn), but the server
           knows which: ask it for the fight as it stands and go on from there. */
        if (token !== Combat.token) return;
        load('/explore/play', {method: 'GET'})
          .then(function (html) { if (token === Combat.token) show(html, sent, true); })
          .catch(function () { location.replace('/explore/play'); });
      });
  }

  /* a page from the server, or a rejected promise when it does not answer in time */
  function load(url, options) {
    var ctl = window.AbortController ? new AbortController() : null;
    var timer = ctl ? setTimeout(function () { ctl.abort(); }, ANSWER_LIMIT) : null;
    options.credentials = 'same-origin';
    if (ctl) options.signal = ctl.signal;
    return fetch(url, options).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.text();
    }).then(function (html) { clearTimeout(timer); return html; }, function (err) { clearTimeout(timer); throw err; });
  }

  /* Swap in the fight the server answered with, and act the turn out if it is a new one. `sent` is the turn the
     move was sent for; `recovered` means this page was asked for after a lost answer. */
  function show(html, sent, recovered) {
    var doc = new DOMParser().parseFromString(html, 'text/html');
    var next = doc.querySelector('main.battle'), now = document.querySelector('main.battle');
    if (!next || !now) {                                        // the fight is over: the next page of the expedition
      Combat.set('finished');
      location.replace('/explore/play');
      return;
    }
    var before = bars(now);
    if (playing) playing.finish(true);
    var fresh = document.importNode(next, true);
    var moved = +fresh.dataset.turn !== sent;                   // the server took the move (or refused it with a notice)
    var played = fresh.dataset.round !== now.dataset.round      // a turn of the fight was played: there is something to act out
      || (!!fresh.dataset.end && !now.dataset.end);             // ... or it was the winning turn (the round count stops there)
    keepHistory(now, fresh);
    now.replaceWith(fresh);                                     // same scroll position: nothing jumps
    init();                                                     // still locked: the new buttons are painted as such
    if (!moved) {                                               // the move never arrived: nothing happened, pick again
      if (recovered) notice(fresh, 'The connection dropped before your move arrived. Nothing was spent: choose again.');
      Combat.set('player_turn');
      return;
    }
    playing = played ? act(fresh, before) : null;               // act the turn out: dash, swing, hit, the beast's answer
    if (!playing) setTimeout(function () { if (Combat.phase !== 'player_turn' && Combat.phase !== 'finished' && fresh.isConnected) Combat.set('player_turn'); }, SETTLE);
  }

  function notice(main, text) {
    var feed = main.querySelector('.bfeed');
    if (!feed) return;
    var p = document.createElement('p');
    p.className = 'toast li-warn'; p.textContent = text;
    feed.appendChild(p);
  }

  /* Battle History stays open (and scrolled to the top, where the newest turn is) when the next turn comes in */
  function keepHistory(now, fresh) {
    var a = now.querySelector('.bhist'), b = fresh.querySelector('.bhist');
    if (a && b && a.open) b.open = true;
  }

  /* ── Acting a turn out ──────────────────────────────────────────────────────────────────────────────
     The server lists what happened in order (data-events, from the engine's log). Each kind of event has
     a recipe below: times in ms, sizes as a share of the scene's width. A new weapon or attack type is one
     more row. Nothing here decides anything: it only shows what the server already resolved. */
  var RECIPES = {
    strike: {dash: 200, swing: 300, hit: 370, recover: 640, end: 960, knock: 0.024},
    break:  {dash: 300, swing: 440, hit: 520, recover: 900, end: 1320, knock: 0.042, slam: true},   // the ground slam (`slam`)
    beast:  {charge: 220, hit: 370, back: 510, end: 900, knock: 0.022},
    tech:   {end: 1100},                                        // techniques play their own animation (style.css)
    pounce: {crouch: 620, hit: 1080, back: 1320, home: 1760, end: 2800, knock: 0.05}   // Mountain-Splitting Pounce
  };
  var GAP = 160;

  /* the frame-by-frame sword attack (looks.ATTACK_SHEETS, from SHOAIB's video): [ms, frame] keys, played in between.
     He raises the blade behind him (0-6), spins it round in a blue Qi arc while he closes in (7-14), lifts it overhead
     (15-28), cuts down and forward through the beast (29-34, the hit) and settles back on guard (35-40).
     Break is the ground slam from SHOAIB's Break video, played with his own sword: blue Qi gathers at his feet as he
     draws the blade back (0-6), he leaps in with it raised overhead (15-28, no spin), brings it down into the ground
     at the beast's feet (34, the hit: `slam`), holds it there while the dust rises, then steps back on guard (35-40).
     hop / dip: how high he leaps and how low he sinks into the blow, as a share of the scene's width. */
  var BLADE = {
    strike: {keys: [[0, 0], [210, 6], [470, 14], [640, 23], [720, 28], [840, 34], [1150, 40]],
             dash: [180, 560], swing: 720, hit: 800, back: [860, 1200], end: 1260, knock: 0.024},
    break:  {keys: [[0, 0], [300, 6], [301, 15], [700, 28], [850, 34], [1220, 34], [1560, 40]],
             dash: [330, 790], swing: 760, hit: 850, back: [1220, 1560], end: 1640, knock: 0.05, slam: true, hop: 0.03, dip: 0.008}
  };

  function ease(x) { return x < 0 ? 0 : x > 1 ? 1 : 1 - Math.pow(1 - x, 3); }
  function inout(x) { return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2; }
  function span(t, a, b) { return Math.max(0, Math.min(1, (t - a) / (b - a))); }

  function bars(main) {
    var out = {};
    ['me', 'enemy'].forEach(function (k) {
      var bar = main.querySelector('[data-bar="' + k + '"] div'), val = main.querySelector('[data-val="' + k + '"]');
      if (bar && val) out[k] = {bar: bar, val: val, width: bar.style.width, text: val.textContent};
    });
    return out;
  }

  function act(main, before) {
    var events = [];
    try { events = JSON.parse(main.dataset.events || '[]'); } catch (e) {}
    var scene = main.querySelector('.bscene'), fighter = main.querySelector('.fighter'), poses = main.querySelector('.fighter .poses');
    var beastBox = main.querySelector('.beast'), beast = main.querySelector('.beast img');
    var end = endOf(main);                                      // the fight was won on this turn: the beast goes down last
    if ((!events.length && !end) || !scene || !fighter || !poses || !beast || !window.requestAnimationFrame ||
        (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches)) return null;

    var after = bars(main), held = {}, W = scene.clientWidth;
    var maxHp = {me: +main.dataset.maxMe || 0, enemy: +main.dataset.maxEnemy || 0};
    function heavy(who, dmg) { return maxHp[who] && dmg >= maxHp[who] * 0.2 ? ' big' : ''; }   // a fifth of the HP or more
    var trail = fighter.querySelector('.trailfx');
    var sheet = fighter.querySelector('.sheetfx:not(.gsheet):not(.msheet)');   // a frame-by-frame attack, when this look has one
    var msheet = fighter.querySelector('.msheet');              // this turn's technique movement (looks.MOTION_SHEETS)
    var cast = null;                                            // this turn's technique, when it has its own look (web/technique_fx.py)
    try { cast = JSON.parse(main.dataset.cast || 'null'); } catch (e) {}
    var gsheet = fighter.querySelector('.gsheet');              // and a frame-by-frame Guard (looks.GUARD_SHEETS)
    var claws = fighter.querySelector('.clawsfx g'), clawClip = fighter.querySelector('#clawclip rect');
    var fr = fighter.getBoundingClientRect(), br = beastBox.getBoundingClientRect();
    var reachMe = Math.max(0, br.left + br.width * 0.12 - (fr.left + fr.width * (parseFloat(fighter.dataset.tip) || 0.962)));     // sword tip to the beast
    var reachBeast = Math.max(0, br.left - (fr.left + fr.width * 0.64));                       // the beast to your body
    var beastFilter = getComputedStyle(beast).filter;
    var bposes = null, home = beast.dataset.pose || 'idle';
    try { bposes = JSON.parse(beastBox.dataset.poses || 'null'); } catch (e) {}
    function bpose(p) {                                        // a beast with cut-out poses (art/beasts/poses/) changes pose
      if (!bposes || !bposes[p] || beast.dataset.pose === p) return;
      var g = bposes[p];
      beast.src = g.src; beast.style.width = g.w + '%'; beast.style.left = g.left + '%'; beast.style.bottom = g.bottom + '%';
      beast.dataset.pose = p;
    }

    function hold(who) {                                        // keep a bar at last turn's value until its hit lands
      if (!before[who] || !after[who] || held[who]) return;
      held[who] = true;
      after[who].bar.style.width = before[who].width; after[who].val.textContent = before[who].text;
    }
    function drop(who) {
      if (!held[who]) return;
      held[who] = false;
      after[who].bar.style.width = after[who].width; after[who].val.textContent = after[who].text;
    }
    function pose(p) { if (fighter.dataset.pose !== p) fighter.dataset.pose = p; }
    function hero(x, y, rot) { poses.style.transform = 'translate(' + x + 'px,' + y + 'px) rotate(' + (rot || 0) + 'deg)'; }
    function animal(x, y, rot, flash) {
      beast.style.transform = 'translate(' + x + 'px,' + y + 'px) rotate(' + rot + 'deg)';
      beast.style.filter = flash > 0.05 ? beastFilter + ' brightness(' + (1 + 1.8 * flash) + ') saturate(' + (1 - 0.6 * flash) + ')' : '';
    }
    function pop(box, cls, text) {
      var n = document.createElement('span');
      n.className = 'tnum ' + cls; n.textContent = text; box.appendChild(n);
      setTimeout(function () { n.remove(); }, 1300);
    }
    function burst(cls, xPct, yPct, color) {
      var n = document.createElement('span');
      n.className = cls; n.style.left = xPct + '%'; n.style.top = yPct + '%';
      if (color) n.style.setProperty('--sc', color);
      scene.appendChild(n);
      setTimeout(function () { n.remove(); }, 700);
    }
    function at(rect, fx, fy) {                                 // a point inside a box, as % of the scene
      var s = scene.getBoundingClientRect();
      return [(rect.left + rect.width * fx - s.left) / s.width * 100, (rect.top + rect.height * fy - s.top) / s.height * 100];
    }
    function knocked(h, size) {                                 // out fast, back slowly: [offset 0..1, flash 0..1]
      if (h < 0) return [0, 0];
      return [size * (ease(span(h, 0, 70)) - ease(span(h, 110, 420))), h < 120 ? 1 - h / 120 : 0];
    }

    /* the moment your weapon lands: the damage number and spark, or Blocked / Missed. A Break (R.slam) comes down into
       the ground at the beast's feet whether it hits or not. */
    function strikes(ev, R) {
      var p = at(br, 0.12, 0.42);
      if (R.slam) slam();
      if (ev.hit) {
        drop('enemy'); pop(beastBox, 'hit' + heavy('enemy', ev.dmg), '−' + ev.dmg); burst('tspark', p[0], p[1]);
        if (R.shake && scene.animate) scene.animate([{transform: 'none'}, {transform: 'translate(-7px,4px)'}, {transform: 'translate(7px,-4px)'},
          {transform: 'translate(-4px,2px)'}, {transform: 'none'}], {duration: 380});
      } else {
        burst('tring', p[0] + 4, p[1] + 6); pop(beastBox, 'word', ev.blocked ? 'Blocked' : 'Missed');
      }
    }

    /* Break's Qi: it gathers in rings at your feet as you draw back (`gathered`), and bursts out of the ground where
       the blade comes down (`slam`): spikes of blue Qi, the split ground (art/fx/break_*.webp, scripts/make_break_fx.py),
       a shockwave, stones, a cloud of dust, and a hard shake. */
    function gathered() {
      var g = at(fr, sheet ? 0.44 : 0.46, 0.96);
      fx('bqring', g[0], g[1], 760); fx('bqring q2', g[0], g[1], 900);
    }
    function slam() {
      var f = at(br, 0.1, 0.96);
      fx('bcrater', f[0], f[1], 2600); fx('bburst', f[0], f[1], 1000); fx('bwave', f[0], f[1], 800); fx('bwave w2', f[0], f[1], 1000);
      fx('bflash', 50, 50, 450);
      for (var i = 0; i < 12; i++) {
        var a = Math.PI * (1.08 + 0.84 * i / 11) + (Math.random() - 0.5) * 0.3, d = 50 + Math.random() * 130;
        fx('pdebris' + (i % 3 ? ' cold' : ''), f[0], f[1] - 1, 900, {'--dx': Math.cos(a) * d + 'px', '--dy': Math.sin(a) * d * 0.9 + 'px',
          '--rot': (Math.random() * 540 - 270) + 'deg', '--sz': (3 + Math.random() * 4) + 'px'});
      }
      for (var j = 0; j < 6; j++) {                              // dust rolls out both ways along the ground
        var side = j % 2 ? 1 : -1;
        fx('bdust', f[0] + side * (1 + j), f[1] - 2 - Math.random() * 3, 1700, {'--dx': side * (30 + 18 * j) + 'px',
          '--s': (0.8 + Math.random() * 0.7).toFixed(2), 'animation-delay': (40 * j) + 'ms'});
      }
      if (scene.animate) scene.animate([{transform: 'none'}, {transform: 'translate(-11px,8px)'}, {transform: 'translate(10px,-6px)'},
        {transform: 'translate(-7px,4px)'}, {transform: 'translate(4px,-2px)'}, {transform: 'none'}], {duration: 520});
    }

    /* your weapon attack: wind up, dash, swing with a trail, then step back */
    function attack(ev) {
      if (sheet) return sweep(ev);
      var R = RECIPES[ev.act] || RECIPES.strike, done = false, began = false;
      if (ev.hit) hold('enemy');
      fighter.dataset.trail = R.slam ? 'slam' : ev.act;
      return {end: R.end, render: function (t) {
        if (R.slam && t >= 0 && !began) { began = true; gathered(); }
        pose(t < 0 || t >= R.recover ? 'idle' : t < R.swing ? 'windup' : 'strike');
        var x = 0, y = 0;
        if (t < R.dash) { var k = ease(span(t, 0, R.dash)); x = -0.011 * W * k; y = 3 * k; }
        else if (t < R.recover) { x = -0.011 * W + (reachMe + 0.011 * W) * ease(span(t, R.dash, R.hit)); }
        else if (t < R.end) { var b = inout(span(t, R.recover, R.end)); x = reachMe * (1 - b); y = -0.035 * W * Math.sin(Math.PI * b); }
        hero(x, y);
        trail.style.clipPath = 'inset(0 ' + (100 - 100 * span(t, R.swing - 20, R.hit + 10)) + '% 0 0)';     // sweeps left to right
        trail.style.opacity = t < R.swing - 20 ? 0 : 1 - span(t, R.hit + 60, R.hit + 300);
        var k2 = ev.hit ? knocked(t - R.hit, R.knock * W) : [0, 0];
        animal(k2[0], 0, k2[0] / (R.knock * W || 1) * 5, k2[1]);
        if (t >= R.hit && !done) { done = true; strikes(ev, R); }
      }};
    }

    /* the same attack, frame by frame from the video: the spin closes the distance, the forward cut lands */
    function sweep(ev) {
      var R = BLADE[ev.act] || BLADE.strike, done = false, began = false;
      var n = +sheet.dataset.frames, cols = +sheet.dataset.cols, rows = +sheet.dataset.rows;
      if (ev.hit) hold('enemy');
      fighter.dataset.trail = R.slam ? 'slam' : ev.act;
      function show(f) {
        f = Math.max(0, Math.min(n - 1, Math.round(f)));
        sheet.style.backgroundPosition = (f % cols) / (cols - 1) * 100 + '% ' + Math.floor(f / cols) / (rows - 1) * 100 + '%';
      }
      return {end: R.end, render: function (t) {
        if (R.slam && t >= 0 && !began) { began = true; gathered(); }
        if (t < 0 || t >= R.end) { pose('idle'); hero(0, 0); }
        else {
          pose('sheet');
          var f = R.keys[R.keys.length - 1][1];
          for (var j = 1; j < R.keys.length; j++) {
            if (t < R.keys[j][0]) { var a = R.keys[j - 1], b = R.keys[j]; f = a[1] + (b[1] - a[1]) * span(t, a[0], b[0]); break; }
          }
          show(f);
          var x = reachMe * inout(span(t, R.dash[0], R.dash[1])), y = 0;
          if (R.hop) y = -R.hop * W * Math.sin(Math.PI * span(t, R.dash[0], R.dash[1]));              // a leap in, blade overhead
          if (R.dip && t >= R.hit && t < R.back[0]) y = R.dip * W * (1 - span(t, R.back[0] - 160, R.back[0]));  // into the blow
          if (t >= R.back[0]) { var r = inout(span(t, R.back[0], R.back[1])); x = reachMe * (1 - r); y = -0.03 * W * Math.sin(Math.PI * r); }
          hero(x, y);
        }
        trail.style.clipPath = 'inset(0 ' + (100 - 100 * span(t, R.swing - 20, R.hit + 10)) + '% 0 0)';
        trail.style.opacity = t < R.swing - 20 ? 0 : 1 - span(t, R.hit + 60, R.hit + 320);
        var k2 = ev.hit ? knocked(t - R.hit, R.knock * W) : [0, 0];
        animal(k2[0], 0, k2[0] / (R.knock * W || 1) * 5, k2[1]);
        if (t >= R.hit && !done) { done = true; strikes(ev, R); }
      }};
    }

    /* your Guard, frame by frame from the video: `h` is ms since the blow landed. He stands with the blade raised as
       the beast comes in (frames 0-3), the blow bursts into a gold flash and sparks on the blade (from frame 4), he
       leans back under it and steadies. False when this look has no Guard frames. */
    var GUARD = {ready: 320, first: 4, ms: 34};
    function block(h) {
      if (!gsheet) return false;
      var n = +gsheet.dataset.frames, cols = +gsheet.dataset.cols, rows = +gsheet.dataset.rows;
      var f = h < 0 ? Math.floor((GUARD.first - 1) * span(h, -GUARD.ready, 0)) : GUARD.first + Math.floor(h / GUARD.ms);
      if (h < -GUARD.ready || f >= n) { pose('idle'); return true; }
      gsheet.style.backgroundPosition = (f % cols) / (cols - 1) * 100 + '% ' + Math.floor(f / cols) / (rows - 1) * 100 + '%';
      pose('guard');
      return true;
    }
    function blockTime() { return gsheet ? (+gsheet.dataset.frames - GUARD.first) * GUARD.ms : 0; }

    /* the beast's attack: rears back, charges, claws; you are hit, or your Guard stops it (and may counter) */
    function charge(ev) {
      var R = RECIPES.beast, guard = ev.act === 'guard', done = false, countered = false;
      if (guard) { if (ev.counter) hold('enemy'); } else hold('me');
      return {end: Math.max(R.end + (guard && ev.counter ? 200 : 0), guard ? R.hit + blockTime() : 0), render: function (t) {
        var x = 0, y = 0, rot = 0;
        if (t < R.charge) { var q = ease(span(t, 0, R.charge)); x = 0.015 * W * q; rot = 4 * q; }
        else if (t < R.back) { var c = span(t, R.charge, R.hit); x = 0.015 * W - (reachBeast + 0.015 * W) * c * c; rot = -6 * c; }
        else if (t < R.end) { var r = inout(span(t, R.back, R.end)); x = -reachBeast * (1 - r); y = -0.024 * W * Math.sin(Math.PI * r); }
        bpose(t < R.charge ? 'crouch' : t < R.back ? 'leap' : 'idle');
        var ck = guard && ev.counter ? knocked(t - R.hit - 130, 0.03 * W) : [0, 0];
        animal(x + ck[0], y, rot, ck[1]);
        var h = t - R.hit;
        if (!guard) {
          var k = knocked(h, R.knock * W);
          pose('idle'); hero(-k[0], 0, -k[0] / 6);
          poses.style.filter = k[1] > 0.05 ? 'sepia(' + 0.7 * k[1] + ') saturate(' + (1 + 3 * k[1]) + ') hue-rotate(-28deg)' : '';
          var cw = span(t, R.hit - 70, R.hit + 15) * 1100;
          clawClip.setAttribute('x', 1320 - cw); clawClip.setAttribute('width', cw);
          claws.setAttribute('opacity', t < R.hit - 70 ? 0 : 1 - span(t, R.hit + 40, R.hit + 260));
        } else {
          if (!block(h)) pose(ev.counter && h >= 110 && h < 380 ? 'strike' : 'idle');
          hero(0, 0);
        }
        if (h >= 0 && !done) {
          done = true;
          var p = at(fr, 0.52, 0.5);
          if (guard) { if (!gsheet) burst('tring', p[0], p[1]); pop(fighter, 'word', 'Blocked'); }
          else { drop('me'); pop(fighter, 'hurt' + heavy('me', ev.dmg), '−' + ev.dmg); burst('tspark', p[0], p[1], '#FFC2B8'); }
        }
        if (guard && ev.counter && h >= 130 && !countered) { countered = true; drop('enemy'); pop(beastBox, 'hit' + heavy('enemy', ev.counter), '−' + ev.counter); }
      }};
    }

    /* a fleeting effect over the scene at (x%, y%): removed after `life` ms */
    var PICTURES = {pcrater: main.dataset.crater || '/art/fx/crater.webp', bcrater: '/art/fx/break_crater.webp', bburst: '/art/fx/break_burst.webp'};
    function fx(cls, xPct, yPct, life, style) {
      var src = PICTURES[cls.split(' ')[0]];
      var n = document.createElement(src ? 'img' : 'span');
      n.className = cls; n.style.left = xPct + '%'; n.style.top = yPct + '%';
      if (src) { n.src = src; n.alt = ''; }
      Object.keys(style || {}).forEach(function (k) { n.style.setProperty(k, style[k]); });
      scene.appendChild(n);
      setTimeout(function () { n.remove(); }, life);
      return n;
    }

    /* the Mountain Tiger's Mountain-Splitting Pounce (battle.UNIQUE_SKILLS): it sinks low with golden Qi swirling at
       its paws, leaps high across the arena, comes down on you and splits the ground in a golden shockwave, bounds
       back and roars, Roused. The damage, the stun and the block come from the server like any other hit. */
    function pounce(ev) {
      var R = RECIPES.pounce, did = {}, lastGhost = -1e9;
      var land = -(reachBeast + 0.03 * W), bf = beastFilter && beastFilter !== 'none' ? beastFilter + ' ' : '';
      if (ev.dmg) hold('me');
      function once(k) { if (did[k]) return false; did[k] = true; return true; }
      return {end: R.end, render: function (t) {
        var x = 0, y = 0, rot = 0, sx = 1, sy = 1, glow = 0;
        if (t < R.crouch) { var q = ease(span(t, 0, R.crouch)); x = 0.02 * W * q; sy = 1 - 0.13 * q; sx = 1 + 0.05 * q; glow = q; }
        else if (t < R.hit) { var c = span(t, R.crouch, R.hit); x = 0.02 * W + (land - 0.02 * W) * inout(c); y = -0.2 * W * Math.sin(Math.PI * c);
          rot = -14 + 30 * c; sy = 1 + 0.06 * Math.sin(Math.PI * c); glow = 1; }
        else if (t < R.back) { var l = span(t, R.hit, R.hit + 170); x = land; sy = 0.88 + 0.12 * l; sx = 1.07 - 0.07 * l; glow = 1 - 0.4 * l; }
        else if (t < R.home) { var r = inout(span(t, R.back, R.home)); x = land * (1 - r); y = -0.07 * W * Math.sin(Math.PI * r); rot = 6 * Math.sin(Math.PI * r); glow = 0.6; }
        else { var p2 = Math.min(1, span(t, R.home, R.end) * 1.6); sx = sy = 1 + 0.06 * Math.sin(Math.PI * p2); glow = 0.6 + 0.7 * Math.sin(Math.PI * p2); }
        if (bposes) { bpose(t < R.crouch ? 'crouch' : t < R.hit ? 'leap' : t < R.back ? 'slam' : t < R.home ? 'idle' : 'roar'); if (t < R.crouch) sy = 1 - 0.05 * (1 - sy) / 0.13; }
        beast.style.transform = 'translate(' + x + 'px,' + y + 'px) rotate(' + rot + 'deg) scale(' + sx + ',' + sy + ')';
        beast.style.filter = glow > 0.02 ? bf + 'drop-shadow(0 0 ' + (6 + 24 * glow) + 'px rgba(255,186,64,' + (0.95 * glow).toFixed(2) + ')) brightness(' + (1 + 0.22 * glow) + ')' : '';
        if (t >= 0 && once('gather')) { var g = at(br, 0.5, 0.96); fx('pqring', g[0], g[1], R.crouch + 260); fx('pqring q2', g[0], g[1], R.crouch + 260); }
        if (t >= R.crouch + 60 && t < R.hit - 40 && t - lastGhost > (bposes ? 130 : 95)) {                     // golden afterimages along the leap
          lastGhost = t;
          var gh = beast.cloneNode(false); gh.className = 'pghost'; gh.style.filter = ''; if (bposes) { gh.style.top = 'auto'; gh.style.height = 'auto'; } beastBox.appendChild(gh);
          setTimeout(function () { gh.remove(); }, 300);
        }
        var h = t - R.hit;
        if (h >= 0 && once('impact')) {
          var f = at(fr, 0.5, 0.97);
          fx('pcrater', f[0], f[1], 3400); fx('pwave', f[0], f[1], 900); fx('pwave w2', f[0], f[1], 1100); fx('pflash', 50, 50, 500);
          for (var i = 0; i < 14; i++) {
            var a = Math.PI * (1.05 + 0.9 * i / 13) + (Math.random() - 0.5) * 0.3, d = 60 + Math.random() * 140;
            fx('pdebris' + (i % 3 ? '' : ' hot'), f[0], f[1], 900, {'--dx': Math.cos(a) * d + 'px', '--dy': Math.sin(a) * d * 0.9 + 'px',
              '--rot': (Math.random() * 540 - 270) + 'deg', '--sz': (5 + Math.random() * 9) + 'px'});
          }
          if (scene.animate) scene.animate([{transform: 'none'}, {transform: 'translate(-14px,9px)'}, {transform: 'translate(13px,-8px)'},
            {transform: 'translate(-9px,5px)'}, {transform: 'translate(6px,-3px)'}, {transform: 'none'}], {duration: 560});
          var p = at(fr, 0.52, 0.5);
          if (ev.guard) { if (!gsheet) burst('tring', p[0], p[1]); pop(fighter, 'word', 'Guarded'); }
          if (ev.dmg) { drop('me'); pop(fighter, 'hurt' + heavy('me', ev.dmg), '−' + ev.dmg); }
        }
        if (ev.stun && h >= 260 && once('stun')) pop(fighter, 'word stun', 'Stunned!');
        if (ev.dmg && !ev.guard) {
          var k = knocked(h, R.knock * W);
          pose('idle'); hero(-k[0], 0, -k[0] / 5);
          poses.style.filter = k[1] > 0.05 ? 'sepia(' + 0.7 * k[1] + ') saturate(' + (1 + 3 * k[1]) + ') hue-rotate(-28deg)' : '';
        } else { if (!(ev.guard && block(h))) pose('idle'); hero(0, 0); }
        if (t >= R.home && once('roar')) {
          var m = at(br, 0.16, 0.36);
          fx('proar', m[0], m[1], 900); fx('proar r2', m[0], m[1], 1100);
          pop(beastBox, 'word roused', 'Roused!');
        }
      }};
    }

    /* A technique with its own look (web/technique_fx.py, docs/web.md "Techniques"). The cultivator plays the shared
       movement (`fist`: SHOAIB's punch video, a jab then a lunging punch, looks.MOTION_SHEETS) and the technique's own
       pictures fly or burst from his fist, everything timed from the release, the frame the fist is furthest out.
       The grade sets how long the cast lasts (technique_fx.GRADE_MS) and how much spectacle surrounds it: Yellow and
       up glow, Mystic and up gather Qi rings, Earth and up raise a pillar of Qi and dim the scene, Heaven darkens the
       sky. The damage comes from the server like any other hit, and the HP bar drops when the blow lands. */
    var TIER = {Mortal: 0, Yellow: 1, Mystic: 2, Earth: 3, Heaven: 4};
    var FIST = {jab: [0.66, 0.28], lunge: [0.685, 0.287]};       // the fist at its furthest, as shares of the fighter's box
    function technique(ev) {
      var X = cast.fx, tier = TIER[cast.grade] || 0, did = {}, made = [], tc = cast.color;
      var mn = msheet ? +msheet.dataset.frames : 0, mcols = msheet ? +msheet.dataset.cols : 1, mrows = msheet ? +msheet.dataset.rows : 1;
      var JAB = msheet ? +msheet.dataset.jab : 5, OUT = msheet ? +msheet.dataset.release : 12, BACK = msheet ? +msheet.dataset.back : 21;
      var dragons = X.play === 'dragons', end = X.ms;
      /* the punches: each lands at `at` (ms), a jab or the lunge. One lunge for most; Nine Dragons throws four,
         jab-lunge-jab-lunge, each loosing X.punches[i] dragons (1-2-3-3: nine). */
      var punches = dragons ? [{at: 360, kind: 'jab'}, {at: 640, kind: 'lunge'}, {at: 960, kind: 'jab'}, {at: 1240, kind: 'lunge'}]
                            : [{at: Math.round(end * 0.45), kind: 'lunge'}];
      var R = punches[punches.length - 1].at;                       // the last release
      var LAND = dragons ? R + 420 : X.play === 'vortex' ? R + 180 : X.play === 'charge' ? R + 40 : R;   // when the blow lands on the beast
      var settle = [[Math.max(R + 280, end * 0.7), BACK - 1], [end * 0.95, (mn || 36) - 1]];   // held out, then back on guard
      var keys = dragons                                              // [ms, frame]: jab, lunge, (pulled back) jab, lunge
        ? [[0, 0], [300, JAB - 1], [360, JAB], [440, 7], [560, 9], [640, OUT], [740, OUT + 2], [820, BACK + 3], [821, 2],
           [900, JAB - 1], [960, JAB], [1040, 7], [1160, 9], [1240, OUT], [1400, OUT + 4]].concat(settle)
        : [[0, 0], [R - 90, 9], [R, OUT], [R + 120, OUT + 2]].concat(settle);
      if (ev.hit) hold('enemy');

      function once(k) { if (did[k]) return false; did[k] = true; return true; }
      function show(f) {
        f = Math.max(0, Math.min(mn - 1, Math.round(f)));
        msheet.style.backgroundPosition = (f % mcols) / (mcols - 1) * 100 + '% ' + Math.floor(f / mcols) / (mrows - 1) * 100 + '%';
      }
      var BIG = Math.max(1, Math.min(2, br.width / (0.25 * W)));     // sized to the beast: phones draw it larger in the scene
      var HAND = msheet && msheet.dataset.hand ? msheet.dataset.hand.split(',').map(Number) : FIST.lunge;
      function fist(kind) { var q = kind === 'jab' ? FIST.jab : HAND; return at(fr, q[0], q[1]); }   // where the blow leaves him
      function pic(src, cls, p, w, life, mirror) {                   // one of the technique's pictures, centred on p
        var n = document.createElement('img');
        n.className = 'tart ' + cls; n.src = src; n.alt = '';
        n.style.left = p[0] + '%'; n.style.top = p[1] + '%'; n.style.width = w * BIG + '%';
        n.style.setProperty('--tc', tc);
        scene.appendChild(n); made.push(n);
        setTimeout(function () { n.remove(); }, life);
        return n;
      }
      function T(dx, dy, s, r, mirror) {
        return 'translate(-50%,-50%) translate(' + dx + 'px,' + dy + 'px) rotate(' + (r || 0) + 'deg) scale(' + (mirror ? -s : s) + ',' + s + ')';
      }
      function behind(n) { scene.insertBefore(n, fighter); }           // a dimmed scene or Heaven sky: over the arena, under everyone
      function px(a, b) { return [(b[0] - a[0]) / 100 * W, (b[1] - a[1]) / 100 * scene.clientHeight]; }
      function shake(k) {
        if (!scene.animate) return;
        var a = 4 + 3 * k;
        scene.animate([{transform: 'none'}, {transform: 'translate(' + -a + 'px,' + a * 0.6 + 'px)'}, {transform: 'translate(' + a + 'px,' + -a * 0.5 + 'px)'},
          {transform: 'translate(' + -a * 0.6 + 'px,' + a * 0.3 + 'px)'}, {transform: 'none'}], {duration: 320 + 50 * k});
      }
      function lands() {                                              // the blow lands: number, knock, flash, shake by grade
        if (ev.hit) { drop('enemy'); pop(beastBox, 'hit' + heavy('enemy', ev.dmg), '−' + ev.dmg); }
        else pop(beastBox, 'word', 'Missed');
        var b = at(br, 0.3, 0.45);
        burst('tspark', b[0], b[1], tc);
        shake(tier + (cast.effect === 'heavy' ? 2 : 0));
        if (cast.effect === 'stagger') setTimeout(function () { var d = at(br, 0.42, 0.12); fx('tdizzy', d[0], d[1], 1300, {'--tc': tc}); }, 150);
        if (cast.effect === 'heavy') { var g = at(br, 0.36, 0.97); fx('pcrater', g[0], g[1], 1800); fx('pwave', g[0], g[1], 800); }   // the golden crater
        if (cast.effect === 'pierce') { var q = at(br, 0.1, 0.45); fx('tpierce', q[0], q[1], 700, {'--tc': tc}); }      // a line of light through it
      }

      // what each technique does with its pictures (technique_fx.PLAYS), h = ms since the last release
      var PLAY = {
        burst: function (h) {                                        // Iron Fist: a burst of iron Qi on the beast
          if (h >= 0 && once('burst')) {
            var n = pic(X.art[0], 'tglow', at(br, 0.3, 0.42), 30, 800);
            n.animate([{transform: T(0, 0, 0.3), opacity: 0}, {transform: T(0, 0, 1.08), opacity: 1, offset: 0.25}, {transform: T(0, 0, 1.18), opacity: 0}],
              {duration: 760, easing: 'ease-out', fill: 'forwards'});
            lands();
          }
        },
        claw: function (h) {                                         // Fierce Tiger Claw: three golden rakes torn across it
          if (h >= -40 && once('claw')) {
            var n = pic(X.art[0], 'tglow tclaw', at(br, 0.36, 0.3), 26, 1100);
            n.animate([{clipPath: 'inset(0 0 100% 100%)', transform: T(0, 0, 0.9), opacity: 1}, {clipPath: 'inset(0 0 0 0)', transform: T(0, 0, 1), opacity: 1, offset: 0.2},
              {clipPath: 'inset(0 0 0 0)', transform: T(0, 0, 1.02), opacity: 1, offset: 0.6}, {clipPath: 'inset(0 0 0 0)', transform: T(0, 0, 1.05), opacity: 0}],
              {duration: 1050, easing: 'ease-out', fill: 'forwards'});
          }
          if (h >= 60 && once('land')) lands();
        },
        charge: function (h) {                                       // Raging Bull Fist: the bull's head charges from the fist
          if (h >= -300 && once('bull')) {
            var from = fist('lunge'), to = at(br, 0.3, 0.45), d = px(to, from);
            var n = pic(X.art[0], 'tglow', to, 34, 1100);
            n.animate([{transform: T(d[0], d[1], 0.35, 0, X.mirror), opacity: 0.2}, {transform: T(d[0] * 0.6, d[1] * 0.6, 0.6, 0, X.mirror), opacity: 1, offset: 0.25},
              {transform: T(0, 0, 1.05, 0, X.mirror), opacity: 1, offset: 0.33}, {transform: T(0.02 * W, 0, 1.2, 0, X.mirror), opacity: 0}],
              {duration: 1040, easing: 'ease-in', fill: 'forwards'});
          }
          if (h >= 40 && once('land')) lands();
        },
        vortex: function (h) {                                       // Rolling Thunder: a thunder vortex rolls onto it and spins
          if (h >= -160 && once('ball')) {                           // launched by the push itself
            var from = fist('lunge'), to = at(br, 0.32, 0.42), d = px(to, from);
            var n = pic(X.art[0], 'tglow tflicker', to, 30, 1300);
            n.animate([{transform: T(d[0], d[1], 0.2, 0), opacity: 0.4}, {transform: T(0, 0, 0.9, 300), opacity: 1, offset: 0.27},
              {transform: T(0, 0, 1.15, 760), opacity: 1, offset: 0.7}, {transform: T(0, 0, 1.25, 1000), opacity: 0}],
              {duration: 1250, easing: 'ease-out', fill: 'forwards'});
          }
          if (h >= 180 && once('land')) lands();
        },
        rise: function (h) {                                         // Mountain-Shattering Fist: a mountain bursts up under it
          if (h >= 0 && once('mountain')) {
            var n = pic(X.art[0], 'trock', at(br, 0.4, 0.99), 46, 1700);
            n.animate([{transform: 'translate(-50%,-100%) translateY(55%) scale(0.9,0.25)', opacity: 0}, {transform: 'translate(-50%,-100%) translateY(-4%) scale(1.04,1.08)', opacity: 1, offset: 0.13},
              {transform: 'translate(-50%,-100%) scale(1)', opacity: 1, offset: 0.2}, {transform: 'translate(-50%,-100%) translateY(2%) scale(1.02)', opacity: 1, offset: 0.7},
              {transform: 'translate(-50%,-100%) translateY(10%) scale(1.04)', opacity: 0}], {duration: 1650, easing: 'ease-out', fill: 'forwards'});
            var g = at(br, 0.4, 0.97);
            for (var i = 0; i < 12; i++) {
              var a = Math.PI * (1.08 + 0.84 * i / 11), dd = 60 + Math.random() * 150;
              fx('pdebris' + (i % 3 ? '' : ' hot'), g[0], g[1] - 2, 1000, {'--dx': Math.cos(a) * dd + 'px', '--dy': Math.sin(a) * dd + 'px',
                '--rot': (Math.random() * 540 - 270) + 'deg', '--sz': (4 + Math.random() * 6) + 'px'});
            }
            lands();
          }
        },
        dragons: function () {},                                     // Nine Dragons: see `loose` below
        prints: function (h) {                                       // Twin Palm Strike: one print for each of its two hits
          [0, 1].forEach(function (k) {
            if (h >= -260 + 140 * k && once('print' + k)) {
              var from = fist('lunge'), to = at(br, 0.3 + 0.04 * k, 0.36 + 0.1 * k), d = px(to, from);
              var n = pic(X.art[k], 'tglow tprint', to, 15, 900);
              n.animate([{transform: T(d[0], d[1], 0.35), opacity: 0}, {transform: T(d[0] * 0.4, d[1] * 0.4, 0.8), opacity: 1, offset: 0.25},
                {transform: T(0, 0, 1), opacity: 1, offset: 0.3}, {transform: T(0.01 * W, 0, 1.12), opacity: 0}],
                {duration: 860, easing: 'ease-in', fill: 'forwards'});
            }
            if (h >= 140 * k && once('hit' + k)) { if (k === 0) lands(); else { var b = at(br, 0.34, 0.46); burst('tspark', b[0], b[1], tc); shake(0); } }
          });
        },
        fan: function (h) {                                          // Thousand Shadow Palm: a fan of shadow palms opens over it
          if (h >= -120 && once('fan')) {                            // from its root on the ground in front of the beast
            var n = pic(X.art[0], 'tglow tfan', at(br, 0.34, 0.98), 46, 1500);
            n.animate([{transform: 'translate(-50%,-100%) scale(0.15,0.1)', opacity: 0},
              {transform: 'translate(-50%,-100%) scale(0.9,0.95)', opacity: 0.95, offset: 0.12},
              {transform: 'translate(-50%,-100%) scale(1)', opacity: 1, offset: 0.25},
              {transform: 'translate(-50%,-100%) scale(1.04,1.06)', opacity: 0.9, offset: 0.75},
              {transform: 'translate(-50%,-100%) scale(1.08,1.12)', opacity: 0}], {duration: 1450, easing: 'ease-out', fill: 'forwards'});
          }
          [0, 1, 2].forEach(function (k) {                           // its three hits
            if (h >= 60 + 140 * k && once('hit' + k)) {
              if (k === 0) lands(); else { var b = at(br, 0.24 + 0.08 * k, 0.3 + 0.12 * k); burst('tspark', b[0], b[1], tc); shake(1); }
            }
          });
        },
        descend: function (h) {                                      // Heaven-Rending Palm: a giant palm comes down through the clouds
          if (h >= -420 && once('palm')) {
            var to = at(br, 0.4, 0.4), n = pic(X.art[0], 'tglow tsky', to, 21, 1500);
            n.animate([{transform: T(0, -0.42 * W, 0.8, 180), opacity: 0}, {transform: T(0, -0.3 * W, 0.92, 180), opacity: 1, offset: 0.12},
              {transform: T(0, 0, 1, 180), opacity: 1, offset: 0.25}, {transform: T(0, 0.006 * W, 1.03, 180), opacity: 1, offset: 0.7},
              {transform: T(0, 0.01 * W, 1.06, 180), opacity: 0}], {duration: 1450, easing: 'ease-in', fill: 'forwards'});
          }
          if (h >= 0 && once('land')) { fx('bflash', 50, 50, 450); var g = at(br, 0.4, 0.97); fx('pwave', g[0], g[1], 900); lands(); }
        }
      };

      /* Nine Dragons Ascending Fist: each punch looses its dragons (1, 2, 3, 3), golden heads streaking from the fist
         to the beast; when the ninth arrives all nine rise around it in one coil of light (the Heaven finale). */
      var flown = 0;
      function loose(i, t) {
        var p = punches[i], n = X.punches[i] || 1;
        if (t < p.at || !once('punch' + i)) return;
        var from = fist(p.kind);
        for (var k = 0; k < n; k++) {
          var to = at(br, 0.28 + 0.06 * k, 0.24 + 0.2 * ((flown + k) % 3)), d = px(to, from);
          var dg = pic(X.art[1 + (flown + k) % 3], 'tglow tdragon', to, 13, 520);
          dg.animate([{transform: T(d[0], d[1], 0.45, -8), opacity: 0}, {transform: T(d[0] * 0.55, d[1] * 0.55 - 14, 0.8, 4), opacity: 1, offset: 0.35},
            {transform: T(0, 0, 1, 0), opacity: 1, offset: 0.8}, {transform: T(10, 0, 1.15, 0), opacity: 0}],
            {duration: 480, delay: 70 * k, easing: 'ease-in', fill: 'both'});
          (function (q) { setTimeout(function () { burst('tspark', q[0], q[1], '#FFD978'); }, 400 + 70 * k); })(to);
        }
        flown += n;
      }

      return {end: end, render: function (t) {
        if (t < 0) return;
        if (once('start')) {                                          // the grade's spectacle around the whole cast
          var feet = at(fr, msheet ? 0.44 : 0.46, 0.96);
          if (tier >= 2) { fx('tqring', feet[0], feet[1], 760, {'--tc': tc}); fx('tqring q2', feet[0], feet[1], 900, {'--tc': tc}); }
          if (tier >= 3) { behind(fx('tdim', 50, 50, end, {'--life': end + 'ms'})); fx('tpillar', feet[0], feet[1], Math.round(end * 0.6), {'--tc': tc}); }
          if (tier >= 4) behind(fx('theaven', 50, 50, end, {'--life': end + 'ms'}));
        }
        var x = 0;
        if (msheet) {
          var f = keys[keys.length - 1][1];
          for (var j = 1; j < keys.length; j++) {
            if (t < keys[j][0]) { var a = keys[j - 1], b = keys[j]; f = a[1] + (b[1] - a[1]) * span(t, a[0], b[0]); break; }
          }
          if (t >= end * 0.95) pose('idle'); else { pose('motion'); show(f); }
        } else {                                                      // no frames for this look: the three poses
          var p = punches.filter(function (q) { return t >= q.at - 200 && t < q.at + 180; })[0];
          pose(!p ? 'idle' : t < p.at ? 'windup' : 'strike');
        }
        x = 0.025 * W * Math.sin(Math.PI * span(t, punches[0].at - 260, R + 380));        // a step in behind the punches
        hero(x, 0);
        poses.style.filter = tier >= 1 && t < R + 200 ? 'drop-shadow(0 0 ' + (4 + 4 * tier) + 'px ' + tc + ')' : '';
        var k2 = ev.hit ? knocked(t - LAND, (0.02 + 0.006 * tier) * W) : [0, 0];
        animal(k2[0], 0, k2[0] / (0.03 * W) * 4, k2[1]);
        if (dragons) {
          punches.forEach(function (_, i) { loose(i, t); });
          if (t >= LAND && once('finale')) {
            var n = pic(X.art[0], 'tglow tcoil', at(br, 0.42, 0.6), 34, 1400);
            n.animate([{transform: T(0, 0.12 * W, 0.6), opacity: 0}, {transform: T(0, 0, 1), opacity: 1, offset: 0.3},
              {transform: T(0, -0.04 * W, 1.06), opacity: 1, offset: 0.75}, {transform: T(0, -0.1 * W, 1.12), opacity: 0}],
              {duration: 1360, easing: 'ease-out', fill: 'forwards'});
            fx('bflash', 50, 50, 450);
            lands();
          }
        } else PLAY[X.play](t - R);
      }, clear: function () { made.forEach(function (n) { n.remove(); }); }};
    }

    /* The victory sequence's middle part (docs/web.md): after the last blow the beast goes down. "warp": its own
       picture goes down through its category's shared movement (drawDeath), then the body stays down. "fall": a beast with no category tips
       over. "rout": bandits scatter. Then the body lies there a moment (linger) before the Victory panel comes up.
       Nothing is decided here: the server has already ended the fight and paid it out, once. */
    function death(d) {
      var cv = d.kind === 'warp' ? beastBox.querySelector('canvas.deathfx') : null, did = {}, total = 0, hitAt = 0;
      if (cv) d.ms.forEach(function (m, n) { if (n < d.impact) hitAt += m; total += m; });
      else total = d.kind === 'rout' ? 600 : 900;
      function once(k) { if (did[k]) return false; did[k] = true; return true; }
      function thud() {
        [0.2, 0.5, 0.8].forEach(function (q, n) { var p = at(br, q, 0.97); fx('ddust', p[0], p[1], 720, {'--dx': (n - 1) * 26 + 'px'}); });
        if (scene.animate) scene.animate([{transform: 'none'}, {transform: 'translate(0,5px)'}, {transform: 'translate(0,-2px)'}, {transform: 'none'}], {duration: 260});
      }
      return {end: total + (d.linger || 800), render: function (t) {
        if (t < 0) return;
        if (once('start')) main.classList.add('dying');
        pose('idle'); hero(0, 0);
        if (cv) {
          drawDeath(main, t);                                  // the beast's own picture, bent through the shared movement
          var flash = 1 - span(t, 0, 200), dim = span(t, total, total + 500);
          cv.style.filter = 'drop-shadow(0 8px 10px rgba(0,0,0,.65)) brightness(' + (1 + 1.2 * flash - 0.28 * dim) + ') saturate(' + (1 - 0.25 * dim) + ')';
          if (t >= hitAt && once('thud')) thud();
        } else if (d.kind === 'rout') {
          var g = ease(span(t, 0, total));
          beast.style.opacity = 1 - g; beast.style.transform = 'translateX(' + 0.06 * W * g + 'px)';
        } else {
          var a = span(t, 0, 260), b = span(t, 260, total), bb = b * b;
          beast.style.transform = 'translateY(' + -30 * bb + '%) rotate(' + (b > 0 ? 82 * bb : -8 * Math.sin(Math.PI * a)) + 'deg)';
          beast.style.filter = 'brightness(' + (1 - 0.45 * bb) + ') saturate(' + (1 - 0.4 * bb) + ')';
          if (b >= 1 && once('thud')) thud();
        }
      }, clear: function () { if (cv) { cv.style.filter = ''; drawDeath(main, Infinity); } beast.style.opacity = ''; }};
    }

    var steps = [], kinds = {};
    function add(step, phase) { step.phase = phase; steps.push(step); }      // whose action this step shows
    events.forEach(function (ev) {
      if (ev.who === 'enemy' && ev.act === 'pounce') { add(pounce(ev), 'beast_acting'); kinds.enemy = 1; if (ev.guard) kinds.guard = 1; }
      else if (ev.who === 'me' && (ev.act === 'strike' || ev.act === 'break')) { add(attack(ev), 'player_acting'); kinds.me = 1; }
      else if (ev.who === 'me' && ev.act === 'guard') { add(charge(ev), 'beast_acting'); kinds.guard = 1; }
      else if (ev.who === 'enemy') { add(charge(ev), 'beast_acting'); kinds.enemy = 1; }
      else if (ev.act === 'tech' && cast && cast.fx) { add(technique(ev), 'player_acting'); kinds.me = 1; }
      else if (ev.act === 'tech') add({end: RECIPES.tech.end, render: function () {}}, 'player_acting');
    });
    var dying = end ? death(end) : null;
    if (dying) { add(dying, 'dying'); main.classList.remove('slain'); }      // .slain (the finished picture) returns in finish()
    if (!steps.length) return null;
    Combat.set(steps[0].phase);
    Object.keys(kinds).forEach(function (k) { main.classList.add('tl-' + k); });
    main.classList.add('tl-hold', 'playing'); fighter.classList.add('acting');
    main.offsetWidth;                                           // the held bars are in place before transitions return
    main.classList.remove('tl-hold');

    var i = 0, start = null, stopped = false;
    function reset() { bpose(home); pose('idle'); poses.style.transform = ''; poses.style.filter = ''; beast.style.transform = ''; beast.style.filter = '';
      trail.style.opacity = 0; claws.setAttribute('opacity', 0); }
    /* the turn has been acted out (or `cut`: another fight replaced this one): hand the turn back to the player */
    function finish(cut) {
      if (stopped) return;
      stopped = true;
      clearTimeout(guard);
      reset(); drop('me'); drop('enemy'); fighter.classList.remove('acting'); main.classList.remove('playing');
      if (dying) {
        dying.clear(); main.classList.remove('dying'); main.classList.add('slain');
        showVictory(main);
        if (cut !== true) Combat.set('finished');               // the fight is won: only the Victory panel's button is left
      }
      if (playing && playing.finish === finish) playing = null;
      if (cut !== true && Combat.phase !== 'dying' && Combat.phase !== 'finished') Combat.set('player_turn');
    }
    function frame(now) {
      if (stopped || !main.isConnected) return;
      if (start === null) start = now;
      var t = now - start, step = steps[i];
      if (t >= step.end + GAP) {
        step.render(step.end + 2000); reset(); i += 1; start = null;
        if (i >= steps.length) return finish();
        Combat.set(steps[i].phase);                             // your action is done: now the beast's (or the other way round)
      }
      else step.render(Math.min(t, step.end));
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
    /* Frames stop while the tab is hidden. The controls must never stay locked because of that: once the
       turn has had its time (and a little more), it ends even if no frame was drawn. */
    var total = steps.reduce(function (sum, st) { return sum + st.end + GAP; }, 0);
    var guard = setTimeout(finish, total + 1500);
    return {finish: finish};
  }

  document.addEventListener('keydown', function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var main = document.querySelector('main.battle');
    if (!main) return;
    if (e.key === 'Escape') { main.querySelectorAll('details[open]').forEach(function (d) { d.open = false; }); return; }
    if (e.key === 'H' || e.key === 'h') { var h = main.querySelector('.bhist'); if (h) h.open = !h.open; return; }   // reading is always allowed
    if (!Combat.can() || e.repeat) return;                      // a held key is not a string of moves
    var k = e.key.toUpperCase(), el = main.querySelector('[data-key="' + k + '"]');
    if (!el) return;
    if (el.tagName === 'DETAILS') { el.open = !el.open; if (el.open) { var f = el.querySelector('.techbtn:not(:disabled)'); if (f) f.focus(); } return; }
    if (!el.disabled) el.click();
  });
  document.addEventListener('click', function (e) {          // close the techniques menu when clicking elsewhere
    document.querySelectorAll('details.techmenu[open]').forEach(function (d) { if (!d.contains(e.target)) d.open = false; });
  });
  window.addEventListener('pageshow', function (e) { if (e.persisted) location.reload(); });   // never a stale, locked page from the back button
  init();
})();
