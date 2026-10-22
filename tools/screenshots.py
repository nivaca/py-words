#!/usr/bin/env python3
"""Takes the screenshots of the README: the four programs (the command
line, the window, the terminal in full screen and the web page), each in
English and in Spanish, looking up the same word.

    python3 tools/screenshots.py [-o FOLDER] [--only cli,gui,tui,web]
                                 [--langs en,es] [--word perspicio]

It writes FOLDER/KIND_LANG.png (by default in docs/img/, where the
READMEs take them from).  Each program runs with settings of its own, in a
temporary folder, so the user's settings and history are not touched:

* the window (words_gui.py) in dark mode, as in the README; only its own
  window is captured, with ImageMagick's import, never the screen;
* the web page (words_web.py) from its server, in light mode, taken by
  Chrome without a window (--headless --screenshot);
* the command line (words.py, interactive) and the terminal in full screen
  (words_tui.py) in a hidden tmux terminal of a fixed size; what it shows,
  with its colours, is drawn in a window of Tk like a terminal, and that
  window is captured.

It needs Linux with an X display (XWayland is enough), ImageMagick, tmux
and Google Chrome (or Chromium); the program itself needs none of them.
"""

import argparse
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import tkinter as tk
import urllib.parse
import urllib.request
from tkinter import font as tkfont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
KINDS = ('cli', 'gui', 'tui', 'web')

#  The size of the hidden terminals (columns, lines), of the window and of
#  the web page (pixels)
TERMINAL = {'cli': (110, 22), 'tui': (100, 30)}
WINDOW = '1000x560'
PAGE = (1000, 640)

#  The colours of the terminal drawn: those of Konsole's Breeze, its usual
#  scheme (background, text, then the 16 colours of the ANSI codes)
BACKGROUND, FOREGROUND = '#232627', '#fcfcfc'
ANSI = ['#232627', '#ed1515', '#11d116', '#f67400', '#1d99f3', '#9b59b6',
        '#1abc9c', '#fcfcfc', '#7f8c8d', '#c0392b', '#1cdc9a', '#fdbc4b',
        '#3daee9', '#8e44ad', '#16a085', '#ffffff']
FONTS = ('Hack', 'DejaVu Sans Mono', 'Liberation Mono', 'Monospace')


def say(text: str):
    print(text, flush=True)


# ---------------------------------------------------------------------------
#  Settings of their own for each program

def settings_folder(lang: str, dark: bool) -> str:
    """A temporary folder with a configuration file: the interface and the
    meanings in LANG, dark or light."""
    folder = tempfile.mkdtemp(prefix=f'py-words-shot-{lang}-')
    with open(os.path.join(folder, 'config.toml'), 'w',
              encoding='utf-8') as f:
        f.write(f'[parameters]\nlanguage = "{lang}"\ninterface = "{lang}"\n'
                f'\n[appearance]\ndark_mode = {str(dark).lower()}\n')
    return folder


def environment(folder: str) -> dict:
    env = dict(os.environ)
    env['WHITAKERS_WORDS_CONFIG'] = folder
    env['WHITAKERS_WORDS_HISTORY'] = os.path.join(folder, 'history')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return env


# ---------------------------------------------------------------------------
#  The window

def gui(lang: str, word: str, out: str):
    """The window, in a process of its own (with its settings)."""
    folder = settings_folder(lang, dark=True)
    subprocess.run([sys.executable, os.path.abspath(__file__), '--child-gui',
                    word, out], env=environment(folder), check=True)
    shutil.rmtree(folder, ignore_errors=True)


def gui_child(word: str, out: str):
    sys.path.insert(0, ROOT)
    import interface
    import words_gui
    interface.use_configured()
    root = tk.Tk(className=words_gui.WM_CLASS)
    words_gui.set_icon(root)
    root.geometry(WINDOW)
    app = words_gui.App(root, DATA)

    def wait(ready, seconds=60):
        end = time.time() + seconds
        while time.time() < end:
            root.update()
            if ready():
                return
            time.sleep(0.03)
        raise SystemExit('the window did not get ready')
    wait(lambda: app.session is not None and
         str(app.button['state']) == 'normal')
    app.entry.insert(0, word)
    app.lookup()
    wait(lambda: str(app.button['state']) == 'normal' and
         app.text.get('1.0', '2.0').strip() == word)
    app.entry.selection_clear()
    app.root.focus_set()
    for _ in range(20):                 # (all drawn)
        root.update()
        time.sleep(0.03)
    #  The menu bar is a window of its own (Tk keeps it outside the window,
    #  and import does not take it with it): both are taken, and put one
    #  over the other.  Only the program's windows, never the screen.
    clones = [str(w) for w in root.tk.call('winfo', 'children', '.')
              if str(w).startswith('.#')]      # (the menu bar on screen)
    menu_bar = root.tk.call('winfo', 'id', clones[0]) if clones else None
    if menu_bar:
        top = out + '.menu.png'
        capture(menu_bar, top)
        capture(root.winfo_id(), out + '.window.png')
        subprocess.run([magick(), top, out + '.window.png', '-append', out],
                       check=True)
        os.remove(top)
        os.remove(out + '.window.png')
    else:
        capture(root.winfo_id(), out)
    root.destroy()


def magick() -> str:
    """ImageMagick's command for putting images together."""
    return 'magick' if shutil.which('magick') else 'convert'


def capture(window_id, out: str):
    """The window WINDOW_ID (only it) as an image."""
    subprocess.run(['import', '-window', str(window_id), out], check=True)


# ---------------------------------------------------------------------------
#  The web page

def free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def chrome() -> str:
    for name in ('google-chrome', 'chromium-browser', 'chromium'):
        if shutil.which(name):
            return name
    raise SystemExit('Chrome or Chromium is needed for the web page')


def web(lang: str, word: str, out: str):
    folder = settings_folder(lang, dark=False)
    port = free_port()
    server = subprocess.Popen(
        [sys.executable, os.path.join(ROOT, 'words_web.py'), '--no-browser',
         '--port', str(port)], env=environment(folder),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        url = f'http://127.0.0.1:{port}/'
        end = time.time() + 60
        while True:
            try:
                urllib.request.urlopen(url, timeout=2).read()
                break
            except OSError:
                if time.time() > end or server.poll() is not None:
                    raise SystemExit('the web server did not start')
                time.sleep(0.3)
        width, height = PAGE
        subprocess.run(
            [chrome(), '--headless=new', '--disable-gpu', '--hide-scrollbars',
             f'--window-size={width},{height}', f'--screenshot={out}',
             f'--user-data-dir={os.path.join(folder, "chrome")}',
             '--force-prefers-reduced-motion',
             f'{url}?{urllib.parse.urlencode({"q": word})}'],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=120)
    finally:
        server.terminate()
        server.wait()
        shutil.rmtree(folder, ignore_errors=True)


# ---------------------------------------------------------------------------
#  The terminals: tmux, then the screen drawn with Tk

class Tmux:
    """A hidden terminal of a size of its own, on a server of its own."""

    def __init__(self, columns: int, lines: int, command: list[str],
                 env: dict):
        self.socket = f'py-words-shots-{os.getpid()}'
        settings = {k: env[k] for k in ('WHITAKERS_WORDS_CONFIG',
                                         'WHITAKERS_WORDS_HISTORY',
                                         'PYTHONDONTWRITEBYTECODE')}
        self.run('-f', '/dev/null', 'new-session', '-d', '-s', 'shot',
                 '-x', str(columns), '-y', str(lines),
                 *[a for k, v in settings.items() for a in ('-e', f'{k}={v}')],
                 ' '.join(map(_quoted, command)))
        self.run('set-option', '-g', 'status', 'off')

    def run(self, *args) -> str:
        return subprocess.run(['tmux', '-L', self.socket, *args],
                              capture_output=True, text=True,
                              check=True).stdout

    def keys(self, *keys):
        self.run('send-keys', '-t', 'shot', *keys)

    def screen(self, colours: bool = False) -> str:
        return self.run('capture-pane', '-p', '-t', 'shot',
                        *(['-e'] if colours else []))

    def wait_for(self, text: str, seconds: float = 60):
        end = time.time() + seconds
        while text not in self.screen():
            if time.time() > end:
                raise SystemExit(f'did not see "{text}" in the terminal')
            time.sleep(0.2)
        time.sleep(0.5)                 # (the rest drawn too)

    def close(self):
        subprocess.run(['tmux', '-L', self.socket, 'kill-server'],
                       capture_output=True)


def _quoted(arg: str) -> str:
    return "'" + arg.replace("'", "'\\''") + "'"


def cli(lang: str, word: str, out: str):
    folder = settings_folder(lang, dark=False)
    columns, lines = TERMINAL['cli']
    term = Tmux(columns, lines, [sys.executable,
                                 os.path.join(ROOT, 'words.py')],
                environment(folder))
    try:
        term.wait_for('=>')             # (tmux leaves out the last space)
        term.keys(word, 'Enter')
        end = time.time() + 60
        while not (term.screen().rstrip().endswith('\n=>') and
                   term.screen().count('=>') >= 2):     # (all shown)
            if time.time() > end:
                raise SystemExit('the results did not come')
            time.sleep(0.2)
        #  (from the welcome text on: the lines before it only say which
        #  settings are used, here a temporary folder)
        lines = term.screen(colours=True).split('\n')
        start = next((i for i, line in enumerate(lines) if '~E' in line), 0)
        draw('\n'.join(lines[start:]), columns, out)
    finally:
        term.close()
        shutil.rmtree(folder, ignore_errors=True)


def tui(lang: str, word: str, out: str):
    folder = settings_folder(lang, dark=False)
    columns, lines = TERMINAL['tui']
    term = Tmux(columns, lines, [sys.executable,
                                 os.path.join(ROOT, 'words_tui.py')],
                environment(folder))
    try:
        term.wait_for('F10')            # (the keys, on the last line)
        term.keys(word, 'Enter')
        term.wait_for('-')              # (stem-ending, in the results)
        time.sleep(1)
        draw(term.screen(colours=True), columns, out)
    finally:
        term.close()
        shutil.rmtree(folder, ignore_errors=True)


SGR = re.compile(r'\x1b\[([0-9;]*)m')


def styled(text: str) -> list[tuple[str, tuple]]:
    """TEXT (with ANSI codes) as (piece, (foreground, background, bold))."""
    out = []
    fg, bg, bold, reverse = None, None, False, False
    at = 0
    for m in SGR.finditer(text):
        if m.start() > at:
            out.append((text[at:m.start()], _style(fg, bg, bold, reverse)))
        at = m.end()
        codes = [int(c) if c else 0 for c in m.group(1).split(';')]
        i = 0
        while i < len(codes):
            c = codes[i]
            if c == 0:
                fg, bg, bold, reverse = None, None, False, False
            elif c == 1:
                bold = True
            elif c == 22:
                bold = False
            elif c == 7:
                reverse = True
            elif c == 27:
                reverse = False
            elif 30 <= c <= 37 or 90 <= c <= 97:
                fg = ANSI[c - 30 if c < 90 else c - 82]
            elif 40 <= c <= 47 or 100 <= c <= 107:
                bg = ANSI[c - 40 if c < 100 else c - 92]
            elif c == 39:
                fg = None
            elif c == 49:
                bg = None
            elif c in (38, 48) and i + 2 < len(codes) and codes[i + 1] == 5:
                colour = _colour256(codes[i + 2])
                fg, bg = (colour, bg) if c == 38 else (fg, colour)
                i += 2
            elif c in (38, 48) and i + 4 < len(codes) and codes[i + 1] == 2:
                r, g, b = codes[i + 2:i + 5]
                colour = f'#{r:02x}{g:02x}{b:02x}'
                fg, bg = (colour, bg) if c == 38 else (fg, colour)
                i += 4
            i += 1
    out.append((text[at:], _style(fg, bg, bold, reverse)))
    return out


def _style(fg, bg, bold, reverse) -> tuple:
    fg, bg = fg or FOREGROUND, bg or BACKGROUND
    if reverse:
        fg, bg = bg, fg
    return fg, bg, bold


def _colour256(n: int) -> str:
    if n < 16:
        return ANSI[n]
    if n >= 232:
        v = 8 + (n - 232) * 10
        return f'#{v:02x}{v:02x}{v:02x}'
    n -= 16
    steps = [0, 95, 135, 175, 215, 255]
    r, g, b = steps[n // 36], steps[n // 6 % 6], steps[n % 6]
    return f'#{r:02x}{g:02x}{b:02x}'


def draw(screen: str, columns: int, out: str):
    """The screen of a terminal (with its colours) as an image."""
    root = tk.Tk()
    root.title('py-words')
    families = set(tkfont.families(root))
    family = next((f for f in FONTS if f in families), 'TkFixedFont')
    text_font = tkfont.Font(root, family=family, size=12)
    bold_font = tkfont.Font(root, family=family, size=12, weight='bold')
    lines = screen.rstrip('\n').split('\n')
    t = tk.Text(root, width=columns, height=len(lines), font=text_font,
                background=BACKGROUND, foreground=FOREGROUND, padx=12,
                pady=10, borderwidth=0, highlightthickness=0,
                insertwidth=0, wrap='none')
    t.pack()
    tags = {}
    for n, line in enumerate(lines):
        for piece, (fg, bg, bold) in styled(line):
            key = (fg, bg, bold)
            if key not in tags:
                tags[key] = f's{len(tags)}'
                t.tag_config(tags[key], foreground=fg, background=bg,
                             font=bold_font if bold else text_font)
            t.insert('end', piece, tags[key])
        if n < len(lines) - 1:
            t.insert('end', '\n')
    t.config(state='disabled')
    root.update()
    for _ in range(20):
        root.update()
        time.sleep(0.03)
    capture(root.winfo_id(), out)
    root.destroy()


# ---------------------------------------------------------------------------

TAKE = {'cli': cli, 'gui': gui, 'tui': tui, 'web': web}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Take the screenshots of the four programs, in English '
                    'and Spanish (for the READMEs).')
    parser.add_argument('-o', '--output',
                        default=os.path.join(ROOT, 'docs', 'img'),
                        help='the folder of the images (default: docs/img)')
    parser.add_argument('--only', default=','.join(KINDS),
                        help='which programs: cli,gui,tui,web')
    parser.add_argument('--langs', default='en,es',
                        help='which languages (default: en,es)')
    parser.add_argument('--word', default='perspicio',
                        help='the word looked up (default: perspicio)')
    parser.add_argument('--child-gui', nargs=2, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.child_gui:
        gui_child(*args.child_gui)
        return
    if not (os.environ.get('DISPLAY') and shutil.which('import')):
        raise SystemExit('this needs an X display and ImageMagick (import)')
    kinds = [k for k in args.only.split(',') if k]
    for kind in kinds:
        if kind not in TAKE:
            raise SystemExit(f'unknown program: {kind}')
        if kind in ('cli', 'tui') and not shutil.which('tmux'):
            raise SystemExit('tmux is needed for cli and tui')
    os.makedirs(args.output, exist_ok=True)
    for lang in args.langs.split(','):
        for kind in kinds:
            out = os.path.join(args.output, f'{kind}_{lang}.png')
            say(f'{kind} ({lang}) -> {out}')
            TAKE[kind](lang, args.word, out)


if __name__ == '__main__':
    main()
