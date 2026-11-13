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
    var hist = main.querySelector('.bhist'), close = main.querySelector('.histclose');
    if (hist && close) close.addEventListener('click', function () { hist.open = false; hist.querySelector('summary').focus(); });
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
    var played = fresh.dataset.round !== now.dataset.round;     // a turn of the fight was played: there is something to act out
    keepHistory(now, fresh);
    now.replaceWith(fresh);                                     // same scroll position: nothing jumps
    init();                                                     // still locked: the new buttons are painted as such
    if (!moved) {                                               // the move never arrived: nothing happened, pick again
      if (recovered) notice(fresh, 'The connection dropped before your move arrived. Nothing was spent: choose again.');
      Combat.set('player_turn');
      return;
    }
    playing = played ? act(fresh, before) : null;               // act the turn out: dash, swing, hit, the beast's answer
    if (!playing) setTimeout(function () { if (Combat.phase !== 'player_turn' && fresh.isConnected) Combat.set('player_turn'); }, SETTLE);
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
    break:  {dash: 260, swing: 380, hit: 450, recover: 780, end: 1120, knock: 0.042, shake: true},
    beast:  {charge: 220, hit: 370, back: 510, end: 900, knock: 0.022},
    tech:   {end: 1100},                                        // techniques play their own animation (style.css)
    pounce: {crouch: 620, hit: 1080, back: 1320, home: 1760, end: 2800, knock: 0.05}   // Mountain-Splitting Pounce
  };
  var GAP = 160;

  /* the frame-by-frame sword attack (looks.ATTACK_SHEETS, from SHOAIB's video): [ms, frame] keys, played in between.
     He raises the blade behind him (0-6), spins it round in a blue Qi arc while he closes in (7-14), lifts it overhead
     (15-28), cuts down and forward through the beast (29-34, the hit) and settles back on guard (35-40). */
  var BLADE = {
    strike: {keys: [[0, 0], [210, 6], [470, 14], [640, 23], [720, 28], [840, 34], [1150, 40]],
             dash: [180, 560], swing: 720, hit: 800, back: [860, 1200], end: 1260, knock: 0.024},
    break:  {keys: [[0, 0], [250, 6], [540, 14], [730, 23], [820, 28], [960, 34], [1300, 40]],
             dash: [200, 640], swing: 820, hit: 910, back: [980, 1340], end: 1400, knock: 0.042, shake: true}
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
    if (!events.length || !scene || !fighter || !poses || !beast || !window.requestAnimationFrame ||
        (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches)) return null;

    var after = bars(main), held = {}, W = scene.clientWidth;
    var maxHp = {me: +main.dataset.maxMe || 0, enemy: +main.dataset.maxEnemy || 0};
    function heavy(who, dmg) { return maxHp[who] && dmg >= maxHp[who] * 0.2 ? ' big' : ''; }   // a fifth of the HP or more
    var trail = fighter.querySelector('.trailfx');
    var sheet = fighter.querySelector('.sheetfx');              // a frame-by-frame attack, when this look has one
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

    /* your weapon attack: wind up, dash, swing with a trail, then step back */
    function attack(ev) {
      if (sheet) return sweep(ev);
      var R = RECIPES[ev.act] || RECIPES.strike, done = false;
      if (ev.hit) hold('enemy');
      fighter.dataset.trail = ev.act;
      return {end: R.end, render: function (t) {
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
        if (t >= R.hit && !done) {
          done = true;
          var p = at(br, 0.12, 0.42);
          if (ev.hit) {
            drop('enemy'); pop(beastBox, 'hit' + heavy('enemy', ev.dmg), '−' + ev.dmg); burst('tspark', p[0], p[1]);
            if (R.shake && scene.animate) scene.animate([{transform: 'none'}, {transform: 'translate(-7px,4px)'}, {transform: 'translate(7px,-4px)'},
              {transform: 'translate(-4px,2px)'}, {transform: 'none'}], {duration: 380});
          } else {
            burst('tring', p[0] + 4, p[1] + 6); pop(beastBox, 'word', ev.blocked ? 'Blocked' : 'Missed');
          }
        }
      }};
    }

    /* the same attack, frame by frame from the video: the spin closes the distance, the forward cut lands */
    function sweep(ev) {
      var R = BLADE[ev.act] || BLADE.strike, done = false;
      var n = +sheet.dataset.frames, cols = +sheet.dataset.cols, rows = +sheet.dataset.rows;
      if (ev.hit) hold('enemy');
      fighter.dataset.trail = ev.act;
      function show(f) {
        f = Math.max(0, Math.min(n - 1, Math.round(f)));
        sheet.style.backgroundPosition = (f % cols) / (cols - 1) * 100 + '% ' + Math.floor(f / cols) / (rows - 1) * 100 + '%';
      }
      return {end: R.end, render: function (t) {
        if (t < 0 || t >= R.end) { pose('idle'); hero(0, 0); }
        else {
          pose('sheet');
          var f = R.keys[R.keys.length - 1][1];
          for (var j = 1; j < R.keys.length; j++) {
            if (t < R.keys[j][0]) { var a = R.keys[j - 1], b = R.keys[j]; f = a[1] + (b[1] - a[1]) * span(t, a[0], b[0]); break; }
          }
          show(f);
          var x = reachMe * inout(span(t, R.dash[0], R.dash[1])), y = 0;
          if (t >= R.back[0]) { var r = inout(span(t, R.back[0], R.back[1])); x = reachMe * (1 - r); y = -0.03 * W * Math.sin(Math.PI * r); }
          hero(x, y);
        }
        trail.style.clipPath = 'inset(0 ' + (100 - 100 * span(t, R.swing - 20, R.hit + 10)) + '% 0 0)';
        trail.style.opacity = t < R.swing - 20 ? 0 : 1 - span(t, R.hit + 60, R.hit + 320);
        var k2 = ev.hit ? knocked(t - R.hit, R.knock * W) : [0, 0];
        animal(k2[0], 0, k2[0] / (R.knock * W || 1) * 5, k2[1]);
        if (t >= R.hit && !done) {
          done = true;
          var p = at(br, 0.12, 0.42);
          if (ev.hit) {
            drop('enemy'); pop(beastBox, 'hit' + heavy('enemy', ev.dmg), '−' + ev.dmg); burst('tspark', p[0], p[1]);
            if (R.shake && scene.animate) scene.animate([{transform: 'none'}, {transform: 'translate(-7px,4px)'}, {transform: 'translate(7px,-4px)'},
              {transform: 'translate(-4px,2px)'}, {transform: 'none'}], {duration: 380});
          } else {
            burst('tring', p[0] + 4, p[1] + 6); pop(beastBox, 'word', ev.blocked ? 'Blocked' : 'Missed');
          }
        }
      }};
    }

    /* the beast's attack: rears back, charges, claws; you are hit, or your Guard stops it (and may counter) */
    function charge(ev) {
      var R = RECIPES.beast, guard = ev.act === 'guard', done = false, countered = false;
      if (guard) { if (ev.counter) hold('enemy'); } else hold('me');
      return {end: R.end + (guard && ev.counter ? 200 : 0), render: function (t) {
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
          pose(ev.counter && h >= 110 && h < 380 ? 'strike' : 'idle'); hero(0, 0);
        }
        if (h >= 0 && !done) {
          done = true;
          var p = at(fr, 0.52, 0.5);
          if (guard) { burst('tring', p[0], p[1]); pop(fighter, 'word', 'Blocked'); }
          else { drop('me'); pop(fighter, 'hurt' + heavy('me', ev.dmg), '−' + ev.dmg); burst('tspark', p[0], p[1], '#FFC2B8'); }
        }
        if (guard && ev.counter && h >= 130 && !countered) { countered = true; drop('enemy'); pop(beastBox, 'hit' + heavy('enemy', ev.counter), '−' + ev.counter); }
      }};
    }

    /* a fleeting effect over the scene at (x%, y%): removed after `life` ms */
    function fx(cls, xPct, yPct, life, style) {
      var n = document.createElement(cls === 'pcrater' ? 'img' : 'span');
      n.className = cls; n.style.left = xPct + '%'; n.style.top = yPct + '%';
      if (cls === 'pcrater') { n.src = main.dataset.crater || '/art/fx/crater.webp'; n.alt = ''; }
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
          if (ev.guard) { burst('tring', p[0], p[1]); pop(fighter, 'word', 'Guarded'); }
          if (ev.dmg) { drop('me'); pop(fighter, 'hurt' + heavy('me', ev.dmg), '−' + ev.dmg); }
        }
        if (ev.stun && h >= 260 && once('stun')) pop(fighter, 'word stun', 'Stunned!');
        if (ev.dmg && !ev.guard) {
          var k = knocked(h, R.knock * W);
          pose('idle'); hero(-k[0], 0, -k[0] / 5);
          poses.style.filter = k[1] > 0.05 ? 'sepia(' + 0.7 * k[1] + ') saturate(' + (1 + 3 * k[1]) + ') hue-rotate(-28deg)' : '';
        } else { pose('idle'); hero(0, 0); }
        if (t >= R.home && once('roar')) {
          var m = at(br, 0.16, 0.36);
          fx('proar', m[0], m[1], 900); fx('proar r2', m[0], m[1], 1100);
          pop(beastBox, 'word roused', 'Roused!');
        }
      }};
    }

    var steps = [], kinds = {};
    function add(step, phase) { step.phase = phase; steps.push(step); }      // whose action this step shows
    events.forEach(function (ev) {
      if (ev.who === 'enemy' && ev.act === 'pounce') { add(pounce(ev), 'beast_acting'); kinds.enemy = 1; if (ev.guard) kinds.guard = 1; }
      else if (ev.who === 'me' && (ev.act === 'strike' || ev.act === 'break')) { add(attack(ev), 'player_acting'); kinds.me = 1; }
      else if (ev.who === 'me' && ev.act === 'guard') { add(charge(ev), 'beast_acting'); kinds.guard = 1; }
      else if (ev.who === 'enemy') { add(charge(ev), 'beast_acting'); kinds.enemy = 1; }
      else if (ev.act === 'tech') add({end: RECIPES.tech.end, render: function () {}}, 'player_acting');
    });
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
