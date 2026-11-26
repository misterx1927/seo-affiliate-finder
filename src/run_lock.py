"""Exclusive, OS-released process lock to prevent overlapping runs."""
import os
from pathlib import Path

class RunLocked(RuntimeError):
    pass

class RunLock:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.file = None
    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("a+b")
        self.file.seek(0)
        if os.name == "nt":
            import msvcrt
            try: msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                self.file.close()
                raise RunLocked("Another run is active") from exc
        else:
            import fcntl
            try: fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                self.file.close()
                raise RunLocked("Another run is active") from exc
        return self
    def __exit__(self, *args):
        if os.name == "nt":
            import msvcrt
            self.file.seek(0)
            msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        self.file.close()
