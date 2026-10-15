"""Serialize canonical writes and index rebuilds across local agent processes."""

from contextlib import contextmanager
from functools import wraps
import os
from pathlib import Path
import threading

_guard = threading.Lock()
_locks = {}
_held = threading.local()


@contextmanager
def project_lock(root: Path):
    key = str(Path(root).resolve())
    with _guard:
        lock = _locks.setdefault(key, threading.RLock())
    with lock:
        held = getattr(_held, "projects", set())
        if key in held:
            yield
            return
        path = Path(key) / ".brain" / "index" / "write.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+b") as handle:
            if os.name == "nt":
                import msvcrt
                if handle.seek(0, os.SEEK_END) == 0:
                    handle.write(b"\0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX)
            _held.projects = held | {key}
            try:
                yield
            finally:
                _held.projects = held
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle, fcntl.LOCK_UN)


def serialized(function):
    @wraps(function)
    def wrapped(root, *args, **kwargs):
        with project_lock(root):
            return function(root, *args, **kwargs)
    return wrapped
