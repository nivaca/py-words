"""A WORDS session: the data, the settings, the current language and the
files the program writes.

* WORD.OUT  the results, when have_output_file and write_output_to_file
            are on (instead of the screen);
* WORD.UNK  the unknown words, when write_unknowns_to_file is on;
* WORD.STA  statistics on the tricks and affixes used, when the developer
            modes have_statistics_file and write_statistics_file are on.

They are written in the current directory.

The meanings are in the language of the settings (see languages.py); in
reverse (~E), words of that language are looked up in Latin.  With the
parameter fuzzy_search, a word that finds nothing is followed by the
results of its near spellings (see fuzzy.py).
"""

from __future__ import annotations

from typing import TextIO
from collections.abc import Callable

import reverse
from analyzer import Analyzer, is_capitalized
from interface import tr
from languages import REFERENCE, Language
from lexicon import Lexicon
from model import Pos
from render import Renderer
from settings import Settings
from xmldata import DataError

OUTPUT_FILE = 'WORD.OUT'
UNKNOWNS_FILE = 'WORD.UNK'
STATS_FILE = 'WORD.STA'


class Session:
    def __init__(self, lexicon: Lexicon, settings: Settings,
                 meanings_only: bool = False,
                 write: Callable[[str], None] = None):
        self.lexicon = lexicon
        self.settings = settings
        self.meanings_only = meanings_only
        self.reverse = False            # (from the language to Latin)
        self.language: Language | None = None
        self.notice = ''                # (why the language is not used)
        self.write = write or (lambda text: print(text, end=''))
        self.output: TextIO | None = None
        self.unknowns: TextIO | None = None
        self.stats: TextIO | None = None
        self.analyzer = Analyzer(lexicon, settings, self._stat)
        self.settings_changed()

    def settings_changed(self):
        """Opens or closes the output files to match the settings."""
        s = self.settings
        self.output = _keep_open(self.output, OUTPUT_FILE,
                                 s.have_output_file)
        if self.output is None:
            s.write_output_to_file = False
        self.unknowns = _keep_open(self.unknowns, UNKNOWNS_FILE,
                                   s.write_unknowns_to_file)
        self.stats = _keep_open(self.stats, STATS_FILE,
                                s.have_statistics_file)
        if self.stats is None:
            s.write_statistics_file = False
        self._choose_language()
        self.analyzer.reset()

    def _choose_language(self):
        """The language of the settings, or English if it cannot be used
        (self.notice says why)."""
        code = self.settings.language
        if self.language is not None and self.language.code == code:
            return
        try:
            self.language = self.lexicon.language(code)
            self.notice = ''
        except (LookupError, DataError) as e:
            self.language = self.lexicon.language(REFERENCE)
            self.notice = tr('The meanings are in English: {error}.',
                             error=e)

    def renderer(self) -> Renderer:
        return Renderer(self.settings, self.meanings_only,
                        self.lexicon.glosses, self.language)

    def close(self):
        for f in (self.output, self.unknowns, self.stats):
            if f is not None:
                f.close()
        self.output = self.unknowns = self.stats = None

    def _stat(self, line: str):
        if self.stats is not None and self.settings.write_statistics_file:
            self.stats.write(line + '\n')

    def _emit(self, text: str):
        if self.output is not None and self.settings.write_output_to_file:
            self.output.write(text)
        else:
            self.write(text)

    # -----------------------------------------------------------------

    def set_language(self, code: str) -> str:
        """~E (from the language of the meanings to Latin) and ~L (Latin
        to it).  Returns a message."""
        code = code.upper()
        name = tr(self.language.name)
        if code == 'E':
            self.reverse = True
            return tr('{language} to Latin: type a word in {language}, and '
                      'optionally a part of speech (N, ADJ, V, PREP ...)',
                      language=name)
        if code == 'L':
            self.reverse = False
            return tr('Latin to {language}', language=name)
        return tr('Use ~E for {language} to Latin, ~L for Latin to '
                  '{language}', language=name)

    def lookup(self, line: str) -> str:
        """The text for a line of input, in the current direction."""
        if self.reverse:
            return self.lookup_reverse(line)
        return self.lookup_latin(line)

    def lookup_latin(self, line: str) -> str:
        az = self.analyzer
        out = []
        for result in az.analyze_line(line, self.meanings_only):
            near = None
            spellings = []
            if result.unknown:
                self._unknown(result.word, line)
                if self.settings.do_stems_for_unknown:
                    near = self.lexicon.neighbours(result.word)
                spellings = self._near_spellings(result.word)
            out.append(self.renderer().word(result, near, spellings))
            for spelling in spellings:
                out.append(self.renderer().word(self._analyze(spelling)))
        return '\n'.join(t for t in out if t)

    def _near_spellings(self, word: str) -> list[str]:
        """The near spellings of the unknown WORD, if the fuzzy search is
        on (not for names, if unknown names are ignored)."""
        s = self.settings
        if not s.fuzzy_search or (s.ignore_unknown_names and
                                  is_capitalized(word)):
            return []
        return self.analyzer.near_spellings(word)

    def _analyze(self, word: str):
        """The result for WORD on its own, not counted as a word of the
        line (WORD.UNK numbers words, and a near spelling isn't one)."""
        az = self.analyzer
        number = az.word_number
        result, _ = az.analyze_word(word, meanings_only=self.meanings_only)
        az.word_number = number
        return result

    def lookup_reverse(self, line: str) -> str:
        """The Latin entries for a word of the language of the meanings
        (and, optionally, a part of speech after it)."""
        words = line.split()
        if not words:
            return ''
        pos = Pos.X
        if len(words) > 1 and words[1].upper() in Pos.__members__:
            pos = Pos[words[1].upper()]
        index = self.lexicon.reverse(self.language.code)
        hits = index.search(words[0], pos)
        near = []
        noise = {reverse.fold(w) for w in self.language.data.noise}
        if not hits and self.settings.fuzzy_search and \
                reverse.fold(words[0]) not in noise:
            near = [self._spelled(w, index.search(w, pos))
                    for w in index.near(words[0], pos)]
        out = [self.renderer().reverse(words[0], hits, near)]
        out += [self.renderer().reverse(w, index.search(w, pos))
                for w in near]
        return '\n'.join(out)

    def _spelled(self, word: str, hits: list) -> str:
        """The indexed WORD as the meaning of its first hit writes it."""
        return reverse.spelled(word, self.language.translated(hits[0].entry)
                               or '')

    def _unknown(self, word: str, line: str):
        if self.unknowns is None:
            return
        if self.settings.include_unknown_context:
            self.unknowns.write(line.rstrip('\n') + '\n')
        self.unknowns.write(f'{word:<20} line {self.analyzer.line_number}, '
                            f'word {self.analyzer.word_number}\n')

    def process(self, line: str):
        """Looks up LINE and writes the result."""
        text = self.lookup(line)
        if text:
            self._emit(text + '\n')


def _keep_open(f, name: str, wanted: bool):
    if wanted and f is None:
        try:
            return open(name, 'w', encoding='utf-8')
        except OSError as e:
            print(tr('Cannot create {path}: {error}', path=name,
                     error=e.strerror))
            return None
    if not wanted and f is not None:
        f.close()
        return None
    return f

