"""The settings of WORDS and the files that keep them.

The parameters (changed with # in interactive mode) are kept in WORD.MOD,
the developer modes (changed with !) in WORD.MDV, one per line:

    TRIM_OUTPUT                      Y
    DO_FIXES                         N

WORD.MDV also holds the three command characters:

    START_FILE_CHARACTER             '@'

Settings files are looked for in the current directory, then in the data
directory, and saved in the current directory.  Names the program does not
know (some older ones did nothing) are ignored.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields
from typing import List

MODE_FILE = 'WORD.MOD'
DEV_MODE_FILE = 'WORD.MDV'

#  The parameters, in the order they are asked about
MODES = (
    'trim_output', 'have_output_file', 'write_output_to_file',
    'do_unknowns_only', 'write_unknowns_to_file', 'ignore_unknown_names',
    'do_compounds', 'do_fixes', 'do_tricks', 'do_dictionary_forms',
    'show_age', 'show_frequency', 'do_examples', 'do_only_meanings',
    'do_stems_for_unknown')

DEV_MODES = (
    'have_statistics_file', 'write_statistics_file', 'show_dictionary',
    'show_dictionary_line', 'show_dictionary_codes', 'do_pearse_codes',
    'do_only_initial_word', 'for_word_list_check', 'do_only_fixes',
    'do_fixes_anyway', 'use_prefixes', 'use_suffixes', 'use_tackons',
    'do_medieval_tricks', 'do_syncope', 'do_two_words',
    'include_unknown_context', 'omit_archaic', 'omit_medieval',
    'omit_uncommon', 'pause_in_screen_output')

CHARACTERS = (('START_FILE_CHARACTER', 'start_file_character'),
              ('CHANGE_PARAMETERS_CHARACTER', 'change_parameters_character'),
              ('CHANGE_DEVELOPER_MODES_CHARACTER',
               'change_developer_modes_character'))


@dataclass
class Settings:
    # Parameters (WORD.MOD)
    trim_output: bool = True
    have_output_file: bool = False
    write_output_to_file: bool = False
    do_unknowns_only: bool = False
    write_unknowns_to_file: bool = False
    ignore_unknown_names: bool = True
    do_compounds: bool = True
    do_fixes: bool = True
    do_tricks: bool = True
    do_dictionary_forms: bool = True
    show_age: bool = False
    show_frequency: bool = False
    do_examples: bool = False
    do_only_meanings: bool = False
    do_stems_for_unknown: bool = False
    # Developer modes (WORD.MDV)
    have_statistics_file: bool = False
    write_statistics_file: bool = False
    show_dictionary: bool = False
    show_dictionary_line: bool = False
    show_dictionary_codes: bool = True
    do_pearse_codes: bool = False
    do_only_initial_word: bool = False
    for_word_list_check: bool = False
    do_only_fixes: bool = False
    do_fixes_anyway: bool = False
    use_prefixes: bool = True
    use_suffixes: bool = True
    use_tackons: bool = True
    do_medieval_tricks: bool = True
    do_syncope: bool = True
    do_two_words: bool = True
    include_unknown_context: bool = True
    omit_archaic: bool = True
    omit_medieval: bool = False
    omit_uncommon: bool = True
    pause_in_screen_output: bool = True
    # Command characters (WORD.MDV)
    start_file_character: str = '@'
    change_parameters_character: str = '#'
    change_developer_modes_character: str = '!'

    def copy(self) -> 'Settings':
        return Settings(**{f.name: getattr(self, f.name)
                           for f in fields(self)})

    # Files ----------------------------------------------------------------

    def load(self, datadir: str = '.') -> List[str]:
        """Reads WORD.MOD and WORD.MDV, if there are any.  Returns messages
        about what was found."""
        messages = []
        for name, kind in ((MODE_FILE, 'parameters'),
                           (DEV_MODE_FILE, 'developer modes')):
            path = find(name, datadir)
            if path is None:
                continue
            try:
                problems = self.read(path)
            except OSError as e:
                messages.append('Cannot read %s: %s' % (path, e.strerror))
                continue
            if problems:
                messages.append('%s has errors (%s); the defaults are used '
                                'for those lines' % (path, '; '.join(problems)))
            else:
                messages.append('Using the %s in %s' % (kind, path))
        return messages

    def read(self, path: str) -> List[str]:
        """Sets what the settings file PATH says; returns its problems."""
        problems = []
        characters = dict(CHARACTERS)
        with open(path, encoding='latin-1') as f:
            for number, line in enumerate(f, 1):
                words = line.split()
                if not words:
                    continue
                name = words[0]
                if name in characters:
                    value = line[len(name):].strip().strip("'")
                    if len(value) == 1 and is_command_character(value):
                        setattr(self, characters[name], value)
                    else:
                        problems.append('line %d: bad character' % number)
                elif name.lower() in MODES + DEV_MODES:
                    reply = words[1].upper() if len(words) > 1 else ''
                    if reply not in ('Y', 'N'):
                        problems.append('line %d: expected Y or N' % number)
                    else:
                        setattr(self, name.lower(), reply == 'Y')
                elif name.upper() != name:
                    problems.append('line %d: unexpected text' % number)
        return problems

    def save_modes(self, path: str = MODE_FILE):
        self._write(path, MODES, with_characters=False)

    def save_dev_modes(self, path: str = DEV_MODE_FILE):
        self._write(path, DEV_MODES, with_characters=True)

    def _write(self, path, names, with_characters):
        with open(path, 'w', encoding='latin-1') as f:
            for name in names:
                f.write('%-34s %s\n' % (name.upper(),
                                        'Y' if getattr(self, name) else 'N'))
            if with_characters:
                for label, attr in CHARACTERS:
                    f.write("%-32s '%s'\n" % (label, getattr(self, attr)))


def find(name: str, datadir: str):
    """NAME in the current folder, the program's folder or DATADIR."""
    for d in ('.', os.path.dirname(os.path.abspath(__file__)), datadir):
        path = os.path.join(d, name)
        if os.path.isfile(path):
            return path
    return None


def is_command_character(c: str) -> bool:
    """The command characters must be punctuation."""
    return c.isascii() and not c.isalnum() and c.isprintable() and c != ' '

