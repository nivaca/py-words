"""The history of the searches, shared by the command line and the window
and kept between sessions in a file:

    Linux     $XDG_STATE_HOME/py-words/history (usually ~/.local/state)
    macOS     ~/Library/Application Support/py-words/history
    Windows   %LOCALAPPDATA%\\py-words\\history

($PY_WORDS_HISTORY names another file; set to nothing, no history
is kept.)  The file has one search per line, the oldest first; the last
MAX are kept, and a search the same as the one before is not added again.
"""

from __future__ import annotations

import os
import sys

import config

MAX = 1000


def history_path() -> str | None:
    """The history file (None: no history)."""
    env = config.env('HISTORY')
    if env is not None:
        return env or None
    home = os.path.expanduser('~')
    if sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA') or \
            os.path.join(home, 'AppData', 'Local')
    elif sys.platform == 'darwin':
        base = os.path.join(home, 'Library', 'Application Support')
    else:
        base = os.environ.get('XDG_STATE_HOME') or \
            os.path.join(home, '.local', 'state')
    return os.path.join(base, 'py-words', 'history')


class History:
    def __init__(self, path: str | None = ''):
        """PATH: the file ('' the usual one, None no file: the history
        lasts only this session)."""
        self.path = history_path() if path == '' else path
        self.items: list[str] = self._read()

    def _read(self) -> list[str]:
        if not self.path:
            return []
        try:
            with open(self.path, encoding='utf-8') as f:
                lines = [line.strip() for line in f]
        except (OSError, UnicodeDecodeError):
            return []
        items = []
        for line in lines:
            if line and (not items or items[-1] != line):
                items.append(line)
        return items[-MAX:]

    def add(self, line: str) -> None:
        """Remembers a search (in the file too, if it can be written)."""
        line = ' '.join(line.split())
        if not line or (self.items and self.items[-1] == line):
            return
        self.items.append(line)
        del self.items[:-MAX]
        if not self.path:
            return
        try:
            os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
            with open(self.path, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
            if os.path.getsize(self.path) > 200 * MAX:     # (trim it)
                self._write()
        except OSError:
            pass                        # (it lasts for this session)

    def _write(self) -> None:
        tmp = self.path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            f.writelines(line + '\n' for line in self.items)
        os.replace(tmp, self.path)

    def recent(self, limit: int = 50) -> list[str]:
        """The latest searches, newest first, each once."""
        seen, out = set(), []
        for line in reversed(self.items):
            if line not in seen:
                seen.add(line)
                out.append(line)
                if len(out) == limit:
                    break
        return out

    def clear(self) -> None:
        self.items = []
        if self.path:
            try:
                os.remove(self.path)
            except FileNotFoundError:
                pass
