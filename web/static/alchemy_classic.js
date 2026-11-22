/* Classic alchemy controls without reloading the page (alchemy_play.html, the button version; docs/web.md "Live
   alchemy"). A button sends its choice in the background (/alchemy/act answers with the next decision's page); the
   stage card is swapped in place and the cauldron scene is kept when the stage stays the same, so its videos never
   restart. The decision timer runs here too: when it runs out the page asks for the next decision the same way.
   Without JavaScript the buttons still post the form and the page reloads, as before. The result (or anything
   unexpected) loads as a whole page, for its reveal or explosion. */
(function () {
  'use strict';
  var busy = false, timer = null;

  function setup(first) {
    clearInterval(timer);
    if (!first && window.AlchemyScene) window.AlchemyScene.init();   // (alchemy.js ran it itself on the first page)
    var tm = document.querySelector('.forgeplay .timer[data-left]');
    if (!tm) return;
    var left = +tm.dataset.left, total = +tm.dataset.seconds || 1;
    var fill = document.getElementById('tfill'), txt = document.getElementById('tleft'), end = Date.now() + left * 1000;
    timer = setInterval(function () {
      var l = Math.max(0, (end - Date.now()) / 1000);
      fill.style.width = (l / total * 100) + '%'; txt.textContent = l.toFixed(1) + 's';
      fill.style.background = l / total > 0.5 ? '#6FD9B0' : l / total > 0.25 ? '#E8C27A' : '#E05A4F';
      if (l <= 0) {                     // time's up: the server plays the timed-out move; fetch what comes next
        clearInterval(timer);
        setTimeout(function () { load(fetch('/alchemy/play', {credentials: 'same-origin', cache: 'no-store'})); }, 1100);
      }
    }, 100);
  }

  function load(request) {
    busy = true;
    request.then(function (r) {
      if (!/\/alchemy\/play/.test(r.url)) { location.href = r.url; return null; }
      return r.text();
    }).then(function (html) {
      if (html !== null) swap(html);
    }).catch(function () {
      location.replace('/alchemy/play');
    }).then(function () { busy = false; });
  }

  function swap(html) {
    var doc = new DOMParser().parseFromString(html, 'text/html');
    var next = doc.querySelector('main.forgeplay'), now = document.querySelector('main.forgeplay');
    if (!next || !now || next.querySelector('.result, #alive')) { location.replace('/alchemy/play'); return; }
    next = document.adoptNode(next);              // into this document first: moving a video across documents restarts it
    var oldScene = now.querySelector('.cscene'), newScene = next.querySelector('.cscene');
    if (oldScene && newScene && oldScene.dataset.stage === newScene.dataset.stage) {   // keep the playing videos
      oldScene.dataset.turn = newScene.dataset.turn;
      oldScene.setAttribute('style', newScene.getAttribute('style') || '');
      var oldFire = oldScene.querySelector('.cfire'), newFire = newScene.querySelector('.cfire');
      if (oldFire && newFire && oldFire.getAttribute('src') !== newFire.getAttribute('src')) oldFire.replaceWith(newFire);
      newScene.replaceWith(oldScene);             // (the heat changed the fire: only that clip is new)
    }
    now.replaceWith(next);
    setup();
  }

  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('.forgeplay .choices button');
    if (!b) return;
    e.preventDefault();
    if (busy) return;
    var form = b.form, data = new URLSearchParams(new FormData(form));
    data.set('key', b.value);
    clearInterval(timer);
    form.querySelectorAll('button').forEach(function (x) { x.disabled = true; });
    b.classList.add('chosen');
    load(fetch('/alchemy/act', {method: 'POST', body: data, credentials: 'same-origin', cache: 'no-store'}));
  });

  setup(true);
})();
