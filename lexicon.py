"""The dictionary data, indexed for analysis.

`Lexicon.load(datadir)` reads the XML files and builds:

* `stems`: every stem of every entry, under its spelling folded by
  `model.fold` (lower case, v as u, j as i), with the stem's number (its
  "key", which says which endings it takes);
* `endings` and `blank_endings`: the inflections, by folded ending;
* `qu_endings`: the endings of the qu- pronouns (qui, quis, ...), which are
  only tried on words beginning with qu or cu;
* `uniques`, by folded form; and the prefixes, suffixes and tackons.

Reading the XML takes about half a second, so the lexicon (and, once
built, the English index) is cached in the user's cache folder (see
`cache_dir`) and read from there while the data files are unchanged.
"""

import bisect
import copy
import hashlib
import os
import pickle
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import NamedTuple

import english, model, xmldata
from version import VERSION
from model import (Pos, Decl, Comparison, NumeralSort, VerbKind, Freq,
                    Codes, Part, Entry, Inflection, Unique, Prefix, Suffix,
                    Tackon, fold)

DICTIONARY = 'dictionary.xml'
SPECIAL = 'special.xml'
INFLECTIONS = 'inflections.xml'
UNIQUES = 'uniques.xml'
ADDONS = 'addons.xml'
DATA_FILES = (DICTIONARY, SPECIAL, INFLECTIONS, UNIQUES, ADDONS)

#  The program's folder, and the data folder in it
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, 'data')


def default_datadir() -> str:
    """$WHITAKERS_WORDS_DATADIR, else the data folder next to the
    program."""
    return os.environ.get('WHITAKERS_WORDS_DATADIR') or DATA_DIR

#  The forms of esse are built in: its second stem is blank (es, est, esse
#  are the bare endings), which a dictionary entry cannot express.
ESSE_MEANING = ('be; exist; (also used to form verb perfect passive tenses) '
                'with NOM PERF PPL')


def esse(id: int) -> Entry:
    """The built-in entry for esse."""
    return Entry(id, ('s', '', 'fu', 'fut'),
                 Part(Pos.V, Decl(5, 1), kind=VerbKind.TO_BE),
                 Codes(freq=Freq.A), ESSE_MEANING)


class StemRef(NamedTuple):
    """One stem of a dictionary entry."""
    stem: str
    key: int                # which endings it takes; 0 for those of stem 1-2
    entry: Entry

    @property
    def part(self) -> Part:
        return self.entry.part


def indexed_stems(entry: Entry) -> list[tuple]:
    """The (stem, key) pairs under which ENTRY is found.

    Nouns, adjectives and verbs whose first two stems are equal are listed
    once, with key 0.  Adjectives, adverbs and numerals of a single degree
    or sort have one stem, whose key is that degree or sort.
    """
    st = entry.stems
    p = entry.part

    def usable(s):
        return s not in ('', 'zzz')
    if p.pos in (Pos.N, Pos.ADJ, Pos.V) and st[0] == st[1] and \
            st[0] != 'zzz':
        out = [(st[0], 0)]
        if p.pos != Pos.N:
            out += [(st[k], k + 1) for k in (2, 3) if usable(st[k])]
        return out
    if p.pos == Pos.ADJ and p.comparison in (Comparison.COMP,
                                             Comparison.SUPER):
        return [(st[0], 3 if p.comparison == Comparison.COMP else 4)]
    if p.pos == Pos.ADV and p.comparison in (Comparison.COMP,
                                             Comparison.SUPER):
        return [(st[0], 2 if p.comparison == Comparison.COMP else 3)]
    if p.pos == Pos.NUM and p.sort != NumeralSort.X:
        return [(st[0], int(p.sort))]
    return [(s, k + 1) for k, s in enumerate(st) if usable(s)]


@dataclass
class Lexicon:
    entries: list[Entry] = field(default_factory=list)
    special: list[Entry] = field(default_factory=list)
    stems: dict[str, list[StemRef]] = field(default_factory=dict)
    endings: dict[str, list[Inflection]] = field(default_factory=dict)
    blank_endings: list[Inflection] = field(default_factory=list)
    qu_endings: dict[str, list[Inflection]] = field(default_factory=dict)
    uniques: dict[str, list[Unique]] = field(default_factory=dict)
    prefixes: list[Prefix] = field(default_factory=list)
    tickons: list[Prefix] = field(default_factory=list)
    suffixes: list[Suffix] = field(default_factory=list)
    tackons: list[Tackon] = field(default_factory=list)
    packons: list[Tackon] = field(default_factory=list)
    _english: object | None = None
    _cache: _Cache | None = None

    @classmethod
    def load(cls, datadir: str, cache: bool = True) -> Lexicon:
        """Reads the data files in DATADIR (raises xmldata.DataError), or
        their cached copy if CACHE and they have not changed since."""
        for name in (DICTIONARY, INFLECTIONS):
            if not os.path.isfile(os.path.join(datadir, name)):
                raise FileNotFoundError('there is no %s in %s'
                                        % (name, datadir))
        store = _Cache.of(datadir) if cache else None
        lex = store.read('lexicon') if store else None
        if not isinstance(lex, cls):
            lex = cls._read(datadir)
            if store:
                store.write('lexicon', lex)
        lex._cache = store
        return lex

    @classmethod
    def _read(cls, datadir: str) -> Lexicon:
        def path(name):
            return os.path.join(datadir, name)
        lex = cls()
        lex.entries = [e for e, _ in xmldata.read_dictionary(path(DICTIONARY))]
        lex.entries.append(esse(len(lex.entries) + 1))
        if os.path.isfile(path(SPECIAL)):
            lex.special = [e for e, _ in xmldata.read_dictionary(
                path(SPECIAL), dictionary='special')]
        lex._index_stems()
        lex._index_inflections(
            [i for i, _ in xmldata.read_inflections(path(INFLECTIONS))])
        if os.path.isfile(path(UNIQUES)):
            for u, _ in xmldata.read_uniques(path(UNIQUES)):
                lex.uniques.setdefault(fold(u.word), []).insert(0, u)
        if os.path.isfile(path(ADDONS)):
            lex._sort_addons([a for a, _ in xmldata.read_addons(path(ADDONS))])
        return lex

    @property
    def english(self):
        """The English index (english.EnglishIndex), built when first
        needed."""
        if self._english is None:
            hits = self._cache.read('english') if self._cache else None
            if isinstance(hits, dict):
                self._english = english.EnglishIndex.unpack(hits,
                                                            self.entries)
            else:
                self._english = english.EnglishIndex.build(self.entries)
                if self._cache:
                    self._cache.write('english', self._english.pack(
                        self.entries))
        return self._english

    def with_entries(self, entries: list[Entry]) -> Lexicon:
        """A copy of this lexicon with ENTRIES as its general dictionary
        (esse is added), for trying out changes to the dictionary."""
        lex = copy.copy(self)
        lex.entries = list(entries) + [esse(len(entries) + 1)]
        lex._english = None
        lex._cache = None
        lex.__dict__.pop('_sorted_stems', None)
        lex._index_stems()
        return lex

    def _index_stems(self):
        index = defaultdict(list)
        for entry in self.entries + self.special:
            if entry is self.entries[-1]:          # esse: all four stems
                refs = [(s, k + 1) for k, s in enumerate(entry.stems)]
            else:
                refs = indexed_stems(entry)
            for stem, key in refs:
                index[fold(stem)].append(StemRef(stem, key, entry))
        self.stems = dict(index)

    def _index_inflections(self, inflections: list[Inflection]):
        """Endings are tried longest first and, for the same ending, in the
        reverse of their order in the file."""
        regular = defaultdict(list)
        qu = defaultdict(list)
        for infl in reversed(inflections):
            if not infl.ending:
                self.blank_endings.append(infl)
            elif infl.form.pos == Pos.PRON and infl.form.decl.which in (1, 2):
                qu[fold(infl.ending)].append(infl)
            elif infl.ending[-1] in ENDING_LETTERS:
                regular[fold(infl.ending)].append(infl)
        self.endings = dict(regular)
        self.qu_endings = dict(qu)

    def _sort_addons(self, addons):
        for a in addons:
            if isinstance(a, Prefix):
                (self.tickons if a.root == Pos.PACK else
                 self.prefixes).append(a)
            elif isinstance(a, Suffix):
                self.suffixes.append(a)
            else:
                (self.packons if a.is_packon else self.tackons).append(a)

    def lookup(self, stem: str) -> list[StemRef]:
        """The entries with this stem (compared by `fold`)."""
        return self.stems.get(fold(stem), [])

    def dictionary(self, name: str) -> list[Entry]:
        return self.special if name == 'special' else self.entries

    def neighbours(self, word: str, before: int = 5,
                   after: int = 3) -> list[Entry]:
        """The general dictionary entries around where WORD would be, for
        an unknown word."""
        if not hasattr(self, '_sorted_stems'):
            self._sorted_stems = sorted(
                (key, ref.entry.id) for key, refs in self.stems.items()
                for ref in refs if ref.entry.dictionary == 'general')
        i = bisect.bisect_left(self._sorted_stems, (fold(word), 0))
        if i == len(self._sorted_stems):
            i -= 1
        n = self._sorted_stems[i][1]
        return self.entries[max(0, n - 1 - before):n + after]


#  Only words ending in one of these letters can have a (non-blank) ending.
ENDING_LETTERS = frozenset('acdeimnorstu')


# ---------------------------------------------------------------------------
#  The cache

def cache_dir() -> str | None:
    """Where the cache is kept: $WHITAKERS_WORDS_CACHE (if empty, there is
    no cache), else the user's cache folder."""
    env = os.environ.get('WHITAKERS_WORDS_CACHE')
    if env is not None:
        return env or None
    if sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA') or \
            os.path.expanduser(r'~\AppData\Local')
    elif sys.platform == 'darwin':
        base = os.path.expanduser('~/Library/Caches')
    else:
        base = os.environ.get('XDG_CACHE_HOME') or \
            os.path.expanduser('~/.cache')
    return os.path.join(base, 'py-words')


KEEP_FOLDERS = 4        # data folders whose cache is kept


class _Cache:
    """The cached data of one data folder.  Each file holds a stamp (the
    size and time of the data files and of the code that reads them) and
    then the data, which is used only if the stamp is still the same."""

    def __init__(self, folder: str, name: str, stamp: tuple):
        self.folder = folder
        self.name = name
        self.stamp = stamp

    @classmethod
    def of(cls, datadir: str) -> _Cache | None:
        folder = cache_dir()
        if not folder:
            return None
        datadir = os.path.abspath(datadir)
        files = [os.path.join(datadir, n) for n in DATA_FILES] + \
            [m.__file__ for m in (model, xmldata, english, sys.modules[
                __name__])]
        stamp = [VERSION, sys.version_info[:2]]
        for f in files:
            try:
                st = os.stat(f)
                stamp.append((f, st.st_size, st.st_mtime_ns))
            except OSError:
                stamp.append((f, None))
        name = hashlib.sha1(datadir.encode('utf-8')).hexdigest()[:16]
        return cls(folder, name, tuple(stamp))

    def path(self, what: str) -> str:
        return os.path.join(self.folder, '%s-%s.pickle' % (what, self.name))

    def read(self, what: str):
        """The cached data, or None."""
        try:
            with open(self.path(what), 'rb') as f:
                if pickle.load(f) != self.stamp:
                    return None
                return pickle.load(f)
        except Exception:               # missing, unreadable or outdated
            return None

    def write(self, what: str, data) -> None:
        """Caches DATA, if the cache folder can be written."""
        path = self.path(what)
        tmp = '%s.%d.tmp' % (path, os.getpid())
        try:
            os.makedirs(self.folder, exist_ok=True)
            with open(tmp, 'wb') as f:
                pickle.dump(self.stamp, f, pickle.HIGHEST_PROTOCOL)
                pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)
            os.replace(tmp, path)
            self.prune(what)
        except Exception:
            try:
                os.remove(tmp)
            except OSError:
                pass

    def prune(self, what: str, keep: int = KEEP_FOLDERS) -> None:
        """Removes all but the KEEP most recently written caches of WHAT."""
        old = sorted((os.path.join(self.folder, n) for n in
                      os.listdir(self.folder)
                      if n.startswith(what + '-') and n.endswith('.pickle')),
                     key=os.path.getmtime, reverse=True)[keep:]
        for path in old:
            os.remove(path)
