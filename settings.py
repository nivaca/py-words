"""The settings of WORDS and the files that keep them.

The parameters (changed with # in interactive mode: what the results show,
and how words are looked up) and the developer modes and command
characters (changed with !) are kept in the configuration file, in its
sections [parameters] and [developer] (see config.py), with the language of
the meanings (see languages.py) and that of the interface (see
interface.py):

    [parameters]
    trim_output = true
    use_affixes = false
    language = "en"
    interface = "en"

The settings files of the original program are still read, if there are
any, but the configuration file comes first: WORD.MOD (the parameters) and
WORD.MDV (the developer modes and characters), one setting per line,

    TRIM_OUTPUT                      Y
    START_FILE_CHARACTER             '@'

looked for in the current folder, the program's folder and the data
folder.  Names the program does not know (some older ones did nothing) are
ignored.  The names of earlier versions (do_fixes, show_age ...) are read
as their new ones (RENAMED), in both kinds of files.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, fields

import config
from interface import N_, tr

MODE_FILE = 'WORD.MOD'
DEV_MODE_FILE = 'WORD.MDV'

#  The parameters, in the order they are asked about: what the results
#  show, and how words are looked up
SHOWN = (
    'show_dictionary_forms', 'show_only_meanings', 'use_glosses',
    'show_long_vowels', 'show_codes', 'explain_codes', 'show_examples',
    'trim_output', 'trim_medieval')
LOOKUP = (
    'fuzzy_search', 'use_affixes', 'use_tricks', 'medieval_spellings',
    'read_compounds', 'ignore_unknown_names', 'unknowns_only',
    'near_entries')
MODES = SHOWN + LOOKUP

DEV_MODES = (
    'show_entry_source', 'pearse_codes', 'word_list_check',
    'pause_in_screen_output')

#  The settings in groups, with their headings, for the dialogues
GROUPS = ((N_('What the results show'), SHOWN),
          (N_('How words are looked up'), LOOKUP),
          (N_('Developer modes'), DEV_MODES))

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
    'trim_medieval': 'trim_output',
    'medieval_spellings': 'use_tricks',
}

#  The names of earlier versions (until 3.1) and the settings that took
#  their place.  Two old ones that became one (show_age and
#  show_frequency) make it on if either is.
RENAMED = {
    'do_dictionary_forms': 'show_dictionary_forms',
    'do_only_meanings': 'show_only_meanings',
    'show_dictionary_codes': 'show_codes',
    'show_age': 'explain_codes',
    'show_frequency': 'explain_codes',
    'do_examples': 'show_examples',
    'omit_medieval': 'trim_medieval',
    'do_fixes': 'use_affixes',
    'do_tricks': 'use_tricks',
    'do_medieval_tricks': 'medieval_spellings',
    'do_compounds': 'read_compounds',
    'do_unknowns_only': 'unknowns_only',
    'do_stems_for_unknown': 'near_entries',
    'show_dictionary': 'show_entry_source',
    'show_dictionary_line': 'show_entry_source',
    'do_pearse_codes': 'pearse_codes',
    'do_only_initial_word': 'word_list_check',
}
MERGED = {'explain_codes', 'show_entry_source'}

#  Settings of earlier versions that are gone: the files WORD.OUT, WORD.UNK
#  and WORD.STA (until 2.15), and switches that were only for testing
#  WORDS, now always as they usually were (until 3.1).  A configuration
#  file that still has them is not wrong.
REMOVED = ('have_output_file', 'write_output_to_file',
           'write_unknowns_to_file', 'have_statistics_file',
           'write_statistics_file', 'include_unknown_context',
           'for_word_list_check', 'do_only_fixes', 'do_fixes_anyway',
           'use_prefixes', 'use_suffixes', 'use_tackons', 'do_syncope',
           'do_two_words', 'omit_archaic', 'omit_uncommon')

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
    """'use_affixes' -> 'Use affixes' (in the language of the
    interface)."""
    return tr(name.replace('_', ' ').capitalize())


def first_sentence(text: str) -> str:
    end = text.find('.  ')
    return text if end < 0 else text[:end + 1]


@dataclass
class Settings:
    # Parameters (WORD.MOD): what the results show ...
    show_dictionary_forms: bool = True
    show_only_meanings: bool = False
    use_glosses: bool = True
    show_long_vowels: bool = True
    show_codes: bool = True
    explain_codes: bool = False
    show_examples: bool = False
    trim_output: bool = True
    trim_medieval: bool = False
    # ... and how words are looked up
    fuzzy_search: bool = True
    use_affixes: bool = True
    use_tricks: bool = True
    medieval_spellings: bool = True
    read_compounds: bool = True
    ignore_unknown_names: bool = True
    unknowns_only: bool = False
    near_entries: bool = False
    language: str = 'en'
    interface: str = 'en'
    # Developer modes (WORD.MDV)
    show_entry_source: bool = False
    pearse_codes: bool = False
    word_list_check: bool = False
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
            self.rename_old(data)
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
        given = {key for name in ('parameters', 'developer')
                 for key in data.get(name, {})}
        old = []
        for name, allowed in (('parameters', MODES + LANGUAGES),
                              ('developer', DEV_MODES + tuple(characters))):
            for key, value in data.get(name, {}).items():
                if key in REMOVED:
                    continue
                if key in RENAMED:
                    if RENAMED[key] not in given and isinstance(value, bool):
                        old.append((key, value))  # (if not, the new wins)
                elif key not in allowed:
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
        self.set_old(old)
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
                         if key not in REMOVED and key not in RENAMED},
                      **{key: values[key] for key in only if key in values}}
        return config.update(name, values)

    def rename_old(self, data: dict):
        """Writes the configuration file DATA again with the names of this
        version, if it has old ones (each with the value it gave), and
        without the settings that are gone.  Nothing happens if it cannot
        be written."""
        sections = {name: dict(data.get(name, {}))
                    for name in ('parameters', 'developer')}
        old = [key for keys in sections.values() for key in keys
               if key in RENAMED or key in REMOVED]
        if not old:
            return
        for name, keys in sections.items():
            for key in list(keys):
                if key in RENAMED:
                    new = RENAMED[key]
                    sections[section_of(new)].setdefault(
                        new, getattr(self, new))
                if key in RENAMED or key in REMOVED:
                    del keys[key]
        try:
            config.write({**config.read(), **sections})
        except (OSError, config.ConfigError):
            pass

    def set_old(self, old: list[tuple[str, bool]]):
        """Sets what the OLD settings (name, value) say through the ones
        that took their place (two old ones made one: on if either is)."""
        values: dict[str, list[bool]] = {}
        for name, value in old:
            values.setdefault(RENAMED[name], []).append(value)
        for new, given in values.items():
            setattr(self, new, any(given) if new in MERGED else given[-1])

    def read(self, path: str) -> list[str]:
        """Sets what the settings file PATH says; returns its problems."""
        problems = []
        characters = dict(CHARACTERS)
        old = []
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
                elif name.lower() in MODES + DEV_MODES + tuple(RENAMED):
                    reply = words[1].upper() if len(words) > 1 else ''
                    if reply not in ('Y', 'N'):
                        problems.append(tr('line {number}: expected Y or N',
                                           number=number))
                    elif name.lower() in RENAMED:
                        old.append((name.lower(), reply == 'Y'))
                    else:
                        setattr(self, name.lower(), reply == 'Y')
                elif name.upper() != name:
                    problems.append(tr('line {number}: unexpected text',
                                       number=number))
        self.set_old(old)
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

