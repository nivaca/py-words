"""The settings of WORDS and the files that keep them.

The parameters (changed with # in interactive mode) and the developer
modes and command characters (changed with !) are kept in the
configuration file, in its sections [parameters] and [developer] (see
config.py), with the language of the meanings (see languages.py) and
that of the interface (see interface.py):

    [parameters]
    trim_output = true
    do_fixes = false
    language = "en"
    interface = "en"

The settings files of the original program are still read, if there are
any, but the configuration file comes first: WORD.MOD (the parameters) and
WORD.MDV (the developer modes and characters), one setting per line,

    TRIM_OUTPUT                      Y
    START_FILE_CHARACTER             '@'

looked for in the current folder, the program's folder and the data
folder.  Names the program does not know (some older ones did nothing) are
ignored.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, fields

import config
from interface import N_, tr

MODE_FILE = 'WORD.MOD'
DEV_MODE_FILE = 'WORD.MDV'

#  The parameters, in the order they are asked about
MODES = (
    'trim_output', 'do_unknowns_only', 'ignore_unknown_names',
    'do_compounds', 'do_fixes', 'do_tricks', 'do_dictionary_forms',
    'show_age', 'show_frequency', 'do_examples', 'use_glosses',
    'show_long_vowels', 'do_only_meanings', 'do_stems_for_unknown',
    'fuzzy_search')

DEV_MODES = (
    'show_dictionary', 'show_dictionary_line', 'show_dictionary_codes',
    'do_pearse_codes', 'do_only_initial_word', 'for_word_list_check',
    'do_only_fixes', 'do_fixes_anyway', 'use_prefixes', 'use_suffixes',
    'use_tackons', 'do_medieval_tricks', 'do_syncope', 'do_two_words',
    'omit_archaic', 'omit_medieval', 'omit_uncommon',
    'pause_in_screen_output')

CHARACTERS = (('START_FILE_CHARACTER', 'start_file_character'),
              ('CHANGE_PARAMETERS_CHARACTER', 'change_parameters_character'),
              ('CHANGE_DEVELOPER_MODES_CHARACTER',
               'change_developer_modes_character'))


#  The languages of the meanings and of the interface: language codes (en,
#  es ...), kept in [parameters]
LANGUAGE_CODE = re.compile(r'[a-z]{2,3}(-[A-Za-z0-9]{1,8})*')

#  The settings of the languages, kept with the parameters
LANGUAGES = ('language', 'interface')

#  A setting that only makes sense with another one on (the dialogues
#  skip it, or grey it out, while that one is off)
DEPENDS = {
    'for_word_list_check': 'do_only_initial_word',
    'do_only_fixes': 'do_fixes',
    'do_fixes_anyway': 'do_fixes',
    'do_medieval_tricks': 'do_tricks',
}

#  Settings of earlier versions, which wrote the files WORD.OUT, WORD.UNK
#  and WORD.STA: a configuration file that still has them is not wrong
REMOVED = ('have_output_file', 'write_output_to_file',
           'write_unknowns_to_file', 'have_statistics_file',
           'write_statistics_file', 'include_unknown_context')

#  Settings that only the interactive command line uses
COMMAND_LINE = ('pause_in_screen_output',)

#  Settings that the window and the web page show on their main screen,
#  with a box of their own, and not in their Settings
#  Si se añade algo aquí, hay que ponerle su casilla en words_gui.py y en
#  words_web.py; si no, no aparece en ninguna parte de esos dos.
ON_SCREEN = ('fuzzy_search',)


def section_of(name: str) -> str:
    """The section of the configuration file that keeps setting NAME."""
    return 'parameters' if name in MODES + LANGUAGES \
        else 'developer'


def label(name: str) -> str:
    """'do_only_fixes' -> 'Do only fixes' (in the language of the
    interface)."""
    return tr(name.replace('_', ' ').capitalize())


def first_sentence(text: str) -> str:
    end = text.find('.  ')
    return text if end < 0 else text[:end + 1]


@dataclass
class Settings:
    # Parameters (WORD.MOD)
    trim_output: bool = True
    do_unknowns_only: bool = False
    ignore_unknown_names: bool = True
    do_compounds: bool = True
    do_fixes: bool = True
    do_tricks: bool = True
    do_dictionary_forms: bool = True
    show_age: bool = False
    show_frequency: bool = False
    do_examples: bool = False
    use_glosses: bool = True
    show_long_vowels: bool = True
    do_only_meanings: bool = False
    do_stems_for_unknown: bool = False
    fuzzy_search: bool = True
    language: str = 'en'
    interface: str = 'en'
    # Developer modes (WORD.MDV)
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
    omit_archaic: bool = True
    omit_medieval: bool = False
    omit_uncommon: bool = True
    pause_in_screen_output: bool = True
    # Command characters (WORD.MDV)
    start_file_character: str = '@'
    change_parameters_character: str = '#'
    change_developer_modes_character: str = '!'

    def copy(self) -> Settings:
        return Settings(**{f.name: getattr(self, f.name)
                           for f in fields(self)})

    # Files ----------------------------------------------------------------

    def load(self, datadir: str = '.') -> list[str]:
        """Reads WORD.MOD and WORD.MDV, if there are any, then the
        configuration file.  Returns messages about what was found."""
        messages = []
        for name, kind in ((MODE_FILE, N_('parameters')),
                           (DEV_MODE_FILE, N_('developer modes'))):
            path = find(name, datadir)
            if path is None:
                continue
            try:
                problems = self.read(path)
            except OSError as e:
                messages.append(tr('Cannot read {path}: {error}',
                                   path=path, error=e.strerror))
                continue
            if problems:
                messages.append(tr('{path} has errors ({problems}); the '
                                   'defaults are used for those lines',
                                   path=path, problems='; '.join(problems)))
            else:
                messages.append(tr('Using the {kind} in {path}',
                                   kind=tr(kind), path=path))
        try:
            data = config.read()
        except config.ConfigError as e:
            messages.append(tr('{error}; its settings are not used',
                               error=e))
            return messages
        exists = os.path.exists(config.config_path())
        made = ensure_config(self)
        if made:
            messages.append(
                tr('Completed the configuration file {path}, with the '
                   'settings in use', path=made) if exists else
                tr('Created the configuration file {path}, with the '
                   'settings in use', path=made))
        if data.get('parameters') or data.get('developer'):
            problems = self.apply_config(data)
            where = config.config_path()
            if problems:
                messages.append(tr('{path} has errors ({problems}); the '
                                   'usual values are used for those '
                                   'settings', path=where,
                                   problems='; '.join(problems)))
            else:
                messages.append(tr('Using the settings in {path}',
                                   path=where))
        return messages

    def apply_config(self, data: dict) -> list[str]:
        """Sets what the sections [parameters] and [developer] of the
        configuration file say; returns their problems."""
        problems = []
        characters = {attr for _, attr in CHARACTERS}
        for name, allowed in (('parameters', MODES + LANGUAGES),
                              ('developer', DEV_MODES + tuple(characters))):
            for key, value in data.get(name, {}).items():
                if key in REMOVED:
                    continue
                if key not in allowed:
                    problems.append(tr('[{section}] {key}: unknown setting',
                                       section=name, key=key))
                elif key in LANGUAGES:
                    if isinstance(value, str) and \
                            LANGUAGE_CODE.fullmatch(value):
                        setattr(self, key, value)
                    else:
                        problems.append(tr('{key}: must be a language code, '
                                           'like "en" or "es"', key=key))
                elif key in characters:
                    if isinstance(value, str) and len(value) == 1 and \
                            is_command_character(value):
                        setattr(self, key, value)
                    else:
                        problems.append(tr('{key}: must be one '
                                           'punctuation character', key=key))
                elif isinstance(value, bool):
                    setattr(self, key, value)
                else:
                    problems.append(tr('{key}: must be true or false',
                                       key=key))
        return problems

    def config_section(self, name: str) -> dict:
        """The values of section NAME (parameters or developer)."""
        if name == 'parameters':
            values = {key: getattr(self, key) for key in MODES}
            values.update((key, getattr(self, key)) for key in LANGUAGES)
            return values
        values = {key: getattr(self, key) for key in DEV_MODES}
        values.update((attr, getattr(self, attr)) for _, attr in CHARACTERS)
        return values

    def save(self, name: str, only=None) -> str:
        """Saves the parameters or the developer modes (NAME) in the
        configuration file; returns its path (raises OSError or
        config.ConfigError if it cannot).  ONLY: the settings to save (the
        others are kept as the file has them, which another program, or
        another window, may have changed since); None: all of them."""
        values = self.config_section(name)
        if only is not None:
            values = {**{key: value for key, value
                         in config.read().get(name, values).items()
                         if key not in REMOVED},
                      **{key: values[key] for key in only if key in values}}
        return config.update(name, values)

    def read(self, path: str) -> list[str]:
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
                        problems.append(tr('line {number}: bad character',
                                           number=number))
                elif name.lower() in MODES + DEV_MODES:
                    reply = words[1].upper() if len(words) > 1 else ''
                    if reply not in ('Y', 'N'):
                        problems.append(tr('line {number}: expected Y or N',
                                           number=number))
                    else:
                        setattr(self, name.lower(), reply == 'Y')
                elif name.upper() != name:
                    problems.append(tr('line {number}: unexpected text',
                                       number=number))
        return problems


def ensure_config(settings: Settings | None = None) -> str | None:
    """Makes sure the configuration file exists and has the sections
    [parameters] and [developer]: creates it, or adds those it lacks, with
    SETTINGS (or the usual ones), keeping what is there.  Returns its path
    if it was created or completed; nothing happens if it cannot be read or
    written."""
    try:
        data = config.read()
    except config.ConfigError:
        return None                     # (left for the user to mend)
    missing = [name for name in ('parameters', 'developer')
               if name not in data]
    if not missing:
        return None
    settings = settings or Settings()
    for name in missing:
        data[name] = settings.config_section(name)
    try:
        config.write(data)
    except OSError:
        return None
    return config.config_path()


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

