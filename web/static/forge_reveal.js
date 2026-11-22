/* The forged piece's reveal (forge_play.html #freveal; docs/web.md "Live forge"): SHOAIB's rune glow blooms, and at its
   flash the piece appears in its rarity's colour (Legendary and Mythical with heavenly rays); then the new passive and
   the rest follow. Once per forge (sessionStorage); a reload, or reduced motion, shows the finished picture. A failed
   forge shakes its cracked piece. */
(function () {
  'use strict';
  var box = document.getElementById('freveal');
  var card = document.querySelector('.result');
  if (!box) {
    var cracked = document.querySelector('.fcracked');
    if (cracked && card) { card.classList.add('failed'); if (window.AlchemySound) window.AlchemySound.play('bad'); }
    return;
  }
  try { sessionStorage.setItem('ma-forge-revealed', box.dataset.id); } catch (e) {}
  if (!card.classList.contains('revealing')) { card.classList.add('revealed'); return; }
  var after = Array.prototype.filter.call(card.children, function (el) { return el !== box && el.tagName !== 'SCRIPT'; });
  var glow = box.querySelector('.frglow');
  function at(ms, f) { setTimeout(f, ms); }
  if (glow) { glow.currentTime = 2.6; glow.addEventListener('playing', function () { glow.classList.add('on'); }, {once: true}); var p = glow.play(); if (p && p.catch) p.catch(function () {}); }
  at(2300, function () {                                  // the flash: the piece appears
    box.classList.add('shown');
    if (window.AlchemySound) window.AlchemySound.play(box.classList.contains('grand') ? 'chime' : 'good');
  });
  after.forEach(function (el, k) { at(2700 + k * 160, function () { el.classList.add('in'); }); });
  at(2700 + after.length * 160 + 400, function () { card.classList.remove('revealing'); card.classList.add('revealed'); });
})();
