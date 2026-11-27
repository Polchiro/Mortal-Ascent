/* The fight screen: send a move without leaving the page (no jump to the top), then swap in the next turn. */
(function () {
  var playing = null;
  /* sound (web/static/fight_sound.js): told what just happened on screen; silent if it isn't there */
  function fs(name, arg, delay, opts) { var F = window.FightSound; return F ? F.play(name, arg, delay, opts) : false; }

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
      var waiting = Combat.phase === 'player_turn' && main.dataset.waiting;          // a team fight: you have moved
      if (chip) chip.textContent = waiting ? (chip.dataset.wait || 'Waiting for your party') : (TURN_TEXT[Combat.phase] || '');
    }
  };
  var TURN_TEXT = {player_turn: 'Your turn', submitting: 'Sending…', player_acting: 'You act', beast_acting: 'The beast acts',
                   dying: '', finished: 'The fight is over'};
  /* the page this fight lives on: /explore/play, or /hunt for a party's hunt (data-play) */
  var PLAY_URL = (document.querySelector('main.battle') || {dataset: {}}).dataset.play || '/explore/play';
  function PLAY() { return PLAY_URL; }
  var SETTLE = 220;            // ms a turn with nothing to act out stays locked: one press is one turn, never two
  var ANSWER_LIMIT = 12000;    // ms to wait for the server before asking it what happened
  window.MACombat = Combat;

  /* A beast with animation frames (art/beasts/sheets/<slug>/, web/beast_sheets.py): idle, attack, hit and death, cut
     from SHOAIB's videos onto one cell. The frames are laid exactly over the beast's still picture (sheets.json `still`:
     where the picture sits in the cell), which stays underneath unseen; whatever the fight does to the picture (its
     transform, flash, fade: `animal`, the knocks, the shakes) is copied onto the frames, so every existing movement
     still carries the beast. The picture itself is never drawn (style.css): it only keeps the beast's size and place.
     One sheet shows at a time (data-anim; style.css fades between them). The idle loops in CSS, also through its roar;
     attack is stepped by the turn (`frame`), hit and death play on their own clock (`play`); death then holds its last
     frame. */
  function BeastSheets(box) {
    var data, img = box.querySelector(':scope > img'), layer = box.querySelector('.bsheets'), raf = null, cur = 'idle';
    try { data = JSON.parse(box.dataset.sheets); } catch (e) { return null; }
    if (!img || !layer || !data) return null;
    var S = data.sheets, k = 1, base = '', at = [0, 0], origin = '';
    function fit() {                                           // the layer onto the picture as drawn (object-fit: contain)
      var nw = img.naturalWidth, nh = img.naturalHeight, w = img.offsetWidth, h = img.offsetHeight;
      if (!nw || !nh || !w || !h) return;
      var s = Math.min(w / nw, h / nh), cw = nw * s, ch = nh * s;
      var pos = (getComputedStyle(img).objectPosition || '50% 50%').split(' ').map(function (v) { return v.indexOf('%') > 0 ? parseFloat(v) / 100 : 0.5; });
      var cx = img.offsetLeft + (w - cw) * pos[0], cy = img.offsetTop + (h - ch) * (pos[1] === undefined ? 0.5 : pos[1]);
      k = cw / data.still[2];
      var left = cx - data.still[0] * k, top = cy - data.still[1] * k;
      layer.style.left = left + 'px'; layer.style.top = top + 'px';
      layer.style.width = data.cell[0] * k + 'px'; layer.style.height = data.cell[1] * k + 'px';
      at = [img.offsetLeft - left, img.offsetTop - top];       // the picture's box, from the layer's corner
      origin = (at[0] + w / 2) + 'px ' + (at[1] + h) + 'px';  // the picture's own 50% 100%
      copy();
    }
    function copy() {                                          // the picture's movement and flash, onto the frames
      if (!base) base = getComputedStyle(img).filter;          // its shadow and glow (style.css), when nothing flashes it
      layer.style.transform = img.style.transform;
      layer.style.filter = img.style.filter || (base !== 'none' ? base : '');
      layer.style.opacity = img.style.opacity;
      var o = img.style.transformOrigin.match(/^(-?[\d.]+)px (-?[\d.]+)px/);   // a pivot of its own (its roar): the same point
      layer.style.transformOrigin = o ? (+o[1] + at[0]) + 'px ' + (+o[2] + at[1]) + 'px' : origin;
    }
    function show(name, f) {
      var sh = S[name], div = layer.querySelector('.bs-' + name);
      if (!sh || !div) return;
      f = Math.max(0, Math.min(sh.frames - 1, Math.floor(f)));
      if (name !== 'idle') div.style.backgroundPosition = (f % sh.cols) / Math.max(1, sh.cols - 1) * 100 + '% ' + Math.floor(f / sh.cols) / Math.max(1, sh.rows - 1) * 100 + '%';
      if (box.dataset.anim !== name) box.dataset.anim = name;
      cur = name;
    }
    function stop() { if (raf) cancelAnimationFrame(raf); raf = null; }
    var api = {
      data: data,
      width: function () { return data.still[2] * k; },       // the picture's width on screen (px)
      now: function () { return cur; },
      busy: function (name) { return cur === name && raf !== null; },
      set: function (name) { stop(); if (name === 'idle') { box.dataset.anim = name; cur = name; } },
      edge: function (name) {                                  // where its front is on screen (px), at rest: standing, or biting
        var r = layer.getBoundingClientRect(), keep = layer.style.transform;
        if (keep) { layer.style.transform = ''; r = layer.getBoundingClientRect(); layer.style.transform = keep; }
        var x = name === 'bite' ? S.attack.bite_x : S.idle.nose_x;
        return x === undefined ? null : r.left + r.width * x;
      },
      frame: function (name, f) { stop(); show(name, f); },
      play: function (name, done) {                            // on its own clock, at its own length
        stop();
        var sh = S[name], t0 = null;
        function tick(now) {
          if (!box.isConnected) return stop();
          if (t0 === null) t0 = now;
          var t = now - t0;
          show(name, t / sh.ms * sh.frames);
          if (t < sh.ms) { raf = requestAnimationFrame(tick); return; }
          raf = null;
          if (name !== 'death') { box.dataset.anim = 'idle'; cur = 'idle'; }
          if (done) done();
        }
        raf = requestAnimationFrame(tick);
      },
      hit: function () { if (cur !== 'death') api.play('hit'); },
      dead: function () { stop(); show('death', S.death.frames - 1); },
      fit: fit
    };
    if (window.MutationObserver) new MutationObserver(copy).observe(img, {attributes: true, attributeFilter: ['style']});
    if (img.complete) fit(); else img.addEventListener('load', fit);
    var idle = layer.querySelector('.bs-idle');                 // the idle keeps its place in time, not restarting each turn:
    if (idle && S.idle && S.idle.ms) idle.style.animationDelay = -(performance.now() % S.idle.ms).toFixed(0) + 'ms';   // (the
    // page is replaced every turn; both pages' idles are timed off the same clock, so the new one goes on where the old was)
    Object.keys(S).forEach(function (n) { keep(S[n].src); });   // every sheet loaded AND unpacked now, and kept across turns:
                                                                // a big attack sheet never shows blank while it unpacks
    return api;
  }
  /* The move panel (.binfo) is as tall as its tallest text from the start (SHOAIB, Nov 26: "it keeps refreshing").
     Guard's and Break's texts are a line longer than Strike's: hovering them grew the panel, the fight scene above it
     shrank by as much, and the beast, the hero and the background all jumped. Each text is tried in the panel once
     (in one frame, never painted) and the tallest kept as its least height; again when the window changes size. */
  function holdInfo(main) {
    var box = main && main.querySelector('.binfo'), title = box && box.querySelector('.ititle'), text = box && box.querySelector('.itext');
    if (!box || !title || !text) return;
    var t0 = title.textContent, x0 = text.textContent, tallest = 0;
    box.style.minHeight = '';
    main.querySelectorAll('[data-info]').forEach(function (el) {
      title.textContent = el.dataset.label + (el.dataset.state ? ' · ' + el.dataset.state : '');
      text.textContent = el.dataset.info;
      tallest = Math.max(tallest, box.offsetHeight);
    });
    title.textContent = t0; text.textContent = x0;
    tallest = Math.max(tallest, box.offsetHeight);
    if (tallest) box.style.minHeight = tallest + 'px';
  }
  window.addEventListener('resize', function () { holdInfo(document.querySelector('main.battle')); });
  window.addEventListener('resize', function () {
    var b = document.querySelector('main.battle .beast.sheeted');
    if (b && b._sheets) b._sheets.fit();
  });

  /* A strong beast's aura (SHOAIB Nov 27, explore_play.beast_power): from Martial King up it stands in a dome of its
     element's light (art/fx/elem/<element>_aura.webp), two copies breathing out of step so it flickers like a living
     flame, brighter each realm up to Martial Saint. Laid on the ground behind the beast, fitted to its picture as
     drawn, and gone as it falls. Presentation only. */
  var AURA_OPACITY = [0, 0.6, 0.72, 0.86, 1];        // one layer now (SHOAIB Nov 27: the two-layer aura made fights lag)
  /* Lite effects (SHOAIB Nov 27: most players will be on phones; a slowed phone dropped to 7-8 frames a second in a
     Saint's roar): on a phone-sized screen, or with "reduce motion" on, the fight keeps every effect but draws about
     half the small particles (droplets, streaks, dust, sparks), skips the full-scene impact-frame filter (the coloured
     flash and the shake stay), and style.css drops the costly blurs and the aura's second layer. */
  var LITE = !!(window.matchMedia && (matchMedia('(max-width: 700px)').matches || matchMedia('(prefers-reduced-motion: reduce)').matches));
  var LITE_SKIP = /^(bdrop|bstreak|bdust|bspark|bmote)\b/;
  if (LITE) document.documentElement.classList.add('lite-fx');
  /* A buzz on the phone when a beast's blow or roar lands on you (Android; iPhones' browser has no vibration, so
     nothing happens there), stronger for a roar and for Elites and Beast Kings; none with "reduce motion" on. */
  var CALM = !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
  /* How hard the screen shakes when a roar or a big blow lands (SHOAIB Nov 27: "I like it but I don't know if it
     works well for others"): about half the old shake, a gentler camera punch (ZOOM) and a softer white flash; with
     "reduce motion" on, no shake, no flash and only a slight punch. */
  var SHAKE = CALM ? 0 : 0.55, ZOOM = CALM ? 0.35 : 0.75;
  function buzz(pattern) {
    try { if (!CALM && navigator.vibrate && 'ontouchstart' in window) navigator.vibrate(pattern); } catch (e) {}
  }
  function aura(main) {
    var box = main.querySelector('.beast'), img = box && box.querySelector(':scope > img'), scene = main.querySelector('.bscene');
    var R = null;
    try { R = JSON.parse((box && box.dataset.roar) || 'null'); } catch (e) {}
    if (!box || !img || !scene || !R || !R.power || !R.element) return;
    var n = scene.querySelector('.baura');
    if (!n) {
      n = document.createElement('div');
      n.className = 'baura p' + R.power;
      var src = '/art/fx/elem/' + R.element + '_aura.webp';
      n.innerHTML = '<img alt="" src="' + src + '"><img alt="" src="' + src + '">';
      n.style.setProperty('--ao', AURA_OPACITY[R.power] || 0.5);
      scene.insertBefore(n, box);                                // behind the beast
    }
    function fit() {                                             // round the picture as drawn (contain, feet down)
      if (!img.naturalWidth) return;
      var s = scene.getBoundingClientRect(), b = box.getBoundingClientRect(), ar = img.naturalWidth / img.naturalHeight;
      var w = Math.min(b.width, b.height * ar), h = w / ar, left = b.left + (b.width - w) / 2, bottom = b.bottom;
      var aw = w * 1.3, ah = h * 1.35;
      n.style.left = (left + w / 2 - aw / 2 - s.left) / s.width * 100 + '%';
      n.style.top = (bottom + h * 0.06 - ah - s.top) / s.height * 100 + '%';
      n.style.width = aw / s.width * 100 + '%'; n.style.height = ah / s.height * 100 + '%';
    }
    if (img.complete) fit(); else img.addEventListener('load', fit, {once: true});
    // Roused (the game's own rule: after its final roar it hits harder): its aura burns red and pulses fast.
    // Wounded (30% HP or less): it pulses faster, the beast near its end. (SHOAIB Nov 27.)
    var bar = main.querySelector('.ehp > div'), hp = bar ? parseFloat(bar.style.width) : 100;
    var rage = main.classList.contains('roused') && !main.classList.contains('slain');
    n.classList.toggle('rage', rage);
    var want = '/art/fx/elem/' + (rage ? 'blood' : R.element) + '_aura.webp';     // roused: the red of the blood aura
    n.querySelectorAll('img').forEach(function (i) { if (i.getAttribute('src') !== want) i.setAttribute('src', want); });
    n.classList.toggle('low', hp <= 30 && !n.classList.contains('rage'));
    if (!aura.bound) { aura.bound = true; window.addEventListener('resize', function () { var m = document.querySelector('main.battle'); if (m) { sized(m); aura(m); } }); }
  }

  /* How big the beast stands (explore_play.beast_scale, SHOAIB: a Martial Saint should be huge): its frame is made
     that much bigger (not zoomed, so every movement, roar and mark keeps lining up), anchored where it stands so it
     grows up and toward you, but never so big that its picture leaves the top of the scene or reaches the
     cultivator. Measured from the layout's own size each time, so phones and resizes get the same rule. */
  function sized(main) {
    var box = main.querySelector('.beast'), img = box && box.querySelector(':scope > img'), scene = main.querySelector('.bscene');
    var fighter = main.querySelector('.fighter'), R = null;
    try { R = JSON.parse((box && box.dataset.roar) || 'null'); } catch (e) {}
    if (!box || !img || !scene || !fighter || !R || !(R.scale > 1)) return;
    if (!img.naturalWidth) { img.addEventListener('load', function () { sized(main); aura(main); }, {once: true}); return; }
    var posed = box.classList.contains('posed');
    box.style.width = ''; box.style.height = ''; box.style.top = '';
    var s = scene.getBoundingClientRect(), b = box.getBoundingClientRect(), f = fighter.getBoundingClientRect();
    var ar = img.naturalWidth / img.naturalHeight, w = Math.min(b.width, posed ? b.width : b.height * ar), h = w / ar;
    var front = f.left + f.width * 0.62 + s.width * 0.03;          // the cultivator's front, and a little air
    var k = Math.min(R.scale, s.height * 0.8 / h, (b.right - front) / ((b.width + w) / 2));
    if (!(k > 1.01)) return;
    box.style.width = b.width * k / s.width * 100 + '%';
    // the frame only as tall as the beast it holds (SHOAIB Nov 27 "the fight is laggy": the picture's shadows are
    // drawn over its whole frame, and a frame grown to the full height was many times bigger than the beast)
    if (!posed) { box.style.top = 'auto'; box.style.height = Math.min(b.height * k, h * k * 1.04) / s.height * 100 + '%'; }
    box.dataset.scaled = k.toFixed(2);
  }

  /* Team fights (SHOAIB Nov 27: "how do players know it's their turn, each character looks alike"). Everyone picks at
     once each round. When a new round starts and you still have to pick, a YOUR TURN banner sweeps across the scene,
     your portrait pulses and the moves glow, and an Android phone gives a double buzz. Each player keeps one colour
     all fight (web/hunt_play.py PARTY_COLORS: you gold), on their portrait's ring and on their name wherever it
     appears in the fight's messages and Battle History (`partyNames`). */
  var seenRound = null;
  function yourTurn(main) {
    if (!main.dataset.team || main.dataset.waiting || main.classList.contains('slain')) return;
    var round = main.dataset.round;
    if (seenRound === round) return;
    var first = seenRound === null;
    seenRound = round;
    var scene = main.querySelector('.bscene');
    if (!scene) return;
    var n = document.createElement('div');
    n.className = 'yourturn'; n.textContent = 'Your turn';
    scene.appendChild(n);
    setTimeout(function () { n.remove(); }, 1900);
    main.classList.add('turnnow');
    setTimeout(function () { main.classList.remove('turnnow'); }, 2600);
    if (!first) buzz([40, 70, 40]);
  }
  function partyNames(main) {
    var allies = [].slice.call(main.querySelectorAll('.ally[data-name]')).filter(function (a) { return !a.classList.contains('me'); });
    if (!allies.length) return;
    var who = allies.map(function (a) { return {name: a.dataset.name, color: getComputedStyle(a).getPropertyValue('--pc').trim()}; })
      .filter(function (w) { return w.name && w.color; });
    function paint(root) {
      if (!root) return;
      var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT), nodes = [], t;
      while ((t = walker.nextNode())) if (!(t.parentNode.classList && t.parentNode.classList.contains('pname'))) nodes.push(t);
      nodes.forEach(function (node) {
        who.forEach(function (w) {
          var i = node.nodeValue.indexOf(w.name);
          if (i < 0 || !node.parentNode) return;
          var after = node.splitText(i), rest = after.splitText(w.name.length), span = document.createElement('b');
          span.className = 'pname'; span.style.color = w.color; span.textContent = w.name;
          after.parentNode.replaceChild(span, after);
          node = rest;
        });
      });
    }
    ['.bfeed', '.histbody', '.binfo'].forEach(function (sel) {
      var root = main.querySelector(sel);
      paint(root);
      if (root && window.MutationObserver && !root.dataset.painted) {
        root.dataset.painted = '1';
        new MutationObserver(function (list) {
          list.forEach(function (m) { [].forEach.call(m.addedNodes, function (x) { if (x.nodeType === 1) paint(x); }); });
        }).observe(root, {childList: true, subtree: true});
      }
    });
  }

  /* Ready before the first roar (SHOAIB Nov 27): the first time a big picture is shown the browser has to unpack
     and prepare it, which made a brief stutter as a roar began. When a fight opens, its beast's roar pictures (its
     element's blast, burst and ground patch, its body type's roar shape, its formation circle) are drawn once,
     all but invisible and at their real size, behind everything, then taken away: by the first roar they are ready.
     Once per beast per page. */
  var WARM_SHAPE = {roar: 'quadruped', screech: 'flying', hiss: 'serpent', storm: 'dragon'};
  var warmed = {};
  function warmUp(main) {
    var box = main.querySelector('.beast'), scene = main.querySelector('.bscene'), R = null;
    try { R = JSON.parse((box && box.dataset.roar) || 'null'); } catch (e) {}
    if (!scene || !R || !R.element || warmed[R.slug]) return;
    warmed[R.slug] = true;
    var srcs = ['_stream', '_burst', '_ground'].map(function (k) { return '/art/fx/elem/' + R.element + k + '.webp'; });
    var shape = R.motion && WARM_SHAPE[R.motion.style] ? '/art/fx/roars/roar_' + WARM_SHAPE[R.motion.style] + '.webp' : null;
    if (R.power >= 1) srcs.push('/art/fx/elem/sigil_' + (R.power >= 4 ? 3 : R.power >= 3 ? 2 : 1) + '.webp');
    var n = document.createElement('div');
    n.className = 'bwarm'; n.setAttribute('aria-hidden', 'true');
    n.innerHTML = srcs.map(function (s) { return '<img alt="" src="' + s + '">'; }).join('') +
      (shape ? '<span class="bwshape" style="--m: url(' + shape + '); --rc: ' + R.color + '"><img alt="" src="' + shape + '"></span>' : '');
    scene.insertBefore(n, scene.firstChild);
    var imgs = [].slice.call(n.querySelectorAll('img'));
    Promise.all(imgs.map(function (i) { return i.decode ? i.decode().catch(function () {}) : null; })).then(function () {
      requestAnimationFrame(function () { requestAnimationFrame(function () { n.remove(); }); });   // painted once, then gone
    });
    setTimeout(function () { n.remove(); }, 4000);
  }

  function init() {
    var main = document.querySelector('main.battle');
    if (!main) return;
    sized(main);
    warmUp(main);
    main.querySelectorAll('.ally[data-strike]').forEach(function (a) {   // teammates' strike pictures, ready for `cameo`
      var i = new Image(); i.src = a.dataset.strike; if (i.decode) i.decode().catch(function () {});
    });
    partyNames(main);
    yourTurn(main);
    aura(main);
    var sheeted = main.querySelector('.beast.sheeted');
    if (sheeted && !sheeted._sheets) {
      sheeted._sheets = BeastSheets(sheeted);
      if (sheeted._sheets && main.classList.contains('slain')) sheeted._sheets.dead();   // a won fight: it lies there
    }
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
    holdInfo(main);                                             // the panel keeps one height whatever it shows
    var posed = main.querySelector('.beast.posed');             // load every pose picture now, so swaps are instant
    if (posed) { try { var ps = JSON.parse(posed.dataset.poses); Object.keys(ps).forEach(function (k) { new Image().src = ps[k].src; }); } catch (e) {} }
    ['/art/fx/break_burst.webp', '/art/fx/break_crater.webp'].forEach(function (src) { new Image().src = src; });   // Break's slam
    var mine = main.querySelector('.fighter[data-preload]');    // this fighter's sheets and technique pictures, loaded and
    if (mine) { try { JSON.parse(mine.dataset.preload).forEach(keep); } catch (e) {} }   // decoded now: no move waits for them
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

  /* Pictures the fight will need (looks sheets, technique art: explore_play.preload), kept loaded and decoded for the
     whole fight. Before, a technique's frames were first asked for when its turn arrived, and the move played over a
     blank or half-loaded sheet (it stuttered). `whenReady` holds a turn's acting until its movement sheet is in. */
  var KEEP = {};
  function keep(src) {
    if (KEEP[src]) return KEEP[src];
    var img = KEEP[src] = new Image();
    img.src = src;
    img._ready = false;                                         // loaded and unpacked (decoded): ready to show at once
    img._unpacked = (img.decode ? img.decode() : new Promise(function (ok) { img.onload = ok; img.onerror = ok; }))
      .catch(function () {}).then(function () { img._ready = true; });
    return img;
  }
  function whenReady(main, go) {
    var el = main.querySelector('.fighter .msheet'), m = el && /url\(["']?([^"')]+)/.exec(el.style.backgroundImage || '');
    var imgs = m ? [keep(m[1])] : [], done = false;
    main.querySelectorAll('.beast .bs').forEach(function (bs) {   // the beast's frames too: unpacked before the turn plays
      var u = /url\(["']?([^"')]+)/.exec(bs.style.backgroundImage || '');
      if (u) imgs.push(keep(u[1]));
    });
    function once() { if (done) return; done = true; go(); }
    var waits = imgs.filter(function (img) { return !img._ready; });
    if (!waits.length) return go();
    Promise.all(waits.map(function (img) { return img._unpacked; })).then(once, once);
    setTimeout(once, 2500);                                     // a slow connection: play it anyway
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
    fs('press');
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
        load(PLAY(), {method: 'GET'})
          .then(function (html) { if (token === Combat.token) show(html, sent, true); })
          .catch(function () { location.replace(PLAY()); });
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
      location.replace(PLAY());
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
    whenReady(fresh, function () {                              // its movement's frames are in: nothing plays blank
      if (!fresh.isConnected) return;
      playing = played ? act(fresh, before) : null;             // act the turn out: dash, swing, hit, the beast's answer
      if (!playing) setTimeout(function () { if (Combat.phase !== 'player_turn' && Combat.phase !== 'finished' && fresh.isConnected) Combat.set('player_turn'); }, SETTLE);
    });
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
    beast:  {charge: 220, hit: 370, back: 510, end: 900, knock: 0.022},   // (timing the defense techniques play against)
    // the beast's own attack, from SHOAIB's beast attack video (a boar): head lowered, a rear, the charge, the goring toss
    gore:   {gather: 300, rear: 460, hit: 720, toss: 860, back: 960, end: 1480, knock: 0.03},
    tech:   {end: 1100},                                        // techniques play their own animation (style.css)
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
    var BS = (beastBox && beastBox._sheets) || null;            // its animation frames (BeastSheets), when it has them
    var FRONT = 0.57;                                            // the cultivator's front (chest and skirt), a share of the fighter's box
    var end = endOf(main);                                      // the fight was won on this turn: the beast goes down last
    if ((!events.length && !end) || !scene || !fighter || !poses || !beast || !window.requestAnimationFrame ||
        (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches)) return null;

    var after = bars(main), held = {}, W = scene.clientWidth;
    var maxHp = {me: +main.dataset.maxMe || 0, enemy: +main.dataset.maxEnemy || 0};
    function heavy(who, dmg) { return maxHp[who] && dmg >= maxHp[who] * 0.2 ? ' big' : ''; }   // a fifth of the HP or more
    var trail = fighter.querySelector('.trailfx');
    var asheets = {};                                           // its frame-by-frame Strike and Break, when this look has them
    fighter.querySelectorAll('.asheet').forEach(function (el) { asheets[el.dataset.act] = el; });
    var msheet = fighter.querySelector('.msheet');              // this turn's technique movement (looks.MOTION_SHEETS)
    var cast = null;                                            // this turn's technique, when it has its own look (web/technique_fx.py)
    try { cast = JSON.parse(main.dataset.cast || 'null'); } catch (e) {}
    var gsheet = fighter.querySelector('.gsheet');              // and a frame-by-frame Guard (looks.GUARD_SHEETS)
    var claws = fighter.querySelector('.clawsfx g'), clawClip = fighter.querySelector('#clawclip rect');
    var fr = fighter.getBoundingClientRect(), br = beastBox.getBoundingClientRect();
    var targetX = br.left + br.width * 0.12;                  // where your blade lands on the beast
    var reachMe = Math.max(0, targetX - (fr.left + fr.width * (parseFloat(fighter.dataset.tip) || 0.962)));     // sword tip to the beast
    var reachBeast = Math.max(0, br.left - (fr.left + fr.width * 0.64));                       // the beast to your body
    if (BS && BS.edge('nose') !== null) {                       // an animated beast: your sword tip to its nose, your body stays clear
      targetX = BS.edge('nose');
      reachMe = Math.max(0, targetX - (fr.left + fr.width * (parseFloat(fighter.dataset.tip) || 0.962)));
    }
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
      if (who === 'enemy') qiCrack();
      after[who].bar.style.width = after[who].width; after[who].val.textContent = after[who].text;
    }
    function pose(p) { if (fighter.dataset.pose !== p) fighter.dataset.pose = p; }
    function hero(x, y, rot) { poses.style.transform = 'translate(' + x + 'px,' + y + 'px) rotate(' + (rot || 0) + 'deg)'; }
    var auraEl = scene.querySelector('.baura');                 // a strong beast's aura (`aura`) goes where it goes
    function animal(x, y, rot, flash) {
      beast.style.transform = 'translate(' + x + 'px,' + y + 'px) rotate(' + rot + 'deg)';
      if (auraEl) auraEl.style.transform = x || y ? 'translate(' + x + 'px,' + y + 'px)' : '';
      beast.style.filter = flash > 0.05 ? beastFilter + ' brightness(' + (1 + 1.8 * flash) + ') saturate(' + (1 - 0.6 * flash) + ')' : '';
    }
    /* A teammate's attack (SHOAIB Nov 27: show the team fighting together without crowding the screen): their own
       strike picture (web/hunt_play.py, data-strike on their portrait) appears just behind you, glowing in their
       player colour, dashes at the beast and hits it (the number, a spark, its Qi cracking if it is strong), then
       fades away. Only movement and fades, so it stays cheap. A miss: it dashes, the beast shrugs it off. */
    var CAMEO_MS = 1000, CAMEO_HIT = 420;
    function cameo(ev) {
      var tag = [].slice.call(main.querySelectorAll('.ally[data-name]')).filter(function (a) { return a.dataset.name === ev.name; })[0];
      var src = tag && tag.dataset.strike, color = tag ? getComputedStyle(tag).getPropertyValue('--pc').trim() : '#5FA8FF';
      var n = null, hit = false, sr = scene.getBoundingClientRect();
      var from = at(fr, 0.02, 1), reach = (br.left + br.width * 0.12 - (fr.left + fr.width * 0.75)) / sr.width * 100;
      return {end: CAMEO_MS, render: function (t) {
        if (t < 0) return;
        if (!n && src) {
          n = document.createElement('img');
          n.className = 'bcameo'; n.src = src; n.alt = '';
          n.style.left = from[0] + '%'; n.style.top = from[1] + '%'; n.style.width = fr.width + 'px'; n.style.setProperty('--pc', color);
          n.style.height = fr.width * 559 / 1024 + 'px';         // the pose pictures are 1024 x 559 (explore_play.html)
          scene.insertBefore(n, fighter.nextSibling);
        }
        var a = ease(span(t, 0, CAMEO_HIT)), back = span(t, CAMEO_HIT + 180, CAMEO_MS);
        var x = Math.max(0, reach) * a, o = Math.min(1, t / 120) * (1 - back);
        if (n) { n.style.transform = 'translate(' + x / 100 * sr.width + 'px,-100%)'; n.style.opacity = o.toFixed(2); }
        if (t >= CAMEO_HIT && !hit) {
          hit = true;
          var p = at(br, 0.4, 0.45);
          if (ev.hit) {
            drop('enemy'); pop(beastBox, 'hit' + heavy('enemy', ev.dmg), '−' + ev.dmg); burst('tspark', p[0], p[1]);
          } else pop(beastBox, 'word', 'Missed');
        }
      }, clear: function () { if (n) n.remove(); }};
    }
    var stepped = false;                                          // the sidestep's own recording has played (sidestepped)
    function pop(box, cls, text) {
      if (BS && box === beastBox && /^hit/.test(cls)) BS.hit();   // it flinches in its own hit animation
      var loud = / big/.test(cls) ? 'big' : '';                   // the sound of what the number or word says
      if (/^hit/.test(cls)) fs('hit', loud);
      else if (/^hurt/.test(cls)) fs('hurt', loud);
      else if (/heal/.test(cls)) fs('heal');
      else if (/stun/.test(cls)) fs('stun');
      else if (/^(Blocked|Guarded|Deflected|Unbreakable|Held)/.test(text)) fs('block', /^Deflected/.test(text) ? 'deflect' : '');
      else if (/^Missed/.test(text)) fs('miss');
      else if (/^(Evaded|Slipped|Shadow step)/.test(text)) { if (!stepped) fs('dodge'); stepped = false; }   // (his step has sounded already)
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
        if (R.shake && scene.animate && SHAKE) scene.animate([{transform: 'none'}, {transform: 'translate(-5px,3px)'}, {transform: 'translate(5px,-3px)'},
          {transform: 'translate(-3px,1px)'}, {transform: 'none'}], {duration: 380});
      } else {
        burst('tring', p[0] + 4, p[1] + 6); pop(beastBox, 'word', ev.blocked ? 'Blocked' : 'Missed');
      }
    }

    /* Break's Qi: it gathers in rings at your feet as you draw back (`gathered`), and bursts out of the ground where
       the blade comes down (`slam`): spikes of blue Qi, the split ground (art/fx/break_*.webp, scripts/make_break_fx.py),
       a shockwave, stones, a cloud of dust, and a hard shake. */
    function gathered() {
      fs('gather');
      var g = at(fr, asheets.break ? 0.44 : 0.46, 0.96);
      fx('bqring', g[0], g[1], 760); fx('bqring q2', g[0], g[1], 900);
    }
    function slam() {
      fs('boom');
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
      if (scene.animate && SHAKE) scene.animate([{transform: 'none'}, {transform: 'translate(-7px,5px)'}, {transform: 'translate(6px,-4px)'},
        {transform: 'translate(-4px,2px)'}, {transform: 'translate(2px,-1px)'}, {transform: 'none'}], {duration: 520});
    }

    /* your weapon attack: wind up, dash, swing with a trail, then step back */
    function attack(ev) {
      if (asheets[ev.act]) return sweep(ev, asheets[ev.act]);
      var R = RECIPES[ev.act] || RECIPES.strike, done = false, began = false;
      if (ev.hit) hold('enemy');
      fighter.dataset.trail = R.slam ? 'slam' : ev.act;
      return {end: R.end, cues: [[R.swing - 90, 'swing', ev.act]], render: function (t) {
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
        animal(BS ? 0 : k2[0], 0, BS ? 0 : k2[0] / (R.knock * W || 1) * 5, k2[1]);
        if (t >= R.hit && !done) { done = true; strikes(ev, R); }
      }};
    }

    /* the same attack, frame by frame from the video: the spin closes the distance, the forward cut lands. A sheet may
       carry its own timing (data-blade, as BLADE) and how far its blade reaches at the hit (data-tip): hers do. */
    function sweep(ev, sheet) {
      var R = BLADE[ev.act] || BLADE.strike, done = false, began = false;
      try { if (sheet.dataset.blade) R = JSON.parse(sheet.dataset.blade); } catch (e) {}
      var reach = sheet.dataset.tip ? Math.max(0, targetX - (fr.left + fr.width * +sheet.dataset.tip)) : reachMe;
      Object.keys(asheets).forEach(function (k) { asheets[k].classList.toggle('on', asheets[k] === sheet); });
      var n = +sheet.dataset.frames, cols = +sheet.dataset.cols, rows = +sheet.dataset.rows;
      if (ev.hit) hold('enemy');
      fighter.dataset.trail = R.slam ? 'slam' : ev.act;
      function show(f) {
        f = Math.max(0, Math.min(n - 1, Math.round(f)));
        sheet.style.backgroundPosition = (f % cols) / (cols - 1) * 100 + '% ' + Math.floor(f / cols) / (rows - 1) * 100 + '%';
      }
      return {end: R.end, cues: [[R.swing - 90, 'swing', ev.act]], render: function (t) {
        if (R.slam && t >= 0 && !began) { began = true; gathered(); }
        if (t < 0 || t >= R.end) { pose('idle'); hero(0, 0); }
        else {
          pose('sheet');
          var f = R.keys[R.keys.length - 1][1];
          for (var j = 1; j < R.keys.length; j++) {
            if (t < R.keys[j][0]) { var a = R.keys[j - 1], b = R.keys[j]; f = a[1] + (b[1] - a[1]) * span(t, a[0], b[0]); break; }
          }
          show(f);
          var x = reach * inout(span(t, R.dash[0], R.dash[1])), y = 0;
          if (R.hop) y = -R.hop * W * Math.sin(Math.PI * span(t, R.dash[0], R.dash[1]));              // a leap in, blade overhead
          if (R.dip && t >= R.hit && t < R.back[0]) y = R.dip * W * (1 - span(t, R.back[0] - 160, R.back[0]));  // into the blow
          if (t >= R.back[0]) { var r = inout(span(t, R.back[0], R.back[1])); x = reach * (1 - r); y = -(R.bob === undefined ? 0.03 : R.bob) * W * Math.sin(Math.PI * r); }
          hero(x, y);
        }
        trail.style.clipPath = 'inset(0 ' + (100 - 100 * span(t, R.swing - 20, R.hit + 10)) + '% 0 0)';
        trail.style.opacity = t < R.swing - 20 ? 0 : 1 - span(t, R.hit + 60, R.hit + 320);
        var k2 = ev.hit ? knocked(t - R.hit, R.knock * W) : [0, 0];
        animal(BS ? 0 : k2[0], 0, BS ? 0 : k2[0] / (R.knock * W || 1) * 5, k2[1]);
        if (t >= R.hit && !done) { done = true; strikes(ev, R); }
      }};
    }

    /* your Guard, frame by frame from the video (looks.GUARD_SHEETS): `h` is ms since the blow landed. He stands with
       the blade raised as the beast comes in (frames 0-3), the blow bursts into a gold flash and sparks on the blade
       (from frame 4), he leans back under it and steadies. She closes her arms into a crossed guard as it comes in
       (0-11), takes the blow on them in a white flash (12) with her sleeves whipping round, and steadies. Each sheet
       may carry its own timing (data-ready, -first, -ms); his are the defaults. False when this look has none. */
    var GUARD = {ready: 320, first: 4, ms: 34};
    var GT = gsheet ? {ready: +gsheet.dataset.ready || GUARD.ready, first: +gsheet.dataset.first || GUARD.first,
                       ms: +gsheet.dataset.ms || GUARD.ms} : GUARD;
    function block(h) {
      if (!gsheet) return false;
      var n = +gsheet.dataset.frames, cols = +gsheet.dataset.cols, rows = +gsheet.dataset.rows;
      var f = h < 0 ? Math.floor((GT.first - 1) * span(h, -GT.ready, 0)) : GT.first + Math.floor(h / GT.ms);
      if (h < -GT.ready || f >= n) { pose('idle'); return true; }
      gsheet.style.backgroundPosition = (f % cols) / (cols - 1) * 100 + '% ' + Math.floor(f / cols) / (rows - 1) * 100 + '%';
      pose('guard');
      return true;
    }
    function blockTime() { return gsheet ? (+gsheet.dataset.frames - GT.first) * GT.ms : 0; }

    /* the beast's attack (its M1), from SHOAIB's beast attack video: it lowers its head and gathers itself, rears,
       charges in kicking up dust and gores, tossing its head up with its jaws open (its open-mouthed roar picture, where
       it has one) as it strikes; a tearing slash and dust burst where it hits, then it trots back home. You are hit, or
       your Guard stops it (and may counter). */
    function charge(ev) {
      var R = RECIPES.gore, guard = ev.act === 'guard', done = false, countered = false, dusted = false, opened = false, marked = false;
      var still = beast.src, open = !bposes && !BS && ROAR && ROAR.art;
      var A = BS && BS.data.sheets.attack, lunge = 0, reach = 0;
      if (A) {                                                  // its own attack video: crouch, lunge and bite, back
        var bite = Math.round(A.bite / A.frames * A.ms);
        lunge = Math.round(bite * 0.5);                          // it springs from the crouch at about half way to the bite
        R = {gather: 0, rear: lunge, hit: bite, toss: bite + 140, back: bite + 140, end: A.ms, knock: RECIPES.gore.knock};
        var jaws = BS.edge('bite');                              // its jaws, as the bite frame draws them where it stands
        reach = jaws !== null ? Math.max(0, jaws - (fr.left + fr.width * FRONT))   // they stop at your front, never inside you
                              : Math.max(0, reachBeast - (A.reach || 0) * BS.width());
      }
      if (guard) { if (ev.counter) hold('enemy'); } else hold('me');
      return {end: Math.max(R.end + (guard && ev.counter ? 200 : 0), guard ? R.hit + blockTime() : 0),
              cues: (guard ? [[0, 'guardup']] : []).concat([[Math.max(0, R.rear - 60), 'lunge']]), render: function (t) {
        var x = 0, y = 0, rot = 0;
        if (A) {                                                // in place through the crouch, then the lunge home to you and back
          if (t < lunge) x = 0;
          else if (t < R.hit) x = -reach * inout(span(t, lunge, R.hit));
          else if (t < R.back) x = -reach;
          else x = -reach * (1 - inout(span(t, R.back, R.end)));
          if (!(countered && BS.busy('hit'))) BS.frame('attack', t / A.ms * A.frames);   // over the last flinch; your counter's own flinch plays
        }
        else if (t < R.gather) { var q = inout(span(t, 0, R.gather)); x = 0.012 * W * q; y = 0.006 * W * q; rot = -5 * q; }      // head down
        else if (t < R.rear) { var q2 = inout(span(t, R.gather, R.rear)); x = 0.012 * W + 0.006 * W * q2; y = 0.006 * W - 0.026 * W * q2; rot = -5 + 13 * q2; }   // rears
        else if (t < R.hit) {                                                     // the charge
          var c = span(t, R.rear, R.hit), e2 = c * c;
          x = 0.018 * W - (reachBeast + 0.018 * W) * e2; y = -0.02 * W * (1 - c) + Math.abs(Math.sin(c * Math.PI * 2)) * -0.006 * W; rot = 8 - 15 * Math.min(1, c * 1.6);
        } else if (t < R.back) {                                                  // the goring toss
          var g = span(t, R.hit, R.toss); x = -reachBeast - 0.006 * W * Math.sin(Math.PI * g); y = -0.012 * W * Math.sin(Math.PI * g); rot = -7 + 19 * Math.sin(Math.PI * 0.5 * Math.min(1, g * 1.2));
        } else if (t < R.end) {                                                   // trots home in two hops
          var r = inout(span(t, R.back, R.end)); x = -reachBeast * (1 - r); y = -0.02 * W * Math.abs(Math.sin(Math.PI * 2 * r)); rot = 12 * (1 - r) * (1 - r);
        }
        if (!A) bpose(t < R.rear ? 'crouch' : t < R.back ? 'leap' : 'idle');
        if (open) {                                                               // jaws open for the gore
          var wide = t >= R.hit - 90 && t < R.back + 60;
          if (wide !== opened) { opened = wide; beast.src = wide ? ROAR.art : still; }
        }
        if (t >= R.rear && !dusted) {                                             // dust kicked up as it charges
          dusted = true;
          var f = at(br, 0.55, 0.97);
          for (var j = 0; j < 7; j++) fx('bdust', f[0] + 2 + 2 * j, f[1] - Math.random() * 2, 1300,
            {'--dx': (40 + 22 * j) + 'px', '--s': (0.6 + Math.random() * 0.5).toFixed(2), 'animation-delay': (30 * j) + 'ms'});
        }
        var ck = guard && ev.counter ? knocked(t - R.hit - 130, 0.03 * W) : [0, 0];
        animal(x + ck[0], y, rot, ck[1]);
        var h = t - R.hit;
        if (!guard) {
          var k = knocked(h, R.knock * W);
          pose('idle'); hero(-k[0], 0, -k[0] / 6);
          poses.style.filter = k[1] > 0.05 ? 'sepia(' + 0.7 * k[1] + ') saturate(' + (1 + 3 * k[1]) + ') hue-rotate(-28deg)' : '';
          if (t >= R.hit - 70 && !marked) { marked = true; mark(); }             // its mark torn across you
        } else {
          if (!block(h)) pose(ev.counter && h >= 110 && h < 380 ? 'strike' : 'idle');
          hero(0, 0);
        }
        if (h >= 0 && !done) {
          done = true;
          var p = at(fr, 0.52, 0.5), fl = at(fr, 0.5, 0.97);
          for (var m = 0; m < 6; m++) { var sd = m % 2 ? 1 : -1;                  // dust burst where it hits
            fx('bdust', fl[0] + sd * (1 + 2 * m), fl[1] - Math.random() * 2, 1200, {'--dx': sd * (30 + 20 * m) + 'px', '--s': (0.5 + Math.random() * 0.5).toFixed(2)}); }
          if (guard) { if (!gsheet) burst('tring', p[0], p[1]); pop(fighter, 'word', 'Blocked'); }
          else { drop('me'); pop(fighter, 'hurt' + heavy('me', ev.dmg), '−' + ev.dmg); burst('tspark', p[0], p[1], '#FFC2B8'); }
        }
        if (guard && ev.counter && h >= 130 && !countered) { countered = true; drop('enemy'); pop(beastBox, 'hit' + heavy('enemy', ev.counter), '−' + ev.counter); }
        if (t >= R.end - 20 && opened) { opened = false; beast.src = still; }
      }};
    }

    /* The mark a beast's blow tears across you (beasts.ATTACK_MARKS, SHOAIB's pictures in art/fx/marks/): one of its
       marks at random (its main one twice as often): a bite, fangs, a horn gore, tusks, a beak, talons, a sting, a
       smash, a tail lash, claws or a slash. Each is drawn in the beast's element colour (its shape filled with the
       colour and glowing, the picture's own white light as a hot core over it) with a small burst of its element's
       pieces (art/fx/elem/<element>_burst.webp). An Elite's mark is bigger; a Beast King's is bigger again and
       doubled. Presentation only. */
    var MARK_ART = {claw: '/art/fx/claw_marks.webp', slash: '/art/fx/beast_slash.webp'};
    var MARK_SIZE = {claw: 0.95, slash: 1.0, bite: 0.7, fang: 0.7, gore: 0.95, tusk: 0.85, beak: 0.9, talon: 0.8,
                     sting: 0.75, smash: 0.68, lash: 0.95};
    function markSrc(k) {
      if (MARK_ART[k]) return MARK_ART[k];
      if (k === 'sting' && Math.random() < 0.5) k = 'sting_alt';
      return '/art/fx/marks/' + k + '.webp';
    }
    function mark() {
      var list = (ROAR && ROAR.marks && ROAR.marks.length) ? ROAR.marks : [ROAR && ROAR.claws ? 'claw' : 'slash'];
      var k = list.length > 1 && Math.random() < 1 / 3 ? list[1] : list[0];
      var tier = ROAR ? (TIER_OF[ROAR.wave] || 0) : 0, color = ROAR ? ROAR.color : '#ff6a5a';
      var mp = at(fr, 0.5, 0.46), size = Math.min(620, fr.height * (MARK_SIZE[k] || 0.9) * (1 + 0.15 * tier));
      function one(dx, dy, flip, delay) {
        var src = markSrc(k), n = document.createElement('span');
        n.className = 'bmark';
        n.style.left = (mp[0] + dx) + '%'; n.style.top = (mp[1] + dy) + '%';
        n.style.setProperty('--s', size + 'px'); n.style.setProperty('--rc', color); n.style.setProperty('--m', 'url(' + src + ')');
        n.style.setProperty('--flip', flip ? -1 : 1); n.style.animationDelay = delay + 'ms';
        n.innerHTML = '<i class="tint"></i><img alt="" src="' + src + '">';
        scene.appendChild(n);
        setTimeout(function () { n.remove(); }, 1000 + delay);
      }
      one(0, 0, false, 0);
      buzz(tier >= 2 ? [45, 60, 45] : tier ? 55 : 40);
      if (tier >= 2) one(3, 4, true, 110);                       // a Beast King's blow lands twice
      if (ELEM) piece('beburst bemark', ELEM + '_burst.webp', mp[0], mp[1], 800, {'--s': size * 0.7 + 'px', '--r': (Math.random() * 60 - 30) + 'deg'});
    }

    /* a fleeting effect over the scene at (x%, y%): removed after `life` ms */
    var PICTURES = {pcrater: main.dataset.crater || '/art/fx/crater.webp', bcrater: '/art/fx/break_crater.webp', bburst: '/art/fx/break_burst.webp',
                    bclawm: '/art/fx/claw_marks.webp', bslashm: '/art/fx/beast_slash.webp'};   // a beast's M1 marks (SHOAIB's pictures)
    function fx(cls, xPct, yPct, life, style) {
      var src = PICTURES[cls.split(' ')[0]];
      var n = document.createElement(src ? 'img' : 'span');
      if (LITE && LITE_SKIP.test(cls) && Math.random() < 0.55) return n;   // lite: about half the small particles
      n.className = cls; n.style.left = xPct + '%'; n.style.top = yPct + '%';
      if (src) { n.src = src; n.alt = ''; }
      Object.keys(style || {}).forEach(function (k) { n.style.setProperty(k, style[k]); });
      scene.appendChild(n);
      setTimeout(function () { n.remove(); }, life);
      return n;
    }

    /* A beast's roar (art/fx/roar_*.webp, scripts/make_roar_fx.py): one shockwave for every beast, played over its own
       picture, never in place of it. It bursts from the beast's mouth (art/beasts/heads.json, read off each picture),
       sized by how tall the beast stands on screen, squashed towards the way it faces, tinted with its element's
       colour; normal beasts get the ring, Elites the double ring, Beast Kings the spiky burst. Only one roar is ever
       on screen: a new one clears the last. `at`: where it bursts, when the beast's own animation knows better (the
       Mountain Tiger's roar pose). */
    var ROAR = null;
    try { ROAR = JSON.parse(beastBox.dataset.roar || 'null'); } catch (e) {}
    var ROAR_MS = 1100, ROAR_FRAMES = 16;
    function roar(where, big) {
      if (!ROAR) return null;
      var old = scene.querySelector('.broar');
      if (old) old.remove();
      var box = beast.getBoundingClientRect(), pic = box;         // the picture as drawn inside its box (object-fit: contain)
      if (beast.naturalWidth && beast.naturalHeight) {
        var ar = beast.naturalWidth / beast.naturalHeight, w = Math.min(box.width, box.height * ar), h = w / ar;
        pic = {left: box.left + (box.width - w) / 2, top: box.top + (box.height - h) / 2, width: w, height: h};
      }
      var p = where || (ROAR.head ? at(pic, ROAR.head[0], ROAR.head[1]) : at(pic, 0.15, 0.35));
      var size = Math.max(90, Math.min(520, pic.height * ROAR.height * (ROAR.wave === 'ring' ? 0.75 : ROAR.wave === 'double' ? 0.9 : 1.05) * (big ? 1.4 : 1)));
      var n = document.createElement('div');
      n.className = 'broar';
      var ahead = ROAR.art ? size * 0.38 / scene.getBoundingClientRect().width * 100 : 0;   // an open-mouthed roar:
      n.style.left = (p[0] - ahead) + '%'; n.style.top = p[1] + '%';                     // the wave goes out in front, the jaws stay in view
      n.style.width = n.style.height = size + 'px';
      n.style.backgroundImage = 'url(/art/fx/roar_' + (big ? 'burst' : ROAR.wave) + '.webp)';     // a final roar: the biggest wave
      n.style.setProperty('--rc', ROAR.color);
      scene.appendChild(n);
      var t0 = performance.now();
      (function frame(now) {
        if (!n.isConnected) return;
        var k = Math.min(1, (now - t0) / ROAR_MS), f = Math.min(ROAR_FRAMES - 1, Math.floor(k * ROAR_FRAMES));
        n.style.backgroundPosition = (f % 8) / 7 * 100 + '% ' + Math.floor(f / 8) * 100 + '%';
        n.style.opacity = k < 0.7 ? 1 : 1 - (k - 0.7) / 0.3;
        if (k < 1) requestAnimationFrame(frame); else n.remove();
      })(t0);
      return n;
    }
    /* a beast's roar (battle.ROAR, a move of its own): a beast without a roar movement just rears back a little */
    /* A beast with a roar movement (beasts.ROAR_ANIMATIONS, by body: "quadruped") roars as ITSELF: its own picture,
       moved whole about its hind feet (no bending, stretching or cropping, so every body shape and size works), through
       the shared keys (eased between): it dips its head and crouches, rears its head up as the roar bursts from its
       own mouth (the wave, tinted with its element, and dust kicked up at its feet), holds it there trembling, and
       settles. A beast with cut-out poses (the Mountain Tiger) takes its own roar pose while it holds. */
    /* The roar's burst, as big as SHOAIB's roar video: it fills the scene, not just the beast's head. At its mouth
       (p, % of the scene) a blinding white flash, a spiky starburst bigger than the beast, two rings rolling out past
       its whole body, speed lines radiating across the scene, the camera punching in on it with a hard shake, and dust
       rolling out along the ground. The rings and lines take a glow of its element. A final roar is bigger still. */
    function wave(p, file, size, ms, delay, cls, from, alpha) {     // from: the first frame (a ring already open)
      from = from || 0; alpha = alpha || 1;
      var n = document.createElement('div');
      n.className = cls || 'broarbig';
      n.style.left = p[0] + '%'; n.style.top = p[1] + '%'; n.style.width = n.style.height = size + 'px';
      n.style.backgroundImage = 'url(/art/fx/roar_' + file + '.webp)'; n.style.opacity = 0;
      n.style.setProperty('--rc', ROAR.color);
      scene.appendChild(n);
      var t0 = performance.now() + (delay || 0);
      (function frame(now) {
        if (!n.isConnected) return;
        var k = (now - t0) / ms;
        if (k >= 0) {
          k = Math.min(1, k);
          var f = Math.min(ROAR_FRAMES - 1, from + Math.floor(k * (ROAR_FRAMES - from)));
          n.style.backgroundPosition = (f % 8) / 7 * 100 + '% ' + Math.floor(f / 8) * 100 + '%';
          n.style.opacity = (k < 0.6 ? 1 : 1 - (k - 0.6) / 0.4) * alpha;
        }
        if (k < 1) requestAnimationFrame(frame); else n.remove();
      })(performance.now());
      return n;
    }
    function bigRoar(p, pic, final) {
      var sr = scene.getBoundingClientRect(), big = final ? 1.3 : 1, tall = pic.height;
      var at2 = function (n) { n.style.setProperty('--x', p[0] + '%'); n.style.setProperty('--y', p[1] + '%'); n.style.setProperty('--rc', ROAR.color); };
      var flash = fx('broarflash', 0, 0, 520); at2(flash);
      var lines = fx('broarlines', 0, 0, 1300); at2(lines);
      var ahead = tall * 0.25 / sr.width * 100;                // centred just in front of the jaws, so they stay in view
      var q = [p[0] - ahead, p[1]];
      wave(q, 'burst', Math.min(1100, tall * 1.6 * big), 520, 0, 'broarbig star', 0, 0.85);
      blast(p, pic, big); shape(p, pic, big, 'quadruped');       // its roar, in its element, across to you
      wave(q, 'double', Math.min(1500, tall * 2.6 * big), 900, 140, 'broarbig', 7, 0.8);    // hollow rings: the beast
      wave(q, 'ring', Math.min(1800, tall * 3.4 * big), 1000, 320, 'broarbig', 7, 0.7);     // stays in view inside them
      var f = at(pic, 0.5, 0.97);                              // dust rolling out along the ground, both ways
      for (var j = 0; j < 12; j++) {
        var side = j % 2 ? 1 : -1;
        fx('bdust', f[0] + side * (3 + 2.5 * j), f[1] - 1 - Math.random() * 3, 1900, {'--dx': side * (50 + 26 * j) + 'px',
          '--s': (1.4 + Math.random() * 0.9).toFixed(2), 'animation-delay': (25 * j) + 'ms'});
      }
      if (scene.animate) {                                     // the camera punches in on it and shakes
        scene.style.transformOrigin = p[0] + '% ' + p[1] + '%';
        var z = 1 + 0.09 * big * ZOOM, k = [];
        [[0, 1, 0, 0], [0.08, z, -10, 7], [0.16, z, 9, -6], [0.24, z, -8, 5], [0.34, z, 6, -4], [0.46, z * 0.995, -4, 3],
         [0.6, z * 0.99, 3, -2], [0.75, 1 + (z - 1) * 0.5, -2, 1], [1, 1, 0, 0]].forEach(function (a) {
          k.push({offset: a[0], transform: 'translate(' + a[2] * SHAKE + 'px,' + a[3] * SHAKE + 'px) scale(' + a[1] + ')'});
        });
        var anim = scene.animate(k, {duration: 1500, easing: 'ease-out'});
        anim.onfinish = function () { scene.style.transformOrigin = ''; };
      }
    }
    function camera(p, zoom, ms) {                              // the camera punches in on p (% of the scene) and shakes
      if (!scene.animate) return;
      zoom = 1 + (zoom - 1) * ZOOM;
      scene.style.transformOrigin = p[0] + '% ' + p[1] + '%';
      var k = [];
      [[0, 1, 0, 0], [0.08, zoom, -10, 7], [0.16, zoom, 9, -6], [0.24, zoom, -8, 5], [0.34, zoom, 6, -4], [0.46, zoom * 0.995, -4, 3],
       [0.6, zoom * 0.99, 3, -2], [0.75, 1 + (zoom - 1) * 0.5, -2, 1], [1, 1, 0, 0]].forEach(function (a) {
        k.push({offset: a[0], transform: 'translate(' + a[2] * SHAKE + 'px,' + a[3] * SHAKE + 'px) scale(' + a[1] + ')'});
      });
      var anim = scene.animate(k, {duration: ms, easing: 'ease-out'});
      anim.onfinish = function () { scene.style.transformOrigin = ''; };
    }

    /* A flying beast's screech (beasts.ROAR_ANIMATIONS["flying"], from SHOAIB's flying roar video). While it rears up
       Qi gathers: glowing motes of its element swirl in from all round and its throat glows brighter (`gather`). As its
       head snaps forward, beak wide (`screech`): a flash at the beak, a cone of sound rings fired along a beam straight
       at you, each ring bigger than the last, then rings pulsing out of its beak while it holds, the camera punching in
       with a hard shake, and its feathers torn loose and scattering across the scene. A final screech is bigger. */
    function gather(p, ms) {
      var throat = fx('bthroat', p[0], p[1], ms + 260, {'--rc': ROAR.color, '--life': ms + 'ms'});
      for (var i = 0; i < 34; i++) {                           // a tight swirl of Qi pulled into its throat
        var a = Math.random() * Math.PI * 2, d = 45 + Math.random() * 95;
        fx('bmote', p[0], p[1], ms, {'--rc': ROAR.color, '--dx': Math.cos(a) * d + 'px', '--dy': Math.sin(a) * d + 'px',
          '--life': (ms * (0.55 + Math.random() * 0.4)) + 'ms', 'animation-delay': (Math.random() * ms * 0.35) + 'ms'});
      }
      return throat;
    }
    /* The two greatest birds screech in their own way (SHOAIB: the strongest beasts in the game should be unique).
       The Vermilion Bird breathes a phoenix-fire blast, crimson with a golden heart, embers streaming along it and a
       ring of fire bursting off its wings. The Kun-Peng, the fish of the northern sea, darkens the sky and screeches a
       tide: a deep-sea blast with a pale heart, a whirlpool turning round it, spray flying and great waves rolling
       out along the ground from it and from where the tide strikes you. */
    var SCREECH_KINDS = {
      vermilion_bird: {tint: '#ff3d1f', core: '#ffc23a', feather: '#ff6a2a', scale: 1.15, special: function (p, you, pic, len, ang, big) {
        var c = at(pic, 0.5, 0.45), sz = Math.min(900, pic.width * 0.9 * big);
        fx('bnova', c[0], c[1], 1500, {'--rc': '#ff5a1f', '--s': sz + 'px', 'animation-delay': '120ms'});
        wave(c, 'ring', sz * 1.2, 700, 160, 'broarbig', 0, 0.5);
        var a = ang * Math.PI / 180;
        for (var j = 0; j < 60; j++) {                         // embers streaming along the blast
          var q = Math.random(), spread = (Math.random() - 0.5) * pic.height * 0.7 * (0.3 + q);
          fx('bdrop', p[0], p[1], 1500, {'--rc': j % 3 ? '#ff7a1a' : '#ffd25a',
            '--dx': (Math.cos(a) * len * q - Math.sin(a) * spread) + 'px', '--dy': (Math.sin(a) * len * q + Math.cos(a) * spread - 40 * Math.random()) + 'px',
            '--s': (0.4 + Math.random() * 0.8).toFixed(2), 'animation-delay': (Math.random() * 1000) + 'ms'});
        }
      }},
      kun_peng_fish_of_the_northern_sea: {tint: '#1b8fd6', core: '#9ff4ff', feather: '#4fc8e8', scale: 1.4, special: function (p, you, pic, len, ang, big) {
        fx('bdeep', 0, 0, 2400, {});                           // the sky darkens
        var c = at(pic, 0.5, 0.5);
        for (var i = 0; i < 6; i++) {                          // a whirlpool turning round it
          fx('bcoil', c[0], c[1] + 10 - i * 4, 1800, {'--rc': i % 2 ? '#9ff4ff' : '#1b8fd6', '--w': pic.width * (1.3 - 0.12 * i) + 'px',
            '--h': pic.height * 0.3 + 'px', '--life': '1800ms', '--r0': (i * 60) + 'deg', 'animation-delay': (i * 60) + 'ms'});
        }
        var f = at(pic, 0.5, 0.98), h = at(fr, 0.5, 0.98);
        [[f, 0], [h, 380]].forEach(function (w) {              // great waves rolling out along the ground
          [0, 240].forEach(function (d, i) {
            fx('bquake', w[0][0], w[0][1], 1700, {'--rc': '#2fb4ff', '--s': Math.min(1500, pic.width * (2.2 - 0.5 * i) * big) + 'px',
              'animation-delay': (w[1] + d) + 'ms'});
          });
        });
        for (var k = 0; k < 70; k++) {                         // spray flying where the tide strikes
          var r = Math.random() * Math.PI * 2, dd = 60 + Math.random() * 260;
          fx('bdrop', you[0], you[1], 1500, {'--rc': k % 2 ? '#9ff4ff' : '#2fb4ff', '--dx': Math.cos(r) * dd + 'px',
            '--dy': (Math.sin(r) * dd * 0.7 - 30) + 'px', '--s': (0.5 + Math.random()).toFixed(2), 'animation-delay': (250 + Math.random() * 700) + 'ms'});
        }
      }},
    };
    function screech(p, pic, final) {
      var sr = scene.getBoundingClientRect(), big = final ? 1.3 : 1, tall = pic.height;
      var you = at(fr, 0.5, 0.42);                             // where it is aimed: your middle
      var dx = (you[0] - p[0]) / 100 * sr.width, dy = (you[1] - p[1]) / 100 * sr.height;
      var len = Math.sqrt(dx * dx + dy * dy), ang = Math.atan2(dy, dx) * 180 / Math.PI;
      var flash = fx('broarflash', 0, 0, 520); flash.style.setProperty('--x', p[0] + '%'); flash.style.setProperty('--y', p[1] + '%');
      var kind = SCREECH_KINDS[ROAR.slug] || {tint: ROAR.color}, scale = (kind.scale || 1) * big;
      wave(p, 'burst', Math.min(700, tall * 0.8 * big), 460, 0, 'broarbig star', 9, 0.55);    // the blast at its beak
      var fy = Math.abs(ang) > 90 ? -1 : 1, wh = Math.min(560, Math.max(200, len * 0.42)) * scale;
      blast(p, pic, big); shape(p, pic, big, 'flying');           // the screech: a spiralling wind of its element, at you
      [420, 900].forEach(function (d, i) {                     // bells pulsing out of its beak while it holds
        wave(p, i % 2 ? 'double' : 'ring', Math.min(1100, tall * (1.2 + 0.3 * i) * big), 820, d, 'broarbig cone', 2, 0.6)
          .style.setProperty('--ang', ang + 'deg');
      });
      if (kind.special) kind.special(p, you, pic, len, ang, big);
      var c = at(pic, 0.5, 0.45);                              // its feathers torn loose, scattering across the scene
      for (var j = 0; j < 40; j++) {
        var a = Math.random() * Math.PI * 2, d = (120 + Math.random() * 320) * big;
        fx('bfeather', c[0] + (Math.random() - 0.5) * 8, c[1] + (Math.random() - 0.5) * 10, 2300, {'--rc': kind.feather || kind.tint,
          '--dx': Math.cos(a) * d + 'px', '--dy': (Math.sin(a) * d * 0.6 + 60 + Math.random() * 90) + 'px',
          '--rot': (Math.random() * 900 - 450) + 'deg', '--s': (0.7 + Math.random() * 0.8).toFixed(2), 'animation-delay': (Math.random() * 260) + 'ms'});
      }
      camera(p, 1 + 0.07 * big, 1400);
    }
    /* A serpent's hiss (beasts.ROAR_ANIMATIONS["serpent"], from SHOAIB's serpent roar video). As it rears up, Qi swirls
       into its jaws (`gather`) and a circle of glowing runes with two spinning golden rings flares up behind it
       (`runes`). As it lunges, jaws wide (`hiss`): a flash at its mouth and a roaring stream of its element breathed
       at you, widening as it goes and churning while it holds, droplets spraying through it, mist rolling out along
       the ground both ways, and the camera punching in. A final hiss is bigger. */
    function hueOf(hex) {                                        // the hue of a #rrggbb colour, in degrees
      var m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || '');
      if (!m) return 150;
      var r = parseInt(m[1], 16) / 255, g = parseInt(m[2], 16) / 255, b = parseInt(m[3], 16) / 255;
      var mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
      if (!d) return 150;
      var h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
      return (h * 60 + 360) % 360;
    }
    function runes(pic, ms) {
      var c = at(pic, 0.5, 0.48), size = Math.min(1000, pic.height * 1.55);
      var n = document.createElement('div');
      n.className = 'brune';
      n.style.left = c[0] + '%'; n.style.top = c[1] + '%'; n.style.width = n.style.height = size + 'px';
      n.style.setProperty('--rc', ROAR.color); n.style.setProperty('--life', ms + 'ms');
      n.innerHTML = '<i class="r1"></i><i class="r2"></i><i class="o1"></i><i class="o2"></i>';
      scene.insertBefore(n, beastBox);                          // behind the serpent
      setTimeout(function () { n.remove(); }, ms + 50);
    }
    function hiss(p, pic, final) {
      var sr = scene.getBoundingClientRect(), big = final ? 1.3 : 1, tall = pic.height;
      var you = at(fr, 0.5, 0.45);
      var dx = (you[0] - p[0]) / 100 * sr.width, dy = (you[1] - p[1]) / 100 * sr.height;
      var len = Math.sqrt(dx * dx + dy * dy) * 1.08, ang = Math.atan2(dy, dx) * 180 / Math.PI;
      var flash = fx('broarflash', 0, 0, 520); flash.style.setProperty('--x', p[0] + '%'); flash.style.setProperty('--y', p[1] + '%');
      wave(p, 'burst', Math.min(800, tall * 0.9 * big), 460, 0, 'broarbig star', 0, 0.9);
      var fy = Math.abs(ang) > 90 ? -1 : 1, hue = hueOf(ROAR.color), tint = (hue > 60 && hue < 170 ? 0 : hue - 150) + 'deg';   // the picture is venom green
      blast(p, pic, big); shape(p, pic, big, 'serpent');          // its coiling breath, in its element, at you
      for (var j = 0; j < 46; j++) {                           // droplets spraying through it
        var q = 0.25 + Math.random() * 0.85, spread = (Math.random() - 0.5) * tall * 0.75 * q * big;
        var a = ang * Math.PI / 180;
        fx('bdrop', p[0], p[1], 1400, {'--rc': ROAR.color,
          '--dx': (Math.cos(a) * len * q - Math.sin(a) * spread) + 'px', '--dy': (Math.sin(a) * len * q + Math.cos(a) * spread) + 'px',
          '--s': (0.6 + Math.random()).toFixed(2), 'animation-delay': (Math.random() * 900) + 'ms'});
      }
      var f = at(pic, 0.5, 0.97);                              // mist rolling out along the ground
      for (var m = 0; m < 12; m++) {
        var side = m % 2 ? 1 : -1;
        fx('bdust bmist', f[0] + side * (3 + 2.5 * m), f[1] + 1 - Math.random() * 2, 2000, {'--rc': ROAR.color,
          '--dx': side * (90 + 35 * m) + 'px', '--s': (0.8 + Math.random() * 0.6).toFixed(2), 'animation-delay': (30 * m) + 'ms'});
      }
      camera(p, 1 + 0.07 * big, 1450);
    }
    /* An amphibian's roar (beasts.ROAR_ANIMATIONS["amphibian"], from SHOAIB's amphibian roar video). As it crouches,
       Qi of its element swirls into its body (`gather`). As it throws its head up (`quake`): a golden starburst at its
       jaws, its whole body erupting in a spiky nova of its element, two shockwave rings racing out along the ground,
       dust rolling both ways, and the camera punching in. A final roar is bigger. */
    function quake(p, pic, final) {
      var big = final ? 1.3 : 1, tall = pic.height;
      var flash = fx('broarflash', 0, 0, 520); flash.style.setProperty('--x', p[0] + '%'); flash.style.setProperty('--y', p[1] + '%');
      wave(p, 'burst', Math.min(700, tall * 0.75 * big), 480, 0, 'broarbig star', 9, 0.5);
      crack(pic, big);                                         // the ground split open all the way to your feet
      var f = at(pic, 0.5, 0.98);
      [0, 260].forEach(function (d, i) {                       // shockwave rings along the ground
        fx('bquake', f[0], f[1], 1500, {'--rc': ROAR.color, '--s': Math.min(1300, pic.width * (1.9 - 0.4 * i) * big) + 'px',
          'animation-delay': (200 + d) + 'ms'});
      });
      for (var m = 0; m < 12; m++) {                           // dust rolling out both ways
        var side = m % 2 ? 1 : -1;
        fx('bdust', f[0] + side * (3 + 2.5 * m), f[1] - 1 - Math.random() * 2, 1900, {'--dx': side * (70 + 30 * m) + 'px',
          '--s': (0.9 + Math.random() * 0.7).toFixed(2), 'animation-delay': (200 + 30 * m) + 'ms'});
      }
      camera(p, 1 + 0.07 * big, 1450);
    }
    /* A dragon's roar (beasts.ROAR_ANIMATIONS["dragon"], from SHOAIB's dragon roar video). As it rears, ribbons of its
       element coil up round its body (`coil`) and Qi swirls into its jaws (`gather`). As it roars (`storm`): a flash
       and a blazing blast of its element at you, lightning streaks fanning out round it, then its whole body bursting
       into a sphere of light with spikes and rings, mist pooling at its base, and the camera punching in. */
    var DRAGON_GOLD = '#fff1d0';                                 // the blast picture's own pale light, beside the element's colour
    function coil(pic, ms) {
      var c = at(pic, 0.45, 0.5);
      for (var i = 0; i < 4; i++) {
        fx('bcoil', c[0], c[1] + 8 - i * 6, ms, {'--rc': i % 2 ? DRAGON_GOLD : ROAR.color, '--w': pic.width * (0.95 - 0.12 * i) + 'px',
          '--h': pic.height * 0.32 + 'px', '--life': ms + 'ms', '--r0': (i * 70) + 'deg', 'animation-delay': (i * 90) + 'ms'});
      }
    }
    function storm(p, pic, final) {
      var sr = scene.getBoundingClientRect(), big = final ? 1.3 : 1, tall = pic.height;
      var you = at(fr, 0.5, 0.45);
      var dx = (you[0] - p[0]) / 100 * sr.width, dy = (you[1] - p[1]) / 100 * sr.height;
      var len = Math.sqrt(dx * dx + dy * dy) * 1.08, ang = Math.atan2(dy, dx) * 180 / Math.PI;
      var flash = fx('broarflash', 0, 0, 520); flash.style.setProperty('--x', p[0] + '%'); flash.style.setProperty('--y', p[1] + '%');
      wave(p, 'burst', Math.min(700, tall * 0.8 * big), 480, 0, 'broarbig star', 9, 0.6);
      var fy = Math.abs(ang) > 90 ? -1 : 1;                    // keep the blast picture the right way up
      blast(p, pic, big); shape(p, pic, big, 'dragon');           // a dragon of light, in its element, at you
      for (var j = 0; j < 12; j++) {                           // lightning streaks fanning out round the blast
        fx('bstreak', p[0], p[1], 1300, {'--rc': j % 2 ? DRAGON_GOLD : ROAR.color, '--len': len * (0.35 + Math.random() * 0.5) + 'px',
          '--ang': (ang + (Math.random() - 0.5) * 50) + 'deg', 'animation-delay': (40 + Math.random() * 500) + 'ms'});
      }
      var f = at(pic, 0.5, 0.98);                              // mist pooling at its base
      for (var m = 0; m < 10; m++) {
        var side = m % 2 ? 1 : -1;
        fx('bdust bmist', f[0] + side * (2 + 2.5 * m), f[1] - Math.random() * 2, 2000, {'--rc': ROAR.color,
          '--dx': side * (40 + 22 * m) + 'px', '--s': (0.9 + Math.random() * 0.6).toFixed(2), 'animation-delay': (600 + 30 * m) + 'ms'});
      }
      camera(p, 1 + 0.07 * big, 1500);
    }
    /* A primate's roar (beasts.ROAR_ANIMATIONS["primate"], from SHOAIB's primate roar video). As it rises and pounds
       its chest, a whirlwind of its element spirals round it (`vortex`) and each blow sends a ring off its chest
       (`beat`). As it roars (`pound`): a flash at its jaws, a sphere of its element bursting round its body with
       rings, streaks shooting out every way, shards flying, dust, and the camera punching in. */
    function vortex(pic, ms) {
      var c = at(pic, 0.5, 0.5);
      for (var i = 0; i < 6; i++) {
        fx('bcoil', c[0], c[1] + 10 - i * 4, ms, {'--rc': ROAR.color, '--w': pic.width * (1.15 - 0.1 * i) + 'px',
          '--h': pic.height * (0.22 + 0.03 * i) + 'px', '--life': ms + 'ms', '--r0': (i * 55) + 'deg', 'animation-delay': (i * 70) + 'ms'});
      }
    }
    function beat(pic) {
      var c = at(pic, 0.5, 0.42);
      wave(c, 'ring', Math.min(500, pic.width * 0.6), 420, 0, 'broarbig', 0, 0.55);
      camera(c, 1.025, 260);
    }
    function pound(p, pic, final) {
      var sr = scene.getBoundingClientRect(), big = final ? 1.3 : 1;
      var flash = fx('broarflash', 0, 0, 520); flash.style.setProperty('--x', p[0] + '%'); flash.style.setProperty('--y', p[1] + '%');
      var tall = pic.height, you = at(fr, 0.5, 0.45), aimed = aim(p, you), len = aimed[0], ang = aimed[1];
      wave(p, 'burst', Math.min(700, tall * 0.75 * big), 460, 0, 'broarbig star', 9, 0.6);   // the blast at its jaws
      blast(p, pic, big);                                      // its element thrown across at you
      for (var i = 0; i < 4; i++) {                            // a wall of sound rolling at you
        var q = 0.15 + 0.22 * i;
        wave([p[0] + (you[0] - p[0]) * q, p[1] + (you[1] - p[1]) * q], i % 2 ? 'double' : 'ring', Math.min(1000, tall * (0.7 + 0.25 * i) * big),
          640, 30 + 60 * i, 'broarbig cone', 3, 0.75).style.setProperty('--ang', ang + 'deg');
      }
      for (var j = 0; j < 14; j++) {                           // streaks fanning out toward you
        fx('bstreak', p[0], p[1], 1000, {'--rc': ROAR.color, '--len': len * (0.4 + Math.random() * 0.6) + 'px',
          '--ang': (ang + (Math.random() - 0.5) * 40) + 'deg', 'animation-delay': (Math.random() * 240) + 'ms'});
      }
      var ar = ang * Math.PI / 180;
      for (var k = 0; k < 24; k++) {                           // shards flung at you
        var r = len * (0.5 + Math.random() * 0.6), sp = (Math.random() - 0.5) * tall * 0.6;
        fx('bdrop', p[0], p[1], 1300, {'--rc': ROAR.color, '--dx': (Math.cos(ar) * r - Math.sin(ar) * sp) + 'px',
          '--dy': (Math.sin(ar) * r + Math.cos(ar) * sp) + 'px', '--s': (0.5 + Math.random()).toFixed(2), 'animation-delay': (Math.random() * 300) + 'ms'});
      }
      var f = at(pic, 0.5, 0.98);
      for (var m = 0; m < 10; m++) {
        var side = m % 2 ? 1 : -1;
        fx('bdust', f[0] + side * (2 + 2.5 * m), f[1] - Math.random() * 2, 1800, {'--dx': side * (60 + 28 * m) + 'px',
          '--s': (0.8 + Math.random() * 0.6).toFixed(2), 'animation-delay': (150 + 30 * m) + 'ms'});
      }
      camera(p, 1 + 0.07 * big, 1450);
    }
    /* An insect's threat display (beasts.ROAR_ANIMATIONS["insect"], from SHOAIB's insect roar video). As it rears,
       venom drips and puffs of poison smoke gather round it (`seep`). As it hisses (`venom`): a flash at its jaws, a
       ring of purple and green venom flames rising round its body, a sphere of poison bursting out with rings and
       droplets, and a cloud of poison smoke left hanging low over the ground. Its element's colour, with purple. */
    var VENOM_PURPLE = '#b04dff';
    function seep(pic, ms) {
      for (var i = 0; i < 10; i++) {
        var c = at(pic, 0.2 + Math.random() * 0.6, 0.35 + Math.random() * 0.4);
        fx('bdrop', c[0], c[1], ms + 200, {'--rc': i % 2 ? VENOM_PURPLE : ROAR.color, '--dx': (Math.random() - 0.5) * 30 + 'px',
          '--dy': (30 + Math.random() * 50) + 'px', '--s': (0.5 + Math.random() * 0.6).toFixed(2), 'animation-delay': (Math.random() * ms * 0.7) + 'ms'});
      }
      var f = at(pic, 0.5, 0.95);
      for (var m = 0; m < 4; m++) {
        var side = m % 2 ? 1 : -1;
        fx('bdust bmist bvmist', f[0] + side * (6 + 4 * m), f[1] + 1, ms + 400, {'--rc': VENOM_PURPLE,
          '--dx': side * (30 + 14 * m) + 'px', '--s': (0.5 + Math.random() * 0.3).toFixed(2), 'animation-delay': (80 * m) + 'ms'});
      }
    }
    function venom(p, pic, final) {
      var big = final ? 1.3 : 1;
      var flash = fx('broarflash', 0, 0, 520); flash.style.setProperty('--x', p[0] + '%'); flash.style.setProperty('--y', p[1] + '%');
      var tall = pic.height, you = at(fr, 0.5, 0.45), aimed = aim(p, you), len = aimed[0], ar = aimed[1] * Math.PI / 180;
      wave(p, 'burst', Math.min(600, tall * 0.7 * big), 440, 0, 'broarbig star', 9, 0.55);
      blast(p, pic, big);                                      // the venom sprayed across at you
      for (var k = 0; k < 40; k++) {                           // poison droplets spraying through it
        var q = 0.25 + Math.random() * 0.85, spread = (Math.random() - 0.5) * tall * 0.6 * q * big;
        fx('bdrop', p[0], p[1], 1300, {'--rc': k % 4 ? ROAR.color : VENOM_PURPLE,
          '--dx': (Math.cos(ar) * len * q - Math.sin(ar) * spread) + 'px', '--dy': (Math.sin(ar) * len * q + Math.cos(ar) * spread) + 'px',
          '--s': (0.5 + Math.random()).toFixed(2), 'animation-delay': (Math.random() * 500) + 'ms'});
      }
      var f = at(fr, 0.5, 0.97);                               // a cloud of poison smoke left hanging round YOUR feet
      for (var m = 0; m < 8; m++) {
        var side = m % 2 ? 1 : -1;
        fx('bdust bmist bvmist', f[0] + side * (3 + 2 * m), f[1] + 1, 2600, {'--rc': m % 3 ? VENOM_PURPLE : ROAR.color,
          '--dx': side * (40 + 20 * m) + 'px', '--s': (0.6 + Math.random() * 0.4).toFixed(2), 'animation-delay': (TRAVEL + 40 * m) + 'ms'});
      }
      camera(p, 1 + 0.07 * big, 1450);
    }
    /* A crocodile's roar (beasts.ROAR_ANIMATIONS["crocodile"], from SHOAIB's crocodile roar video). It presses low as Qi
       gathers into its jaws (`gather`), then throws its head up and bellows (`bellow`): rings of sound pulsing out of
       its gaping jaws toward you, a burst of its element flaring round its head with a golden heart and spikes of light,
       dust blasting up off the ground on both sides, and the camera punching in. A final roar is bigger. */
    function bellow(p, pic, final) {
      var sr = scene.getBoundingClientRect(), big = final ? 1.3 : 1, tall = pic.height;
      var you = at(fr, 0.5, 0.45), ang = Math.atan2((you[1] - p[1]) * sr.height, (you[0] - p[0]) * sr.width) * 180 / Math.PI;
      var flash = fx('broarflash', 0, 0, 520); flash.style.setProperty('--x', p[0] + '%'); flash.style.setProperty('--y', p[1] + '%');
      var sz = Math.min(820, Math.max(pic.height * 2.2, pic.width * 0.7) * big);
      fx('bnova', p[0], p[1], 1100, {'--rc': '#ffd98a', '--s': sz * 0.4 + 'px', 'animation-delay': '40ms'});
      blast(p, pic, big);                                      // its element thrown across at you
      for (var i = 0; i < 5; i++) {                            // rings of sound rolling out of its jaws all the way to you
        var q = 0.08 + 0.19 * i;
        wave([p[0] + (you[0] - p[0]) * q, p[1] + (you[1] - p[1]) * q], i % 2 ? 'double' : 'ring', Math.min(1100, tall * (0.7 + 0.28 * i) * big),
          680, 30 + 60 * i, 'broarbig cone', 3, 0.8).style.setProperty('--ang', ang + 'deg');
      }
      for (var j = 0; j < 12; j++) {                           // spikes of light fanning toward you
        fx('bstreak', p[0], p[1], 1100, {'--rc': j % 3 ? ROAR.color : '#ffe3a0', '--len': sz * (0.35 + Math.random() * 0.4) + 'px',
          '--ang': (ang + (Math.random() - 0.5) * 60) + 'deg', 'animation-delay': (60 + Math.random() * 300) + 'ms'});
      }
      var f = at(pic, 0.3, 0.98);                              // dust blasting up off the ground
      for (var m = 0; m < 14; m++) {
        var side = m % 2 ? 1 : -1;
        fx('bdust', f[0] + side * (2 + 2.2 * m), f[1] - Math.random() * 2, 1800, {'--dx': side * (60 + 26 * m) + 'px',
          '--s': (0.9 + Math.random() * 0.7).toFixed(2), 'animation-delay': (120 + 25 * m) + 'ms'});
      }
      camera(p, 1 + 0.07 * big, 1450);
    }
    /* A tortoise's roar (beasts.ROAR_ANIMATIONS["tortoise"], from SHOAIB's tortoise roar video). As it braces, its
       shell's runes light up and crackle with energy of its element (`charged`: a glow over the shell, sparks arcing
       over it). As it roars (`shell`): a cone of sound rings blasting out of its jaws at you, then a great dome of its
       element swelling up round its whole body like a shield, rings rippling over it, mist rolling out along the
       ground, and the camera punching in. A final roar is bigger. */
    function charged(pic, ms) {
      var c = at(pic, 0.55, 0.32);
      fx('bshellglow', c[0], c[1], ms, {'--rc': ROAR.color, '--w': pic.width * 0.75 + 'px', '--h': pic.height * 0.6 + 'px', '--life': ms + 'ms'});
      for (var j = 0; j < 14; j++) {                           // energy crackling over the shell
        fx('bstreak', c[0] + (Math.random() - 0.5) * 18, c[1] + (Math.random() - 0.5) * 12, 380, {'--rc': j % 3 ? ROAR.color : '#ffffff',
          '--len': (30 + Math.random() * 70) + 'px', '--ang': (Math.random() * 360) + 'deg', 'animation-delay': (Math.random() * (ms - 300)) + 'ms'});
      }
    }
    function shell(p, pic, final) {
      var sr = scene.getBoundingClientRect(), big = final ? 1.3 : 1, tall = pic.height;
      var you = at(fr, 0.5, 0.45), ang = Math.atan2((you[1] - p[1]) * sr.height, (you[0] - p[0]) * sr.width) * 180 / Math.PI;
      var flash = fx('broarflash', 0, 0, 520); flash.style.setProperty('--x', p[0] + '%'); flash.style.setProperty('--y', p[1] + '%');
      blast(p, pic, big);                                      // its element thrown across at you
      for (var i = 0; i < 5; i++) {                            // the cone of sound rings blasting all the way to you
        var q = 0.06 + 0.2 * i;
        wave([p[0] + (you[0] - p[0]) * q, p[1] + (you[1] - p[1]) * q], i % 2 ? 'double' : 'ring', Math.min(1100, tall * (0.6 + 0.3 * i) * big),
          720, 40 + 70 * i, 'broarbig cone', 3, 0.85).style.setProperty('--ang', ang + 'deg');
      }
      var c = at(pic, 0.5, 0.62), sz = Math.min(800, Math.max(pic.width, pic.height) * 0.95 * big);
      fx('bdome', c[0], c[1], 1400, {'--rc': ROAR.color, '--s': sz + 'px', 'animation-delay': '420ms'});    // its shield, after the blast
      var f = at(pic, 0.5, 0.98);                              // mist rolling out along the ground
      for (var m = 0; m < 12; m++) {
        var side = m % 2 ? 1 : -1;
        fx('bdust bmist', f[0] + side * (3 + 2.5 * m), f[1] - Math.random() * 2, 2000, {'--rc': ROAR.color,
          '--dx': side * (70 + 28 * m) + 'px', '--s': (0.9 + Math.random() * 0.6).toFixed(2), 'animation-delay': (300 + 30 * m) + 'ms'});
      }
      camera(p, 1 + 0.06 * big, 1550);
    }
    /* The roar HITS you (SHOAIB, Nov 27: the scorpion's, toad's, ape's... roars "look like they are roaring to
       themselves"). Every roar now goes: Qi gathered at its mouth, a blast of its own element thrown from its mouth
       across to you (art/fx/elem/<element>_stream.webp, scripts/make_element_fx.py), and TRAVEL ms later the hit on
       you (`impact`): its element bursting on your body, a white impact frame, you knocked back, a hard shake, and its
       element left on the ground at your feet (<element>_ground.webp) for a moment. The toads and lizards instead
       slam a crack along the ground to your feet (ground_crack.webp) and the burst erupts under you. An Elite's roar
       also pulses its element round the edge of the screen; a Beast King's darkens the scene, cracks the ground under
       itself and follows with an aftershock. Presentation only: the damage and debuffs are the server's (`struck`). */
    var TRAVEL = 280;
    var ELEM = ROAR && ROAR.element ? '/art/fx/elem/' + ROAR.element : null;
    var TIER_OF = {ring: 0, double: 1, burst: 2};               // normal, Elite, Beast King (beast_roar "wave")
    function preload(src) { var i = new Image(); i.src = src; if (i.decode) i.decode().catch(function () {}); }
    if (ELEM) ['_stream', '_burst', '_ground'].forEach(function (k) { preload(ELEM + k + '.webp'); });
    var SHAPE_OF = {roar: 'quadruped', screech: 'flying', hiss: 'serpent', storm: 'dragon'};          // `shape`
    if (ROAR && ROAR.motion && SHAPE_OF[ROAR.motion.style]) preload('/art/fx/roars/roar_' + SHAPE_OF[ROAR.motion.style] + '.webp');
    if (ROAR && ROAR.power >= 1) preload('/art/fx/elem/sigil_' + (ROAR.power >= 4 ? 3 : ROAR.power >= 3 ? 2 : 1) + '.webp');
    if (ROAR && ROAR.marks) ROAR.marks.forEach(function (k) { new Image().src = markSrc(k); });   // its hit marks (`mark`)
    function aim(p, you) {                                       // from p to you: [length in px, angle in degrees]
      var sr = scene.getBoundingClientRect(), dx = (you[0] - p[0]) / 100 * sr.width, dy = (you[1] - p[1]) / 100 * sr.height;
      return [Math.sqrt(dx * dx + dy * dy), Math.atan2(dy, dx) * 180 / Math.PI];
    }
    function piece(cls, src, xPct, yPct, life, style) {          // one of the element's pictures, over the scene
      var n = document.createElement('img');
      n.className = cls; n.src = src; n.alt = '';
      n.style.left = xPct + '%'; n.style.top = yPct + '%';
      Object.keys(style || {}).forEach(function (k) { n.style.setProperty(k, style[k]); });
      scene.appendChild(n);
      setTimeout(function () { n.remove(); }, life);
      return n;
    }
    /* Out of the mouth (SHOAIB Nov 27: "make sure the roar looks like it comes out of the mouth"): a roar's blast
       starts a touch in front of the open jaws, is drawn BEHIND the beast's picture (so where they overlap the jaws
       cover it and it pours out of the mouth), and the element glows at the mouth while it roars (`mouthGlow`). */
    function lip(p, pic) {
      var you = at(fr, 0.5, 0.45), a = aim(p, you), r = a[1] * Math.PI / 180, sr = scene.getBoundingClientRect(), d = pic.height * 0.05;
      return [p[0] + Math.cos(r) * d / sr.width * 100, p[1] + Math.sin(r) * d / sr.height * 100];
    }
    function underBeast(n) { scene.insertBefore(n, beastBox); }
    function mouthGlow(p, pic) {
      if (scene.querySelector('.bmouth')) return;
      fx('bmouth', p[0], p[1], 1100, {'--rc': ROAR.color, '--s': Math.min(260, pic.height * 0.32) + 'px'});
    }
    function blast(p, pic, big) {                                // the element thrown from its mouth across to you
      if (!ELEM) return;
      mouthGlow(p, pic); p = lip(p, pic);
      var you = at(fr, 0.5, 0.45), a = aim(p, you), len = a[0] * 1.12;
      var h = Math.min(pic.height * 1.1, Math.max(150, len * 0.42)) * big;
      var wrap = document.createElement('div');                  // turned to face you; the picture's bright end at its mouth
      wrap.className = 'bestream'; wrap.style.left = p[0] + '%'; wrap.style.top = p[1] + '%';
      wrap.style.setProperty('--rot', (a[1] - 180) + 'deg');
      wrap.innerHTML = '<img alt="" src="' + ELEM + '_stream.webp"><img class="glow" alt="" src="' + ELEM + '_stream.webp">';
      wrap.style.setProperty('--len', len + 'px'); wrap.style.setProperty('--h', h + 'px');
      underBeast(wrap);
      setTimeout(function () { wrap.remove(); }, 1500);
    }
    /* A body type's own roar (SHOAIB Nov 27: "I want it to be detailed"): his white picture of its shape
       (art/fx/roars/roar_<body>.webp: a four-legged beast's sound rings, a bird's spiralling wind, a serpent's
       coiling breath, a dragon of light) thrown from its mouth across to you in its element's colour (the picture's
       shape filled with the colour, its own white light over it), over its element's blast (`blast`). */
    var SHAPE_RATIO = {quadruped: 0.69, flying: 0.52, serpent: 0.44, dragon: 0.44};
    function shape(p, pic, big, body) {
      mouthGlow(p, pic); p = lip(p, pic);
      var you = at(fr, 0.5, 0.45), a = aim(p, you), len = a[0] * 1.08, src = '/art/fx/roars/roar_' + body + '.webp';
      var h = Math.min(pic.height * 1.5, len * SHAPE_RATIO[body]) * big;
      var wrap = document.createElement('div');
      wrap.className = 'bestream bshape'; wrap.style.left = p[0] + '%'; wrap.style.top = p[1] + '%';
      wrap.style.setProperty('--rot', (a[1] - 180) + 'deg'); wrap.style.setProperty('--len', len + 'px'); wrap.style.setProperty('--h', h + 'px');
      wrap.style.setProperty('--rc', ROAR.color); wrap.style.setProperty('--m', 'url(' + src + ')');
      wrap.innerHTML = '<span class="bsh"><i class="tint"></i><img alt="" src="' + src + '"></span>';
      underBeast(wrap);
      setTimeout(function () { wrap.remove(); }, 1500);
    }
    function crack(pic, big) {                                   // a crack slammed along the ground to your feet
      var from = at(pic, 0.15, 0.97), to = at(fr, 0.55, 0.97), a = aim(from, to);
      var wrap = document.createElement('div');
      wrap.className = 'bestream bcrack'; wrap.style.left = from[0] + '%'; wrap.style.top = from[1] + '%';
      wrap.style.setProperty('--rot', (a[1] - 180) + 'deg');
      wrap.style.setProperty('--len', a[0] * 1.15 + 'px'); wrap.style.setProperty('--h', Math.min(240, a[0] * 0.3) * big + 'px');
      wrap.innerHTML = '<img alt="" src="/art/fx/elem/ground_crack.webp">';
      if (ROAR.element !== 'earth') wrap.style.setProperty('--rc', ROAR.color);
      scene.insertBefore(wrap, fighter);                         // on the ground, under you
      setTimeout(function () { wrap.remove(); }, 2200);
    }
    function impact(final, low) {                                // the roar lands on you
      var big = final ? 1.3 : 1, tier = TIER_OF[ROAR.wave] || 0;
      buzz(tier >= 2 || final ? [90, 40, 140] : tier ? [70, 30, 90] : [60, 30, 60]);
      var you = at(fr, 0.5, low ? 0.7 : 0.45), feet = at(fr, 0.5, 0.97), sz = Math.min(760, fr.height * (0.95 + 0.15 * tier) * big);
      if (ELEM) {
        piece('beburst', ELEM + '_burst.webp', you[0], you[1], 900, {'--s': sz + 'px', '--r': (Math.random() * 40 - 20) + 'deg'});
        piece('beburst b2', ELEM + '_burst.webp', you[0], you[1], 1000, {'--s': sz * 0.7 + 'px', '--r': (Math.random() * 90 + 60) + 'deg'});
        var g = piece('beground', ELEM + '_ground.webp', feet[0], feet[1], 2400, {'--w': Math.min(560, fr.width * 0.85 * big) + 'px'});
        scene.insertBefore(g, fighter);                          // on the ground, under your feet
      }
      var flash = fx('broarflash behit', 0, 0, 420); flash.style.setProperty('--x', you[0] + '%'); flash.style.setProperty('--y', you[1] + '%');
      flash.style.setProperty('--rc', ROAR.color);
      if (scene.animate) {                                       // the impact frame: one blinding beat, then the shake
        var q = (9 + 4 * tier) * SHAKE;
        fighter.animate([{transform: 'none'}, {transform: 'translate(' + -q + 'px,' + q * 0.4 + 'px)'}, {transform: 'translate(' + q * 0.7 + 'px,' + -q * 0.3 + 'px)'},
                         {transform: 'translate(' + -q * 0.4 + 'px,0)'}, {transform: 'none'}], {duration: 380});
      }
      if (tier >= 2 && ELEM) setTimeout(function () {           // a Beast King's aftershock
        piece('beburst', ELEM + '_burst.webp', you[0], you[1], 900, {'--s': sz * 1.35 + 'px', '--r': '30deg'});
      }, 420);
    }
    /* A strong beast's roar (explore_play.beast_power): a formation circle of its element flares on the ground under
       it (art/fx/elem/sigil_<1-3>.webp: King and Emperor, Ancestor, Saint), and from Martial Ancestor up its spirit,
       a giant ghost of itself in its element's light, rises behind it and fades (`avatar`, from its own picture). */
    function sigil(pic) {
      var lvl = ROAR.power >= 4 ? 3 : ROAR.power >= 3 ? 2 : 1, f = at(pic, 0.5, 0.97), src = '/art/fx/elem/sigil_' + lvl + '.webp';
      var n = document.createElement('span');
      n.className = 'besigil s' + lvl; n.style.left = f[0] + '%'; n.style.top = f[1] + '%';
      n.style.setProperty('--w', Math.min(1300, pic.width * (1.3 + 0.15 * lvl)) + 'px'); n.style.setProperty('--rc', ROAR.color);
      n.style.setProperty('--m', 'url(' + src + ')');
      n.innerHTML = '<i class="tint"></i><img alt="" src="' + src + '">';
      scene.insertBefore(n, beastBox);                           // on the ground, under the beast
      setTimeout(function () { n.remove(); }, 2600);
    }
    function avatar(pic, src, cls, life) {
      if (!src) return;
      var f = at(pic, 0.5, 1), n = document.createElement('span');
      n.className = 'bavatar' + (ROAR.power >= 4 ? ' saint' : '') + (cls ? ' ' + cls : '');
      n.style.left = f[0] + '%'; n.style.top = f[1] + '%';
      n.style.width = pic.width + 'px'; n.style.height = pic.height + 'px';
      n.style.setProperty('--rc', ROAR.color); n.style.setProperty('--m', 'url(' + src + ')');
      n.innerHTML = '<i class="tint"></i><img alt="" src="' + src + '">';
      scene.insertBefore(n, beastBox);                           // behind the beast
      setTimeout(function () { n.remove(); }, life || 2300);
    }
    /* Your blows crack a strong beast's Qi (SHOAIB Nov 27): when a hit lands on a beast of Martial King and up, its
       aura flares and a few pieces of its element burst off where it was struck. */
    function qiCrack() {
      if (!ROAR || !(ROAR.power >= 1) || !ELEM) return;
      if (auraEl) { auraEl.classList.remove('flare'); void auraEl.offsetWidth; auraEl.classList.add('flare'); }
      var p = at(br, 0.35 + Math.random() * 0.3, 0.35 + Math.random() * 0.25);
      piece('beburst bechip', ELEM + '_burst.webp', p[0], p[1], 700, {'--s': Math.min(420, br.height * 0.7) + 'px', '--r': (Math.random() * 90) + 'deg'});
    }
    /* A strong beast dies in its element (SHOAIB Nov 27): its aura shatters into its element's pieces, and from
       Martial Ancestor up its spirit tears loose and rises away, slow and fading, as it falls. */
    function departs() {
      if (!ROAR || !(ROAR.power >= 1) || !ELEM) return;
      var c = at(br, 0.5, 0.55), sz = Math.min(820, br.height * 1.2);
      piece('beburst', ELEM + '_burst.webp', c[0], c[1], 1000, {'--s': sz + 'px', '--r': '0deg'});
      setTimeout(function () { piece('beburst', ELEM + '_burst.webp', c[0], c[1], 1100, {'--s': sz * 1.3 + 'px', '--r': '40deg'}); }, 180);
      var f = at(br, 0.5, 0.97), g = piece('beground', ELEM + '_ground.webp', f[0], f[1], 3200, {'--w': Math.min(700, br.width * 1.1) + 'px'});
      scene.insertBefore(g, beastBox);
      if (ROAR.power >= 3) avatar(br, beast.src, 'depart', 3200);
    }
    function presence(pic, final, src) {                         // what an Elite's or a Beast King's roar does to the whole scene
      if (ROAR.power >= 1) sigil(pic);
      if (ROAR.power >= 3) avatar(pic, src);
      var tier = TIER_OF[ROAR.wave] || 0;
      if (final && tier < 1) tier = 1;
      if (tier >= 1) { var v = fx('bevignette', 0, 0, 1700); v.style.setProperty('--rc', ROAR.color); }
      if (tier >= 2) {
        scene.insertBefore(fx('tdim', 50, 50, 2200, {'--life': '2200ms'}), beastBox);
        var f = at(pic, 0.5, 0.97);
        var c = piece('beground bekcrack', '/art/fx/elem/ground_crack.webp', f[0], f[1], 2400, {'--w': Math.min(1100, pic.width * 1.6) + 'px', '--rc': ROAR.color});
        scene.insertBefore(c, beastBox);
      }
    }
    var roarPic = null;                                          // the open-mouthed roar picture, loaded ahead
    if (ROAR && ROAR.art) { roarPic = new Image(); roarPic.src = ROAR.art; }
    function roaringMoved(M, ev) {
      ev = ev || {};
      var did = {}, keys = M.keys, at0 = [0], pic = null, pivot = null, still = beast.src, opened = false;
      var beastStill = {naturalWidth: beast.naturalWidth, naturalHeight: beast.naturalHeight};
      for (var i = 0; i < M.ms.length; i++) at0.push(at0[i] + M.ms[i]);
      var BURST = at0[M.burst], HOLD0 = at0[M.hold], HOLD1 = at0[M.hold + 1], TOTAL = at0[at0.length - 1];
      var IMPACT = BURST + TRAVEL;                             // the blast reaches you
      function once(k) { if (did[k]) return false; did[k] = true; return true; }
      function measure(img) {                                  // the picture as drawn (object-fit: contain, feet down)
        img = img || beast;
        var keep = beast.style.transform;
        beast.style.transform = '';
        var box = beast.getBoundingClientRect();
        beast.style.transform = keep;
        var w = box.width, h = box.height;
        if (img.naturalWidth && img.naturalHeight) {
          var ar = img.naturalWidth / img.naturalHeight;
          w = Math.min(box.width, box.height * ar); h = w / ar;
        }
        pic = {left: box.left + (box.width - w) / 2, top: box.top + box.height - h, width: w, height: h, box: box};
        if (pivot && img !== beast) return;                    // a picture swapped mid-roar turns about the same feet
        pivot = [pic.left + pic.width * (M.pivot || 0.85) - box.left, pic.top + pic.height - box.top];   // its (hind) feet, in the box
        beast.style.transformOrigin = pivot[0] + 'px ' + pivot[1] + 'px';
      }
      function pose3(t) {                                      // lean, drop, tilt at t, eased between the keys
        for (var k = 1; k < keys.length; k++) if (t < at0[k]) {
          var q = inout(span(t, at0[k - 1], at0[k])), A = keys[k - 1], B = keys[k];
          return [A[0] + (B[0] - A[0]) * q, A[1] + (B[1] - A[1]) * q, A[2] + (B[2] - A[2]) * q];
        }
        return keys[keys.length - 1];
      }
      function mouth(p) {                                      // its mouth where the move has carried it, in % of the scene
        var s = scene.getBoundingClientRect(), hd = (opened && ROAR.head_open) || ROAR.head || [0.15, 0.35];
        var mx = pic.left + pic.width * hd[0], my = pic.top + pic.height * hd[1];
        var ox = pic.box.left + pivot[0], oy = pic.box.top + pivot[1], a = p[2] * Math.PI / 180;   // as the picture turns
        var dx = mx - ox, dy = my - oy;
        var rx = ox + dx * Math.cos(a) - dy * Math.sin(a) - p[0] * pic.width, ry = oy + dx * Math.sin(a) + dy * Math.cos(a) + p[1] * pic.height;
        return [(rx - s.left) / s.width * 100, (ry - s.top) / s.height * 100];
      }
      function dust() {                                        // kicked up at its feet as it roars
        var f = at(pic, 0.5, 0.97);
        for (var j = 0; j < 6; j++) {
          var side = j % 2 ? 1 : -1;
          fx('bdust', f[0] + side * (2 + 3 * j), f[1] - 1 - Math.random() * 2, 1500, {'--dx': side * (26 + 16 * j) + 'px',
            '--s': (0.7 + Math.random() * 0.6).toFixed(2), 'animation-delay': (30 * j) + 'ms'});
        }
      }
      return {end: Math.max(TOTAL + 200, BURST + ROAR_MS, IMPACT + 900) + 150, render: function (t) {
        if (t < 0) return;
        if (once('start')) { measure(); if (ev.dmg) hold('me'); }
        if (M.style === 'screech' && t >= at0[1] && once('gather')) gather(mouth(pose3(at0[2])), BURST - at0[1]);
        if (M.style === 'quake' && t >= at0[1] && once('gather')) gather(mouth(pose3(at0[2])), BURST - at0[1]);
        if (M.style === 'storm' && t >= at0[1] && once('gather')) { gather(mouth(pose3(at0[2])), BURST - at0[1]); coil(pic, BURST - at0[1] + 200); }
        if (M.style === 'pound' && t >= at0[1] && once('gather')) vortex(pic, BURST - at0[1] + 250);
        if (M.style === 'shell' && t >= at0[1] && once('gather')) { gather(mouth(pose3(at0[2])), BURST - at0[1]); charged(pic, HOLD1 + 200 - at0[1]); }
        if (M.style === 'bellow' && t >= at0[1] && once('gather')) gather(mouth(pose3(at0[2])), BURST - at0[1]);
        if (M.style === 'venom' && t >= at0[1] && once('gather')) { gather(mouth(pose3(at0[2])), BURST - at0[1]); seep(pic, BURST - at0[1]); }
        if (M.style === 'pound' && t >= at0[3] && once('beat1')) beat(pic);
        if (M.style === 'pound' && t >= at0[5] && once('beat2')) beat(pic);
        if (M.style === 'hiss' && t >= at0[1] && once('gather')) { gather(mouth(pose3(at0[2])), BURST - at0[1]); runes(pic, HOLD1 + 300 - at0[1]); }
        var p = pose3(t), shake = 0;
        if (t >= BURST && t < HOLD1) shake = Math.sin(t / 16) * 1.6 * (1 - span(t, HOLD0, HOLD1) * 0.7);   // trembling
        var sw = 1 + (M.swell || 0) * (t < BURST ? span(t, BURST - 150, BURST) : 1 - span(t, HOLD1, TOTAL));   // thrown toward you
        beast.style.transform = 'translate(' + (-p[0] * pic.width + shake) + 'px,' + (p[1] * pic.height) + 'px) rotate(' + p[2] + 'deg) scale(' + sw + ')';   // clockwise: a left-facing head goes up
        if (t >= IMPACT && t < TOTAL + 200) {                  // the blast knocks you back, then you find your feet
          var push = t < HOLD1 ? ease(span(t, IMPACT, IMPACT + 140)) : 1 - span(t, HOLD1, TOTAL + 200);
          var back = ev.guard ? 0.016 : 0.04;                  // a Guard holds its ground better
          hero(-back * W * push + (t < HOLD1 ? Math.sin(t / 23) * 1.6 : 0), 0, ev.guard ? 0 : -3 * push);
        }
        if (ev.guard && t >= IMPACT - 320) { if (!block(t - IMPACT)) pose('idle'); }   // your Guard takes it
        if (bposes && bposes.roar) bpose(t >= BURST - 60 && t < HOLD1 ? 'roar' : home);
        else if (roarPic && roarPic.complete && roarPic.naturalWidth) {      // its own open-mouthed roar picture
          var open = t >= BURST - 60 && t < HOLD1;
          if (open !== opened) {
            opened = open; beast.src = open ? ROAR.art : still; measure(open ? roarPic : beastStill);
            if (BS) beastBox.classList.toggle('roaring', open);   // an animated beast: its picture over its frames, jaws open
          }
        }
        if (t >= BURST && once('burst')) {
          if (M.style === 'screech') screech(mouth(p), pic, ev.final);
          else if (M.style === 'hiss') hiss(mouth(p), pic, ev.final);
          else if (M.style === 'quake') quake(mouth(p), pic, ev.final);
          else if (M.style === 'storm') storm(mouth(p), pic, ev.final);
          else if (M.style === 'pound') pound(mouth(p), pic, ev.final);
          else if (M.style === 'venom') venom(mouth(p), pic, ev.final);
          else if (M.style === 'bellow') bellow(mouth(p), pic, ev.final);
          else if (M.style === 'shell') shell(mouth(p), pic, ev.final);
          else bigRoar(mouth(p), pic, ev.final);
          presence(pic, ev.final, still);
          if (scene.animate && SHAKE) scene.animate([{transform: 'none'}, {transform: 'translate(-2px,2px)'}, {transform: 'translate(2px,-1px)'}, {transform: 'none'}], {duration: 300});
        }
        if (t >= IMPACT && once('impact')) { impact(ev.final, M.style === 'quake'); struck(ev); }
      }, clear: function () {
        hero(0, 0); if (ev.guard) pose('idle');
        scene.querySelectorAll('.broar,.broarbig,.broarlines,.broarflash,.bmote,.bbeam,.bfeather,.bthroat,.brune,.bbreath,.bdrop,.bnova,.bquake,.bcoil,.bstreak,.bblast,.bsblast,.bwind,.bdeep,.bdome,.bshellglow,.bestream,.beburst,.beground,.bevignette,.besigil,.bavatar,.bmouth').forEach(function (n) { n.remove(); });
        if (opened) { beast.src = still; opened = false; }
        beastBox.classList.remove('roaring');
        beast.style.transform = ''; beast.style.transformOrigin = '';
        if (bposes) bpose(home);
        var n = scene.querySelector('.broar'); if (n) n.remove();
      }};
    }
    /* what the roar did to you, as the engine logged it (battle.ROAR): the damage, "Guarded" when your Guard
       halved it, and the debuffs it left (Shaken, Exposed, Stunned) */
    function struck(ev) {
      if (!ev || ev.why) return;
      if (ev.dmg) { drop('me'); pop(fighter, 'hurt' + heavy('me', ev.dmg), '−' + ev.dmg); }
      var words = (ev.final && !ev.skill ? ['Final Roar'] : []).concat(ev.guard ? ['Guarded'] : (ev.status || []).concat(ev.stun ? ['Stunned'] : []));
      words.forEach(function (w, i) { setTimeout(function () { pop(fighter, 'word', w); }, 380 + 300 * i); });   // after the damage number
      if (!ev.guard && scene.animate) fighter.animate([{transform: 'none'}, {transform: 'translate(-6px,0)'}, {transform: 'translate(4px,0)'}, {transform: 'none'}], {duration: 320});
    }
    function roaring(ev) {
      if (ROAR && ROAR.motion) return roaringMoved(ROAR.motion, ev);
      var done = false, hit = false;
      return {end: Math.max(ROAR_MS, 120 + TRAVEL + 900) + 150, render: function (t) {
        if (t < 0) return;
        var k = span(t, 0, 260), back = k < 1 ? Math.sin(Math.PI * k) : 0;     // it rears back a little as it roars
        animal(0.008 * W * back, -0.006 * W * back, 3 * back, 0);
        if (t >= 120 && !done) {
          done = true; roar();
          var bx = beast.getBoundingClientRect();
          blast(ROAR.head ? at(bx, ROAR.head[0], ROAR.head[1]) : at(bx, 0.15, 0.35), bx, ev.final ? 1.3 : 1); presence(bx, ev.final, beast.src);
        }
        if (t >= 120 + TRAVEL && !hit) { hit = true; impact(ev.final); struck(ev); }
      }, clear: function () { var n = scene.querySelector('.broar'); if (n) n.remove(); }};
    }

    /* the Mountain Tiger's Mountain-Splitting Pounce (battle.UNIQUE_SKILLS) plays as its great roar (SHOAIB, Nov 26:
       "just make it roar": the old leap across the arena wasn't smooth). Its own open-jawed roar, the big burst, the
       damage, "Guarded" or "Stunned" from the server like any other hit, then it is Roused. */
    function skillRoar(ev) {
      var r = roaring({dmg: ev.dmg, guard: ev.guard, stun: ev.stun, final: true, skill: true}), draw = r.render, roused = false;
      r.render = function (t) {
        draw(t);
        if (!roused && t >= r.end * 0.6) { roused = true; pop(beastBox, 'word roused', 'Roused!'); }
      };
      return r;
    }

    /* A technique with its own look (web/technique_fx.py, docs/web.md "Techniques"). The cultivator plays the shared
       movement (`fist`: SHOAIB's punch video, a jab then a lunging punch, looks.MOTION_SHEETS) and the technique's own
       pictures fly or burst from his fist, everything timed from the release, the frame the fist is furthest out.
       The grade sets how long the cast lasts (technique_fx.GRADE_MS) and how much spectacle surrounds it: Yellow and
       up glow, Mystic and up gather Qi rings, Earth and up raise a pillar of Qi and dim the scene, Heaven darkens the
       sky. The damage comes from the server like any other hit, and the HP bar drops when the blow lands. */
    var TIER = {Mortal: 0, Yellow: 1, Mystic: 2, Earth: 3, Heaven: 4};
    var FIST = {jab: [0.66, 0.28], lunge: [0.685, 0.287]};       // the fist at its furthest, as shares of the fighter's box
    /* A technique's extra pieces (web/technique_fx.py PARTS, scripts/make_tech_fx.py; docs/web.md "Techniques: the
       pieces"): stills moved here, so a Mortal to Earth technique plays as several pictures, not one sliding. They carry
       no CSS filter (each is painted with its own glow), so they cost little on a phone. `made`: the step's list, cleared
       with it; `w`: % of the scene wide; `frames`: its keyframes over `life` ms; opt: delay, under (a node it goes
       behind), origin, easing. */
    function part(made, src, p, w, life, frames, opt) {
      if (!src) return null;
      opt = opt || {};
      /* it always fits the scene: no wider than the room on either side of its spot (a fighter near a phone's edge),
         and with `tall` (its height / width) no taller than `maxH` of the scene (a short sideways phone) */
      if (!opt.free) w = Math.min(w, Math.max(2 * Math.min(p[0], 100 - p[0]) - 2, w * 0.45));
      if (opt.tall) w = Math.min(w, scene.clientHeight * (opt.maxH || 0.6) / opt.tall / W * 100);
      var n = document.createElement('img');
      n.className = 'tart tpart'; n.src = src; n.alt = '';
      n.style.left = p[0] + '%'; n.style.top = p[1] + '%'; n.style.width = w + '%';
      if (opt.origin) n.style.transformOrigin = opt.origin;
      if (opt.under && opt.under.parentNode === scene) { n.style.zIndex = 'auto'; scene.insertBefore(n, opt.under); } else scene.appendChild(n);
      made.push(n);
      setTimeout(function () { n.remove(); }, life + (opt.delay || 0) + 80);
      if (n.animate) n.animate(frames, {duration: life, delay: opt.delay || 0, easing: opt.easing || 'ease-out', fill: 'both'});
      else n.style.opacity = 1;
      return n;
    }
    function bloom(made, src, p, w, life, opt) {                      // a piece bursting open on a spot, then fading
      var a = opt && opt.anchor || 'translate(-50%,-50%)';
      return part(made, src, p, w, life || 700, [{transform: a + ' scale(0.35)', opacity: 0}, {transform: a + ' scale(1)', opacity: 1, offset: 0.2},
        {transform: a + ' scale(1.06)', opacity: 0.9, offset: 0.5}, {transform: a + ' scale(1.16)', opacity: 0}], opt);
    }
    function technique(ev) {
      var X = cast.fx, tier = TIER[cast.grade] || 0, did = {}, made = [], tc = cast.color, P = X.parts || {};
      var mn = msheet ? +msheet.dataset.frames : 0, mcols = msheet ? +msheet.dataset.cols : 1, mrows = msheet ? +msheet.dataset.rows : 1;
      var JAB = msheet ? +msheet.dataset.jab : 5, OUT = msheet ? +msheet.dataset.release : 12, BACK = msheet ? +msheet.dataset.back : 21;
      var dragons = X.play === 'dragons', end = Math.max(X.ms, msheet && !dragons ? +msheet.dataset.ms || 0 : 0);   // a sheet's own least time (looks `ms`)
      /* the punches: each lands at `at` (ms), a jab or the lunge. One lunge for most; Nine Dragons throws four,
         jab-lunge-jab-lunge, each loosing X.punches[i] dragons (1-2-3-3: nine). */
      /* Nine Dragons plays as a cutscene (`CUT`): bars close in and its name is shown for INTRO ms, the punches come
         slower (x1.4), the finale plays at 60 ms a frame. `S` maps the plain timing onto the cutscene's. */
      var CUT = !!(X.sheets && X.sheets.finale && !X.sheets.finale.pre), INTRO = 1100;   // (every Heaven attack: technique_fx `sheets`)
      function S(ms) { return CUT ? INTRO + ms * 1.4 : ms; }
      var punches = dragons ? [{at: S(360), kind: 'jab'}, {at: S(640), kind: 'lunge'}, {at: S(960), kind: 'jab'}, {at: S(1240), kind: 'lunge'}]
                            : [{at: CUT ? INTRO + 700 : Math.round(end * 0.45), kind: 'lunge'}];
      var R = punches[punches.length - 1].at;                       // the last release
      var DS = CUT ? X.sheets : null, FIN = R + (DS && DS.finale.lead || 0), FMS = 60;   // Nine Dragons' finale: starts as the ninth arrives, 60 ms a frame
      var skipBy = 0, self = null;                                    // the cutscene skipped: this much time jumped
      if (DS) end = FIN + DS.finale.frames * FMS + 150;
      var LAND = DS ? FIN + DS.finale.boom * FMS : dragons ? R + 420 : X.play === 'vortex' ? R + 180 : X.play === 'streak' ? R + 100 : X.play === 'beam' ? R + 160 : X.play === 'charge' ? R + 40 : X.play === 'palms' ? R + 160 : R;   // when the blow lands on the beast
      var WIND = msheet && msheet.dataset.windup ? +msheet.dataset.windup : 9;   // the frame drawn back, just before the release
      var PULL = Math.round((JAB + WIND) / 2);                       // on the way back from the jab
      var settle = [[Math.max(R + 280, end * 0.7), BACK - 1], [end * 0.95, (mn || 36) - 1]];   // held out, then back on guard
      var keys = dragons                                              // [ms, frame]: jab, lunge, (pulled back) jab, lunge
        ? [[0, 0]].concat([[300, JAB - 1], [360, JAB], [440, PULL], [560, WIND], [640, OUT], [740, OUT + 2], [820, BACK + 3], [821, 2],
           [900, JAB - 1], [960, JAB], [1040, PULL], [1160, WIND], [1240, OUT], [1400, OUT + 4]].map(function (k) { return [S(k[0]), k[1]]; })).concat(settle)
        : [[0, 0], [R - 90, WIND], [R, OUT], [R + 120, OUT + 2]].concat(settle);
      if (ev.hit) hold('enemy');

      function once(k) { if (did[k]) return false; did[k] = true; return true; }
      function show(f) {
        f = Math.max(0, Math.min(mn - 1, Math.round(f)));
        msheet.style.backgroundPosition = (f % mcols) / (mcols - 1) * 100 + '% ' + Math.floor(f / mcols) / (mrows - 1) * 100 + '%';
      }
      var BIG = Math.max(1, Math.min(2, br.width / (0.25 * W)));     // sized to the beast: phones draw it larger in the scene
      var KICK = [0.6, 0.62];                                         // the kicking foot, when this look has no kick frames
      var HAND = msheet && msheet.dataset.hand ? msheet.dataset.hand.split(',').map(Number) : X.motion === 'kick' ? KICK : FIST.lunge;
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
      function strip(src, S, cls, p, w, life, play, f0) {           // a moving picture: a strip of frames played once over `play` ms (from frame `f0`)
        var n = document.createElement('div');
        n.className = 'tart tstrip ' + cls;
        n.style.left = p[0] + '%'; n.style.top = p[1] + '%'; n.style.width = w * BIG + '%';
        n.style.backgroundImage = 'url(' + src + ')'; n.style.backgroundSize = S.cols * 100 + '% ' + S.rows * 100 + '%';
        scene.appendChild(n); made.push(n);
        var t0 = performance.now() - (f0 || 0) / S.frames * play;
        (function step() {
          if (!n.parentNode) return;
          var f = Math.min(S.frames - 1, Math.floor((performance.now() - t0) / play * S.frames));
          n.style.backgroundPosition = (f % S.cols) / (S.cols - 1) * 100 + '% ' + (S.rows > 1 ? Math.floor(f / S.cols) / (S.rows - 1) * 100 : 0) + '%';
          requestAnimationFrame(step);
        })();
        setTimeout(function () { n.remove(); }, life);
        return n;
      }
      function T(dx, dy, s, r, mirror) {
        return 'translate(-50%,-50%) translate(' + dx + 'px,' + dy + 'px) rotate(' + (r || 0) + 'deg) scale(' + (mirror ? -s : s) + ',' + s + ')';
      }
      function behind(n) { scene.insertBefore(n, fighter); }           // a dimmed scene or Heaven sky: over the arena, under everyone
      function px(a, b) { return [(b[0] - a[0]) / 100 * W, (b[1] - a[1]) / 100 * scene.clientHeight]; }
      function shake(k) {
        if (!scene.animate || !SHAKE) return;
        var a = (4 + 3 * k) * 0.7;
        scene.animate([{transform: 'none'}, {transform: 'translate(' + -a + 'px,' + a * 0.6 + 'px)'}, {transform: 'translate(' + a + 'px,' + -a * 0.5 + 'px)'},
          {transform: 'translate(' + -a * 0.6 + 'px,' + a * 0.3 + 'px)'}, {transform: 'none'}], {duration: 320 + 50 * k});
      }
      function lands() {                                              // the blow lands: number, knock, flash, shake by grade
        if (CUT) { if (ev.hit) drop('enemy'); written(ev.hit ? '−' + ev.dmg : 'Missed'); }   // over the explosion, where it can be read
        else if (ev.hit) { drop('enemy'); pop(beastBox, 'hit' + heavy('enemy', ev.dmg), '−' + ev.dmg); }
        else pop(beastBox, 'word', 'Missed');
        var b = at(br, 0.3, 0.45);
        burst('tspark', b[0], b[1], tc);
        if (P.hit) {                                                  // its own impact (technique_fx PARTS "hit")
          if (X.play === 'sweep') bloom(made, P.hit, at(br, 0.4, 0.97), 30 * BIG, 760, {anchor: 'translate(-50%,-92%)', origin: '50% 92%'});   // kicked up off the ground
          else bloom(made, P.hit, at(br, 0.32, 0.44), (tier >= 3 ? 30 : 24) * BIG, 720);
        }
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
            var rw = Math.min(46, scene.clientHeight * 0.62 / (618 / 900) / W * 100 / BIG);   // no taller than the scene allows (a sideways phone)
            var n = pic(X.art[0], 'trock', at(br, 0.4, 0.99), rw, 1700);
            n.animate([{transform: 'translate(-50%,-100%) translateY(55%) scale(0.9,0.25)', opacity: 0}, {transform: 'translate(-50%,-100%) translateY(-4%) scale(1.04,1.08)', opacity: 1, offset: 0.13},
              {transform: 'translate(-50%,-100%) scale(1)', opacity: 1, offset: 0.2}, {transform: 'translate(-50%,-100%) translateY(2%) scale(1.02)', opacity: 1, offset: 0.7},
              {transform: 'translate(-50%,-100%) translateY(10%) scale(1.04)', opacity: 0}], {duration: 1650, easing: 'ease-out', fill: 'forwards'});
            var g = at(br, 0.4, 0.97);
            part(made, P.ground, [g[0], g[1] + 1], 58 * BIG, 1900, [{transform: 'translate(-50%,-50%) scale(0.2,0.5)', opacity: 0},   // the earth cracks open under it
              {transform: 'translate(-50%,-50%) scale(1)', opacity: 1, offset: 0.1}, {transform: 'translate(-50%,-50%) scale(1.02)', opacity: 0.9, offset: 0.7},
              {transform: 'translate(-50%,-50%) scale(1.04)', opacity: 0}], {under: fighter});
            part(made, P.debris, [g[0] + 2, g[1] - 10], 40 * BIG, 1150, [{transform: 'translate(-50%,-10%) scale(0.3) rotate(-8deg)', opacity: 0},   // its rocks flung up and out
              {transform: 'translate(-50%,-55%) scale(0.95) rotate(0)', opacity: 1, offset: 0.25}, {transform: 'translate(-48%,-75%) scale(1.12) rotate(6deg)', opacity: 0.85, offset: 0.55},
              {transform: 'translate(-46%,-30%) scale(1.2) rotate(12deg)', opacity: 0}], {easing: 'cubic-bezier(.2,.7,.4,1)', tall: 453 / 800, maxH: 0.5});
            for (var i = 0; i < 12; i++) {
              var a = Math.PI * (1.08 + 0.84 * i / 11), dd = 60 + Math.random() * 150;
              fx('pdebris' + (i % 3 ? '' : ' hot'), g[0], g[1] - 2, 1000, {'--dx': Math.cos(a) * dd + 'px', '--dy': Math.sin(a) * dd + 'px',
                '--rot': (Math.random() * 540 - 270) + 'deg', '--sz': (4 + Math.random() * 6) + 'px'});
            }
            lands();
          }
        },
        dragons: function () {},                                     // Nine Dragons: see `loose` below
        beam: function (h) {                                         // Viper Fang / River-Splitting: a beam from the fingertip
          if (h >= 0 && once('beam')) {                              // tail pinned to the fingertip, head on the beast
            var from = fist('lunge'), to = at(br, 0.5, 0.42), d = px(from, to);   // finger to beast
            var len = Math.hypot(d[0], d[1]), ang = Math.atan2(d[1], d[0]) * 180 / Math.PI;
            var n = document.createElement('img');
            n.className = 'tart tglow tbeam' + (X.part ? ' twater' : ''); n.src = X.art[0]; n.alt = '';
            n.style.left = from[0] + '%'; n.style.top = from[1] + '%'; n.style.width = len / W * 100 + '%';
            n.style.setProperty('--tc', tc);
            scene.appendChild(n); made.push(n);
            setTimeout(function () { n.remove(); }, 1300);
            var B = function (sx, sy) { return 'translate(0,-50%) rotate(' + ang + 'deg) scale(' + sx + ',' + sy + ')'; };
            n.animate(X.part                                        // River: the beam shoots out, then the two walls of water open
              ? [{transform: B(0, 0.25), opacity: 1}, {transform: B(1, 0.3), opacity: 1, offset: 0.13},
                 {transform: B(1, 1.08), opacity: 1, offset: 0.35}, {transform: B(1.02, 1), opacity: 1, offset: 0.75}, {transform: B(1.04, 1.06), opacity: 0}]
              : [{transform: B(0, 1), opacity: 1}, {transform: B(1, 1), opacity: 1, offset: 0.14},       // Viper: the head strikes out
                 {transform: B(1.03, 1.05), opacity: 1, offset: 0.7}, {transform: B(1.05, 1.08), opacity: 0}],
              {duration: 1250, easing: 'ease-out', fill: 'forwards'});
            if (P.head) {                                            // Viper: its head flies along the beam and bites
              part(made, P.head, to, 22 * BIG, 520, [{transform: 'translate(-50%,-50%) translate(' + -d[0] + 'px,' + -d[1] + 'px) scale(0.5)', opacity: 0},
                {transform: 'translate(-50%,-50%) translate(' + -d[0] * 0.55 + 'px,' + -d[1] * 0.55 + 'px) scale(0.85)', opacity: 1, offset: 0.2},
                {transform: 'translate(-50%,-50%) scale(1.05)', opacity: 1, offset: 0.34}, {transform: 'translate(-50%,-50%) translateX(2%) scale(1.15)', opacity: 0}], {easing: 'ease-in'});
            }
            if (P.water) {                                           // River: the water parts above and below the beam
              var mid = [(from[0] + to[0]) / 2, (from[1] + to[1]) / 2], ww = len / W * 100 * 1.05;
              part(made, P.water, mid, ww, 1250, [{transform: 'translate(-50%,-50%) rotate(' + ang + 'deg) scale(0.6,0)', opacity: 0},
                {transform: 'translate(-50%,-50%) rotate(' + ang + 'deg) scale(1,0.25)', opacity: 1, offset: 0.14},
                {transform: 'translate(-50%,-50%) rotate(' + ang + 'deg) scale(1,1)', opacity: 1, offset: 0.4},
                {transform: 'translate(-50%,-50%) rotate(' + ang + 'deg) scale(1.03,1.15)', opacity: 0}], {free: true});
            }
          }
          if (h >= 160 && once('land')) lands();
        },
        sweep: function (h) {                                        // Crescent Sweep: a pale crescent swept across it
          if (h >= -60 && once('arc')) {
            var n = pic(X.art[0], 'tglow tarc', at(br, 0.36, 0.44), 30, 900);
            n.animate([{clipPath: 'inset(0 100% 0 0)', transform: T(-0.02 * W, 0, 0.92, -10), opacity: 1},
              {clipPath: 'inset(0 0 0 0)', transform: T(0, 0, 1, 0), opacity: 1, offset: 0.3},
              {clipPath: 'inset(0 0 0 0)', transform: T(0.01 * W, 0, 1.03, 4), opacity: 0.9, offset: 0.6},
              {clipPath: 'inset(0 0 0 0)', transform: T(0.02 * W, 0, 1.06, 6), opacity: 0}], {duration: 880, easing: 'ease-out', fill: 'forwards'});
          }
          if (h >= 40 && once('land')) lands();
        },
        streak: function (h) {                                       // Swift Swallow Kick: the swallow flies from the foot through it
          if (h >= -250 && once('bird')) {
            var from = fist('lunge'), to = at(br, 0.34, 0.42), d = px(to, from);
            var n = pic(X.art[0], 'tglow tbird', to, 40, 800);
            n.animate([{transform: T(d[0], d[1], 0.5, 0, X.mirror), opacity: 0}, {transform: T(d[0] * 0.5, d[1] * 0.5, 0.85, 0, X.mirror), opacity: 1, offset: 0.25},
              {transform: T(0, 0, 1, 0, X.mirror), opacity: 1, offset: 0.5}, {transform: T(0.14 * W, -0.01 * W, 1.05, 0, X.mirror), opacity: 0}],
              {duration: 700, easing: 'linear', fill: 'forwards'});
          }
          if (h >= 100 && once('land')) lands();
        },
        whirl: function (h) {                                        // Autumn Wind Kick: a whirl of autumn leaves spins round it
          if (h >= -80 && once('whirl')) {
            var n = pic(X.art[0], 'tglow tleaf', at(br, 0.36, 0.5), 38, 1300);
            n.animate([{transform: T(-0.03 * W, 0, 0.5, -20), opacity: 0}, {transform: T(0, 0, 1, 0), opacity: 1, offset: 0.2},
              {transform: T(0, -0.01 * W, 1.05, 12), opacity: 1, offset: 0.65}, {transform: T(0.02 * W, -0.03 * W, 1.12, 24), opacity: 0}],
              {duration: 1250, easing: 'ease-out', fill: 'forwards'});
          }
          if (h >= 40 && once('leaves')) {                            // the leaves it tore loose drift down across the beast
            var lv = at(br, 0.36, 0.38);
            part(made, P.leaves, lv, 40 * BIG, 1700, [{transform: 'translate(-50%,-50%) translate(-6%,-12%) scale(0.6) rotate(-10deg)', opacity: 0},
              {transform: 'translate(-50%,-50%) scale(1) rotate(0)', opacity: 1, offset: 0.2}, {transform: 'translate(-50%,-50%) translate(4%,10%) scale(1.06) rotate(8deg)', opacity: 0.9, offset: 0.65},
              {transform: 'translate(-50%,-50%) translate(8%,24%) scale(1.1) rotate(14deg)', opacity: 0}], {easing: 'linear'});
          }
          [0, 1, 2].forEach(function (k) {                           // its three hits
            if (h >= 40 + 140 * k && once('hit' + k)) {
              if (k === 0) lands(); else { var b = at(br, 0.26 + 0.08 * k, 0.32 + 0.1 * k); burst('tspark', b[0], b[1], tc); shake(1); }
            }
          });
        },
        meteor: function (h) {                                       // Meteor-Falling Kick: a blazing meteor falls onto it from the sky
          if (h >= -450 && once('meteor')) {
            var to = at(br, 0.36, 0.5), n = pic(X.art[0], 'tglow tfire', to, 26, 1200);
            n.animate([{transform: T(-0.3 * W, -0.42 * W, 0.7, 180), opacity: 0}, {transform: T(-0.22 * W, -0.31 * W, 0.8, 180), opacity: 1, offset: 0.1},
              {transform: T(0, 0, 1, 180), opacity: 1, offset: 0.38}, {transform: T(0.01 * W, 0.01 * W, 1.15, 180), opacity: 0}],
              {duration: 1180, easing: 'ease-in', fill: 'forwards'});
          }
          if (h >= 0 && once('land')) { fx('bflash', 50, 50, 450); lands(); }
        },
        prints: function (h) {                                       // Twin Palm Strike: one print for each of its two hits
          [0, 1].forEach(function (k) {
            if (h >= -260 + 140 * k && once('print' + k)) {
              var from = fist('lunge'), to = at(br, 0.3 + 0.04 * k, 0.36 + 0.1 * k), d = px(to, from);
              var n = pic(X.art[k], 'tglow tprint', to, 15, 900);
              n.animate([{transform: T(d[0], d[1], 0.35), opacity: 0}, {transform: T(d[0] * 0.4, d[1] * 0.4, 0.8), opacity: 1, offset: 0.25},
                {transform: T(0, 0, 1), opacity: 1, offset: 0.3}, {transform: T(0.01 * W, 0, 1.12), opacity: 0}],
                {duration: 860, easing: 'ease-in', fill: 'forwards'});
            }
            if (h >= 140 * k && once('hit' + k)) { if (k === 0) lands(); else { var b = at(br, 0.34, 0.46); burst('tspark', b[0], b[1], tc); bloom(made, P.hit, b, 20 * BIG, 640); shake(0); } }
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
        palms: function (h) {                                        // Thousand Shadow Palm: three waves of shadow palms from the push
          [0, 1, 2].forEach(function (k) {                           // each wave: a fan of palms flying to the beast, a teal burst where they strike
            var w0 = -200 + 140 * k;
            if (h >= w0 && once('wave' + k)) {
              var from = fist('lunge');
              [-1, 0, 1, 2].forEach(function (j, i) {
                if (LITE && i === 3) return;
                var to = at(br, 0.3 + 0.03 * k, 0.26 + 0.13 * (j + 1) + 0.04 * k), d = px(to, from), r = -10 * j + 8;
                part(made, P.hand, to, (13 - Math.abs(j) * 1.5) * BIG, 520, [{transform: 'translate(-50%,-50%) translate(' + d[0] + 'px,' + (d[1] - j * 8) + 'px) scale(0.35) rotate(' + r + 'deg)', opacity: 0},
                  {transform: 'translate(-50%,-50%) translate(' + d[0] * 0.5 + 'px,' + d[1] * 0.5 + 'px) scale(0.8) rotate(' + r * 0.5 + 'deg)', opacity: 0.95, offset: 0.25},
                  {transform: 'translate(-50%,-50%) scale(1)', opacity: 1, offset: 0.62}, {transform: 'translate(-50%,-50%) translateX(3%) scale(1.12)', opacity: 0}],
                  {delay: 30 * i, easing: 'ease-in'});
              });
            }
            if (h >= w0 + 360 && once('hit' + k)) {
              if (k === 0) lands();
              else { var b = at(br, 0.28 + 0.06 * k, 0.32 + 0.1 * k); burst('tspark', b[0], b[1], tc); bloom(made, P.hit, b, 22 * BIG, 620); shake(1); }
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
        fs('cast', 'dragon', 0, {exact: true});                     // the dragon's roar, from the video
        var from = fist(p.kind);
        for (var k = 0; k < n; k++) {
          var to = at(br, 0.28 + 0.06 * k, 0.24 + 0.2 * ((flown + k) % 3)), d = px(to, from);
          var dg = strip(X.art[1], DS.fly, 'tdragon', to, 24, 640 + 80 * k, 560);   // it flies writhing, head first
          dg.animate([{transform: T(d[0] - 0.04 * W, d[1], 0.4, -6), opacity: 0}, {transform: T(d[0] * 0.6, d[1] * 0.6 - 12, 0.75, 3), opacity: 1, offset: 0.3},
            {transform: T(-0.03 * W, 0, 1, 0), opacity: 1, offset: 0.8}, {transform: T(0.05 * W, 0, 1.1, 0), opacity: 0}],
            {duration: 560, delay: 80 * k, easing: 'ease-in', fill: 'both'});
          (function (q) { setTimeout(function () { burst('tspark', q[0], q[1], '#FFD978'); }, 460 + 80 * k); })(to);
        }
        flown += n;
      }

      /* The cutscene's dressing: black bars close in from top and bottom, the technique's name is written large across
         the scene, the camera closes on the cultivator; a Skip button jumps to the explosion (the damage still lands). */
      function written(text) {                                       // the cutscene's damage: large, above every effect
        var p = at(br, 0.42, 0.2), n = document.createElement('b');
        n.className = 'tbig'; n.textContent = text;
        n.style.left = Math.min(86, p[0]) + '%'; n.style.top = Math.max(24, p[1]) + '%';
        scene.appendChild(n); made.push(n);
        fs(ev.hit ? 'hit' : 'miss', ev.hit ? 'big' : '');
        setTimeout(function () { n.remove(); }, 2000);
      }
      function cutscene() {
        var el = function (tag, cls, text) { var n = document.createElement(tag); n.className = cls; if (text) n.textContent = text; scene.appendChild(n); made.push(n); return n; };
        main.classList.add('cutscene');                             // the small name plate and the turn's lines wait for the blow
        var card = el('div', 'tcard');
        card.style.setProperty('--life', INTRO + 500 + 'ms');
        setTimeout(function () { card.remove(); }, INTRO + 700);
        var a = document.createElement('small'); a.textContent = (cast.grade || 'Heaven') + ' Technique';
        var b = document.createElement('b'); b.textContent = cast.name || '';
        card.appendChild(a); card.appendChild(b);
        var skip = el('button', 'tskip', 'Skip ▸▸'); skip.type = 'button';
        skip.addEventListener('click', function (e) {
          e.stopPropagation();
          if (skipBy || !self) return;
          var now = self.now || 0, to = LAND - 2 * FMS;
          if (now >= to) return;
          skipBy = to - now; self.end -= skipBy;                    // the turn ends that much sooner
          did.rise = false;
          made.forEach(function (n) { if (/tfinale|tdragon|tcard/.test(n.className)) n.remove(); });
          skip.remove();
        });
      }
      return (self = {end: end, render: function (t) {
        if (t < 0) return;
        self.now = t; t += skipBy;
        if (CUT && once('cut')) cutscene();
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
        } else {                                                      // no frames for this look: its own three poses
          var p = punches.filter(function (q) { return t >= q.at - 200 && t < q.at + 180; })[0];
          pose(!p ? 'idle' : t < p.at ? 'windup' : 'strike');
        }
        x = 0.025 * W * Math.sin(Math.PI * span(t, punches[0].at - 260, R + 380));        // a step in behind the punches
        var y = 0;
        if (X.motion === 'kick' && !msheet) {                        // a kick without frames: a hop into it (Meteor: a leap)
          var big = X.play === 'meteor', jump = span(t, R - (big ? 420 : 260), R + (big ? 140 : 160));
          y = -(big ? 0.09 : 0.035) * W * Math.sin(Math.PI * jump);
          x += (big ? 0.05 : 0.02) * W * Math.sin(Math.PI * jump);
        }
        hero(x, y);
        poses.style.filter = tier >= 1 && t < R + 200 ? 'drop-shadow(0 0 ' + (4 + 4 * tier) + 'px ' + tc + ')' : '';
        var k2 = ev.hit ? knocked(t - LAND, (0.02 + 0.006 * tier) * W) : [0, 0];
        animal(BS ? 0 : k2[0], 0, BS ? 0 : k2[0] / (0.03 * W) * 4, k2[1]);
        if (dragons) punches.forEach(function (_, i) { loose(i, t); });
        if (CUT) {
          if (t >= FIN && once('rise')) {                             // all nine burst from the ground under the beast and coil up
            var life = DS.finale.frames * FMS, g = at(br, 0.42, 0.97), A = DS.finale.anchor || [0.5, 0.99], snd = DS.finale.sound;
            var fw = Math.min(105, g[1] / 100 * scene.clientHeight / A[1] * 16 / 9 / W * 100);   // as tall as the scene above the ground allows
            var f0 = skipBy ? DS.finale.boom - 2 : 0;                 // skipped: straight to the explosion
            var n = strip(X.art[0], DS.finale, 'tfinale', [g[0], g[1]], fw / BIG, life + 60, life, f0);
            n.style.transform = 'translate(' + -A[0] * 100 + '%,' + -A[1] * 100 + '%)';
            n.animate([{opacity: 1}, {opacity: 1, offset: 0.88}, {opacity: 0}], {duration: life, fill: 'forwards'});
            if (!skipBy && !fs('gather', snd, 0, {exact: true})) fs('gather');
          }
          if (t >= LAND && once('finale')) {                          // they explode in golden light: the blow lands
            main.classList.remove('cutscene');
            made.forEach(function (n) { if (/tskip/.test(n.className)) n.remove(); });
            fx('bflash', 50, 50, 450);
            if (!fs('boom', DS.finale.sound, 0, {exact: true})) fs('boom');
            lands();
          }
        } else if (!dragons) PLAY[X.play](t - R);
      }, release: R, clear: function () { main.classList.remove('cutscene'); made.forEach(function (n) { n.remove(); }); }});
    }

    /* A Body defense technique that braces (web/technique_fx.py "brace"), played inside the beast's attack: the fighter
       crosses the arms up and sinks into a wide stance (looks.MOTION_SHEETS "brace", their own frames) while the beast
       winds up; the technique's own effect forms around them as they settle, and the beast's blow lands on it. Then
       what really happened, read from the server's log: Blocked, a Break held (part of it still hurts), HP recovered,
       a counter. `hitEv`: the beast's blow, when part of it got through. The effects are placed around the braced
       figure (`body`), so they fit either look. */
    /* A sheet's `pace` (looks.py): the brace and the deflection, and the beast's blow they answer, play this much
       slower than their recipes say, so they can be followed. */
    function paced(o, k) { var out = {}; Object.keys(o).forEach(function (n) { out[n] = /knock/.test(n) ? o[n] : o[n] * k; }); return out; }
    var PACE = msheet && +msheet.dataset.pace || 1;
    /* A Heaven defence plays long (SHOAIB's rule for the grade: long, its name written large, a moving effect with its
       own sound, a Skip; no black bars). `inner` is the technique's ordinary exchange (braced, deflected, sidestepped):
       it plays whole, after `pre` ms in which the effect forms; the effect's `boom` frame falls on the beast's blow
       (`inner.hit`), and the rest of it plays out at 50 ms a frame. */
    function heavenly(inner) {
      var X = cast.fx, S = X.sheets && X.sheets.finale;
      if (!S || !S.pre) return inner;
      var PRE = S.pre, HIT = PRE + (inner.hit || 0), TAIL = (S.frames - S.boom) * 50;
      var did = {}, made = [], skipBy = 0, node = null, self;
      var num = function (k, d) { return msheet && msheet.dataset[k] ? msheet.dataset[k].split(',').map(Number) : d; };
      var Bd = num('body', [0.5, 0.15, 0.94, 0.24]), HAND = num('hand', [0.62, 0.4]);
      function el(tag, cls, text) { var n = document.createElement(tag); n.className = cls; if (text) n.textContent = text; scene.appendChild(n); made.push(n); return n; }
      function start() {
        main.classList.add('cutscene');
        var card = el('div', 'tcard'); card.style.setProperty('--life', Math.min(PRE, 1600) + 'ms');
        var a = document.createElement('small'); a.textContent = (cast.grade || 'Heaven') + ' Technique';
        var b = document.createElement('b'); b.textContent = cast.name || '';
        card.appendChild(a); card.appendChild(b);
        var p = S.on === 'hand' ? at(fr, HAND[0], HAND[1]) : at(fr, Bd[0], S.on === 'feet' ? Bd[2] : (Bd[1] + Bd[2]) / 2);
        var n = node = document.createElement('div');
        n.className = 'tart tstrip tfinale theld';
        n.style.left = p[0] + '%'; n.style.top = p[1] + '%';
        n.style.width = fr.height * (Bd[2] - Bd[1]) * S.tall * 16 / 9 / W * 100 + '%';
        n.style.transform = 'translate(' + -S.anchor[0] * 100 + '%,' + -S.anchor[1] * 100 + '%)';
        n.style.backgroundImage = 'url(' + X.art[0] + ')'; n.style.backgroundSize = S.cols * 100 + '% ' + S.rows * 100 + '%';
        if (S.behind) { n.style.zIndex = 'auto'; scene.insertBefore(n, fighter); } else scene.appendChild(n);
        made.push(n);
        setTimeout(function () { made.forEach(function (m) { m.remove(); }); main.classList.remove('cutscene'); }, self.end + 1500);   // never left behind
        n.style.opacity = 1; n.animate([{opacity: 0}, {opacity: 1}], {duration: 350});
        fs('gather', S.sound, 0, {exact: true});
        var skip = el('button', 'tskip', 'Skip ▸▸'); skip.type = 'button';
        skip.addEventListener('click', function (e) {
          e.stopPropagation();
          var now = self.now || 0, to = HIT - 300;
          if (skipBy || now >= PRE) return;                          // only the forming is skipped: the exchange plays
          skipBy = Math.max(0, Math.min(PRE, to) - now); self.end -= skipBy;
          card.remove(); skip.remove();
        });
      }
      function show(t) {                                             // the effect's frame: forming up to the blow, then playing out
        var f = t < HIT ? S.boom * t / HIT : S.boom + (t - HIT) / 50;
        f = Math.max(0, Math.min(S.frames - 1, Math.floor(f)));
        node.style.backgroundPosition = (f % S.cols) / (S.cols - 1) * 100 + '% ' + Math.floor(f / S.cols) / (S.rows - 1) * 100 + '%';
        node.style.opacity = 1;
        if (t > HIT + TAIL - 300) node.style.opacity = Math.max(0, (HIT + TAIL - t) / 300);
        if (t >= HIT + TAIL - 20) node.remove();                    // played out
      }
      return (self = {end: Math.max(inner.end + PRE, HIT + TAIL), pre: PRE, render: function (t) {
        if (t < 0) return;
        self.now = t; t += skipBy;
        if (!did.start) { did.start = 1; start(); }
        show(t);
        if (t >= HIT && !did.hit) {
          did.hit = 1; main.classList.remove('cutscene');
          made.forEach(function (n) { if (/tskip/.test(n.className)) n.remove(); });
          fs('boom', S.sound, 0, {exact: true});
        }
        if (S.late && t >= HIT + S.late[0] && !did.late) { did.late = 1; fs(S.late[1], S.sound, 0, {exact: true}); }
        if (t >= PRE) inner.render(Math.min(t - PRE, inner.end));
      }, clear: function () { main.classList.remove('cutscene'); made.forEach(function (n) { n.remove(); }); if (inner.clear) inner.clear(); }});
    }
    function later(cues, ms) { return ms ? cues.map(function (c) { var d = c.slice(); d[0] += ms; return d; }) : cues; }   // a step's sounds, after its `pre`
    function braced(ev, hitEv) {
      var X = cast.fx, tier = TIER[cast.grade] || 0, did = {}, made = [], tc = cast.color, R = paced(RECIPES.beast, PACE), P = X.parts || {};
      var attacked = !!(hitEv || ev.blocked || ev.hold);
      var HIT = attacked ? R.hit : 900 * PACE, END = attacked ? Math.max(R.end + (ev.counter ? 220 : 0), R.hit + 1000 * PACE) : 1700 * PACE;
      var mn = msheet ? +msheet.dataset.frames : 0, mcols = msheet ? +msheet.dataset.cols : 1, mrows = msheet ? +msheet.dataset.rows : 1;
      var SET = msheet ? +msheet.dataset.release : 16;
      var Bd = msheet && msheet.dataset.body ? msheet.dataset.body.split(',').map(Number) : [0.46, 0.12, 0.92, 0.24];
      var HAND = msheet && msheet.dataset.hand ? msheet.dataset.hand.split(',').map(Number) : [0.5, 0.32];
      var bodyW = fr.width * Bd[3] / W * 100, bodyH = fr.height * (Bd[2] - Bd[1]);   // % of the scene, and px
      var feet = at(fr, Bd[0], Bd[2]), mid = at(fr, Bd[0], (Bd[1] + Bd[2]) / 2);
      if (hitEv && hitEv.dmg || ev.heal) hold('me');
      if (ev.counter) hold('enemy');
      function once(k) { if (did[k]) return false; did[k] = true; return true; }
      function show(f) {
        f = Math.max(0, Math.min(mn - 1, Math.round(f)));
        msheet.style.backgroundPosition = (f % mcols) / (mcols - 1) * 100 + '% ' + Math.floor(f / mcols) / (mrows - 1) * 100 + '%';
        return msheet.style.backgroundPosition;
      }
      function art(cls, p, w, behind) {                             // the technique's picture at p, w% of the scene wide
        var n = document.createElement('img');
        n.className = 'tart tbrace ' + cls; n.src = X.art[0]; n.alt = '';
        if (X.sheets) n.style.display = 'none';                     // a Heaven technique: its moving effect plays instead (`heavenly`)
        n.style.left = p[0] + '%'; n.style.top = p[1] + '%'; n.style.width = w + '%'; n.style.setProperty('--tc', tc);
        if (behind) scene.insertBefore(n, fighter); else scene.appendChild(n);
        made.push(n);
        return n;
      }
      var wide = function (aspect, share) { return bodyH * share / aspect / W * 100; };   // wide enough to stand `share` of the body tall
      var FX = null, sheen = null, sheenLit = null;
      var FORM = {                                                  // the effect forms as the stance settles, and stays to the end
        dust: function () { FX = art('', feet, Math.min(bodyW * 3.4, Math.max(2 * feet[0] - 2, bodyW * 1.6)), true);   // inside the scene, near a phone's edge too
          part(made, P.hit, [feet[0], feet[1] + 1], bodyW * 2.6, 900, [{transform: 'translate(-50%,-70%) scale(0.3,0.5)', opacity: 0},   // the stomp throws up a ring of dust
            {transform: 'translate(-50%,-70%) scale(1)', opacity: 0.95, offset: 0.25}, {transform: 'translate(-50%,-74%) scale(1.15)', opacity: 0}], {under: fighter});
          FX.animate([{transform: 'translate(-50%,-60%) scale(0.25)', opacity: 0}, {transform: 'translate(-50%,-60%) scale(1)', opacity: 1, offset: 0.3},
            {transform: 'translate(-50%,-62%) scale(1.15)', opacity: 0.8, offset: 0.8}, {transform: 'translate(-50%,-64%) scale(1.25)', opacity: 0}], {duration: END - FORM_AT, fill: 'forwards'}); },
        mist: function () { FX = art('tsoft', mid, wide(472 / 330, 1.15));
          var top = at(fr, Bd[0], Bd[1]);                           // Calm Breath: a spiral of breath rising off the head
          part(made, P.breath, [top[0], top[1] + 4], wide(371 / 480, 0.5), END - FORM_AT, [{transform: 'translate(-50%,-30%) scale(0.4) rotate(0)', opacity: 0},
            {transform: 'translate(-50%,-55%) scale(0.9) rotate(-90deg)', opacity: 0.8, offset: 0.3}, {transform: 'translate(-50%,-85%) scale(1.05) rotate(-220deg)', opacity: 0.55, offset: 0.75},
            {transform: 'translate(-50%,-110%) scale(1.15) rotate(-300deg)', opacity: 0}], {easing: 'linear'});
          FX.animate([{transform: 'translate(-50%,-40%) rotate(-6deg)', opacity: 0}, {transform: 'translate(-50%,-50%) rotate(0)', opacity: 0.85, offset: 0.3},
            {transform: 'translate(-50%,-56%) rotate(4deg)', opacity: 0.75, offset: 0.8}, {transform: 'translate(-50%,-62%) rotate(6deg)', opacity: 0}], {duration: END - FORM_AT, fill: 'forwards'}); },
        sheen: function () {                                        // the weave, laid over the fighter's own frame
          if (!msheet) return;
          sheen = msheet.cloneNode(false); sheen.className = 'sheetfx tsheen';
          sheen.style.backgroundImage = 'url(' + X.art[0] + ')';
          sheen.style.webkitMaskImage = sheen.style.maskImage = msheet.style.backgroundImage;
          sheen.style.webkitMaskSize = sheen.style.maskSize = msheet.style.backgroundSize;
          msheet.parentNode.insertBefore(sheen, msheet.nextSibling); made.push(sheen);
          var lit = sheen.cloneNode(false); lit.className = 'sheetfx tsheen tlit'; lit.style.backgroundImage = 'none';   // a steel rim of light on the body
          msheet.parentNode.insertBefore(lit, sheen.nextSibling); made.push(lit); sheenLit = lit;
          lit.animate([{opacity: 0}, {opacity: 0.55, offset: 0.2}, {opacity: 0.4, offset: 0.85}, {opacity: 0}], {duration: END - FORM_AT, fill: 'forwards'});
          part(made, P.figure, mid, wide(442 / 600, 1.15), END - FORM_AT, [{transform: 'translate(-50%,-50%) scale(1.25)', opacity: 0},   // a steel echo of a fighter settles behind
            {transform: 'translate(-50%,-50%) scale(1.05)', opacity: 0.55, offset: 0.25}, {transform: 'translate(-50%,-50%) scale(1.05)', opacity: 0.4, offset: 0.85},
            {transform: 'translate(-50%,-50%) scale(1.1)', opacity: 0}], {under: fighter});
          sheen.animate([{opacity: 0}, {opacity: 1, offset: 0.2}, {opacity: 0.85, offset: 0.85}, {opacity: 0}], {duration: END - FORM_AT, fill: 'forwards'}); },
        roots: function () {
          if (P.roots) {                                            // the jade mountain rises behind, its roots spread at the feet
            FX = art('', [feet[0], feet[1] + 1], wide(537 / 700, 1.55), true);
            FX.animate([{transform: 'translate(-50%,-100%) scaleY(0.05)', opacity: 0}, {transform: 'translate(-50%,-100%) scaleY(1.04)', opacity: 0.85, offset: 0.25},
              {transform: 'translate(-50%,-100%) scaleY(1)', opacity: 0.8, offset: 0.85}, {transform: 'translate(-50%,-100%) scaleY(1)', opacity: 0}], {duration: END - FORM_AT, fill: 'forwards'});
            part(made, P.roots, [feet[0], feet[1] + 1.5], bodyW * 3.2, END - FORM_AT, [{transform: 'translate(-50%,-50%) scale(0.1,0.6)', opacity: 0},
              {transform: 'translate(-50%,-50%) scale(1)', opacity: 1, offset: 0.2}, {transform: 'translate(-50%,-50%) scale(1.02)', opacity: 1, offset: 0.85},
              {transform: 'translate(-50%,-50%) scale(1.02)', opacity: 0}], {under: fighter});
            return;
          }
          FX = art('', [feet[0], feet[1] + 2], wide(534 / 758, 1.35), true);
          FX.animate([{transform: 'translate(-50%,-100%) scaleY(0.05)', opacity: 0}, {transform: 'translate(-50%,-100%) scaleY(1)', opacity: 1, offset: 0.25},
            {transform: 'translate(-50%,-100%) scaleY(1)', opacity: 1, offset: 0.85}, {transform: 'translate(-50%,-100%) scaleY(1)', opacity: 0}], {duration: END - FORM_AT, fill: 'forwards'}); },
        bell: function () { FX = art('tscreen', [feet[0], feet[1] + 1], wide(601 / 760, 1.35));
          part(made, P.ring, [feet[0], feet[1]], bodyW * 2.4, END - FORM_AT, [{transform: 'translate(-50%,-50%) scale(0.2)', opacity: 0},   // where it lands, a ring of runes
            {transform: 'translate(-50%,-50%) scale(0.2)', opacity: 0, offset: 0.17}, {transform: 'translate(-50%,-50%) scale(1)', opacity: 1, offset: 0.3},
            {transform: 'translate(-50%,-50%) scale(1.05)', opacity: 0.7, offset: 0.85}, {transform: 'translate(-50%,-50%) scale(1.1)', opacity: 0}], {under: fighter});
          FX.animate([{transform: 'translate(-50%,-160%)', opacity: 0}, {transform: 'translate(-50%,-100%)', opacity: 1, offset: 0.2},
            {transform: 'translate(-50%,-100%)', opacity: 0.95, offset: 0.85}, {transform: 'translate(-50%,-100%)', opacity: 0}], {duration: END - FORM_AT, easing: 'ease-in', fill: 'forwards'}); },
        shell: function () { FX = art('tdome', [feet[0], feet[1] + 2], wide(457 / 800, 1.0));
          FX.animate([{transform: 'translate(-50%,-100%) scale(0.2)', opacity: 0}, {transform: 'translate(-50%,-100%) scale(1)', opacity: 0.8, offset: 0.25},
            {transform: 'translate(-50%,-100%) scale(1)', opacity: 0.75, offset: 0.85}, {transform: 'translate(-50%,-100%) scale(1.04)', opacity: 0}], {duration: END - FORM_AT, fill: 'forwards'}); },
        lotus: function () { FX = art('', [feet[0], feet[1] + 3], bodyW * 2.6, true);
          FX.animate([{transform: 'translate(-50%,-80%) scale(0.15)', opacity: 0}, {transform: 'translate(-50%,-80%) scale(1)', opacity: 1, offset: 0.3},
            {transform: 'translate(-50%,-84%) scale(1.04)', opacity: 1, offset: 0.85}, {transform: 'translate(-50%,-88%) scale(1.08)', opacity: 0}], {duration: END - FORM_AT, fill: 'forwards'}); },
        parry: function () {}
      };
      var FORM_AT = Math.max(200 * PACE, HIT - 420 * PACE);
      function struck() {                                           // the beast's blow meets the brace
        var h = at(fr, HAND[0], HAND[1]);
        burst('tspark', h[0], h[1], X.play === 'parry' ? '#FFE6A0' : tc);
        if (X.play === 'parry') { burst('tspark', h[0] + 2, h[1] - 3, '#FFE6A0'); fx('tring', h[0], h[1], 500); }
        if (P.hit && X.play !== 'dust') bloom(made, P.hit, [h[0] + 2, h[1]], bodyW * (X.play === 'bell' ? 2 : 1.4), 640);   // its own impact where the blow meets it
        if (FX) FX.animate([{filter: 'brightness(1)'}, {filter: 'brightness(1.8)'}, {filter: 'brightness(1)'}], {duration: 320});
        if (FX && (X.play === 'bell' || X.play === 'roots' || X.play === 'shell'))
          FX.animate([{rotate: '0deg'}, {rotate: '-3deg'}, {rotate: '2.5deg'}, {rotate: '-1.5deg'}, {rotate: '0deg'}], {duration: 520, composite: 'add'});
        if (scene.animate) scene.animate([{transform: 'none'}, {transform: 'translate(-5px,3px)'}, {transform: 'translate(4px,-2px)'}, {transform: 'none'}], {duration: 300});
        if (hitEv && hitEv.dmg) { drop('me'); pop(fighter, 'hurt' + heavy('me', hitEv.dmg), '−' + hitEv.dmg); }
        pop(fighter, 'word', ev.hold ? (cast.effect === 'unbreakable' ? 'Unbreakable!' : 'Held ' + ev.hold + '%') : 'Blocked');
      }
      return {end: END, hit: HIT, render: function (t) {
        if (t < 0) return;
        if (once('start')) {                                        // the grade's spectacle, as for every technique
          if (tier >= 2) { fx('tqring', feet[0], feet[1], 760, {'--tc': tc}); fx('tqring q2', feet[0], feet[1], 900, {'--tc': tc}); }
          if (tier >= 3) { scene.insertBefore(fx('tdim', 50, 50, END, {'--life': END + 'ms'}), fighter); fx('tpillar', feet[0], feet[1], Math.round(END * 0.6), {'--tc': tc}); }
          if (tier >= 4) scene.insertBefore(fx('theaven', 50, 50, END, {'--life': END + 'ms'}), fighter);
        }
        if (attacked) {                                             // the beast, as in its own attack
          var x = 0, y = 0, rot = 0;
          if (t < R.charge) { var q = ease(span(t, 0, R.charge)); x = 0.015 * W * q; rot = 4 * q; }
          else if (t < R.back) { var c = span(t, R.charge, R.hit); x = 0.015 * W - (reachBeast + 0.015 * W) * c * c; rot = -6 * c; }
          else if (t < R.end) { var r = inout(span(t, R.back, R.end)); x = -reachBeast * (1 - r); y = -0.024 * W * Math.sin(Math.PI * r); }
          bpose(t < R.charge ? 'crouch' : t < R.back ? 'leap' : 'idle');
          var ck = ev.counter ? knocked(t - HIT - 130, 0.03 * W) : [0, 0];
          animal(x + ck[0], y, rot, ck[1]);
        }
        if (msheet) {                                               // into the stance by FORM_AT, then held
          var f = t < FORM_AT ? 4 + (SET - 4) * span(t, 0, FORM_AT) : SET + (mn - 1 - SET) * span(t, FORM_AT, END);
          if (t >= END - 60) pose('idle'); else { pose('motion'); var bp = show(f); if (sheen) sheen.style.webkitMaskPosition = sheen.style.maskPosition = bp; if (sheenLit) sheenLit.style.webkitMaskPosition = sheenLit.style.maskPosition = bp; }
        } else pose(t < END - 60 ? 'windup' : 'idle');
        var kb = hitEv && hitEv.dmg ? knocked(t - HIT, 0.012 * W) : [0, 0];
        hero(-kb[0], 0);
        poses.style.filter = tier >= 1 && t < END - 200 ? 'drop-shadow(0 0 ' + (4 + 3 * tier) + 'px ' + tc + ')' : '';
        if (t >= FORM_AT && once('form')) FORM[X.play]();
        if (attacked && t >= HIT && once('hit')) struck();
        if (ev.heal && t >= HIT + 260 && once('heal')) {
          drop('me'); pop(fighter, 'word heal', '+' + ev.heal); fx('tqring', feet[0], feet[1], 700, {'--tc': '#7CF0BE'});
          part(made, P.motes, [mid[0], feet[1]], wide(480 / 222, 0.9), 1500, [{transform: 'translate(-50%,-60%) scale(0.8)', opacity: 0},   // Turtle Shell: healing light rises
            {transform: 'translate(-50%,-85%) scale(1)', opacity: 1, offset: 0.3}, {transform: 'translate(-50%,-115%) scale(1.05)', opacity: 0}], {easing: 'linear'});
        }
        if (ev.counter && t >= HIT + 130 && once('counter')) {
          var h2 = at(fr, HAND[0], HAND[1]); fx('tpierce', h2[0], h2[1], 600, {'--tc': X.play === 'parry' ? '#FFE6A0' : tc});
          drop('enemy'); pop(beastBox, 'hit' + heavy('enemy', ev.counter), '−' + ev.counter);
        }
        if (!attacked && t >= HIT && once('steady')) pop(fighter, 'word', 'Steady');
      }, clear: function () { made.forEach(function (n) { n.remove(); }); }};
    }

    /* A deflection technique (web/technique_fx.py MOVES_FX, "deflect"), played by either cultivator with their own frames; told
       here as she plays it (he reaches back and sweeps a Qi arc round instead of her sleeve). Inside the
       beast's attack like a brace, but she never stands to take the blow: on guard, palm raised, while the beast
       winds up; she turns into it as it comes (`jab`), meets it with her hand at the moment it lands (`release`, the
       hit), carries it round and aside with a swirl of her sleeve (furthest behind her at `sweep`) and settles back
       on guard (`back` on), then idle. The beast is turned aside, not stopped: it slides off past her and drops, then
       goes home. The technique's own picture follows the contact and the sleeve (`hand`, `tip` in
       looks.MOTION_SHEETS). Then what really happened, read from the server's log: Deflected, a Break held (part of
       it still hurts), HP recovered, a counter. The beast's lunge is slower than its own attack (RECIPES.beast) so
       there is time to read it: DEFLECT below. */
    var DEFLECT = {charge: 380, hit: 600, glance: 780, home: 1180, turn: 320, sweep: 430, back: 560};
    function deflected(ev, hitEv) {
      var X = cast.fx, tier = TIER[cast.grade] || 0, did = {}, made = [], tc = cast.color, D = paced(DEFLECT, PACE), P = X.parts || {};
      var attacked = !!(hitEv || ev.blocked || ev.hold);
      var HIT = D.hit, END = Math.max(HIT + 1150 * PACE + (ev.counter ? 200 : 0), attacked ? D.home + 300 : 0);
      var mn = msheet ? +msheet.dataset.frames : 0, mcols = msheet ? +msheet.dataset.cols : 1, mrows = msheet ? +msheet.dataset.rows : 1;
      var JAB = msheet ? +msheet.dataset.jab : 6, REL = msheet ? +msheet.dataset.release : 12;
      var SWEEP = msheet && msheet.dataset.sweep ? +msheet.dataset.sweep : 23, BACK = msheet ? +msheet.dataset.back : 26;
      var num = function (k, d) { return msheet && msheet.dataset[k] ? msheet.dataset[k].split(',').map(Number) : d; };
      var Bd = num('body', [0.52, 0.2, 0.94, 0.23]), HAND = num('hand', [0.66, 0.33]), TIP = num('tip', [0.33, 0.71]);
      var bodyW = fr.width * Bd[3] / W * 100, bodyH = fr.height * (Bd[2] - Bd[1]);
      var feet = at(fr, Bd[0], Bd[2]), mid = at(fr, Bd[0], (Bd[1] + Bd[2]) / 2);
      var C = at(fr, HAND[0], HAND[1]), S = at(fr, TIP[0], TIP[1]);            // where she meets the blow; her sleeve's tip
      var sr = scene.getBoundingClientRect();
      var toS = [(S[0] - C[0]) / 100 * sr.width, (S[1] - C[1]) / 100 * sr.height];   // the way the blow is carried, px
      var KEYS = [[0, 0], [HIT - D.turn, JAB], [HIT, REL], [HIT + D.sweep, SWEEP], [HIT + D.back, BACK], [END - 140, mn - 1]];
      if (hitEv && hitEv.dmg || ev.heal) hold('me');
      if (ev.counter) hold('enemy');
      function once(k) { if (did[k]) return false; did[k] = true; return true; }
      function frame(t) {                                           // her frame at t: eased between the keys
        for (var i = 1; i < KEYS.length; i++) if (t < KEYS[i][0])
          return KEYS[i - 1][1] + (KEYS[i][1] - KEYS[i - 1][1]) * inout(span(t, KEYS[i - 1][0], KEYS[i][0]));
        return mn - 1;
      }
      function show(f) {
        f = Math.max(0, Math.min(mn - 1, Math.round(f)));
        msheet.style.backgroundPosition = (f % mcols) / (mcols - 1) * 100 + '% ' + Math.floor(f / mcols) / (mrows - 1) * 100 + '%';
      }
      function art(cls, p, w, behind) {                             // the technique's picture at p, w% of the scene wide
        var n = document.createElement('img');
        n.className = 'tart tbrace ' + cls; n.src = X.art[0]; n.alt = '';
        if (X.sheets) n.style.display = 'none';                     // a Heaven technique: its moving effect plays instead (`heavenly`)
        n.style.left = p[0] + '%'; n.style.top = p[1] + '%'; n.style.width = w + '%'; n.style.setProperty('--tc', tc);
        if (behind) scene.insertBefore(n, fighter); else scene.appendChild(n);
        made.push(n);
        return n;
      }
      var wide = function (aspect, share) { return bodyH * share / aspect / W * 100; };   // aspect: height / width, as `braced`
      var mv = function (q, extra) { return 'translate(calc(-50% + ' + toS[0] * q + 'px), calc(-50% + ' + toS[1] * q + 'px)) ' + (extra || ''); };
      var toward = [C[0] + 3.5, C[1] - 1];                          // just in front of her palm, toward the beast
      var FX = null;
      var FORM = {                                                  // [when it forms, how it plays to the end]
        // Parrying Arm: a streak of light runs along her arm as she meets the blow and is carried down with it
        glance: [HIT - 90, function (life) { FX = art('tglance', C, bodyW * 2.3);
          FX.style.transformOrigin = '88% 22%';
          FX.animate([{transform: 'translate(-88%,-22%) scale(0.5) rotate(-8deg)', opacity: 0},
            {transform: 'translate(-88%,-22%) scale(1) rotate(0)', opacity: 1, offset: 0.18},
            {transform: 'translate(calc(-88% + ' + toS[0] * 0.5 + 'px), calc(-22% + ' + toS[1] * 0.5 + 'px)) scale(1.05) rotate(28deg)', opacity: 0.9, offset: 0.55},
            {transform: 'translate(calc(-88% + ' + toS[0] + 'px), calc(-22% + ' + toS[1] + 'px)) scale(1.1) rotate(48deg)', opacity: 0}],
            {duration: life, easing: 'ease-out', fill: 'forwards'}); }],
        // Flowing Stream Palm: a ring of water spins up at her palm and rolls the blow away along her sleeve
        stream: [HIT - 220, function (life) { FX = art('twater', C, wide(514 / 578, 0.5));
          FX.animate([{transform: mv(0, 'scale(0.3) rotate(0)'), opacity: 0}, {transform: mv(0, 'scale(1) rotate(-160deg)'), opacity: 0.95, offset: 0.3},
            {transform: mv(0.6, 'scale(0.95) rotate(-330deg)'), opacity: 0.85, offset: 0.7}, {transform: mv(1, 'scale(0.7) rotate(-470deg)'), opacity: 0}],
            {duration: life, fill: 'forwards'}); }],
        // Crane Wing Deflection: a white wing opens from her sleeve across the blow and sweeps it down
        crane: [HIT - 160, function (life) { FX = art('tcrane', C, bodyW * 2.5);
          FX.style.transformOrigin = '15% 80%';
          FX.animate([{transform: 'translate(-15%,-80%) scale(0.25,0.6) rotate(-25deg)', opacity: 0},
            {transform: 'translate(-15%,-80%) scale(1) rotate(-6deg)', opacity: 1, offset: 0.25},
            {transform: 'translate(calc(-15% + ' + toS[0] * 0.55 + 'px), calc(-80% + ' + toS[1] * 0.55 + 'px)) scale(1) rotate(30deg)', opacity: 0.9, offset: 0.65},
            {transform: 'translate(calc(-15% + ' + toS[0] * 0.8 + 'px), calc(-80% + ' + toS[1] * 0.8 + 'px)) scale(0.9) rotate(52deg)', opacity: 0}],
            {duration: life, easing: 'ease-out', fill: 'forwards'}); }],
        // Moon Mirror Palm: a moon mirror rises before her palm, turned toward the beast; the blow glances off it
        moon: [HIT - 260, function (life) { FX = art('tmoon', toward, wide(607 / 640, 0.55));
          FX.animate([{transform: 'translate(-50%,-50%) scale(0.15,0.4)', opacity: 0}, {transform: 'translate(-50%,-50%) scale(0.62,1)', opacity: 0.9, offset: 0.3},
            {transform: mv(0.15, 'scale(0.62,1) rotate(-10deg)'), opacity: 0.85, offset: 0.65}, {transform: mv(0.35, 'scale(0.5,0.9) rotate(-18deg)'), opacity: 0}],
            {duration: life, fill: 'forwards'}); }],
        // Thousand Hands Deflection: a ring of jade hands opens around her and turns the blow round her
        hands: [HIT - 300, function (life) {
          if (P.hand) {                                             // a wheel of jade hands, fingers out, turning round her
            var box = document.createElement('div'), bw = wide(1, 1.25), bpx = bw / 100 * W;
            box.className = 'tart thandwheel'; box.style.left = mid[0] + '%'; box.style.top = mid[1] + '%'; box.style.width = bw + '%'; box.style.height = bpx + 'px';
            var N = LITE ? 8 : 11;
            for (var i = 0; i < N; i++) {
              var im = document.createElement('img'); im.src = P.hand; im.alt = '';
              im.style.cssText = 'position:absolute;left:50%;top:50%;width:30%;transform:translate(-50%,-50%) rotate(' + (360 * i / N) + 'deg) translateX(' + (bpx * 0.33) + 'px)';
              box.appendChild(im);
            }
            scene.insertBefore(box, fighter); made.push(box); FX = box;
            box.animate([{transform: 'translate(-50%,-50%) scale(0.2) rotate(-60deg)', opacity: 0}, {transform: 'translate(-50%,-50%) scale(1) rotate(0)', opacity: 0.95, offset: 0.3},
              {transform: 'translate(-50%,-50%) scale(1.03) rotate(70deg)', opacity: 0.9, offset: 0.75}, {transform: 'translate(-50%,-50%) scale(1.1) rotate(110deg)', opacity: 0}],
              {duration: life, fill: 'forwards'});
            return;
          }
          FX = art('thands', mid, wide(1, 1.15), true);
          FX.animate([{transform: 'translate(-50%,-50%) scale(0.2) rotate(-40deg)', opacity: 0}, {transform: 'translate(-50%,-50%) scale(1) rotate(0)', opacity: 0.9, offset: 0.3},
            {transform: 'translate(-50%,-50%) scale(1.04) rotate(45deg)', opacity: 0.85, offset: 0.75}, {transform: 'translate(-50%,-50%) scale(1.1) rotate(70deg)', opacity: 0}],
            {duration: life, fill: 'forwards'}); }],
        // Void Mirror Stance: a dark mirror of the void forms before her palm; the blow cracks it and is lost in it
        void: [HIT - 320, function (life) { FX = art('tvoid', toward, wide(511 / 756, 0.72));
          FX.animate([{transform: 'translate(-50%,-50%) scale(0.5) rotate(-12deg)', opacity: 0}, {transform: 'translate(-50%,-50%) scale(1) rotate(0)', opacity: 0.95, offset: 0.3},
            {transform: 'translate(-50%,-50%) scale(1.02) rotate(2deg)', opacity: 0.9, offset: 0.65}, {transform: 'translate(-50%,-50%) scale(1.12) rotate(4deg)', opacity: 0}],
            {duration: life, fill: 'forwards'}); }]
      };
      var F = FORM[X.play] || [HIT, function () {}];
      var FORM_AT = Math.max(0, F[0]), FX_END = X.play === 'hands' ? END - 160 : HIT + 640 * PACE;
      function struck() {                                           // her hand meets the blow and turns it aside
        var spark = X.play === 'glance' ? '#FFE6A0' : tc;
        burst('tspark', C[0], C[1], spark);
        burst('tspark', C[0] - 3, C[1] + 5, spark);                 // carried off down her sleeve
        if (FX) FX.animate([{filter: 'brightness(1)'}, {filter: 'brightness(2)'}, {filter: 'brightness(1)'}], {duration: 340});
        if (FX && X.play === 'void') FX.animate([{translate: '0 0'}, {translate: '-5px 2px'}, {translate: '4px -2px'}, {translate: '0 0'}], {duration: 360});
        if (P.hit) bloom(made, P.hit, X.play === 'moon' ? toward : [C[0] + 1.5, C[1]], bodyW * (X.play === 'moon' ? 1.5 : 1.4), 680);   // its own impact where she meets it
        if (P.feathers) part(made, P.feathers, C, bodyW * 2.6, 1300, [{transform: 'translate(-50%,-50%) scale(0.3)', opacity: 0},   // Crane Wing: feathers torn loose, drifting down
          {transform: 'translate(-50%,-50%) scale(1)', opacity: 1, offset: 0.2}, {transform: 'translate(-50%,-40%) scale(1.1) rotate(8deg)', opacity: 0.8, offset: 0.6},
          {transform: 'translate(-50%,-25%) scale(1.15) rotate(14deg)', opacity: 0}], {easing: 'linear'});
        if (scene.animate) scene.animate([{transform: 'none'}, {transform: 'translate(3px,2px)'}, {transform: 'translate(-2px,-1px)'}, {transform: 'none'}], {duration: 260});
        if (hitEv && hitEv.dmg) { drop('me'); pop(fighter, 'hurt' + heavy('me', hitEv.dmg), '−' + hitEv.dmg); }
        pop(fighter, 'word', ev.hold ? 'Held ' + ev.hold + '%' : 'Deflected');
      }
      return {end: END, hit: HIT, render: function (t) {
        if (t < 0) return;
        if (once('start')) {                                        // the grade's spectacle, as for every technique
          if (tier >= 2) { fx('tqring', feet[0], feet[1], 760, {'--tc': tc}); fx('tqring q2', feet[0], feet[1], 900, {'--tc': tc}); }
          if (tier >= 3) { scene.insertBefore(fx('tdim', 50, 50, END, {'--life': END + 'ms'}), fighter); fx('tpillar', feet[0], feet[1], Math.round(END * 0.6), {'--tc': tc}); }
          if (tier >= 4) scene.insertBefore(fx('theaven', 50, 50, END, {'--life': END + 'ms'}), fighter);
        }
        if (attacked) {                                             // the beast lunges, is turned aside past her, goes home
          var x = 0, y = 0, rot = 0, lunge = reachBeast + 0.015 * W;
          if (t < D.charge) { var q = ease(span(t, 0, D.charge)); x = 0.015 * W * q; rot = 4 * q; }
          else if (t < HIT) { var c = span(t, D.charge, HIT); x = 0.015 * W - lunge * c * c; rot = -6 * c; }
          else if (t < D.glance) { var g = ease(span(t, HIT, D.glance)); x = -reachBeast - 0.012 * W * g; y = 0.03 * W * g; rot = -6 + 16 * g; }
          else if (t < D.home) { var r = inout(span(t, D.glance, D.home)); x = (-reachBeast - 0.012 * W) * (1 - r); y = 0.03 * W * (1 - r) - 0.02 * W * Math.sin(Math.PI * r); rot = 10 * (1 - r); }
          bpose(t < D.charge ? 'crouch' : t < D.glance ? 'leap' : 'idle');
          var ck = ev.counter ? knocked(t - HIT - 260, 0.03 * W) : [0, 0];
          animal(x + ck[0], y, rot, ck[1]);
        }
        if (msheet) {
          if (t >= END - 60) pose('idle'); else { pose('motion'); show(frame(t)); }
        } else pose(t < END - 60 ? 'windup' : 'idle');
        var kb = hitEv && hitEv.dmg ? knocked(t - HIT, 0.008 * W) : [0, 0];
        hero(-kb[0], 0);
        poses.style.filter = tier >= 1 && t < END - 200 ? 'drop-shadow(0 0 ' + (4 + 3 * tier) + 'px ' + tc + ')' : '';
        if (t >= FORM_AT && once('form')) F[1](FX_END - FORM_AT);
        if (attacked && t >= HIT && once('hit')) struck();
        if (ev.heal && t >= HIT + 300 && once('heal')) { drop('me'); pop(fighter, 'word heal', '+' + ev.heal); fx('tqring', feet[0], feet[1], 700, {'--tc': '#7CF0BE'}); }
        if (ev.counter && t >= HIT + 260 && once('counter')) {     // the blow sent back as she turns it
          fx('tpierce', C[0], C[1], 600, {'--tc': X.play === 'glance' ? '#FFE6A0' : tc});
          if (P.push) part(made, P.push, [C[0] + 7, C[1]], bodyW * 2.2, 620, [{transform: 'translate(-50%,-50%) scale(0.4,0.6)', opacity: 0},   // Thousand Hands: the blow shoved back
            {transform: 'translate(-40%,-50%) scale(1)', opacity: 1, offset: 0.25}, {transform: 'translate(-20%,-50%) scale(1.1)', opacity: 0}]);
          drop('enemy'); pop(beastBox, 'hit' + heavy('enemy', ev.counter), '−' + ev.counter);
        }
        if (!attacked && t >= HIT && once('steady')) pop(fighter, 'word', 'Steady');
      }, clear: function () { made.forEach(function (n) { n.remove(); }); }};
    }

    /* An evade technique that worked (web/technique_fx.py MOVES_FX, "sidestep"), played by either cultivator with their own
       frames; told here as she plays it (he dashes low in place, wrapped in Qi, `give` 0, and rises out of it): the
       beast's Break comes in and she slips it. Her frames play one for one at the video's own pace (`fps` in
       looks.MOTION_SHEETS), never sped up or stretched: on guard, then from `jab` she sweeps her sleeve and drops into
       a deep side lunge, out of the blow's line at `release`, when the Break arrives where she stood; from `back` she
       rises into the same guard she started in, then idle. She also gives a little ground and takes it back (moved,
       not distorted), so the Break passes clear of her. The technique's afterimages are left where she stood and the
       Break goes through them: they stream off behind her and dissolve. Nothing is hit and no number drops: the
       engine's log says she took no damage. Only played on such a turn (`ev.evaded`, `ev.slipped`); otherwise the technique keeps
       its CSS look. The same when an evade technique takes a Strike with a full block (no roll: she is untouched),
       "Evaded", with the Guard's counter if the engine logged one. */
    function sidestepped(ev) {
      var X = cast.fx, tier = TIER[cast.grade] || 0, did = {}, made = [], tc = cast.color, P = X.parts || {};
      var mn = msheet ? +msheet.dataset.frames : 27, mcols = msheet ? +msheet.dataset.cols : 1, mrows = msheet ? +msheet.dataset.rows : 1;
      var FPS = msheet && msheet.dataset.fps ? +msheet.dataset.fps : 12, MS = 1000 / FPS;
      var JAB = msheet ? +msheet.dataset.jab : 3, REL = msheet ? +msheet.dataset.release : 10, BACK = msheet ? +msheet.dataset.back : 14;
      var Bd = msheet && msheet.dataset.body ? msheet.dataset.body.split(',').map(Number) : [0.52, 0.2, 0.94, 0.24];
      var HIT = REL * MS, PLAYED = mn * MS, END = PLAYED + 120;          // the Break arrives as she is out of its line
      var STEP_IN = JAB * MS, STEP_OUT = BACK * MS, HOME = Math.min(PLAYED, (BACK + 8) * MS);
      var GIVE = (msheet && msheet.dataset.give ? +msheet.dataset.give : 0.06) * W;   // the ground given and taken back (looks `give`), px
      var bodyH = fr.height * (Bd[2] - Bd[1]);
      var stood = at(fr, Bd[0], (Bd[1] + Bd[2]) / 2);                // where she stood: the lead afterimage stays there
      var charge = HIT - 340;                                         // the beast crouches, then leaps for the Break
      var HAND = msheet && msheet.dataset.hand ? msheet.dataset.hand.split(',').map(Number) : [0.64, 0.4];
      if (ev.counter) hold('enemy');                                  // a full block of a Strike may still counter
      function once(k) { if (did[k]) return false; did[k] = true; return true; }
      function show(f) {
        f = Math.max(0, Math.min(mn - 1, Math.floor(f)));
        msheet.style.backgroundPosition = (f % mcols) / (mcols - 1) * 100 + '% ' + Math.floor(f / mcols) / (mrows - 1) * 100 + '%';
      }
      var wide = function (aspect, share) { return bodyH * share / aspect / W * 100; };   // aspect: height / width
      var ASPECT = {mist_steps: 331 / 828, cloud_steps: 275 / 919};
      var FX = null;
      function afterimages() {                                       // left where she stood, behind her
        if (P.figure && !X.sheets) {                                 // Mist Steps: three mist figures where she stood, streaming off on a trail
          var life2 = PLAYED - STEP_IN, fw = wide(374 / 600, 1.05), hit = (HIT - STEP_IN) / life2;
          var gap = Math.min(3.5, stood[0] * 0.2);                   // the echoes behind her: closer together near a phone's edge
          part(made, P.trail, [stood[0] - gap, stood[1] + 2], fw * 1.9, life2, [{transform: 'translate(-50%,-50%) scale(0.3,0.6)', opacity: 0},
            {transform: 'translate(-50%,-50%) scale(1)', opacity: 0.8, offset: hit}, {transform: 'translate(-62%,-50%) scale(1.1,1)', opacity: 0}], {under: fighter});
          [0, 1, 2].forEach(function (k) {
            var n = part(made, P.figure, [stood[0] - gap * k, stood[1]], fw, life2, [{transform: 'translate(-50%,-50%) scale(0.92)', opacity: 0},
              {transform: 'translate(-50%,-50%) scale(1)', opacity: 0.85 - 0.25 * k, offset: hit * 0.8},
              {transform: 'translate(-56%,-50%) scale(1.04,1)', opacity: 0.8 - 0.25 * k, offset: hit},
              {transform: 'translate(-80%,-52%) scale(1.12,1)', opacity: 0}], {under: fighter, delay: 70 * k});
            if (k === 0) FX = n;
          });
          return;
        }
        var n = document.createElement('img');
        n.className = 'tart tbrace tsidestep ' + (X.play === 'cloud_steps' ? 'tcloudsteps' : 'tmiststeps');
        n.src = X.art[0]; n.alt = '';
        if (X.sheets) n.style.display = 'none';
        n.style.left = stood[0] + '%'; n.style.top = stood[1] + '%'; n.style.width = wide(ASPECT[X.play] || 0.38, 0.95) + '%';
        n.style.setProperty('--tc', tc);
        scene.insertBefore(n, fighter); made.push(n); FX = n;
        var life = PLAYED - STEP_IN;
        n.style.transformOrigin = '85% 50%';                          // the lead figure, on the spot she left
        n.animate([{transform: 'translate(-85%,-50%) scale(0.9,0.96)', opacity: 0},
          {transform: 'translate(-85%,-50%) scale(1)', opacity: 0.9, offset: (HIT - STEP_IN) / life * 0.8},
          {transform: 'translate(-90%,-50%) scale(1.04,1)', opacity: 0.85, offset: (HIT - STEP_IN) / life},
          {transform: 'translate(-104%,-52%) scale(1.12,1)', opacity: 0.35, offset: Math.min(0.9, (HIT + 600 - STEP_IN) / life)},
          {transform: 'translate(-112%,-53%) scale(1.15,1)', opacity: 0}], {duration: life, easing: 'ease-out', fill: 'forwards'});
      }
      function slipped() {                                           // the Break goes through the afterimages
        if (FX) FX.animate([{filter: 'brightness(1)'}, {filter: 'brightness(1.7)'}, {filter: 'brightness(1)'}], {duration: 380});
        var p = stood;
        burst('tspark', p[0], p[1], X.play === 'cloud_steps' ? '#FFF1C8' : '#CFE6FF');
        pop(fighter, 'word', ev.idle ? 'Shadow step' : ev.slipped ? 'Slipped away' : 'Evaded');
      }
      return {end: END, hit: HIT, render: function (t) {
        if (t < 0) return;
        if (once('start')) {                                        // the grade's spectacle, as for every technique
          var feet = at(fr, Bd[0], Bd[2]);
          if (tier >= 2) { fx('tqring', feet[0], feet[1], 760, {'--tc': tc}); fx('tqring q2', feet[0], feet[1], 900, {'--tc': tc}); }
          if (tier >= 3) { scene.insertBefore(fx('tdim', 50, 50, END, {'--life': END + 'ms'}), fighter); fx('tpillar', feet[0], feet[1], Math.round(END * 0.6), {'--tc': tc}); }
          if (tier >= 4) scene.insertBefore(fx('theaven', 50, 50, END, {'--life': END + 'ms'}), fighter);
        }
        if (t >= STEP_IN && once('step')) stepped = fs('dodge', 'step', 0, {exact: true}) === true;   // the step's own recording, as it starts
        // the beast's Break: a crouch, a leap to where she stood, through the afterimages and a little past, then home
        var x = 0, y = 0, rot = 0, lunge = reachBeast - 0.03 * W + 0.02 * W, past = 0.012 * W, land = reachBeast - 0.03 * W;
        if (t < charge) { var q = ease(span(t, 0, charge)); x = 0.02 * W * q; rot = 5 * q; }
        else if (t < HIT) { var c = span(t, charge, HIT); x = 0.02 * W - lunge * c * c; rot = -7 * c; }
        else if (t < HIT + 220) { var g = ease(span(t, HIT, HIT + 220)); x = -land - past * g; y = 0.012 * W * g; rot = -7 + 4 * g; }
        else if (t < HIT + 820) { var r = inout(span(t, HIT + 220, HIT + 820)); x = (-land - past) * (1 - r); y = 0.012 * W * (1 - r) - 0.02 * W * Math.sin(Math.PI * r); rot = -3 * (1 - r); }
        if (ev.idle) { x = y = rot = 0; bpose('idle'); }            // no blow came (the beast Guarded): it stays where it is
        else bpose(t < charge ? 'crouch' : t < HIT + 220 ? 'leap' : 'idle');
        animal(x, y, rot, 0);
        // her: the video's frames one for one, and the ground she gives and takes back
        if (msheet && t < END - 60) { pose('motion'); show(t / MS); } else pose(msheet ? 'idle' : t < END - 60 ? 'windup' : 'idle');
        var away = t < STEP_IN ? 0 : t < HIT ? ease(span(t, STEP_IN, HIT)) : t < STEP_OUT ? 1 : 1 - inout(span(t, STEP_OUT, HOME));
        hero(-GIVE * away, 0);
        poses.style.filter = tier >= 1 && t < END - 200 ? 'drop-shadow(0 0 ' + (4 + 3 * tier) + 'px ' + tc + ')' : '';
        if (t >= STEP_IN && once('form')) afterimages();
        if (t >= HIT && once('slip')) slipped();
        if (ev.counter && t >= HIT + 260 && once('counter')) {         // the Guard's counter, as the engine logged it
          var h = at(fr, HAND[0], HAND[1]); fx('tpierce', h[0], h[1], 600, {'--tc': tc});
          drop('enemy'); pop(beastBox, 'hit' + heavy('enemy', ev.counter), '−' + ev.counter);
        }
      }, clear: function () { made.forEach(function (n) { n.remove(); }); }};
    }

    /* The victory sequence's middle part (docs/web.md): after the last blow the beast goes down. "warp": its own
       picture goes down through its category's shared movement (drawDeath), then the body stays down. "fall": a beast with no category tips
       over. "rout": bandits scatter. Then the body lies there a moment (linger) before the Victory panel comes up.
       Nothing is decided here: the server has already ended the fight and paid it out, once. */
    function death(d) {
      var cv = d.kind === 'warp' ? beastBox.querySelector('canvas.deathfx') : null, did = {}, total = 0, hitAt = 0;
      var DS = d.kind === 'sheet' && BS ? BS.data.sheets.death : null;          // its own death animation
      if (cv) d.ms.forEach(function (m, n) { if (n < d.impact) hitAt += m; total += m; });
      else if (DS) { total = d.ms; hitAt = d.impact; }
      else total = d.kind === 'rout' ? 600 : 1000;
      function once(k) { if (did[k]) return false; did[k] = true; return true; }
      function thud() {
        [0.2, 0.5, 0.8].forEach(function (q, n) { var p = at(br, q, 0.97); fx('ddust', p[0], p[1], 720, {'--dx': (n - 1) * 26 + 'px'}); });
        if (scene.animate) scene.animate([{transform: 'none'}, {transform: 'translate(0,5px)'}, {transform: 'translate(0,-2px)'}, {transform: 'none'}], {duration: 260});
      }
      return {end: total + (d.linger || 800), render: function (t) {
        if (t < 0) return;
        if (once('start')) { main.classList.add('dying'); departs(); }
        pose('idle'); hero(0, 0);
        if (DS) {                                              // it falls in its own frames, and lies there
          BS.frame('death', t / total * DS.frames);
          if (t >= hitAt && once('thud')) thud();
        } else if (cv) {
          drawDeath(main, t);                                  // the beast's own picture, bent through the shared movement
          var flash = 1 - span(t, 0, 200), dim = span(t, total, total + 500);
          cv.style.filter = 'drop-shadow(0 8px 10px rgba(0,0,0,.65)) brightness(' + (1 + 1.2 * flash - 0.28 * dim) + ') saturate(' + (1 - 0.25 * dim) + ')';
          if (t >= hitAt && once('thud')) thud();
        } else if (d.kind === 'rout') {
          var g = ease(span(t, 0, total));
          beast.style.opacity = 1 - g; beast.style.transform = 'translateX(' + 0.06 * W * g + 'px)';
        } else {
          // it staggers, its legs give, then it rolls over onto its side (away into the scene, or toward you) and lands
          var a = span(t, 0, 320), b = span(t, 320, total), bb = b * b, side = d.side || 1;
          var land = span(t, total, total + 220), bounce = Math.sin(Math.PI * land) * (1 - land);
          // always onto its far flank (falling toward you would sink it under the ground); `side` sets which end
          // touches down first, the head (1) or the hindquarters (-1)
          var roll = 60 * bb - 6 * bounce, sway = b > 0 ? side * 4 * bb : 4 * Math.sin(Math.PI * 2 * a);
          beast.style.transform = 'perspective(900px) translateY(' + (2.5 * Math.sin(Math.PI * a) + 2 * bb) + '%) rotateZ(' + -sway + 'deg) rotateX(' + roll + 'deg) scaleY(' + (1 - 0.08 * Math.sin(Math.PI * a)) + ')';
          beast.style.filter = 'brightness(' + (1 - 0.25 * bb) + ') saturate(' + (1 - 0.3 * bb) + ')';
          if (b >= 1 && once('thud')) thud();
        }
      }, clear: function () { if (cv) { cv.style.filter = ''; drawDeath(main, Infinity); } if (DS) BS.dead(); beast.style.opacity = ''; }};
    }

    var steps = [], kinds = {};
    function add(step, phase, cues) {                            // whose action this step shows, and its sounds ([ms, name, arg])
      step.phase = phase; if (cues) step.cues = (step.cues || []).concat(cues); steps.push(step);
    }
    var castTier = cast ? (TIER[cast.grade] || 0) : 0;
    if (window.FightSound) window.FightSound.voice = fighter.dataset.voice || '';       // whose recordings the cultivator's moves play
    if (window.FightSound) window.FightSound.body = beastBox.dataset.body || '';         // whose voice the beast's sounds are
    var braceHit = null;                                         // a brace or deflection takes the beast's blow itself
    var inside = cast && cast.fx && (cast.fx.motion === 'brace' || cast.fx.motion === 'deflect');
    if (inside) {
      var bi = events.findIndex(function (e) { return e.act === 'tech'; });
      var hi = events.findIndex(function (e, i) { return i > bi && e.who === 'enemy' && e.act === 'attack'; });
      if (bi >= 0 && hi >= 0) { braceHit = events[hi]; events = events.filter(function (_, i) { return i !== hi; }); }
    }
    events.forEach(function (ev) {
      if (ev.who === 'ally') { add(cameo(ev), 'player_acting'); return; }      // a teammate dashes in (`cameo`)
      if (ev.who === 'enemy' && ev.act === 'roar') { add(roaring(ev), 'beast_acting', [[120, 'roar', ev.final ? 'big' : '', 0, {land: ROAR && ROAR.motion ? 480 : 0}]]); kinds.enemy = 1; }
      else if (ev.act === 'tech' && cast && cast.fx && cast.fx.motion === 'brace') { var hs = heavenly(braced(ev, braceHit)); add(hs, 'beast_acting', later(ev.idle ? [[0, 'guardup', 'brace']] : [[0, 'guardup', 'brace'], [120 * PACE, 'lunge']], hs.pre)); kinds.enemy = 1; }
      else if (ev.act === 'tech' && cast && cast.fx && cast.fx.motion === 'deflect') { var hs = heavenly(deflected(ev, braceHit)); add(hs, 'beast_acting', later(ev.idle ? [[0, 'guardup', 'deflect']] : [[0, 'guardup', 'deflect'], [120 * PACE, 'lunge']], hs.pre)); kinds.enemy = 1; }
      else if (ev.act === 'tech' && (ev.evaded || ev.idle) && cast && cast.fx && cast.fx.motion === 'sidestep') { var hs = heavenly(sidestepped(ev)); add(hs, ev.idle ? 'player_acting' : 'beast_acting', later(ev.idle ? [] : [[60, 'lunge']], hs.pre)); kinds.enemy = 1; }
      else if (ev.who === 'enemy' && ev.act === 'pounce') { add(skillRoar(ev), 'beast_acting', [[120, 'roar', 'big', 0, {land: ROAR && ROAR.motion ? 480 : 0}]]); kinds.enemy = 1; if (ev.guard) kinds.guard = 1; }
      else if (ev.who === 'me' && (ev.act === 'strike' || ev.act === 'break')) { add(attack(ev), 'player_acting'); kinds.me = 1; }
      else if (ev.who === 'me' && ev.act === 'guard') { add(charge(ev), 'beast_acting'); kinds.guard = 1; }
      else if (ev.who === 'enemy') { add(charge(ev), 'beast_acting'); kinds.enemy = 1; }
      else if (ev.act === 'tech' && cast && cast.fx) { var ts = technique(ev); add(ts, 'player_acting', cast.fx.play === 'dragons' ? [] : [[Math.max(0, (cast.fx.sheets ? ts.release : Math.round(ts.end * 0.45)) - 470), 'cast', castTier, 0, {as: cast.fx.motion, land: 470}]]); kinds.me = 1; }
      else if (ev.act === 'tech') add({end: RECIPES.tech.end, render: function () {}}, 'player_acting');
    });
    var dying = end ? death(end) : null;
    if (dying) { add(dying, 'dying', [[60, 'death']]); main.classList.remove('slain'); if (BS) BS.set('idle'); }   // .slain (the finished picture) returns in finish(); it stands until it falls
    if (!steps.length) return null;
    Combat.set(steps[0].phase);
    Object.keys(kinds).forEach(function (k) { main.classList.add('tl-' + k); });
    main.classList.add('tl-hold', 'playing'); fighter.classList.add('acting');
    main.offsetWidth;                                           // the held bars are in place before transitions return
    main.classList.remove('tl-hold');

    var i = 0, start = null, stopped = false;
    function reset() { bpose(home); if (BS && BS.now() !== 'death' && !BS.busy('hit')) BS.set('idle'); pose('idle'); poses.style.transform = ''; poses.style.filter = ''; beast.style.transform = ''; beast.style.filter = ''; if (auraEl) auraEl.style.transform = '';
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
        if (cut !== true) fs('victory');
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
      else {
        if (step.cues) step.cues.forEach(function (c) { if (!c[3] && t >= c[0]) { c[3] = 1; fs(c[1], c[2], 0, c[4]); } });
        step.render(Math.min(t, step.end));
      }
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
  /* ── A team fight (a party's hunt, data-team) ──────────────────────────────────────────────────────
     Your move may be waiting on the others, and a turn can also end when its 30 seconds run out. So while it is
     your turn to look at, the page asks the server for the fight every so often: a new turn is acted out exactly
     like an answer to your own move; otherwise only the party's picks and the turn timer are brought up to date. */
  var POLL = 1500;
  function poll() {
    var main = document.querySelector('main.battle');
    if (!main || !main.dataset.team || main.classList.contains('slain')) return;
    if (Combat.phase !== 'player_turn' || document.hidden) { setTimeout(poll, POLL); return; }
    var token = Combat.token, sent = +main.dataset.turn;
    load(PLAY(), {method: 'GET'}).then(function (html) {
      if (token !== Combat.token || Combat.phase !== 'player_turn') return;
      var doc = new DOMParser().parseFromString(html, 'text/html'), next = doc.querySelector('main.battle');
      var now = document.querySelector('main.battle');
      if (!now) return;
      if (!next || next.dataset.turn !== now.dataset.turn) { Combat.set('submitting'); show(html, sent); return; }
      var a = now.querySelector('.allies'), b = next.querySelector('.allies');
      if (a && b) a.replaceWith(document.importNode(b, true));
      var c = now.querySelector('.turnchip'), d = next.querySelector('.turnchip');   // who you are still waiting for
      if (c && d && d.dataset.wait) { c.dataset.wait = d.dataset.wait; if (now.dataset.waiting) c.textContent = d.dataset.wait; }
      var t = now.querySelector('.teamtimer'), u = next.querySelector('.teamtimer');
      if (t && u) { t.dataset.left = u.dataset.left; }
    }).catch(function () {}).then(function () { setTimeout(poll, POLL); });
  }
  setInterval(function () {                                    // the turn timer bar counts down between polls
    var t = document.querySelector('main.battle .teamtimer');
    if (!t) return;
    var left = Math.max(0, (+t.dataset.left || 0) - 1);
    t.dataset.left = left;
    t.firstElementChild.style.width = (left / (+t.dataset.total || 30) * 100) + '%';
  }, 1000);
  setTimeout(poll, POLL);

  window.addEventListener('pageshow', function (e) { if (e.persisted) location.reload(); });   // never a stale, locked page from the back button
  init();
})();
