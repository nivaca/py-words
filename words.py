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

import argparse
import os
import sys
from typing import Callable, List, Optional

from version import CREDITS
from helptext import HELP
from lexicon import Lexicon, DICTIONARY, default_datadir
from settings import Settings, MODES, DEV_MODES, is_command_character
from session import Session
from xmldata import DataError

SCREEN_LINES = 20

Ask = Callable[[str], str]


def load(datadir: str) -> Lexicon:
    try:
        return Lexicon.load(datadir)
    except (DataError, FileNotFoundError) as e:
        sys.exit('words: %s' % e)


# ---------------------------------------------------------------------------
#  The settings dialogues

class _Skip(Exception):
    """A reply of spaces skips the rest of a dialogue."""


def _yes_no(settings: Settings, name: str, ask: Ask, say) -> None:
    current = getattr(settings, name)
    while True:
        reply = ask('%-34s %s => ' % (name.upper(), 'Y' if current else 'N'))
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
        reply = ask("%-34s '%s' => " % (name.upper(), getattr(settings, name)))
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


def _save(ask: Ask, say, save) -> None:
    while True:
        reply = ask('Save these settings? (N) => ').strip()
        if reply[:1] == '?':
            say(HELP['save'])
            continue
        if reply[:1].upper() == 'Y':
            save()
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
        _save(ask, say, lambda: (s.save_modes(),
                                 say('Parameters saved in WORD.MOD')))
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
        _save(ask, say, lambda: (s.save_dev_modes(),
                                 say('Developer modes saved in WORD.MDV')))
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
        "%sFILE: look up a file   %s: parameters   %s: developer modes   "
        "?: help\n"
        "An empty line twice quits." % (
            s.start_file_character,
            s.change_parameters_character,
            s.change_developer_modes_character))


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
         write: Callable[[str], None] = None) -> None:
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


def interactive_help(s: Settings) -> str:
    return '\n'.join([
        'Type a word or a line of Latin (or, after ~E, an English word).',
        '  ~E / ~L    English to Latin / Latin to English',
        '  %sFILE      look up each line of FILE' % s.start_file_character,
        '  %s          change the parameters' % s.change_parameters_character,
        '  %s          change the developer modes'
        % s.change_developer_modes_character,
        'In the parameter dialogues, ? explains each setting.',
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
        say('Cannot read %s: %s' % (name, e.strerror))


# ---------------------------------------------------------------------------

class _Credits(argparse.Action):
    """--version: the credits, as written (argparse would rewrap them)."""

    def __call__(self, parser, namespace, values, option_string=None):
        print(CREDITS)
        parser.exit()


def main(argv: Optional[List[str]] = None, meanings_only: bool = False):
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
    parser.add_argument('--datadir', default=None,
                        help='the folder with the data files (default: '
                             '$WHITAKERS_WORDS_DATADIR, or the data '
                             'folder next to the program)')
    parser.add_argument('--version', action=_Credits, nargs=0,
                        help='show the version and credits, and exit')
    args = parser.parse_args(argv)

    datadir = args.datadir or default_datadir()
    settings = Settings()
    messages = settings.load(datadir)
    interactive = not args.words and not args.file and sys.stdin.isatty()
    lexicon = load(datadir)

    out = sys.stdout
    if args.output:
        try:
            out = open(args.output, 'w', encoding='utf-8')
        except OSError as e:
            sys.exit('words: cannot write %s: %s' % (args.output,
                                                      e.strerror))
    session = Session(lexicon, settings, args.meanings_only, out.write)
    session.english = args.english
    try:
        if interactive:
            for m in messages:
                print(m)
            try:
                import readline  # noqa: F401  (line editing for input())
            except ImportError:
                pass
            repl(session)
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


def meanings(argv: Optional[List[str]] = None):
    """`meanings`: WORDS showing only dictionary forms and meanings."""
    main(argv, meanings_only=True)


if __name__ == '__main__':
    main()
