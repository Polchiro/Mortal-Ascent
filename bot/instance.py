"""
Only one copy of the bot may run at a time.

If the bot is started twice (two terminals, an old window still running, or a second copy of the
repo folder), every copy reads every "m ..." message and answers it, so one command runs twice.
Three guards stop that:

1. At startup the bot locks a file next to the database AND a file in the computer's temp folder
   named after its token (a hash of it, never the token itself). A second copy on the same
   computer can't get the locks and stops with a clear message, even if it runs from another
   folder. The operating system lets go of the locks when the bot exits, even after a crash.
2. Every "m" message is claimed in the database before it is answered (db.claim_message), so
   copies that share a database answer each message once.
3. "m ping" tells you which computer and process answered. If you get two answers, two copies
   are running; the computer name tells you where the other one is.

A copy on another computer or a hosting service can't be seen by any of these, since it has its
own files. Stop it there, or reset the bot token in the Discord Developer Portal (that logs every
copy out; put the new token in .env).
"""
import hashlib
import os
import socket
import tempfile
import time

STARTED_AT = time.time()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lock(path):
    f = open(path, "a+")
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


def token_lock_path(token):
    digest = hashlib.sha256(token.encode()).hexdigest()[:16]
    return os.path.join(tempfile.gettempdir(), f"mortal-ascent-{digest}.lock")


def acquire(db_path, token=None):
    """Take the locks. Returns the open lock files (keep them open while the bot runs),
    or None if another copy of the bot already holds one."""
    paths = [f"{db_path}.lock"] + ([token_lock_path(token)] if token else [])
    held = []
    for path in paths:
        f = _lock(path)
        if f is None:
            for g in held:
                g.close()
            return None
        held.append(f)
    return held


def code_version():
    """The short git commit this copy runs, or "unknown"."""
    try:
        git = os.path.join(ROOT, ".git")
        with open(os.path.join(git, "HEAD")) as f:
            head = f.read().strip()
        if head.startswith("ref: "):
            ref = head[5:]
            ref_file = os.path.join(git, *ref.split("/"))
            if os.path.exists(ref_file):
                with open(ref_file) as f:
                    return f.read().strip()[:7]
            with open(os.path.join(git, "packed-refs")) as f:
                for line in f:
                    if line.strip().endswith(ref):
                        return line.split()[0][:7]
            return "unknown"
        return head[:7]
    except OSError:
        return "unknown"


def describe():
    """One line naming this copy: computer, process, start time, code version."""
    return (f"🖥️ **{socket.gethostname()}** · process {os.getpid()} · started <t:{int(STARTED_AT)}:R> · "
            f"code `{code_version()}`")
