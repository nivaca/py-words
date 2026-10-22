#!/usr/bin/env python3
"""Takes the screenshots of the README: the four programs (the command
line, the window, the terminal in full screen and the web page), each in
English and in Spanish, looking up the same word.

    python3 tools/screenshots.py [-o FOLDER] [--only cli,gui,tui,web]
                                 [--langs en,es] [--word perspicio]
                                 [--scale 2]

It writes FOLDER/KIND_LANG.png (by default in docs/img/, where the
READMEs take them from), at SCALE times the size of the screen (2 by
default, sharp on screens of high resolution).  Each program runs with
settings of its own, in a temporary folder, so the user's settings and
history are not touched:

* the window (words_gui.py) in dark mode, as in the README; only its own
  window is captured, with ImageMagick's import, never the screen.  If
  Xvfb is installed the window is opened there, out of sight and with
  room for any scale; if not, on the screen, and the scale is made
  smaller when the window would not fit;
* the web page (words_web.py) from its server, in light mode, taken by
  Chrome without a window (--headless --screenshot);
* the command line (words.py, interactive) and the terminal in full screen
  (words_tui.py) in a hidden tmux terminal of a fixed size; what it shows,
  with its colours, is written as a web page like a terminal, and Chrome
  takes it as the other.

It needs Linux with an X display (XWayland is enough) or Xvfb,
ImageMagick, tmux and Google Chrome (or Chromium); the program itself
needs none of them.
"""

import argparse
import html
import math
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
KINDS = ('cli', 'gui', 'tui', 'web')

#  The size of the hidden terminals (columns, lines), of the window and of
#  the web page (pixels, before the scale)
TERMINAL = {'cli': (110, 22), 'tui': (100, 30)}
WINDOW = (1000, 620)
PAGE = (1000, 640)
SCALE = 2

#  The colours of the terminal drawn: those of Konsole's Breeze, its usual
#  scheme (background, text, then the 16 colours of the ANSI codes)
BACKGROUND, FOREGROUND = '#232627', '#fcfcfc'
ANSI = ['#232627', '#ed1515', '#11d116', '#f67400', '#1d99f3', '#9b59b6',
        '#1abc9c', '#fcfcfc', '#7f8c8d', '#c0392b', '#1cdc9a', '#fdbc4b',
        '#3daee9', '#8e44ad', '#16a085', '#ffffff']
FONTS = ('Hack', 'DejaVu Sans Mono', 'Liberation Mono', 'monospace')
#  The terminal's letters (pixels, before the scale), the width of one
#  (that of these fonts, a little more) and the space around the text
FONT_SIZE, CHAR_WIDTH, LINE_HEIGHT, MARGIN = 15, 0.61, 1.3, 12


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

class Display:
    """Where the window is opened: an Xvfb of its own if there is one (out
    of sight, as large as needed), the screen if not."""

    def __init__(self, scale: float):
        self.server = None
        self.name = os.environ.get('DISPLAY', '')
        if shutil.which('Xvfb'):
            width, height = WINDOW
            size = f'{math.ceil(width * scale) + 200}x' \
                   f'{math.ceil(height * scale) + 400}x24'
            read, write = os.pipe()
            self.server = subprocess.Popen(
                ['Xvfb', '-displayfd', str(write), '-screen', '0', size,
                 '-nolisten', 'tcp'], pass_fds=(write,),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.close(write)
            with os.fdopen(read) as f:
                number = f.readline().strip()
            if not number:
                raise SystemExit('Xvfb did not start')
            self.name = f':{number}'

    def close(self):
        if self.server:
            self.server.terminate()
            self.server.wait()


def gui(lang: str, word: str, out: str, scale: float, display: Display):
    """The window, in a process of its own (with its settings)."""
    folder = settings_folder(lang, dark=True)
    env = environment(folder)
    env['DISPLAY'] = display.name
    env.pop('WAYLAND_DISPLAY', None)
    scale = fit(scale, display.name)
    #  (Tk's letters are drawn by Xft, which does not follow Tk's scaling
    #  but the dpi of fontconfig: this one, for this window only)
    env['FONTCONFIG_FILE'] = os.path.join(folder, 'fonts.conf')
    with open(env['FONTCONFIG_FILE'], 'w', encoding='utf-8') as f:
        f.write(f'''<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>
  <match target="pattern">
    <edit name="dpi" mode="assign"><double>{96 * scale}</double></edit>
  </match>
</fontconfig>
''')
    subprocess.run([sys.executable, os.path.abspath(__file__), '--child-gui',
                    word, out, str(scale)], env=env, check=True)
    shutil.rmtree(folder, ignore_errors=True)


def gui_child(word: str, out: str, scale: str):
    sys.path.insert(0, ROOT)
    import interface
    import words_gui
    interface.use_configured()
    root = tk.Tk(className=words_gui.WM_CLASS)
    #  (the fonts are given in points, so they grow with Tk's scaling; the
    #  window too, with its size)
    width, height = WINDOW
    scale = float(scale)
    root.tk.call('tk', 'scaling', 96 / 72 * scale)
    words_gui.set_icon(root)
    app = words_gui.App(root, DATA)
    root.geometry(f'{round(width * scale)}x{round(height * scale)}')

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


def fit(scale: float, display: str) -> float:
    """SCALE, or a smaller one if the window would not fit on the screen
    of DISPLAY (with the menu bar, and the panel of the desktop)."""
    width, height = WINDOW
    root = tk.Tk(screenName=display)
    room = min((root.winfo_screenwidth() - 20) / width,
               (root.winfo_screenheight() - 120) / height)
    root.destroy()
    if scale > room:
        say(f'  (the screen is too small for --scale {scale:g}: using '
            f'{room:.2f}; Xvfb gives room for any scale)')
        return room
    return scale


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


def shoot(url: str, size: tuple[int, int], out: str, scale: float,
          folder: str):
    """The page at URL, of SIZE (pixels before the scale), as an image."""
    width, height = size
    subprocess.run(
        [chrome(), '--headless=new', '--disable-gpu', '--hide-scrollbars',
         f'--window-size={width},{height}', f'--screenshot={out}',
         f'--force-device-scale-factor={scale:g}',
         f'--user-data-dir={os.path.join(folder, "chrome")}',
         '--force-prefers-reduced-motion', url],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=120)


def web(lang: str, word: str, out: str, scale: float, _display=None):
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
        shoot(f'{url}?{urllib.parse.urlencode({"q": word})}', PAGE, out,
              scale, folder)
    finally:
        server.terminate()
        server.wait()
        shutil.rmtree(folder, ignore_errors=True)


# ---------------------------------------------------------------------------
#  The terminals: tmux, then the screen as a web page

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


def cli(lang: str, word: str, out: str, scale: float, _display=None):
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
        draw('\n'.join(lines[start:]), columns, out, scale, folder)
    finally:
        term.close()
        shutil.rmtree(folder, ignore_errors=True)


def tui(lang: str, word: str, out: str, scale: float, _display=None):
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
        draw(term.screen(colours=True), columns, out, scale, folder)
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


def draw(screen: str, columns: int, out: str, scale: float, folder: str):
    """The screen of a terminal (with its colours) as an image: written as
    a web page, which Chrome takes."""
    lines = screen.rstrip('\n').split('\n')
    body = []
    for line in lines:
        for piece, (fg, bg, bold) in styled(line):
            weight = 'font-weight:bold;' if bold else ''
            body.append(f'<span style="color:{fg};background:{bg};{weight}">'
                        f'{html.escape(piece)}</span>')
        body.append('\n')
    family = ', '.join(f"'{f}'" if f != 'monospace' else f for f in FONTS)
    page = os.path.join(folder, 'terminal.html')
    with open(page, 'w', encoding='utf-8') as f:
        f.write(f'''<!doctype html><meta charset="utf-8"><style>
html, body {{ margin: 0; background: {BACKGROUND}; }}
pre {{ margin: 0; padding: {MARGIN}px; color: {FOREGROUND};
      font: {FONT_SIZE}px/{LINE_HEIGHT} {family}; }}
</style><pre>{''.join(body).rstrip()}</pre>''')
    size = (math.ceil(columns * FONT_SIZE * CHAR_WIDTH) + 2 * MARGIN,
            math.ceil(len(lines) * FONT_SIZE * LINE_HEIGHT) + 2 * MARGIN)
    shoot('file://' + page, size, out, scale, folder)
    #  (the width of the letters is only near: the space left over is cut,
    #  and the same margin put all round)
    subprocess.run([magick(), out, '-trim', '+repage', '-bordercolor',
                    BACKGROUND, '-border', str(round(MARGIN * scale)), out],
                   check=True)


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
    parser.add_argument('--scale', type=float, default=SCALE,
                        help='times the size on the screen (default: 2)')
    parser.add_argument('--child-gui', nargs=3, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.child_gui:
        gui_child(*args.child_gui)
        return
    kinds = [k for k in args.only.split(',') if k]
    for kind in kinds:
        if kind not in TAKE:
            raise SystemExit(f'unknown program: {kind}')
        if kind in ('cli', 'tui') and not shutil.which('tmux'):
            raise SystemExit('tmux is needed for cli and tui')
    if 'gui' in kinds and not (shutil.which('import') and (
            os.environ.get('DISPLAY') or shutil.which('Xvfb'))):
        raise SystemExit('the window needs ImageMagick (import) and an X '
                         'display or Xvfb')
    if args.scale <= 0:
        raise SystemExit('the scale must be more than 0')
    os.makedirs(args.output, exist_ok=True)
    display = Display(args.scale) if 'gui' in kinds else None
    try:
        for lang in args.langs.split(','):
            for kind in kinds:
                out = os.path.join(args.output, f'{kind}_{lang}.png')
                say(f'{kind} ({lang}) -> {out}')
                TAKE[kind](lang, args.word, out, args.scale, display)
    finally:
        if display:
            display.close()


if __name__ == '__main__':
    main()
