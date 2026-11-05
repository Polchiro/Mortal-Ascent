"""
Only one copy of the bot may run on the same database.

If the bot is started twice (two terminals, or an old window still running), both copies read
every "m ..." message and both answer it. That let one "m explore" start two expeditions at once,
because each copy keeps its own list of running sessions. So at startup the bot takes a lock on a
small file next to the database; a second copy can't get it and stops with a clear message.
The operating system lets go of the lock when the bot exits, even after a crash.
"""
import os


def acquire(db_path):
    """Lock '<db_path>.lock'. Returns the open lock file (keep it open while the bot runs),
    or None if another copy of the bot already holds it."""
    f = open(f"{db_path}.lock", "a+")
    try:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    return f
