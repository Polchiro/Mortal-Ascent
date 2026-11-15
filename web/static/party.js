/* Lobby and hunt pages: ask the server every few seconds whether anything changed (a member joined, the leader
   chose a place, the hunt moved on) and reload when it did. It also tells the server you are still here.
   The page carries the numbers it was drawn at: <body data-p="party version" data-h="hunt version">. */
(function () {
  var b = document.body, p = b.dataset.p, h = b.dataset.h || '';
  var EVERY = 2500;
  function tick() {
    if (document.hidden) return setTimeout(tick, EVERY);
    fetch('/hunt/v', {credentials: 'same-origin', cache: 'no-store'}).then(function (r) { return r.json(); }).then(function (v) {
      if (v.gone) { location.replace('/explore'); return; }
      var hv = v.h === null || v.h === undefined ? '' : String(v.h);
      if ((p !== '' && String(v.p) !== p) || hv !== h) {
        if (document.querySelector('form :focus') ) return setTimeout(tick, EVERY);   // never pull the page out from under typing
        location.reload(); return;
      }
      setTimeout(tick, EVERY);
    }).catch(function () { setTimeout(tick, EVERY * 2); });
  }
  setTimeout(tick, EVERY);
})();
