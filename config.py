"""The configuration file, config.toml, in the user's settings folder.

    Linux     $XDG_CONFIG_HOME/py-words/config.toml (usually ~/.config)
    macOS     ~/Library/Application Support/py-words/config.toml
    Windows   %APPDATA%\\py-words\\config.toml

($PY_WORDS_CONFIG names another folder.)  It has four sections:

    [data]         folder: where the data files are
    [parameters]   the parameters (changed with # in interactive mode)
    [developer]    the developer modes and command characters (!)
    [fonts]        the fonts of the windows
    [appearance]   dark_mode: whether the windows are dark

Every setting may be left out, and then has its usual value.  The program
writes the file when settings are saved (with all the comments, but not
comments of one's own); it can also be edited by hand.  Its comments are
in the language of the interface.
"""

from __future__ import annotations

import os
import sys
import tomllib

from helptext import HELP
from interface import N_, tr

CONFIG_FILE = 'config.toml'
SECTIONS = ('data', 'parameters', 'developer', 'fonts', 'appearance')


class ConfigError(Exception):
    """config.toml cannot be read."""


def env(name: str) -> str | None:
    """The environment variable $PY_WORDS_NAME, or the one of earlier
    versions, $WHITAKERS_WORDS_NAME (None if neither is set)."""
    for prefix in ('PY_WORDS_', 'WHITAKERS_WORDS_'):
        value = os.environ.get(prefix + name)
        if value is not None:
            return value
    return None


def config_dir() -> str:
    """Where the user's settings are kept: $PY_WORDS_CONFIG, else
    the usual settings folder of the system."""
    env_ = env('CONFIG')
    if env_:
        return env_
    if sys.platform == 'win32':
        base = os.environ.get('APPDATA') or \
            os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming')
    elif sys.platform == 'darwin':
        base = os.path.join(os.path.expanduser('~'), 'Library',
                            'Application Support')
    else:
        base = os.environ.get('XDG_CONFIG_HOME') or \
            os.path.join(os.path.expanduser('~'), '.config')
    return os.path.join(base, 'py-words')


def config_path() -> str:
    return os.path.join(config_dir(), CONFIG_FILE)


def read() -> dict[str, dict]:
    """The sections of the configuration file ({} if there is none);
    raises ConfigError if it is not valid TOML."""
    try:
        with open(config_path(), 'rb') as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        return {}
    except OSError as e:
        raise ConfigError(tr('cannot read {path}: {error}',
                                path=config_path(), error=e.strerror))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f'{config_path()}: {e}')
    return {name: value for name, value in data.items()
            if isinstance(value, dict)}


def section(name: str) -> dict:
    """One section of the file, or {} (also if the file is unreadable)."""
    try:
        return read().get(name, {})
    except ConfigError:
        return {}


def data_folder() -> str | None:
    """The data folder named in the file, if any."""
    folder = section('data').get('folder')
    if isinstance(folder, str) and folder.strip():
        return os.path.expanduser(folder.strip())
    return None


def update(name: str, values: dict) -> str:
    """Replaces section NAME with VALUES (none: removes it) and writes the
    file, keeping the other sections; returns its path.  Raises OSError if
    it cannot be written, ConfigError if the file there is unreadable (it
    is then left alone)."""
    data = read()
    if values:
        data[name] = dict(values)
    else:
        data.pop(name, None)
    write(data)
    return config_path()


def write(data: dict[str, dict]) -> None:
    os.makedirs(config_dir(), exist_ok=True)
    path = config_path()
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(render(data))
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
#  Writing TOML: the values are only booleans, integers and strings

def toml_value(value) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    text = str(value)
    for old, new in (('\\', '\\\\'), ('"', '\\"'), ('\n', '\\n'),
                     ('\t', '\\t')):
        text = text.replace(old, new)
    return f'"{text}"'


HEADER = N_('The settings of py-words.  Each setting can be left out (or '
            'the whole file deleted) to use its usual value.  The program '
            'rewrites this file when settings are saved: the values are '
            'kept, but not comments of your own.')

INTRO = {
    'data': N_('Where dictionary.xml and the other data files are; empty: '
               'the data folder next to the program.  (--datadir and '
               '$PY_WORDS_DATADIR come first.)'),
    'parameters': N_('The parameters (changed with # in interactive mode).'),
    'developer': N_('The developer modes and command characters (changed '
                    'with ! in interactive mode).'),
    'fonts': N_('The fonts of the windows (also changed with "Font…" and '
                'Ctrl and + or -).  Sizes are in points.'),
    'appearance': N_('The look of the windows and the web page: dark_mode = '
                     'true for dark, false for light (none: the web page '
                     'follows the system).  Also changed with the moon (or '
                     'sun) in the window and on the web page.'),
}
FONTS = N_('text_family and text_size: the results (a fixed-width font); '
           'ui_family and ui_size: the rest of the windows.')


def _comment(text: str, width: int = 76) -> list[str]:
    """TEXT as comment lines."""
    lines, line = [], '#'
    for word in text.split():
        if len(line) + 1 + len(word) > width and line != '#':
            lines.append(line)
            line = '#'
        line += ' ' + word
    lines.append(line)
    return lines


def _first_sentence(text: str) -> str:
    end = text.find('.  ')
    return text if end < 0 else text[:end + 1]


def render(data: dict[str, dict]) -> str:
    out = _comment(tr(HEADER)) + ['']
    names = [n for n in SECTIONS if n in data or n in ('data', 'fonts')] \
        + [n for n in data if n not in SECTIONS]
    for name in names:
        values = data.get(name, {})
        if name == 'data' and 'folder' not in values:
            values = {'folder': '', **values}
        out.append(f'[{name}]')
        if name in INTRO:
            out += _comment(tr(INTRO[name]))
        if name == 'fonts':
            out += _comment(tr(FONTS))
        for key, value in values.items():
            if name in ('parameters', 'developer') and key in HELP:
                out += _comment(_first_sentence(tr(HELP[key])))
            out.append(f'{key} = {toml_value(value)}')
        out.append('')
    return '\n'.join(out)
