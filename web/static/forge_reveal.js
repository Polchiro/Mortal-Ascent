/* The forged piece's reveal (forge_play.html #freveal; docs/web.md "Live forge"): SHOAIB's golden burst
   (art/forge/reveal_burst.mp4, tinted to the rarity) flashes, and at its flash the piece appears in its rarity's colour
   (Legendary and Mythical with heavenly rays and his rune glow); then the new passive and the rest follow.
   A failed forge (#fcrackbox): his glowing bar cracks apart in sparks and smoke (art/forge/crack.mp4) and stays broken.
   Once per forge (sessionStorage); a reload, or reduced motion, shows the finished picture. */
(function () {
  'use strict';
  var card = document.querySelector('.result');
  if (!card) return;
  var box = document.getElementById('freveal'), crack = document.getElementById('fcrackbox');
  var main = box || crack;
  if (!main) return;
  function Snd(n) { if (window.AlchemySound) window.AlchemySound.play(n); }
  function at(ms, f) { setTimeout(f, ms); }
  function play(v) { if (!v) return; var p = v.play(); if (p && p.catch) p.catch(function () {}); }
  try { sessionStorage.setItem('ma-forge-revealed', main.dataset.id); } catch (e) {}
  if (!card.classList.contains('revealing')) { card.classList.add('revealed'); return; }
  var after = Array.prototype.filter.call(card.children, function (el) { return el !== main && el.tagName !== 'SCRIPT'; });
  var shown;
  if (box) {
    var burst = box.querySelector('.frburst'), glow = box.querySelector('.frglow');
    if (burst) { burst.addEventListener('playing', function () { burst.classList.add('on'); }, {once: true}); play(burst); }
    at(1000, function () {                                  // the flash: the piece appears
      box.classList.add('shown');
      Snd(box.classList.contains('grand') ? 'chime' : 'good');
    });
    if (glow && box.classList.contains('grand')) at(1200, function () {
      glow.currentTime = 2.6; glow.addEventListener('playing', function () { glow.classList.add('on'); }, {once: true}); play(glow);
    });
    shown = 1400;
  } else {
    // the crack's timeline starts when the video really plays (a slow load must not leave the bar to crack unseen);
    // if it never plays, the broken bar (its poster) and the rest show after a moment
    var v = crack.querySelector('.fcrack'), go = false;
    var start = function (playing) {
      if (go) return; go = true;
      if (playing) at(970, function () { crack.classList.add('shake'); Snd('bad'); });   // the bar cracks
      rest(playing ? 1900 : 0);
    };
    v.addEventListener('playing', function () { start(true); }, {once: true});
    play(v);
    at(2500, function () { start(false); });
    return;
  }
  rest(shown);
  function rest(from) {
    after.forEach(function (el, k) { at(from + k * 160, function () { el.classList.add('in'); }); });
    at(from + after.length * 160 + 400, function () { card.classList.remove('revealing'); card.classList.add('revealed'); });
  }
})();
