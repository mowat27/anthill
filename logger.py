import sys
from datetime import datetime


class Logger:
    """Minimal logger that writes levelled messages to stdout."""

    def __init__(self, name: str = None):
        self.name = name

    def _emit(self, level: str, msg: str):
        ts = datetime.utcnow().isoformat(timespec="seconds")
        prefix = f"{ts} [{level}]"
        if self.name:
            prefix += f" {self.name}:"
        print(f"{prefix} {msg}", file=sys.stdout)

    def info(self, msg: str):
        self._emit("INFO", msg)

    def debug(self, msg: str):
        self._emit("DEBUG", msg)

    def error(self, msg: str):
        self._emit("ERROR", msg)
