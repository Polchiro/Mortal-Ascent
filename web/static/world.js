/* The World Map (world.html, web/world.py, docs/world.md).

   The scroll is a picture; each place on it is a button (its marker). Pressing one opens its card: what is there, and
   whether you may go (set out on a Solo Hunt, or go back to town). Esc, Close or a click outside closes it. The
   server checks everything again when you set out, so this only shows and hides cards. */
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
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && open) { hide(); e.preventDefault(); } });
})();
