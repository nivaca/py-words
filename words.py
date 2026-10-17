#!/usr/bin/env python3
"""py-words, a Latin dictionary: python3 words.py

    words                          interactive
    words amicus est               look up words (a line of Latin)
    words -f in.txt [-o out.txt]   a file of lines ('-': standard input);
                                   a line ~E or ~L changes the language
    words -e friend [--pos N]      English to Latin
    words -m ...                   only dictionary forms and meanings

In interactive mode a line is looked up, unless it starts with one of
these:

    ~E / ~L     English to Latin / Latin to English
    @FILE       look up the lines of FILE
    #           change the parameters
    !           change the developer modes
    ?           this help

An empty line twice, or end of input, quits.
"""

from __future__ import annotations

from version import check_python
check_python()          # (before the modules that need it)

import argparse
import os
import sys
from collections.abc import Callable

from version import ABOUT, CREDITS
import config
from config import ConfigError
from helptext import HELP
from history import History
from lexicon import Lexicon, default_datadir
from settings import Settings, MODES, DEV_MODES, is_command_character
from session import Session
from xmldata import DataError

SCREEN_LINES = 20

Ask = Callable[[str], str]


def load(datadir: str) -> Lexicon:
    try:
        return Lexicon.load(datadir)
    except (DataError, FileNotFoundError) as e:
        sys.exit(f'words: {e}')


# ---------------------------------------------------------------------------
#  The settings dialogues

class _Skip(Exception):
    """A reply of spaces skips the rest of a dialogue."""


def _yes_no(settings: Settings, name: str, ask: Ask, say) -> None:
    current = getattr(settings, name)
    while True:
        reply = ask(f"{name.upper():<34} {'Y' if current else 'N'} => ")
        if reply == '':
            return
        if not reply.strip():
            raise _Skip()
        c = reply.strip()[0].upper()
        if c == '?':
            say(HELP.get(name, '(no help)'))
        elif c in 'YN':
            setattr(settings, name, c == 'Y')
            return
        else:
            say('Answer Y or N, ? for help, Enter to keep, a space to stop.')


def _character(settings: Settings, name: str, ask: Ask, say) -> None:
    others = {getattr(settings, n) for n in (
        'start_file_character', 'change_parameters_character',
        'change_developer_modes_character') if n != name} | {'~'}
    while True:
        reply = ask(f"{name.upper():<34} '{getattr(settings, name)}' => ")
        if reply == '':
            return
        if not reply.strip():
            raise _Skip()
        c = reply.strip()[0]
        if c == '?':
            say(HELP['characters'])
        elif is_command_character(c) and c not in others:
            setattr(settings, name, c)
            return
        else:
            say('Not an acceptable character: it may conflict with another.')


def _save(ask: Ask, say, settings: Settings, section: str) -> None:
    """Offers to save the parameters or developer modes (SECTION) in the
    configuration file."""
    while True:
        reply = ask('Save these settings? (N) => ').strip()
        if reply[:1] == '?':
            say(HELP['save'])
            continue
        if reply[:1].upper() == 'Y':
            try:
                say(f'Saved in {settings.save(section)}')
            except (OSError, ConfigError) as e:
                say(f'Not saved: {e}')
        return


def change_parameters(session: Session, ask: Ask, say) -> None:
    """The # dialogue."""
    s = session.settings
    say('Answer Y or N; Enter keeps the current value, ? gives help, a space '
        'skips the rest.')
    try:
        for name in MODES:
            if name == 'write_output_to_file' and not s.have_output_file:
                s.write_output_to_file = False
                continue
            _yes_no(s, name, ask, say)
            if name == 'have_output_file':
                session.settings_changed()
        _save(ask, say, s, 'parameters')
    except _Skip:
        pass
    session.settings_changed()


def change_developer_modes(session: Session, ask: Ask, say) -> None:
    """The ! dialogue."""
    s = session.settings
    say('Answer Y or N; Enter keeps the current value, ? gives help, a space '
        'skips the rest.  Developer modes are for special purposes.')
    skip = {'write_statistics_file': not s.have_statistics_file,
            'for_word_list_check': False,
            'do_only_fixes': not s.do_fixes,
            'do_fixes_anyway': not s.do_fixes,
            'do_medieval_tricks': not s.do_tricks}
    try:
        for name in DEV_MODES:
            if name == 'for_word_list_check' and \
                    not s.do_only_initial_word:
                s.for_word_list_check = False
                continue
            if skip.get(name):
                continue
            _yes_no(s, name, ask, say)
            if name == 'have_statistics_file':
                session.settings_changed()
                skip['write_statistics_file'] = not s.have_statistics_file
        for name in ('start_file_character', 'change_parameters_character',
                     'change_developer_modes_character'):
            _character(s, name, ask, say)
        _save(ask, say, s, 'developer')
    except _Skip:
        pass
    session.settings_changed()


# ---------------------------------------------------------------------------
#  Interactive use

def banner(session: Session) -> str:
    s = session.settings
    return CREDITS + '\n\n' + (
        "Type a Latin word or line and Enter.  ~E: English to Latin, "
        "~L: back to Latin.\n"
        f"{s.start_file_character}FILE: look up a file   "
        f"{s.change_parameters_character}: parameters   "
        f"{s.change_developer_modes_character}: developer modes   "
        "?: help\n"
        "An empty line twice quits.")


class Pager:
    """Writes text, pausing after each screenful if asked to."""

    def __init__(self, session: Session, ask: Ask, write):
        self.session = session
        self.ask = ask
        self._write = write
        self.count = 0

    def reset(self):
        self.count = 0

    def write(self, text: str):
        if not self.session.settings.pause_in_screen_output:
            self._write(text)
            return
        for line in text.splitlines(keepends=True):
            if self.count >= SCREEN_LINES:
                try:
                    self.ask('-- more (Enter) --')
                except EOFError:
                    pass
                self.count = 0
            self._write(line)
            self.count += 1


def repl(session: Session, ask: Ask = input,
         write: Callable[[str], None] = None,
         remember: Callable[[str], None] | None = None) -> None:
    """The interactive mode.  REMEMBER(line) is told each line typed at
    the prompt (for the history)."""
    write = write or (lambda text: print(text, end='', flush=True))

    def say(text):
        write(text + '\n')
    pager = Pager(session, ask, write)
    session.write = pager.write
    say(banner(session))
    blank = 0
    while True:
        try:
            line = ask('=> ')
        except (EOFError, KeyboardInterrupt):
            write('\n')
            return
        pager.reset()
        if remember and line.strip():
            remember(line)
        if not line.strip():
            blank += 1
            if blank >= 2:
                return
            say('(another empty line quits)')
            continue
        blank = 0
        s = session.settings
        first = line.lstrip()[0]
        if first == '~':
            say(session.set_language(line.lstrip()[1:2]))
        elif first == s.start_file_character:
            run_file(session, line.lstrip()[1:].strip(), say)
        elif first == s.change_parameters_character:
            change_parameters(session, ask, say)
        elif first == s.change_developer_modes_character:
            change_developer_modes(session, ask, say)
        elif line.strip() == '?':
            say(interactive_help(s))
        else:
            session.process(line)


def line_history() -> Callable[[str], None]:
    """Line editing for input(), with the history of the searches (Up and
    Down bring them back, also those of earlier sessions and of the
    window).  Returns what remembers a search."""
    history = History()
    try:
        import readline
    except ImportError:                 # (no line editing: Windows)
        return history.add
    try:
        readline.set_auto_history(False)    # (not the answers to # and !)
    except AttributeError:
        pass
    readline.clear_history()
    for line in history.items:
        readline.add_history(line)

    def remember(line: str):
        history.add(line)
        readline.add_history(line.strip())
    return remember


def interactive_help(s: Settings) -> str:
    return '\n'.join([
        'Type a word or a line of Latin (or, after ~E, an English word).',
        '  ~E / ~L    English to Latin / Latin to English',
        f'  {s.start_file_character}FILE      look up each line of FILE',
        f'  {s.change_parameters_character}          change the parameters',
        f'  {s.change_developer_modes_character}          change the '
        'developer modes',
        'In the parameter dialogues, ? explains each setting.',
        'Up and Down bring back earlier searches (also those of earlier '
        'sessions).',
        'An empty line twice, or Ctrl-D, quits.'])


def feed(session: Session, lines, say=None) -> None:
    """Looks up LINES; a line ~E or ~L changes the language."""
    for line in lines:
        text = line.strip()
        if not text:
            continue
        if text.startswith('~'):
            message = session.set_language(text[1:2])
            if say is not None:
                say(message)
        else:
            session.process(line)


def run_file(session: Session, name: str, say) -> None:
    try:
        with open(name, encoding='utf-8', errors='replace') as f:
            feed(session, f, say)
    except OSError as e:
        say(f'Cannot read {name}: {e.strerror}')


# ---------------------------------------------------------------------------

class _Credits(argparse.Action):
    """--version: the credits, as written (argparse would rewrap them)."""

    def __call__(self, parser, namespace, values, option_string=None):
        print(ABOUT)
        parser.exit()


def main(argv: list[str] | None = None, meanings_only: bool = False):
    parser = argparse.ArgumentParser(
        prog='meanings' if meanings_only else 'words',
        description="py-words, based on William Whitaker's WORDS: a "
                    "Latin-English dictionary that "
                    "analyses inflected Latin words.  With no arguments it "
                    "is interactive.",
        epilog="In interactive mode, type ? for help.")
    parser.add_argument('words', nargs='*', metavar='WORD',
                        help='Latin words (or, with -e, an English word)')
    parser.add_argument('-f', '--file',
                        help="look up each line of FILE ('-' for standard "
                             "input)")
    parser.add_argument('-o', '--output', help='write the results to OUTPUT')
    parser.add_argument('-e', '--english', action='store_true',
                        help='English to Latin')
    parser.add_argument('--pos', help='with -e: only this part of speech '
                                      '(N, V, ADJ, PREP ...)')
    parser.add_argument('-m', '--meanings-only', action='store_true',
                        default=meanings_only,
                        help='show only dictionary forms and meanings')
    parser.add_argument('--glosses', action=argparse.BooleanOptionalAction,
                        default=None,
                        help='write the analyses in Leipzig glossing '
                             'abbreviations (GEN.PL), or with --no-glosses '
                             'in words (genitive plural); this time only '
                             '(the setting is use_glosses)')
    parser.add_argument('--datadir', default=None,
                        help='the folder with the data files (default: '
                             '$WHITAKERS_WORDS_DATADIR, the folder in the '
                             'configuration file, or the data folder next '
                             'to the program)')
    parser.add_argument('--config', action='store_true',
                        help='show where the configuration file is')
    parser.add_argument('--clear-history', action='store_true',
                        help='forget the earlier searches, and exit')
    parser.add_argument('--version', action=_Credits, nargs=0,
                        help='show the version and credits, and exit')
    args = parser.parse_args(argv)

    datadir = args.datadir or default_datadir()
    settings = Settings()
    messages = settings.load(datadir)
    if args.config:
        print(make_config(settings))
        return
    if args.clear_history:
        History().clear()
        print('The history of the searches is cleared.')
        return
    interactive = not args.words and not args.file and sys.stdin.isatty()
    lexicon = load(datadir)

    out = sys.stdout
    if args.output:
        try:
            out = open(args.output, 'w', encoding='utf-8')
        except OSError as e:
            sys.exit(f'words: cannot write {args.output}: {e.strerror}')
    if args.glosses is not None:
        settings.use_glosses = args.glosses
    session = Session(lexicon, settings, args.meanings_only, out.write)
    session.english = args.english
    try:
        if interactive:
            for m in messages:
                print(m)
            repl(session, remember=line_history())
        elif args.words:
            words = list(args.words)
            if args.english and args.pos:
                words = words[:1] + [args.pos]
            session.process(' '.join(words))
        else:
            source = sys.stdin if args.file in (None, '-') else \
                open(args.file, encoding='utf-8', errors='replace')
            with source:
                feed(session, source)
    except BrokenPipeError:
        pass
    finally:
        session.close()
        if out is not sys.stdout:
            out.close()


def make_config(settings: Settings) -> str:
    """Says where the configuration file is (it is made at start-up, if it
    can be)."""
    path = config.config_path()
    if os.path.exists(path):
        return f'The configuration file is {path}'
    sys.exit(f'words: cannot create {path}')


def meanings(argv: list[str] | None = None):
    """`meanings`: WORDS showing only dictionary forms and meanings."""
    main(argv, meanings_only=True)


if __name__ == '__main__':
    main()
