"""Shared test setup. The shared rare herb events (web/herb_events.py) rise at random moments of the day, so they are
off for the tests unless one turns them on (tests/test_herb_events.py does): no other test meets one by chance."""
import os

os.environ.setdefault("MA_HERB_EVENTS", "off")
