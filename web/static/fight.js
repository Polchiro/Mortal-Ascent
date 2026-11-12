/* The fight screen: send a move without leaving the page (no jump to the top), then swap in the next turn. */
(function () {
  var busy = false, playing = null;

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
    var hist = main.querySelector('.bhist'), close = main.querySelector('.histclose');
    if (hist && close) close.addEventListener('click', function () { hist.open = false; hist.querySelector('summary').focus(); });
    main.querySelectorAll('form.fightform').forEach(function (form) {
      form.addEventListener('submit', function (ev) {
        ev.preventDefault();
        var button = ev.submitter;
        if (busy || !button || button.disabled) return;
        send(form, button);
      });
    });
  }

  function send(form, button) {
    busy = true;
    var data = new FormData(form);
    data.set(button.name, button.value);
    document.querySelectorAll('main.battle button').forEach(function (b) { b.disabled = true; });
    fetch(form.action, {method: 'POST', body: new URLSearchParams(data), credentials: 'same-origin'})
      .then(function (r) { return r.text().then(function (html) { return {url: r.url, html: html}; }); })
      .then(function (res) {
        var doc = new DOMParser().parseFromString(res.html, 'text/html');
        var next = doc.querySelector('main.battle'), now = document.querySelector('main.battle');
        if (next && now) {
          var before = bars(now);
          if (playing) playing.finish();
          var fresh = document.importNode(next, true);
          keepHistory(now, fresh);
          now.replaceWith(fresh);                             // same scroll position: nothing jumps
          busy = false;
          init();
          playing = act(fresh, before);                       // act the turn out: dash, swing, hit, the beast's answer
        } else {
          location.replace('/explore/play');                  // the fight is over: the next page of the expedition
        }
      })
      .catch(function () { location.replace('/explore/play'); });
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
    tech:   {end: 1100}                                         // techniques play their own animation (style.css)
  };
  var GAP = 160;

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
    var claws = fighter.querySelector('.clawsfx g'), clawClip = fighter.querySelector('#clawclip rect');
    var fr = fighter.getBoundingClientRect(), br = beastBox.getBoundingClientRect();
    var reachMe = Math.max(0, br.left + br.width * 0.12 - (fr.left + fr.width * 0.962));     // sword tip to the beast
    var reachBeast = Math.max(0, br.left - (fr.left + fr.width * 0.64));                       // the beast to your body
    var beastFilter = getComputedStyle(beast).filter;

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

    /* the beast's attack: rears back, charges, claws; you are hit, or your Guard stops it (and may counter) */
    function charge(ev) {
      var R = RECIPES.beast, guard = ev.act === 'guard', done = false, countered = false;
      if (guard) { if (ev.counter) hold('enemy'); } else hold('me');
      return {end: R.end + (guard && ev.counter ? 200 : 0), render: function (t) {
        var x = 0, y = 0, rot = 0;
        if (t < R.charge) { var q = ease(span(t, 0, R.charge)); x = 0.015 * W * q; rot = 4 * q; }
        else if (t < R.back) { var c = span(t, R.charge, R.hit); x = 0.015 * W - (reachBeast + 0.015 * W) * c * c; rot = -6 * c; }
        else if (t < R.end) { var r = inout(span(t, R.back, R.end)); x = -reachBeast * (1 - r); y = -0.024 * W * Math.sin(Math.PI * r); }
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

    var steps = [], kinds = {};
    events.forEach(function (ev) {
      if (ev.who === 'me' && (ev.act === 'strike' || ev.act === 'break')) { steps.push(attack(ev)); kinds.me = 1; }
      else if (ev.who === 'me' && ev.act === 'guard') { steps.push(charge(ev)); kinds.guard = 1; }
      else if (ev.who === 'enemy') { steps.push(charge(ev)); kinds.enemy = 1; }
      else if (ev.act === 'tech') steps.push({end: RECIPES.tech.end, render: function () {}});
    });
    if (!steps.length) return null;
    Object.keys(kinds).forEach(function (k) { main.classList.add('tl-' + k); });
    main.classList.add('tl-hold'); fighter.classList.add('acting');
    main.offsetWidth;                                           // the held bars are in place before transitions return
    main.classList.remove('tl-hold');

    var i = 0, start = null, stopped = false;
    function reset() { pose('idle'); poses.style.transform = ''; poses.style.filter = ''; beast.style.transform = ''; beast.style.filter = '';
      trail.style.opacity = 0; claws.setAttribute('opacity', 0); }
    function finish() {
      if (stopped) return;
      stopped = true;
      reset(); drop('me'); drop('enemy'); fighter.classList.remove('acting');
      if (playing && playing.finish === finish) playing = null;
    }
    function frame(now) {
      if (stopped || !main.isConnected) return;
      if (start === null) start = now;
      var t = now - start, step = steps[i];
      if (t >= step.end + GAP) { step.render(step.end + 2000); reset(); i += 1; start = null; if (i >= steps.length) return finish(); }
      else step.render(Math.min(t, step.end));
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
    scene.addEventListener('click', finish, {once: true});      // click the scene to skip
    return {finish: finish};
  }

  document.addEventListener('keydown', function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey || busy) return;
    var main = document.querySelector('main.battle');
    if (!main) return;
    if (e.key === 'Escape') { main.querySelectorAll('details[open]').forEach(function (d) { d.open = false; }); return; }
    var k = e.key.toUpperCase(), el = main.querySelector('[data-key="' + k + '"]');
    if (!el) return;
    if (el.tagName === 'DETAILS') { el.open = !el.open; if (el.open) { var f = el.querySelector('.techbtn:not(:disabled)'); if (f) f.focus(); } return; }
    if (!el.disabled) el.click();
  });
  document.addEventListener('click', function (e) {          // close the techniques menu when clicking elsewhere
    document.querySelectorAll('details.techmenu[open]').forEach(function (d) { if (!d.contains(e.target)) d.open = false; });
  });
  init();
})();
