/* The pill's reveal when a craft succeeds (alchemy_play.html #preveal; docs/web.md "The pill reveal"): the cauldron
   bursts open, the pill rises glowing in its tier's colour, its patterns etch on one ring at a time (counted 一纹…九纹),
   the tier stamps in and the rewards follow. Plays once per craft (sessionStorage); a reload, or reduced motion,
   shows the finished picture at once. */
(function () {
  'use strict';
  var box = document.getElementById('preveal');
  if (!box) return;
  var card = box.closest('.result');
  try { sessionStorage.setItem('ma-alchemy-revealed', box.dataset.id); } catch (e) {}
  if (!card.classList.contains('revealing')) { card.classList.add('revealed'); return; }   // (the page's inline check)

  var CN = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九'];
  var n = +box.dataset.patterns, count = document.getElementById('rcount'), rings = box.querySelectorAll('.rrings circle');
  var after = Array.prototype.filter.call(card.children, function (el) { return el !== box && el.tagName !== 'SCRIPT'; });

  var light = box.querySelector('.rlight');
  if (light) { light.addEventListener('playing', function () { light.classList.add('on'); }, {once: true}); var p = light.play(); if (p && p.catch) p.catch(function () {}); }

  function at(ms, f) { setTimeout(f, ms); }
  at(150, function () { box.classList.add('burst'); });                   // the lid blasts open, light rises
  at(900, function () { box.classList.add('rise'); });                    // the pill floats up out of it
  var t0 = 1700, step = Math.max(160, Math.min(320, 2200 / Math.max(1, n)));
  count.textContent = '';
  for (var i = 0; i < n; i++) (function (k) {
    at(t0 + k * step, function () {
      rings[k].classList.add('on');
      count.textContent = CN[k + 1] + '纹';
      count.classList.remove('tick'); void count.offsetWidth; count.classList.add('tick');
    });
  })(i);
  var end = t0 + n * step + 250;
  at(end, function () { box.classList.add('done'); if (box.classList.contains('perfect')) box.classList.add('glory'); });
  after.forEach(function (el, k) { at(end + 150 + k * 140, function () { el.classList.add('in'); }); });
  at(end + 150 + after.length * 140 + 400, function () { card.classList.remove('revealing'); card.classList.add('revealed'); });
})();
