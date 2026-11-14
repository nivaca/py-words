"""The entries of Logeion (https://logeion.uchicago.edu), the Latin and
Greek dictionaries of the University of Chicago, for the words looked up:
the second source of the window, the terminal interface and the command
line, beside this program's own dictionary ("local").

Logeion has the entries of many dictionaries (Lewis and Short, Georges,
Gaffiot, DMLBS, Du Cange …) but does not analyse an inflected form, so the
words are analysed here first, and Logeion is asked for their lemmas: the
first of the principal parts of each entry found (arma: armum and armo;
dixit: dico).  The analysis is shown before Logeion's entries, as this
program shows it but without its meanings: the entries and the forms
(dixi: dico, dicere, dixi, dictus; dix-ī  1SG.PRF.ACT.IND).  A word
with no lemma here (one that is not found, an irregular form or pronoun)
is asked for as it is written, and Logeion finds what it can for it.

The entries can be those of all the dictionaries of Logeion, or of one
(DICTIONARIES): the others are left out, but not the short definition,
the frequency and the examples from the corpus.  The source and the
dictionary chosen are kept in the section [logeion] of the configuration
file (source = "local" or "logeion", dictionary = "all" or a code of
DICTIONARIES), for the next start of any of the programs.  Asking
Logeion needs the internet; its pages are kept in memory while the
program runs.  The engine that asks Logeion and renders its entries
(logeion_api.py, logeion_entry.py, logeion_render.py, logeion_dom.py,
logeion_text.py) is that of py-logeion.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass, field

import colours
import config
import logeion_api as api
from config import ConfigError
from forms import describe_part, principal_parts
from interface import N_, tr
from logeion_entry import DICTIONARIES as NAMES_OF, DICTIONARY, Entry, \
    Options, page_entry, slug
from logeion_render import Style, render_entry
from layout import kind_of
from model import Pos, PronounKind
from render import MEANING_CODE, Renderer
from results import Origin, WordResult

LOCAL, LOGEION = 'local', 'logeion'
SOURCES = (LOCAL, LOGEION)
#  The names of the sources, in the selectors
NAMES = {LOCAL: N_('Local'), LOGEION: N_('Logeion')}
SECTION = 'logeion'

#  The dictionaries to choose from: all, or one of the Latin ones of
#  Logeion, by their codes (those of py-logeion: -d ls), with their names
ALL = 'all'
LEWIS_SHORT = 'ls'
DICTIONARIES = {ALL: N_('All dictionaries')} | {
    code: name for code, name in (NAMES_OF[dname] for dname in (
        'LewisShort', 'Lewis', 'Georges', 'Gaffiot 2016', 'DMLBS', 'LaNe',
        'DuCange', 'Lana-Michelone', 'FriezeDennisonVergil',
        'Latino-Sinicum'))}


def dictionary_name(code: str) -> str:
    """The name of the dictionary CODE, as the selectors show it."""
    return tr(DICTIONARIES[code]) if code == ALL else DICTIONARIES[code]


def dictionary_code(wanted: str) -> str | None:
    """The code of the dictionary WANTED (its code or name, as typed:
    'ls', 'Lewis & Short', 'gaffiot'), or None."""
    w = slug(wanted)
    for code, name in DICTIONARIES.items():
        if w in (slug(code), slug(name)):
            return code
    for code, name in DICTIONARIES.items():     # (the start of a name)
        if code != ALL and len(w) > 2 and slug(name).startswith(w):
            return code
    return None


def saved_source() -> str:
    """The source kept in the configuration file (local if none)."""
    source = config.section(SECTION).get('source')
    return source if source in SOURCES else LOCAL


def saved_dictionary() -> str:
    """The dictionary kept in the configuration file (all if none)."""
    code = config.section(SECTION).get('dictionary')
    return code if code in DICTIONARIES else ALL


def save_source(source: str) -> str:
    """Keeps SOURCE in the configuration file; returns '' or why it could
    not be kept."""
    return _save('source', source)


def save_dictionary(code: str) -> str:
    """Keeps the dictionary CODE, as save_source."""
    return _save('dictionary', code)


def _save(key: str, value: str) -> str:
    try:
        config.update(SECTION, {**config.section(SECTION), key: value})
    except (OSError, ConfigError) as e:
        return tr('The settings were not saved: {error}', error=e)
    return ''


# Lemmas -------------------------------------------------------------------

#  The lemmas of the pronouns whose principal parts are not given: the
#  personal ones by their first stem, those of qui and aliqui by their
#  kind (the substantive ones are quis and aliquis)
PERSONAL = {'ego': 'ego', 'tu': 'tu', 'n': 'nos', 'v': 'vos', 'zzz': 'sui'}
SUBSTANTIVE = (PronounKind.INTERR, PronounKind.INDEF)


def lemma(entry) -> str:
    """The lemma of a dictionary ENTRY, as Logeion writes it: the first of
    its principal parts, with i for j (juvo: iuvo); for the pronouns that
    have none, their nominative (qui, quis, ego, nos, sui …), or ''."""
    first = principal_parts(entry).split(',')[0].strip()
    if not first and entry.part.pos == Pos.PRON:
        stem = entry.stems[0]
        if entry.part.decl[0] == 5:
            first = PERSONAL.get(stem, '')
        elif stem.endswith('qu'):
            first = stem + ('is' if entry.part.kind in SUBSTANTIVE else 'i')
    return first.replace('j', 'i').replace('J', 'I')


def lemmas(result: WordResult) -> list[str]:
    """The lemmas to ask Logeion for, for the analysis RESULT of a word,
    each once; the word itself for a reading without one (an irregular
    form, a pronoun), and if nothing is found."""
    out: list[str] = []
    for reading in result.readings:
        entries = [p.entry for p in reading.forms if p.entry is not None]
        if not entries and reading.forms and \
                reading.forms[0].origin != Origin.UNIQUE:
            continue                    # (a prefix or a trick: its word
                                        # has a reading of its own)
        name = lemma(entries[0]) if entries else ''
        name = name or result.word
        if name not in out:
            out.append(name)
    return out or [result.word]


# Asking Logeion -----------------------------------------------------------

@dataclass
class Page:
    """What Logeion has for one LEMMA: its ENTRY, or PROBLEM (why there is
    none)."""
    lemma: str
    entry: Entry | None = None
    problem: str = ''


@dataclass
class Word:
    """A word looked up, its analysis (the lines of analysis()) and the
    pages of its lemmas."""
    word: str
    lemmas: list[str]
    pages: list[Page] = field(default_factory=list)
    analysis: list[str] = field(default_factory=list)


class AnalysisRenderer(Renderer):
    """The results of this program without their meanings (those of
    Logeion come after them), and with each entry only as its dictionary
    form and its part of speech: its codes, flags (medieval, rare …) and
    number belong to this program's meaning, which is not shown, and
    would only tell apart entries that are, here, the same word (the four
    entries of dico)."""

    def line(self, text: str, indent: int = 0, code: int | None = None):
        if code != MEANING_CODE:
            super().line(text, indent, code)

    def entry_header(self, entry) -> str:
        if not self.s.show_dictionary_forms:
            return ''
        return '  '.join(w for w in (principal_parts(entry, self.t),
                                     describe_part(entry.part, self.t))
                         if w)


def analysis(session, result: WordResult) -> list[str]:
    """The lines of the analysis RESULT, as this program shows them but
    without the line of the word (the line of the results of Logeion
    shows it) nor the meanings (see AnalysisRenderer); an entry once where
    several of them are alike (dico: four entries; quae: eight of qui and
    quis, four kinds of pronoun), with all their forms."""
    text = session.renderer(AnalysisRenderer).word(result)
    lines = text.rstrip('\n').split('\n')[1:]
    if session.settings.pearse_codes:   # (no indentation to go by)
        return [line for n, line in enumerate(lines)
                if n == 0 or line != lines[n - 1]]
    #  an entry (two spaces in), and its forms below: those of the same
    #  entry line together, each form once, in the order they come
    blocks: dict[str, list[str]] = {}
    current: list[str] = []
    for line in lines:
        if len(line) - len(line.lstrip(' ')) <= 2:
            current = blocks.setdefault(line, [])
        elif line not in current:
            current.append(line)
    return [line for head, forms in blocks.items()
            for line in [head] + forms]


def queries(session, line: str) -> list[Word]:
    """The words of LINE (Latin), their analysis and their lemmas, from
    SESSION (without asking Logeion yet)."""
    return [Word(r.word, lemmas(r), analysis=analysis(session, r))
            for r in session.analyzer.analyze_line(line)]


class Logeion:
    """Asks Logeion for pages, keeping them while the program runs."""

    def __init__(self, client: api.Client | None = None):
        self.client = client or api.Client()

    def fetch(self, words: list[Word]) -> list[Word]:
        """The pages of the lemmas of WORDS (filled in, and returned); first,
        that of the word as written, if it is a headword of Lewis and
        Short's (arma, whose lemma here is armum; not dixi or est, which
        other dictionaries have only to send to dico and sum).  If Logeion
        cannot be reached, a page says why, and the rest are not asked
        for."""
        shown: set[str] = set()         # (two lemmas, one page: volo)
        for word in words:
            if word.word not in word.lemmas:
                try:
                    page = self.client.page(word.word)
                except api.NotFound:
                    page = None
                except api.NetworkError as e:
                    word.pages.append(unreachable(word.word, e))
                    return words
                if page is not None and \
                        page['word'] == api.normal_word(word.word) and \
                        LEWIS_SHORT in (s.code for s in
                                        page_entry(page).dictionaries):
                    self._add(word, word.word, page, shown)
            for name in word.lemmas:
                try:
                    page = self.client.page(name)
                except api.NotFound as e:
                    word.pages.append(Page(name, problem=not_found(e)))
                    continue
                except api.NetworkError as e:
                    word.pages.append(unreachable(name, e))
                    return words
                self._add(word, name, page, shown)
        return words

    @staticmethod
    def _add(word: Word, name: str, page: dict, shown: set[str]):
        """PAGE (of NAME) among those of WORD, unless it is shown already."""
        if page['word'] in shown:
            return
        shown.add(page['word'])
        #  (Logeion's analysis of the lemma, a form of itself, is not what
        #  was looked up)
        page = {**page, 'parses': [], 'lemmas': []}
        word.pages.append(Page(name, page_entry(page)))

    def look_up(self, session, line: str) -> list[Word]:
        return self.fetch(queries(session, line))


def not_found(e: api.NotFound) -> str:
    if e.closest:
        return tr('Logeion has no entry for {word} (the nearest: '
                  '{closest}).', word=e.word, closest=e.closest)
    return tr('Logeion has no entry for {word}.', word=e.word)


def unreachable(name: str, e: BaseException) -> Page:
    return Page(name, problem=tr('Logeion could not be reached: {error}',
                                 error=reason(e)))


def reason(e: BaseException) -> str:
    """Why a request failed, briefly."""
    return str(getattr(e, 'reason', None) or e)


# Showing ------------------------------------------------------------------

#  The kinds of the lines of render(): the line of a word looked up, those
#  of its analysis (as this program shows its results), and those of the
#  pages (and of the problems) after it
HEAD, ANALYSIS, PAGE = 'head', 'analysis', 'page'


def render(words: list[Word], style: Style, width: int,
           dictionary: str = ALL, wrap_analysis: bool = True,
           colour: bool = False) -> list[tuple[str, str]]:
    """The lines of WORDS, WIDTH wide, as (kind, line): for each word, a
    line with it and its lemmas (HEAD), its analysis (ANALYSIS: plain
    text, as this program's results; wrapped to WIDTH unless not
    WRAP_ANALYSIS, for the window, which styles them as those), then the
    pages (PAGE), with the ANSI codes and links of STYLE, which the
    terminal interface and the window turn into their own; with COLOUR,
    the analysis too, as colours.py colours this program's results.
    DICTIONARY: all of them, or the code of the only one shown."""
    lines: list[tuple[str, str]] = []
    for word in words:
        if lines:
            lines.append((PAGE, ''))
        head = style.headword(word.word)
        if word.lemmas != [word.word]:
            head += style.dim('  →  ' + ', '.join(word.lemmas))
        lines.append((HEAD, head))
        for line in word.analysis:
            pieces = wrapped(line, width, wrap_analysis)
            if colour:
                rest = colours.KINDS.get(kind_of(line), '')
                pieces = [colours.line(pieces[0])] + \
                    [colours.styled(p, rest) for p in pieces[1:]]
            lines += [(ANALYSIS, piece) for piece in pieces]
        for page in word.pages:
            lines.append((PAGE, ''))
            if page.entry is None:
                lines += [(PAGE, style.dim(line)) for line in
                          textwrap.wrap(page.problem, width)]
                continue
            missing = missing_from(page.entry, dictionary)
            rendered = render_entry(page.entry, dictionary, style, width,
                                    Options()).lines
            if missing:                 # (the title, then why)
                rendered[1:1] = [''] + [style.dim(line) for line in
                                        textwrap.wrap(missing, width)]
            lines += [(PAGE, line) for line in rendered]
    return lines


def wrapped(line: str, width: int, wrap: bool = True) -> list[str]:
    """LINE of the analysis in lines of WIDTH (if WRAP), the next ones
    indented two spaces more, as words_tui.py wraps the results."""
    if not wrap or len(line) <= width:
        return [line]
    indent = ' ' * (len(line) - len(line.lstrip()) + 2)
    return textwrap.wrap(line, width, subsequent_indent=indent) or [line]


def missing_from(entry: Entry, dictionary: str) -> str:
    """'' if ENTRY has an entry of DICTIONARY (or it is all); else, that it
    has none, and which dictionaries have one."""
    if dictionary == ALL or any(s.code == dictionary
                                for s in entry.dictionaries):
        return ''
    others = ', '.join(s.name for s in entry.sections
                       if s.kind == DICTIONARY)
    name = dictionary_name(dictionary)
    if not others:
        return tr('{dictionary} has no entry for {word}.',
                  dictionary=name, word=entry.word)
    return tr('{dictionary} has no entry for {word} (it is in: '
              '{dictionaries}).', dictionary=name, word=entry.word,
              dictionaries=others)


def text(words: list[Word], width: int = 78, styled: bool = False,
         dictionary: str = ALL) -> str:
    """WORDS as text (STYLED: with the colours and links of a terminal)."""
    return '\n'.join(line for _, line in
                     render(words, Style(styled), width, dictionary,
                            colour=styled))

