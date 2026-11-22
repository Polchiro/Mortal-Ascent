/* The alchemy craft's cauldron, alive (web/templates/alchemy_play.html .cscene; docs/web.md "Alchemy animations"):
   the clips from SHOAIB's videos (art/fx/alchemy/, scripts/make_alchemy_fx.py), laid on the dark card with `screen`
   so their black is see-through.

   Each decision reloads the page, so this remembers the last stage it showed (sessionStorage) to know what just
   happened: a herb went in (Add herbs again: the splash), a round of the Tribulation was weathered (its lightning),
   Condense has just begun (the light spirals in once, then the pill pulses), the craft has just blown up (the
   explosion, which then stays smoking; once per craft, by its id, since the live controls never pass through here). Loops (the fire, the Qi swirl, the storm, the pulse) just play. A clip shows
   only once it plays (class "on"), so a slow one never covers the still pictures with black. Nothing here touches the
   craft: the server has already decided everything. With reduced motion nothing plays (style.css shows the stills). */
(function () {
  'use strict';
  function init() {
  var scene = document.querySelector('.cscene:not(.lscene)');
  if (!scene) return;
  if (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var KEY = 'ma-alchemy-scene', prev = null;
  try { prev = JSON.parse(sessionStorage.getItem(KEY) || 'null'); } catch (e) {}
  var stage = scene.dataset.stage, turn = +scene.dataset.turn;
  var again = prev && prev.stage === stage && prev.turn < turn;     // a decision was made in this same stage
  try { sessionStorage.setItem(KEY, JSON.stringify({stage: stage, turn: turn})); } catch (e) {}

  function play(v, onEnd) {
    if (!v) return;
    v.addEventListener('playing', function () { v.classList.add('on'); }, {once: true});
    if (onEnd) v.addEventListener('ended', onEnd, {once: true});
    var p = v.play(); if (p && p.catch) p.catch(function () {});
  }
  function once(v, keepEnd) {                                   // a one-off: shows while it plays, then fades
    play(v, function () { if (!keepEnd) v.classList.remove('on'); });
  }

  scene.querySelectorAll('.cloop:not(.ccond)').forEach(function (v) { play(v); });

  if (again && stage === '2') once(scene.querySelector('.csplash'));          // a herb went in
  if (again && stage === '6') once(scene.querySelector('.clight'));           // the heavens struck

  if (stage === '4') {                                                         // Condense: in once, then the pulse
    var cin = scene.querySelector('.ccondin'), loop = scene.querySelector('.ccond');
    if (!(prev && prev.stage === '4') && cin) play(cin, function () { cin.classList.remove('on'); play(loop); });
    else play(loop);
  }

  if (stage === 'done') {                                                      // the cauldron blew up
    var boom = scene.querySelector('.cboom');
    if (boom) {
      scene.classList.add('live');
      var BOOM = 'ma-alchemy-boom', seen = null;                              // once per craft (its id), whatever page came
      try { seen = sessionStorage.getItem(BOOM); sessionStorage.setItem(BOOM, scene.dataset.craft); } catch (e) {}
      if (seen !== scene.dataset.craft) once(boom, true);                     // it happens now: the whole explosion
      else {                                                                   // the page again: it lies smoking
        boom.addEventListener('loadedmetadata', function () { boom.currentTime = Math.max(0, boom.duration - 0.2); boom.classList.add('on'); }, {once: true});
        if (boom.readyState >= 1) boom.dispatchEvent(new Event('loadedmetadata'));
      }
    }
  }
  }
  window.AlchemyScene = {init: init};      // static/alchemy_classic.js runs it again after each decision
  init();
})();
