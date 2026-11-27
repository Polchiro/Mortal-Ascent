"""No page reloads on the Bag and the Techniques page (web/static/softnav.js, docs/web.md "No page reloads")."""
import os

STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "static")


def test_the_bag_and_techniques_pages_change_softly():
    for page, cls in (("inventory", "inventory"), ("techniques", "techpage")):
        html = open(f"web/templates/{page}.html").read()
        assert f'<main class="{cls}" data-soft>' in html and "asset('softnav.js')" in html, page
    assert "data-soft-reveal" in open("web/templates/inventory.html").read()       # the item's details, on a phone


def test_the_script_falls_back_to_an_ordinary_load():
    js = open(os.path.join(STATIC, "softnav.js")).read()
    assert "opts.form.submit()" in js and "window.location.href = url" in js        # anything odd: the page as before
    assert "u.pathname !== location.pathname" in js                                  # only the page's own links
    assert "history.pushState" in js and "popstate" in js                            # Back still works
