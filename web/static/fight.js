/* The fight screen: send a move without leaving the page (no jump to the top), then swap in the next turn. */
(function () {
  var busy = false;

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
          now.replaceWith(document.importNode(next, true));   // same scroll position: nothing jumps
          busy = false;
          init();
        } else {
          location.replace('/explore/play');                  // the fight is over: the next page of the expedition
        }
      })
      .catch(function () { location.replace('/explore/play'); });
  }

  document.addEventListener('keydown', function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey || busy) return;
    var main = document.querySelector('main.battle');
    if (!main) return;
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
