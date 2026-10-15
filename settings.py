"""The settings of WORDS and the files that keep them.

The parameters (changed with # in interactive mode) and the developer
modes and command characters (changed with !) are kept in the
configuration file, in its sections [parameters] and [developer] (see
config.py):

    [parameters]
    trim_output = true
    do_fixes = false

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
from dataclasses import dataclass, fields

import config

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

    def copy(self) -> Settings:
        return Settings(**{f.name: getattr(self, f.name)
                           for f in fields(self)})

    # Files ----------------------------------------------------------------

    def load(self, datadir: str = '.') -> list[str]:
        """Reads WORD.MOD and WORD.MDV, if there are any, then the
        configuration file.  Returns messages about what was found."""
        messages = []
        for name, kind in ((MODE_FILE, 'parameters'),
                           (DEV_MODE_FILE, 'developer modes')):
            path = find(name, datadir)
            if path is None:
                continue
            try:
                problems = self.read(path)
            except OSError as e:
                messages.append(f'Cannot read {path}: {e.strerror}')
                continue
            if problems:
                messages.append(f"{path} has errors ({'; '.join(problems)}); "
                                'the defaults are used for those lines')
            else:
                messages.append(f'Using the {kind} in {path}')
        try:
            data = config.read()
        except config.ConfigError as e:
            messages.append(f'{e}; its settings are not used')
            return messages
        exists = os.path.exists(config.config_path())
        made = ensure_config(self)
        if made:
            messages.append(f"{'Completed' if exists else 'Created'} the "
                            f'configuration file {made}, with the settings '
                            'in use')
        if data.get('parameters') or data.get('developer'):
            problems = self.apply_config(data)
            where = config.config_path()
            if problems:
                messages.append(f"{where} has errors ({'; '.join(problems)})"
                                '; the usual values are used for those '
                                'settings')
            else:
                messages.append(f'Using the settings in {where}')
        return messages

    def apply_config(self, data: dict) -> list[str]:
        """Sets what the sections [parameters] and [developer] of the
        configuration file say; returns their problems."""
        problems = []
        characters = {attr for _, attr in CHARACTERS}
        for name, allowed in (('parameters', MODES),
                              ('developer', DEV_MODES + tuple(characters))):
            for key, value in data.get(name, {}).items():
                if key not in allowed:
                    problems.append(f'[{name}] {key}: unknown setting')
                elif key in characters:
                    if isinstance(value, str) and len(value) == 1 and \
                            is_command_character(value):
                        setattr(self, key, value)
                    else:
                        problems.append(f'{key}: must be one punctuation '
                                        'character')
                elif isinstance(value, bool):
                    setattr(self, key, value)
                else:
                    problems.append(f'{key}: must be true or false')
        return problems

    def config_section(self, name: str) -> dict:
        """The values of section NAME (parameters or developer)."""
        if name == 'parameters':
            return {key: getattr(self, key) for key in MODES}
        values = {key: getattr(self, key) for key in DEV_MODES}
        values.update((attr, getattr(self, attr)) for _, attr in CHARACTERS)
        return values

    def save(self, name: str) -> str:
        """Saves the parameters or the developer modes (NAME) in the
        configuration file; returns its path (raises OSError or
        config.ConfigError if it cannot)."""
        return config.update(name, self.config_section(name))

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
                        problems.append(f'line {number}: bad character')
                elif name.lower() in MODES + DEV_MODES:
                    reply = words[1].upper() if len(words) > 1 else ''
                    if reply not in ('Y', 'N'):
                        problems.append(f'line {number}: expected Y or N')
                    else:
                        setattr(self, name.lower(), reply == 'Y')
                elif name.upper() != name:
                    problems.append(f'line {number}: unexpected text')
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

