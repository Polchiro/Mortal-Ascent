/* Soft page changes (docs/web.md "No page reloads"): on the Bag and the Techniques page, pressing Equip / Unequip /
   Learn / Read, picking an item or switching a tab no longer reloads the whole page and throws you back to the top.
   The same request goes to the server as before (the server still decides everything); only the answer is swapped in:
   the page's <main> and the top bar (for the coins) are replaced, the address bar follows, and you stay where you were
   on the page. Picking an item on a phone, where the item's details sit below the grid, brings them into view.
   Anything this can't handle (an error, a different page, an old browser) falls back to an ordinary page load. */
(function () {
  if (!window.fetch || !window.DOMParser || !document.querySelector('main[data-soft]')) return;
  var busy = false;

  function runScripts(root) {               // scripts inside the new <main> (the Techniques filter) run again
    root.querySelectorAll('script').forEach(function (old) {
      var s = document.createElement('script');
      s.textContent = old.textContent;
      old.replaceWith(s);
    });
  }

  function carry(old, fresh) {              // what you had set on the page stays: the Techniques filter, folded sections
    var show = old.dataset.show, btn = show && fresh.querySelector('.tfbtn[data-show="' + show + '"]');
    if (btn) btn.click();
    var was = old.querySelectorAll('details'), now = fresh.querySelectorAll('details');
    if (was.length === now.length) now.forEach(function (d, i) { if (d.className === was[i].className) d.open = was[i].open; });
  }

  function swap(html, url, opts) {
    var doc = new DOMParser().parseFromString(html, 'text/html');
    var fresh = doc.querySelector('main[data-soft]'), here = document.querySelector('main[data-soft]');
    if (!fresh || !here || fresh.className !== here.className) return false;   // a different page: load it for real
    var y = window.scrollY;
    here.replaceWith(fresh);
    var bar = doc.querySelector('header.topbar'), oldBar = document.querySelector('header.topbar');
    if (bar && oldBar) oldBar.replaceWith(bar);
    if (doc.title) document.title = doc.title;
    if (opts.push) history.pushState({ soft: true }, '', url); else history.replaceState({ soft: true }, '', url);
    runScripts(fresh);
    carry(here, fresh);
    window.scrollTo(0, y);
    var note = opts.post && fresh.querySelector('[role=status]');
    if (note) {                             // what the server said, where you can see it, if its own spot is off screen
      var nr = note.getBoundingClientRect();
      if (nr.bottom < 0 || nr.top > window.innerHeight) {
        var t = document.createElement('div');
        t.className = 'softtoast'; t.setAttribute('role', 'status'); t.innerHTML = note.innerHTML;
        document.body.appendChild(t);
        setTimeout(function () { t.classList.add('gone'); }, 2600);
        setTimeout(function () { t.remove(); }, 3200);
      }
    }
    if (opts.reveal) {
      var el = fresh.querySelector(opts.reveal);
      if (el) {
        var r = el.getBoundingClientRect();
        if (r.top > window.innerHeight - 80 || r.bottom < 0) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }
    return true;
  }

  function go(url, init, opts) {
    if (busy) return;
    busy = true;
    document.documentElement.classList.add('softbusy');
    fetch(url, Object.assign({ credentials: 'same-origin', redirect: 'follow' }, init))
      .then(function (res) {
        if (!res.ok || (res.headers.get('content-type') || '').indexOf('text/html') < 0) throw new Error('no');
        return res.text().then(function (html) {
          if (!swap(html, res.url, opts)) throw new Error('no');
        });
      })
      .catch(function () {
        if (init && init.method === 'POST') opts.form.submit(); else window.location.href = url;
      })
      .then(function () { busy = false; document.documentElement.classList.remove('softbusy'); });
  }

  document.addEventListener('submit', function (e) {
    var f = e.target;
    if (!f.closest('main[data-soft]') || (f.method || '').toLowerCase() !== 'post') return;
    e.preventDefault();
    var data = new FormData(f);
    if (e.submitter && e.submitter.name) data.append(e.submitter.name, e.submitter.value);
    go(f.action, { method: 'POST', body: new URLSearchParams(data) }, { form: f, push: false, post: true });
  });

  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('main[data-soft] a[href]');
    if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || a.target) return;
    var u = new URL(a.href, location.href);
    if (u.origin !== location.origin || u.pathname !== location.pathname) return;   // only this page's own tabs and items
    e.preventDefault();
    go(u.href, { method: 'GET' }, { push: true, reveal: u.searchParams.has('item') ? '[data-soft-reveal]' : null });
  });

  window.addEventListener('popstate', function (e) {
    if (e.state && e.state.soft) go(location.href, { method: 'GET' }, { push: false });
  });
  history.replaceState({ soft: true }, '', location.href);
})();
