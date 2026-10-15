"""A WORDS session: the data, the settings, the current language and the
files the program writes.

* WORD.OUT  the results, when have_output_file and write_output_to_file
            are on (instead of the screen);
* WORD.UNK  the unknown words, when write_unknowns_to_file is on;
* WORD.STA  statistics on the tricks and affixes used, when the developer
            modes have_statistics_file and write_statistics_file are on.

They are written in the current directory.
"""

from __future__ import annotations

from typing import Callable, Optional, TextIO

from analyzer import Analyzer
from lexicon import Lexicon
from model import Pos
from render import Renderer
from settings import Settings

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
        self.english = False
        self.write = write or (lambda text: print(text, end=''))
        self.output: Optional[TextIO] = None
        self.unknowns: Optional[TextIO] = None
        self.stats: Optional[TextIO] = None
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
        self.analyzer.reset()

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
        """~E and ~L.  Returns a message."""
        code = code.upper()
        if code == 'E':
            self.english = True
            return 'English to Latin: type an English word, and optionally ' \
                'a part of speech (N, ADJ, V, PREP ...)'
        if code == 'L':
            self.english = False
            return 'Latin to English'
        return 'Use ~E for English to Latin, ~L for Latin to English'

    def lookup(self, line: str) -> str:
        """The text for a line of input, in the current language."""
        if self.english:
            return self.lookup_english(line)
        return self.lookup_latin(line)

    def lookup_latin(self, line: str) -> str:
        az = self.analyzer
        out = []
        for result in az.analyze_line(line, self.meanings_only):
            near = None
            if result.unknown:
                self._unknown(result.word, line)
                if self.settings.do_stems_for_unknown:
                    near = self.lexicon.neighbours(result.word)
            out.append(Renderer(self.settings, self.meanings_only).word(
                result, near))
        return '\n'.join(t for t in out if t)

    def lookup_english(self, line: str) -> str:
        words = line.split()
        if not words:
            return ''
        pos = Pos.X
        if len(words) > 1 and words[1].upper() in Pos.__members__:
            pos = Pos[words[1].upper()]
        hits = self.lexicon.english.search(words[0], pos)
        return Renderer(self.settings).english(words[0], hits)

    def _unknown(self, word: str, line: str):
        if self.unknowns is None:
            return
        if self.settings.include_unknown_context:
            self.unknowns.write(line.rstrip('\n') + '\n')
        self.unknowns.write('%-20s line %d, word %d\n' % (
            word, self.analyzer.line_number, self.analyzer.word_number))

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
            print('Cannot create %s: %s' % (name, e.strerror))
            return None
    if not wanted and f is not None:
        f.close()
        return None
    return f

