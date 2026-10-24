"""The help ("Help"): how to search, how to read the results (what the
codes in brackets like [XXXBO] and the abbreviations of the analyses
mean), and where the settings are.

Every program shows it, in the language of the interface: "Help" (and F1)
in the window, the "Help" section of the web page, F1 in words_tui.py,
~H in the interactive command line, and words.py --guide.  Each program
passes its own paragraphs on how to use it (USING); the rest is shared.
The example, the code tables and the abbreviations are built from the
program and its data, so the help can't go stale.

It's a list of blocks, (kind, text): 'h' a heading, 'p' a paragraph,
'li' a list item and 'pre' preformatted text; text() and html() write it
out.
"""

from __future__ import annotations

import html as _html
import os
import textwrap

import config
import interface
import xmldata
from editor import CODE_FIELDS, DESCRIPTIONS, FIELD_LABELS
from interface import N_, tr
from lexicon import GLOSSES, source_names
from settings import Settings
from version import NAME

Block = tuple[str, str]

EXAMPLE = 'amicorum'
EXAMPLE_CODES = 'XXXBO'         # (those of amicus, amici)

#  The examples to click before the first search (in the window and on the
#  web page): Latin ones, and a word of the meanings to look up in Latin,
#  by the language of the meanings
LATIN_EXAMPLES = ('amicorum', 'arma virumque cano')
TO_LATIN_EXAMPLE = {'en': 'friend', 'es': 'amigo'}
#  Ojo: el ejemplo se busca en vivo, pero estos códigos están escritos a
#  mano.  Si cambian los de amicus en el diccionario, actualizarlos.

INTRO = N_('{name} is a Latin dictionary that knows Latin grammar: it '
           'analyses a Latin word into the dictionary entries and the forms '
           'it can be, with their meanings, and finds the Latin for a word '
           'of the language of the meanings.')

SEARCHING = (
    N_('Type a Latin word, or a whole line of Latin, and look it up: each '
       'word is analysed in turn.  Capitals do not matter, nor do u and v, '
       'or i and j (iulius, Julius and IVLIVS are the same word), nor long '
       'marks and other accents: amīcus is amicus, and cælum is caelum.'),
    N_('In the other direction, from the language of the meanings to '
       'Latin, type one word and, if you like, a part of speech after it '
       '(friend N, friend ADJ; the parts of speech are N, PRON, ADJ, NUM, '
       'ADV, V, PREP, CONJ and INTERJ): the Latin entries whose meanings '
       'have that word are listed, the best first.'),
    N_('When a word finds nothing as it is typed, the program tries other '
       'spellings (medieval ones, syncope, two words written as one ...) '
       'and says what it did.  With the fuzzy search (on as usual), a word '
       'that still finds nothing is followed by the results of its near '
       'spellings: amicuss finds amicus.  Unknown words with a capital are '
       'taken as names, and left alone.'),
)

#  How each program is used (the terminal and the command line give their
#  own lists of keys and commands)
WINDOW = (
    N_('Type in the box at the top and press Enter, or "Look up"; the '
       'arrow at the right of the box lists the earlier searches.'),
    N_('"Latin → …" and "… → Latin" choose the direction of the search, '
       '"Meanings in" the language of the meanings, and "Fuzzy search", '
       'beside it, whether a word that finds nothing is followed by its '
       'near spellings.  The menus have the rest: Dictionary (the '
       'dictionary editor, and the other settings, each with its help), '
       'View (find in the results, the size of the text, the fonts, dark '
       'mode) and Help (this text, and the version and the credits).'),
    N_('In the results, click the first word of an entry to look it up, or '
       'double-click any word (a word of the meanings is looked up in '
       'Latin).  Point at the codes in brackets or at an analysis (GEN.PL) '
       'to see what they mean.  A right click copies or looks up a word, '
       'and Ctrl and F finds a text in the results.'),
    N_('Ctrl and + or − make the text larger or smaller (Ctrl and 0: as '
       'usual), and the moon at the bottom right makes the window dark (a '
       'sun, then, makes it light again).'),
)
WEB = (
    N_('Type in the box at the top and press Enter, or "Look up"; the two '
       'choices below it give the direction of the search, "Meanings in" '
       'the language of the meanings, and "Fuzzy search" whether a word '
       'that finds nothing is followed by its near spellings.'),
    N_('The first word of each entry of the results is a link to its own '
       'search, and every search has its own address, which can be '
       'bookmarked.  The moon makes the page dark, and the sun light '
       'again.  At the foot, '
       '"Earlier searches" lists the recent ones, "Settings" has the other '
       'settings (each with its help), "Help" is this text and "About" '
       'shows the version and the credits.'),
    N_('Double-click any word of the results to look it up (a word of the '
       'meanings is looked up in Latin), and point at the codes in '
       'brackets or at an analysis (GEN.PL), or tap them, to see what they '
       'mean.'),
)

RESULTS = N_('This is what {name} shows for {word}:')
LINES = (
    N_('The first line is the word looked up.  Each entry it can be '
       'follows, indented.'),
    N_('The first line of an entry has its dictionary form (the principal '
       'parts: amicus, amici), its part of speech and its grammar in words '
       '(noun, 2nd declension, masculine), the codes in brackets '
       '([XXXBO], see below) and, for some entries, their age or frequency '
       'in words (archaic, lesser ...).'),
    N_('The next line is the meaning.  Its senses are separated by '
       'semicolons, the commonest first; a slash separates alternatives '
       '(counselor/courtier), and parentheses give the context.  [en] '
       'before a meaning says that it is not translated, and is given in '
       'English.'),
    N_('Then come the forms the word can be: the stem and the ending, '
       'separated by a hyphen (amīc-ōrum, with the long vowels marked), '
       'and what the form is, in the abbreviations listed below '
       '(GEN.PL: genitive plural) or, with the setting use_glosses off, in '
       'words.  One spelling can be several forms: the amīc-ōrum of the '
       'adjective is GEN.PL.M and GEN.PL.N.'),
    N_('A line before an entry may say how the word was found: a prefix, a '
       'suffix or an enclitic (-que, -ne, -ve) that was taken off, with '
       'its meaning, or a spelling trick (spelling: ...), with a sentence '
       'on what was done.'),
    N_('Notes in parentheses: (unknown), for a word that was not found; '
       '(near spellings: ...), before the results of its near spellings; '
       '(less likely forms are not shown), when the setting trim_output '
       'left some out.  From the language of the meanings: (no match), '
       '(near words: ...) and, after the best six entries, (... more not '
       'shown).'),
)

CODES = N_('The five letters in brackets after an entry say when, where, '
           'how often and on whose authority the word is used, in this '
           'order: its age, its area (the subject it belongs to), its '
           'region, its frequency and its source.  X says that there is '
           'nothing particular to say: in use throughout, general, '
           'everywhere, or not known.  So the [{codes}] of amicus is read:')
EACH_LETTER = N_('Each letter can be:')
CODES_MORE = N_('An entry can have more than one source: then the others '
                'follow the five letters, each after a + ([XXXCO+M] is '
                'also from source M).  '
                'The age, when it is known, and the frequency, when it is '
                'lesser or rarer, are also given in words after the codes '
                '(archaic, lesser ...).  The parameter '
                'show_codes hides the codes, and the dictionary '
                'editors explain each code of an entry as it is edited.')

GLOSSES_TEXT = N_('The forms are written with the abbreviations of the '
                  'Leipzig Glossing Rules, joined by full stops (GEN.PL, '
                  '1SG.PRF.ACT.IND); those marked * are not in the Leipzig '
                  'list.  They are kept in data/gloss.xml, where they can '
                  'be changed.')
CATEGORIES = {'case': N_('case'), 'number': N_('number'),
              'gender': N_('gender'), 'person': N_('person'),
              'tense': N_('tense'), 'voice': N_('voice'),
              'mood': N_('mood'), 'form': N_('other verb forms'),
              'comparison': N_('degree'), 'sort': N_('numerals')}

SETTINGS = N_('Each setting has its own help: in the Settings of the window '
              'and the web page, in F3 of the terminal, and with ? in the # '
              'and ! dialogues of the command line.  The parameters are for '
              'everyone, the developer modes for special purposes; the '
              'programs share them.')

SOURCES = (
    N_('The dictionary is that of WORDS, by William Whitaker (1936-2010), '
       'with additions from five other works.  R. E. Latham, Revised '
       'Medieval Latin Word-List from British and Irish Sources, gave '
       'medieval senses, words and spellings (source code M).  '
       'J. Echave-Sustaeta, Lengua latina. Vocabulario básico, gave senses '
       'and words, in English and in Spanish (source code A).  Lewis and '
       'Short, A Latin Dictionary, in the text of the Perseus Digital '
       'Library (CC BY-SA 4.0), gave some 3,000 rare words that WORDS did '
       'not have (source code S, as other entries of WORDS taken from it).  '
       'R. de Miguel and the Marqués de Morante, Nuevo diccionario '
       'latino-español etimológico (1867), gave some 13,800 rare words and '
       'proper names that WORDS did not have, and the Spanish meanings of '
       'some 37,000 entries (source code m); Echave-Sustaeta gave those of '
       'the entries De Miguel does not have, and the other Spanish '
       'meanings are translations.  '
       'Collatinus, '
       'by Yves Ouvrard and Philippe Verkerk, gave the long vowels of the '
       'stems and endings, and some abbreviations (source code H).  '
       'Collatinus, '
       'in its turn, made its lexicon with the help of the dictionaries '
       'of Gaffiot, Jeanneau, Du Cange and Lewis and Short, among others; '
       'the README names all the sources and people it thanks.'),
    N_('{name} is free software, distributed under the GNU General Public '
       'License, version 3 or later (see LICENCE.txt): it can be used, '
       'copied, changed and shared, but a program that includes it must be '
       'shared under the same licence, with its source code.  The data of '
       'WORDS are free for any use, by permission of William Whitaker.  '
       '"About" gives the version and the credits.'),
)


def blocks(session, using) -> list[Block]:
    """The help, for the program whose own paragraphs are USING (blocks),
    with the data of SESSION."""
    out: list[Block] = [('p', tr(INTRO, name=NAME)),
                        ('h', tr('Searching'))]
    out += [('p', tr(t)) for t in SEARCHING]
    out += [('h', tr('Using this program'))] + list(using)
    out += [('h', tr('Reading the results')),
            ('p', tr(RESULTS, name=NAME, word=EXAMPLE)),
            ('pre', example(session))]
    out += [('li', tr(t)) for t in LINES]
    out += codes(session.lexicon.datadir)
    out += glosses(session)
    out += [('h', tr('Settings')), ('p', tr(SETTINGS))]
    out += [('h', tr('Sources and licence'))]
    out += [('p', tr(t, name=NAME)) for t in SOURCES]
    return out


def paragraphs(texts) -> list[Block]:
    """The paragraphs TEXTS (to translate), as blocks."""
    return [('p', tr(t)) for t in texts]


def example(session) -> str:
    """The results for EXAMPLE, with the usual settings (but the language
    of the meanings, and the glosses, of SESSION)."""
    from session import Session
    s = session.settings
    settings = Settings(language=s.language, use_glosses=s.use_glosses)
    text = Session(session.lexicon, settings,
                   write=lambda text: None).lookup_latin(EXAMPLE)
    return text.rstrip('\n')


def codes(datadir: str) -> list[Block]:
    """What the codes in brackets mean: the example, then each letter."""
    names = _sources(datadir)

    def meaning(field: str, letter: str) -> str:
        if field == 'source':
            return names.get(letter, '')
        return tr(DESCRIPTIONS[field].get(letter, ''))
    labels = {f: tr(FIELD_LABELS[f]) for f in CODE_FIELDS}
    width = max(len(v) for v in labels.values())
    read = '\n'.join(f'{letter}  {labels[f]:<{width}}  {meaning(f, letter)}'
                     for f, letter in zip(CODE_FIELDS, EXAMPLE_CODES))
    out: list[Block] = [('h', tr('The codes in brackets')),
                        ('p', tr(CODES, codes=EXAMPLE_CODES)),
                        ('pre', read), ('p', tr(EACH_LETTER))]
    for f in CODE_FIELDS:
        letters = names if f == 'source' else DESCRIPTIONS[f]
        rows = [f'  {letter}  {meaning(f, letter)}' for letter in letters
                if not meaning(f, letter).startswith('(')]   # (unused)
        out.append(('pre', '\n'.join([labels[f].capitalize()] + rows)))
    out.append(('p', tr(CODES_MORE)))
    return out


#  The sources in sources.xml that aren't books.  Estas sí se traducen; los
#  títulos de los libros se dejan como están.
GENERAL_SOURCES = (N_('general or unknown'), N_('other dictionaries'),
                   N_('found in a translation'), N_("Whitaker's guess"),
                   N_('temporary'), N_('sent by a user'))


def _sources(datadir: str) -> dict[str, str]:
    try:
        names = source_names(datadir)
    except xmldata.DataError:
        return {}
    return {code: tr(name) if name in GENERAL_SOURCES else name
            for code, name in names.items()}


def _glosses(session) -> list[tuple]:
    """(gloss, meaning) for the abbreviations of gloss.xml; the meanings
    are in the language of the interface if there is a language file for
    it (they are texts of the results)."""
    path = os.path.join(session.lexicon.datadir, GLOSSES)
    try:
        items = [g for g, _ in xmldata.read_glosses(path)]
    except (OSError, xmldata.DataError):
        return []
    try:
        language = session.lexicon.language(interface.code())
    except (LookupError, xmldata.DataError):
        language = None
    return [(g, language.text(g.meaning) if language else g.meaning)
            for g in items]


def glosses(session) -> list[Block]:
    """The abbreviations of the analyses, from gloss.xml, by category."""
    items = _glosses(session)
    if not items:
        return []
    by_category: dict[str, list[str]] = {}
    for g, meaning in items:
        star = '' if g.leipzig else '*'
        by_category.setdefault(g.category, []).append(
            f'{g.abbreviation}{star} {meaning}')
    out: list[Block] = [('h', tr('The abbreviations of the analyses')),
                        ('p', tr(GLOSSES_TEXT))]
    for category, abbreviations in by_category.items():
        name = tr(CATEGORIES.get(category, category))
        out.append(('li', f'{name.capitalize()}: ' +
                    ', '.join(abbreviations) + '.'))
    return out


# ---------------------------------------------------------------------------
#  Short explanations, for the window's tooltips (the same words as the
#  help)

def explain_codes(codes: str, datadir: str) -> str:
    """What the codes in brackets of an entry mean, one letter a line:
    "XXXBO" -> "X  age: in use throughout" ...; the other sources after
    a + ("XXXCO+M") too."""
    names = _sources(datadir)
    first, *more = codes.split('+')
    lines = []
    for field, letter in zip(CODE_FIELDS, first):
        if field == 'source':
            meaning = names.get(letter, '')
        else:
            meaning = tr(DESCRIPTIONS[field].get(letter, ''))
        lines.append(f'{letter}  {tr(FIELD_LABELS[field])}: {meaning}')
    for letter in more:
        lines.append(f'{letter}  {tr("other source")}: '
                     f'{names.get(letter, "")}')
    return '\n'.join(lines)


def gloss_table(session) -> dict[str, str]:
    """{abbreviation: meaning}, from gloss.xml."""
    return {g.abbreviation: meaning for g, meaning in _glosses(session)}


def explain_analysis(analysis: str, table: dict[str, str]) -> str:
    """What the abbreviations of an analysis mean, one a line: "2SG.PRF"
    -> "2  second person", "SG  singular", "PRF  perfect" ('' if it has
    none that TABLE knows)."""
    parts = analysis.split('.')
    lines = []
    i = 0
    while i < len(parts):
        two = '.'.join(parts[i:i + 2])          # (FUT.PRF is one)
        if i + 1 < len(parts) and two in table:
            lines.append(f'{two}  {table[two]}')
            i += 2
            continue
        part = parts[i]
        person, rest = part[:1], part[1:]
        if person.isdigit() and person in table and rest in table:
            lines += [f'{person}  {table[person]}',      # (2SG)
                      f'{rest}  {table[rest]}']
        elif part in table:
            lines.append(f'{part}  {table[part]}')
        i += 1
    return '\n'.join(lines)


def examples(language: str) -> list[tuple[str, str, bool]]:
    """The examples to click before the first search: (label, query, to
    Latin), for the language of the meanings LANGUAGE."""
    out = [(query, query, False) for query in LATIN_EXAMPLES]
    word = TO_LATIN_EXAMPLE.get(language)
    if word:
        out.append((tr('{word} (to Latin)', word=word), word, True))
    return out


def configuration() -> Block:
    """Where the configuration file is (not for the web page in the
    browser, whose settings are kept by the browser)."""
    return ('p', tr('The configuration file is {path}',
                    path=config.config_path()) + '.')


# ---------------------------------------------------------------------------
#  Writing it out

def text(help_blocks: list[Block], width: int = 76) -> str:
    """The help as plain text, lines at most WIDTH long."""
    out = []
    previous = ''
    for kind, body in help_blocks:
        if kind == 'h':
            out += ['', body, '-' * len(body)]
        elif kind == 'p':
            out += [''] + textwrap.wrap(body, width, break_on_hyphens=False,
                                        break_long_words=False)
        elif kind == 'li':
            if previous != 'li':
                out.append('')
            out += textwrap.wrap(body, width, initial_indent='  * ',
                                 break_on_hyphens=False,
                                 subsequent_indent='    ')
        else:
            out += [''] + ['  ' + line for line in body.split('\n')]
        previous = kind
    while out and not out[0]:
        out.pop(0)
    return '\n'.join(out) + '\n'


def html(help_blocks: list[Block]) -> str:
    """The help as HTML (inside an element of the page)."""
    out = []
    in_list = False
    for kind, body in help_blocks:
        if kind == 'li' and not in_list:
            out.append('<ul>')
        elif kind != 'li' and in_list:
            out.append('</ul>')
        in_list = kind == 'li'
        e = _html.escape(body, quote=False)
        out.append({'h': f'<h3>{e}</h3>', 'p': f'<p>{e}</p>',
                    'li': f'<li>{e}</li>', 'pre': f'<pre>{e}</pre>'}[kind])
    if in_list:
        out.append('</ul>')
    return '\n'.join(out)
