"""Tests of the lexicon cache."""

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # the package, when run from anywhere

import lexicon, xmldata
from lexicon import Lexicon

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
DATA_FILES = ('dictionary.xml', 'inflections.xml', 'uniques.xml',
              'addons.xml')


def summary(lex):
    """Everything a lexicon holds, as comparable text."""
    return ([xmldata.entry_xml(e) for e in lex.entries[:-1]],
            {k: [(r.stem, r.key, r.entry.id) for r in refs]
             for k, refs in lex.stems.items()},
            {k: [repr(i) for i in v] for k, v in lex.endings.items()},
            [repr(i) for i in lex.blank_endings],
            {k: [repr(i) for i in v] for k, v in lex.qu_endings.items()},
            {k: [(u.word, u.meaning, repr(u.form)) for u in v]
             for k, v in lex.uniques.items()},
            [repr(a) for a in lex.prefixes + lex.tickons + lex.suffixes +
             lex.tackons + lex.packons])


class CacheTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = os.path.join(self.tmp.name, 'cache')
        self.data = os.path.join(self.tmp.name, 'data')
        os.mkdir(self.data)
        for name in DATA_FILES:
            with open(os.path.join(DATA, name), 'rb') as f, \
                    open(os.path.join(self.data, name), 'wb') as g:
                g.write(f.read())
        self.old = os.environ.get('WHITAKERS_WORDS_CACHE')
        os.environ['WHITAKERS_WORDS_CACHE'] = self.cache

    def tearDown(self):
        if self.old is None:
            del os.environ['WHITAKERS_WORDS_CACHE']
        else:
            os.environ['WHITAKERS_WORDS_CACHE'] = self.old
        self.tmp.cleanup()

    def cached(self, what):
        return [n for n in os.listdir(self.cache) if n.startswith(what)]

    def test_cached_lexicon_is_the_same(self):
        fresh = Lexicon.load(self.data, cache=False)
        Lexicon.load(self.data)                         # fills the cache
        self.assertEqual(len(self.cached('lexicon')), 1)
        cached = Lexicon.load(self.data)
        self.assertEqual(summary(cached), summary(fresh))
        # the stems still point at the entries of the lexicon
        ref = cached.lookup('amic')[0]
        self.assertIs(ref.entry, cached.entries[ref.entry.id - 1])

    def test_cached_english_is_the_same(self):
        fresh = Lexicon.load(self.data, cache=False).english
        Lexicon.load(self.data).english                 # fills the cache
        self.assertEqual(len(self.cached('english')), 1)
        lex = Lexicon.load(self.data)
        for word in ('friend', 'love', 'be', 'war'):
            self.assertEqual(
                [(h.entry.id, h.sense, h.kind, h.rank)
                 for h in lex.english.search(word)],
                [(h.entry.id, h.sense, h.kind, h.rank)
                 for h in fresh.search(word)])
        hit = lex.english.search('friend')[0]
        self.assertIs(hit.entry, lex.entries[hit.entry.id - 1])

    def test_a_changed_file_is_read_again(self):
        Lexicon.load(self.data)
        path = os.path.join(self.data, 'dictionary.xml')
        with open(path, encoding='utf-8') as f:
            text = f.read()
        time.sleep(0.01)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text.replace('friend, ally, disciple;',
                                 'friend (changed);'))
        lex = Lexicon.load(self.data)
        self.assertTrue(any(e.meaning.startswith('friend (changed);')
                            for e in lex.entries))

    def test_a_bad_cache_is_ignored(self):
        Lexicon.load(self.data)
        path = os.path.join(self.cache, self.cached('lexicon')[0])
        with open(path, 'wb') as f:
            f.write(b'not a pickle')
        self.assertEqual(len(Lexicon.load(self.data).entries), 39336)

    def test_no_cache_where_it_cannot_be_written(self):
        with open(self.cache, 'w'):             # a file, not a folder
            pass
        self.assertEqual(len(Lexicon.load(self.data).entries), 39336)

    def test_no_cache_if_switched_off(self):
        os.environ['WHITAKERS_WORDS_CACHE'] = ''
        Lexicon.load(self.data)
        self.assertFalse(os.path.exists(self.cache))

    def test_old_caches_are_removed(self):
        lex = Lexicon.load(self.data)
        for i in range(lexicon.KEEP_FOLDERS + 2):
            path = os.path.join(self.cache, 'lexicon-old%d.pickle' % i)
            with open(path, 'wb'):
                pass
            os.utime(path, (1000 + i, 1000 + i))
        lex._cache.prune('lexicon')
        left = self.cached('lexicon')
        self.assertEqual(len(left), lexicon.KEEP_FOLDERS)
        self.assertIn(os.path.basename(lex._cache.path('lexicon')), left)


if __name__ == '__main__':
    unittest.main()
