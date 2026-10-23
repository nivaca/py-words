#!/usr/bin/env python3
"""py-words, a Latin dictionary: python3 words.py

    words                          interactive
    words amicus est               look up words (a line of Latin)
    words -f in.txt [-o out.txt]   a file of lines ('-': standard input);
                                   a line ~E or ~L changes the language
    words -e friend [--pos N]      English to Latin
    words -m ...                   only dictionary forms and meanings
    words --language es ...        the meanings in another language
                                   (--languages lists them)
    words --guide                  the help: how to search and read the
                                   results

In interactive mode a line is looked up, unless it starts with one of
these:

    ~E / ~L     English (the language of the meanings) to Latin / Latin
                to English
    ~H          the help: how to search and read the results
    ~A          about: the version and the credits
    @FILE       look up the lines of FILE
    #           change the parameters
    !           change the developer modes
    ?           this help

An empty line twice, or end of input, quits.  Ctrl-C stops what is being
done (a long list of results, a file, a dialogue), but does not quit.
"""

from __future__ import annotations

from version import check_python
check_python()          # (before the modules that need it)

import argparse
import os
import sys
from collections.abc import Callable

from version import about
import config
import guide
import interface
import languages
from config import ConfigError
from helptext import HELP
from history import History
from interface import tr
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
            say(tr(HELP[name]) if name in HELP else tr('(no help)'))
        elif c in 'YNS':
            setattr(settings, name, c != 'N')
            return
        else:
            say(tr('Answer Y or N, ? for help, Enter to keep, a space to '
                   'stop.'))


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
            say(tr(HELP['characters']))
        elif is_command_character(c) and c not in others:
            setattr(settings, name, c)
            return
        else:
            say(tr('Not an acceptable character: it may conflict with '
                   'another.'))


def _interface(settings: Settings, ask: Ask, say,
               languages=()) -> None:
    """The language of the interface: a code (en, es), used at once; the
    meanings follow it, if it is one of LANGUAGES (of the meanings)."""
    names = interface.names()
    while True:
        reply = ask(f"{'INTERFACE':<34} '{settings.interface}' (" +
                    ', '.join(names) + ') => ').strip()
        if reply == '':
            return
        if reply == '?':
            say(tr(HELP['interface']))
        elif reply.lower() in names:
            settings.interface = reply.lower()
            interface.use(settings.interface)
            if settings.interface in languages:
                settings.language = settings.interface
            return
        else:
            say(tr('Answer one of: {codes}; Enter keeps the current one.',
                   codes=', '.join(names)))


def _save(ask: Ask, say, settings: Settings, section: str) -> None:
    """Offers to save the parameters or developer modes (SECTION) in the
    configuration file."""
    while True:
        reply = ask(tr('Save these settings? (N)') + ' => ').strip()
        if reply[:1] == '?':
            say(tr(HELP['save']))
            continue
        if reply[:1].upper() in ('Y', 'S'):
            try:
                say(tr('Saved in {path}', path=settings.save(section)))
            except (OSError, ConfigError) as e:
                say(tr('Not saved: {error}', error=e))
        return


def change_parameters(session: Session, ask: Ask, say) -> None:
    """The # dialogue."""
    s = session.settings
    say(tr('Answer Y or N; Enter keeps the current value, ? gives help, '
           'a space skips the rest.'))
    try:
        for name in MODES:
            _yes_no(s, name, ask, say)
        _interface(s, ask, say, session.lexicon.language_names())
        _save(ask, say, s, 'parameters')
    except _Skip:
        pass
    session.settings_changed()


def change_developer_modes(session: Session, ask: Ask, say) -> None:
    """The ! dialogue."""
    s = session.settings
    say(tr('Answer Y or N; Enter keeps the current value, ? gives help, '
           'a space skips the rest.  Developer modes are for special '
           'purposes.'))
    skip = {'for_word_list_check': False,
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
    return '\n'.join([
        tr('Type a Latin word or line and Enter.  ~E: {language} to Latin, '
           '~L: back to Latin.', language=tr(session.language.name)),
        tr('{file}FILE: look up a file   {parameters}: parameters   '
           '{developer}: developer modes   ?: commands   ~H: help   '
           '~A: about',
           file=s.start_file_character,
           parameters=s.change_parameters_character,
           developer=s.change_developer_modes_character),
        tr('An empty line twice quits.')])


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
                    self.ask(tr('-- more (Enter) --'))
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
        except EOFError:
            write('\n')
            return
        except KeyboardInterrupt:       # (not to quit: the line is dropped)
            write('\n')
            say(tr('(Ctrl-C does not quit: an empty line twice, or Ctrl-D, '
                   'quits)'))
            blank = 0
            continue
        pager.reset()
        if remember and line.strip():
            remember(line)
        if not line.strip():
            blank += 1
            if blank >= 2:
                return
            say(tr('(another empty line quits)'))
            continue
        blank = 0
        try:
            command(session, line, ask, say)
        except KeyboardInterrupt:       # (what was being done stops)
            write('\n')
            say(tr('(interrupted)'))
            session.settings_changed()  # (after a dialogue cut short)


def command(session: Session, line: str, ask: Ask, say) -> None:
    """Does what a line typed in interactive mode says."""
    s = session.settings
    first = line.lstrip()[0]
    if line.strip().upper() == '~A':
        say(about())
    elif line.strip().upper() == '~H':
        say(help_text(session).rstrip('\n'))
    elif first == '~':
        say(session.set_language(line.lstrip()[1:2]))
    elif first == s.start_file_character:
        run_file(session, line.lstrip()[1:].strip(), say)
    elif first == s.change_parameters_character:
        change_parameters(session, ask, say)
    elif first == s.change_developer_modes_character:
        change_developer_modes(session, ask, say)
    elif line.strip() == '?':
        say(interactive_help(s, session.language.name))
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


def help_text(session: Session) -> str:
    """The help (see guide.py), for the command line."""
    using = [('pre', interactive_help(session.settings,
                                      session.language.name)),
             ('p', tr('words.py --help lists the options of the command '
                      'line.')),
             guide.configuration()]
    return guide.text(guide.blocks(session, using))


def interactive_help(s: Settings, language: str = 'English') -> str:
    language = tr(language)
    return '\n'.join([
        tr('Type a word or a line of Latin (or, after ~E, a word in '
           '{language}).', language=language),
        '  ~E / ~L    ' + tr('{language} to Latin / Latin to {language}',
                             language=language),
        f'  {s.start_file_character}{tr("FILE"):<9} ' +
        tr('look up each line of FILE'),
        f'  {s.change_parameters_character}          ' +
        tr('change the parameters'),
        f'  {s.change_developer_modes_character}          ' +
        tr('change the developer modes'),
        '  ~H         ' + tr('the help: how to search and read the '
                             'results'),
        '  ~A         ' + tr('about: the version and the credits'),
        tr('In the parameter dialogues, ? explains each setting.'),
        tr('Up and Down bring back earlier searches (also those of earlier '
           'sessions).'),
        tr('An empty line twice, or Ctrl-D, quits; Ctrl-C stops what is '
           'being done.')])


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
        say(tr('Cannot read {path}: {error}', path=name, error=e.strerror))


# ---------------------------------------------------------------------------

class _Credits(argparse.Action):
    """--version: the credits, as written (argparse would rewrap them)."""

    def __call__(self, parser, namespace, values, option_string=None):
        print(about())
        parser.exit()


def main(argv: list[str] | None = None, meanings_only: bool = False):
    """The program; Ctrl-C (outside interactive mode, where it only stops
    what is being done) ends it quietly."""
    try:
        _main(argv, meanings_only)
    except KeyboardInterrupt:
        print(file=sys.stderr)
        sys.exit(130)


def _main(argv: list[str] | None, meanings_only: bool):
    interface.use(_interface_option(argv) or interface.use_configured())
    interface.translate_argparse()
    parser = argparse.ArgumentParser(
        prog='meanings' if meanings_only else 'words',
        description=tr("py-words, based on William Whitaker's WORDS: a "
                       "Latin-English-Latin and Latin-Spanish-Latin "
                       "dictionary that analyses inflected Latin words.  "
                       "With no arguments it is interactive."),
        epilog=tr("In interactive mode, type ? for help."))
    parser.add_argument('words', nargs='*', metavar=tr('WORD'),
                        help=tr('Latin words (or, with -e, a word in the '
                                'language of the meanings)'))
    parser.add_argument('-f', '--file', metavar=tr('FILE'),
                        help=tr("look up each line of FILE ('-' for "
                                "standard input)"))
    parser.add_argument('-o', '--output', metavar=tr('OUTPUT'),
                        help=tr('write the results to OUTPUT'))
    parser.add_argument('-e', '--english', action='store_true',
                        help=tr('from the language of the meanings '
                                '(English, unless --language says '
                                'otherwise) to Latin'))
    parser.add_argument('--pos', help=tr('with -e: only this part of '
                                         'speech (N, V, ADJ, PREP ...)'))
    parser.add_argument('-m', '--meanings-only', action='store_true',
                        default=meanings_only,
                        help=tr('show only dictionary forms and meanings'))
    parser.add_argument('--glosses', action=argparse.BooleanOptionalAction,
                        default=None,
                        help=tr('write the analyses in Leipzig glossing '
                                'abbreviations (GEN.PL), or with '
                                '--no-glosses in words (genitive plural); '
                                'this time only (the setting is '
                                'use_glosses)'))
    parser.add_argument('--fuzzy', action=argparse.BooleanOptionalAction,
                        default=None,
                        help=tr('for a word that finds nothing, show the '
                                'results of its near spellings (or not, '
                                'with --no-fuzzy); this time only (the '
                                'setting is fuzzy_search)'))
    parser.add_argument('--language', metavar=tr('CODE'),
                        help=tr('the language of the meanings (en, es ...); '
                                'this time only (the setting is language)'))
    parser.add_argument('--languages', action='store_true',
                        help=tr('list the languages of the meanings, and '
                                'exit'))
    parser.add_argument('--interface', metavar=tr('CODE'),
                        help=tr('the language of the interface (en, es); '
                                'this time only (the setting is interface)'))
    parser.add_argument('--datadir', default=None, metavar=tr('DATADIR'),
                        help=tr('the folder with the data files (default: '
                                '$WHITAKERS_WORDS_DATADIR, the folder in the '
                                'configuration file, or the data folder '
                                'next to the program)'))
    parser.add_argument('--config', action='store_true',
                        help=tr('show where the configuration file is'))
    parser.add_argument('--clear-history', action='store_true',
                        help=tr('forget the earlier searches, and exit'))
    parser.add_argument('--guide', action='store_true',
                        help=tr('show the help: how to search and read the '
                                'results, and exit'))
    parser.add_argument('--version', action=_Credits, nargs=0,
                        help=tr('show the version and credits, and exit'))
    args = parser.parse_args(argv)

    datadir = args.datadir or default_datadir()
    settings = Settings()
    messages = settings.load(datadir)
    if args.interface:
        settings.interface = args.interface
        if not args.language and \
                args.interface in languages.names(datadir):
            settings.language = args.interface      # (the meanings too)
    interface.use(settings.interface)
    if args.config:
        print(make_config(settings))
        return
    if args.clear_history:
        History().clear()
        print(tr('The history of the searches is cleared.'))
        return
    if args.languages:
        for code, name in languages.names(datadir).items():
            mark = '  ' + tr('(in use)') if code == settings.language \
                else ''
            print(f'{code:<8}{tr(name)}{mark}')
        return
    interactive = not args.words and not args.file and sys.stdin.isatty()
    lexicon = load(datadir)

    out = sys.stdout
    if args.output:
        try:
            out = open(args.output, 'w', encoding='utf-8')
        except OSError as e:
            sys.exit('words: ' + tr('cannot write {path}: {error}',
                                    path=args.output, error=e.strerror))
    if args.glosses is not None:
        settings.use_glosses = args.glosses
    if args.fuzzy is not None:
        settings.fuzzy_search = args.fuzzy
    if args.language:
        settings.language = args.language
    session = Session(lexicon, settings, args.meanings_only, out.write)
    session.reverse = args.english
    if session.notice:
        print(session.notice, file=sys.stderr)
    if args.guide:
        out.write(help_text(session))
        return
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
        if out is not sys.stdout:
            out.close()


def make_config(settings: Settings) -> str:
    """Says where the configuration file is (it is made at start-up, if it
    can be)."""
    path = config.config_path()
    if os.path.exists(path):
        return tr('The configuration file is {path}', path=path)
    sys.exit('words: ' + tr('cannot create {path}', path=path))


def _interface_option(argv: list[str] | None) -> str | None:
    """The language given with --interface, if any (it is needed before
    the arguments are read, for their help)."""
    argv = sys.argv[1:] if argv is None else argv
    for i, arg in enumerate(argv):
        if arg == '--interface' and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith('--interface='):
            return arg.split('=', 1)[1]
    return None


def meanings(argv: list[str] | None = None):
    """`meanings`: WORDS showing only dictionary forms and meanings."""
    main(argv, meanings_only=True)


if __name__ == '__main__':
    main()
