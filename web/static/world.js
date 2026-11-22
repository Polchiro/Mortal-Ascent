/* The World Map (world.html, web/world.py, docs/world.md).

   The scroll is a picture; each place on it is a button (its marker). Pressing one opens its card: what is there, and
   whether your realm may enter. You travel by walking (the Crossroads, outside the town gate): this is only a map.
   Esc, Close or a click outside closes a card; Back, M or Esc goes back to where you opened the map. */
(function () {
  'use strict';
  var open = null, opener = null;
  function show(id, from) {
    hide();
    open = document.getElementById(id); opener = from;
    if (!open) return;
    open.hidden = false;
    (open.querySelector('.tgo .hbtn') || open).focus();
  }
  function hide() {
    if (!open) return;
    open.hidden = true; open = null;
    if (opener) { opener.focus(); opener = null; }
  }
  document.querySelectorAll('.wmark').forEach(function (b) {
    b.addEventListener('click', function (e) { e.stopPropagation(); show(b.getAttribute('data-card'), b); });
  });
  document.querySelectorAll('[data-close]').forEach(function (b) { b.addEventListener('click', hide); });
  document.querySelectorAll('.wcard').forEach(function (c) { c.addEventListener('click', function (e) { e.stopPropagation(); }); });
  document.addEventListener('click', function () { if (open) hide(); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && open) { hide(); e.preventDefault(); return; }
    if ((e.key === 'm' || e.key === 'M' || e.key === 'Escape') && !open) back();
  });
  // Back: to the page you opened the map from (the town, the Crossroads, a hunt), else to town
  var wback = document.getElementById('wback');
  function back() { if (document.referrer && new URL(document.referrer).origin === location.origin) history.back(); else location.href = '/town'; }
  if (wback) wback.addEventListener('click', function (e) { e.preventDefault(); back(); });
})();
