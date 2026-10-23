How py-words was made
=====================

py-words is a Latin-English-Latin and Latin-Spanish-Latin dictionary: a
Python version of WORDS, the Latin-English dictionary program that
Colonel William Whitaker (1936-2010) wrote, with its meanings translated
to Spanish.  Nicolas Vaughan made it in 2026, starting from the Ada
version of WORDS maintained in
[mk270/whitakers-words](https://github.com/mk270/whitakers-words).  Here
I explain how it was made, in eight stages.

The dictionary has four sources: WORDS, by William Whitaker, for the
program and almost all of the entries; R. E. Latham's *Revised Medieval
Latin Word-List from British and Irish Sources*, for medieval senses,
words and spellings; J. Echave-Sustaeta's *Lengua latina. Vocabulario
básico*, for senses and words in English and in Spanish; and Collatinus,
by Yves Ouvrard and Philippe Verkerk, for the long vowels and the
meanings in French, German, Catalan and Galician (Collatinus, in its
turn, made its lexicon with the dictionaries of Gaffiot, Jeanneau, Du
Cange and Lewis and Short, among others, and the README names all the
sources and people it thanks).  py-words is free software, under the
GNU General Public License, version 3 or later; the data of WORDS are
free for any use, by permission of Whitaker.

Nicolas Vaughan is Associate Professor of Literature at the School of Arts
and Humanities of the Universidad de los Andes, Bogotá, Colombia.

1. A faithful translation
-------------------------

The first version was a translation, line by line, of the Ada program.
Its modules followed very closely the Ada packages, and it copied exactly
the behaviour of Ada, with all its peculiarities: strings of fixed length
filled with blanks, arrays counted from 1 (or from the bound that the Ada
code declared), exceptions used for controlling the program, as Ada did
with `Constraint_Error` and `End_Error`, an output based on columns as
with the `Text_IO` of Ada, and the dictionary kept in sorted files of
stems, searched with binary search through an index of their first two
letters.

The objective was an output identical, byte by byte, to the one of the
Ada program, and the measure were the regression tests of the Ada
version itself, whose inputs include 735 lines of the *Aeneid*.  As a
reference it was useful.  But in reality it was Ada written in Python:
around 10,300 lines in 26 modules, difficult to read and more difficult
to change.

2. The data in XML
------------------

WORDS keeps its data in four text files with fixed columns: DICTLINE.GEN
(the dictionary), INFLECTS.LAT (the endings), UNIQUES.LAT (irregular
forms) and ADDONS.LAT (prefixes, suffixes and enclitics).  I converted
them to XML:

| Original      | Now               | Contents                          |
|---------------|-------------------|-----------------------------------|
| DICTLINE.GEN  | `dictionary.xml`  | 39,335 entries                    |
| INFLECTS.LAT  | `inflections.xml` | 1,797 inflectional endings        |
| UNIQUES.LAT   | `uniques.xml`     | 79 irregular forms                |
| ADDONS.LAT    | `addons.xml`      | prefixes, suffixes and enclitics  |
| (in the code) | `sources.xml`     | the 26 source codes and the dictionaries they stand for |
| (new)         | `gloss.xml`       | the glossing abbreviations of the analyses (Leipzig Glossing Rules) |

The grammatical codes are written as in the original files (`N`, `V`,
`NOM`, `PRES`, the declensions as "2 1" ...), so any person who knows
WORDS can read an entry.  An XML Schema, `words.xsd`, describes the
format, and this permits an XML editor to check the files while you
write.  `words_convert.py` converts files in the original format to XML,
and `words_check.py` reports the mistakes in files edited by hand, with
the line numbers.

3. A redesign in idiomatic Python
---------------------------------

With the translation as reference, I wrote the program again as normal
Python.  What had to survive was what WORDS finds for a word; almost all
the rest could go.  The grammatical codes became enumerations, and the
entries, endings and forms became immutable records (dataclasses) that
reflect the XML.  Instead of the sorted files and the binary searches
there are now dictionaries in memory, so the stems, endings and
irregular forms are looked up directly, with u/v and i/j as the same
letter.  The analysis gives now structured results, which are ordered
and trimmed with a normal sort, instead of filling shared arrays, and the
settings are passed explicitly, not changed for a moment as a way of
passing arguments.  There is no shared mutable state.

The output received a new layout, more easy to read, and the command line
a modern one (`argparse`).  What the users really use was kept: the
settings files WORD.MOD and WORD.MDV, in their original format, with the
`#` and `!` dialogues, and the developer modes.  (The output files
WORD.OUT, WORD.UNK and WORD.STA were kept at first, and taken out
later.)  The result has around 6,700 lines, in modules
organised by task (see "How it works" in the README).

Checking the redesign
~~~~~~~~~~~~~~~~~~~~~

I compared the new analyser with the faithful translation in a corpus of
133,671 words: all the stems of the dictionary, forms generated from the
stems and the endings, and the inputs of the regression tests.  For each
word, the results of both versions were reduced to records that can be
compared (entry, stem, ending, grammatical form, and the affix or
spelling trick used, if any), and then compared.  99.2% of the words gave
the same results.  I revised every one of the other differences.  Each
one was a change on purpose, or a bug of the original that the redesign
does not repeat: stems matched with entries that have nothing to do,
results given to the wrong enclitic, malformed Roman numerals accepted, a
spelling rule that could never apply.  They are listed in "Changes from
the original program" in the README.  The searches from English to Latin
were checked in the same way.

4. Tools and refinements
------------------------

Over this base came the tools.  There is a window for the dictionary
(`words_gui.py`, with Tk, from the standard library), and two editors of
the dictionary, one in a window (`words_edit_gui.py`) and one in the
terminal (`words_edit.py`), for adding, correcting and deleting entries
without touching the XML.  They explain each code, show the entry as
WORDS will show it, and permit to try a word with the edited dictionary
before saving.  `dictionary.xml` received a layout easy to read, one
element in each line, which the editors and the converter respect.

The start became faster: the XML is read as a stream, and what is read
goes to a cache, so the program starts in around a quarter of a second.
The organisation is simple (the programs in one folder, the data in
`data/`), and there is nothing to install apart from Python 3.11 or
later.  The code was updated to Python 3.11 (modern type annotations,
f-strings, `match`, dataclasses with slots), and each program says
clearly when it runs with a Python too old.

The dictionary works also in full screen in the terminal (`words_tui.py`,
with `curses`) and in a web browser (`words_web.py`, a small web server of
the standard library that, by default, only this computer can access).
A configuration file, `config.toml`, keeps the settings, the fonts and the
data folder, and all the programs share the same history of searches.
The analyses can be written with the abbreviations of the Leipzig
Glossing Rules (`GEN.PL`, `3SG.PRF.ACT.IND`), kept in `gloss.xml`, or in
words.

Each program has also a help (`guide.py`): "Help" in the window and in
the web page, F1 in the terminal, `~H` or `--guide` in the command line.
It explains how to search and how to read the results, also the codes in
brackets after an entry (`[XXXBO]`: age, area, region, frequency and
source) and the abbreviations of the analyses.  Its example, its tables
of codes and its list of abbreviations come directly from the program
and its data (`sources.xml`, `gloss.xml`), so the help cannot become old.

In 2.12 the window and the web page received a better look.  The results
are the same text as in the command line, but each line is shown
according to what it is (the word looked up, an entry, a meaning, a
form, a note), which `layout.py` recognizes from the layout of the
results, without Tk, so the online version can use it too.  The first
word of an entry is a link, a double click looks up any word, and the
codes in brackets and the analyses explain themselves when you put the
mouse over them, or touch them in a phone.  The window has also menus,
a find bar and a menu with the right button.

Later I found that the words with long marks were not understood: each
letter with a mark cut the word, so amīcus was looked up as "am" and
"cus".  The same happened with breves, diaeresis and the ligatures æ and
œ.  Now, before the search, the line loses its marks and accents and the
ligatures are written ae and oe (`plain_letters` in `analyzer.py`), so a
text copied from a school edition works without changes.  The marks
typed do not help yet to choose between forms, but since 2.16 the
results show the long vowels themselves (see "8. What came from
Collatinus").

5. Other languages of the meanings
----------------------------------

WORDS gives its meanings in English.  For showing them in other languages
without copying the dictionary, each language has its own file in
`data/languages/` (`es.xml` ...), with the meaning in that language of
each entry, irregular form and affix that it translates.  For this, each
entry, irregular form and affix received an `id`, a number that does not
move when others are added, moved or deleted, so a translation is not
lost when the dictionary changes; the editors keep the ids, and
`words_check.py` checks them.  What a language does not translate is
shown in English, marked `[en]`.

A language file can translate also the rest of the results: the grammar
in words (noun, 2nd declension), the labels, and the notes about spelling
tricks and compound tenses.  These texts are identified by their English,
which can be a pattern (`Word mod {1}/{2}`).  The search from the
meanings to Latin works in the language chosen and ignores the accents
("corazon" finds "corazón").  You choose the language in all the programs
(a list in the window and in the web page, a key in the terminal,
`--language` in the command line), and the choice is remembered.  The
dictionary editors edit the meanings in English and, if one is chosen, in
another language, and save each one in its own file.

The interface (menus, buttons, messages and help) can be also in Spanish.
Each text of the programs passes through one function, `tr`, which looks
for it by its English in `data/interface/es.xml`; the language of the
interface is a setting apart, different from the one of the meanings.  A
test makes sure that every text is translated and that every translation
is used.  The Spanish of the interface was also written with the help of
Claude.

The Spanish translation
~~~~~~~~~~~~~~~~~~~~~~~

The whole dictionary was translated into Spanish (`es.xml`) with the help
of Claude, the large language model of Anthropic (the model Claude Opus
5.5, `claude-opus-5-5`), in October 2026, at the request and under the
direction of Nicolas Vaughan: the 39,592 entries, the 79 irregular forms,
the 343 prefixes, suffixes and enclitics, and the texts of the results.

It was made in batches, by meaning, so a meaning shared by several
entries was translated only one time.  The conventions were decided at
the beginning.  The senses and their order stay (separated by `;`), and
also the source codes and abbreviations (L+S, OLD, Ecc, PASS, GEN ...)
and the Latin in brackets, from which only the English side is
translated.  "w/" becomes "c/", BC and AD become "a. C." and "d. C.", and
the measures are metric.  The English is followed closely, also where it
is strange, and corrected only where it is clearly wrong (for example,
the capacities of the Hebrew ephah and omer were exaggerated around
thirty times).

A second revision read every translated entry together with its English
and corrected around 260 of them: repeated senses, ambiguous or wrong
words ("de nuevo" for "newly", "librería" for "bookcase"), and spelling
mistakes.  Like any translation of this size, surely it has still some
mistakes; the editors make easy to correct them.

Later the dictionary was compared with two more lists, also with the
help of Claude: the Latin-Spanish basic vocabulary of
J. Echave-Sustaeta, which corrected 321 entries and added 254, and the
medieval word-list of R. E. Latham, which added its medieval senses
(2,444 entries), corrected 21 meanings, and added 1,140 missing words
and parts of speech and 1,204 spelling variants, all with their Spanish
meanings.  The README tells how it was done.

6. In the browser
-----------------

After that, the dictionary went online, in
<https://nicolasvaughan.org/py-words/>, so it is possible to use it
without installing anything.  There is no server behind.  The browser
runs the program itself with Pyodide (CPython compiled for WebAssembly),
and as py-words needs only the standard library, Pyodide does not need
anything more.

The page is the same that `words_web.py` serves.  Its WSGI application
runs inside Pyodide, and a short script, `pages/app.js`, makes the role
of the web server: it catches the links and the forms of the page, gives
them to the application as requests, and puts the page that comes back
in the place of the old one.  Each search keeps its own address, so it
can go to the bookmarks and the Back button works.

The program and its data travel in one zip of less than 3 MB, which is
downloaded at the same time as Pyodide and unpacked in the files of
Pyodide.  After that, a search takes some milliseconds, like in a
computer.  In each visit the browser asks if its copy of the zip is still
current, so a new version appears immediately.  The configuration file
and the history live in the local storage of the browser between the
visits, and the cache of the dictionary lives in its IndexedDB.  There
was one problem: the cache compares the dates of the files, and when
Pyodide unpacked the zip every file had the hour of the visit, so the
cache was never valid.  Now the zip is unpacked keeping the dates it has
inside, and the cache is valid until a new version.  To read the XML
takes around one second in the browser, and to read the cache around a
quarter of one, so the first visit takes some seconds (the most part
downloading Python) and the next ones around one second and a half.

`pages/build.py` builds the static site, which any web server can host,
from its root or from a folder.  In GitHub, a workflow runs the tests,
builds the site and publishes it in GitHub Pages with each push to the
main branch.

7. A fuzzy search
-----------------

WORDS looks up a word as it was written, with u/v and i/j as the same
letter and with its spelling tricks (medieval spellings, syncope ...),
but only one typo is enough for finding nothing.  The fuzzy search, the
parameter `fuzzy_search` (on, except if you untick it), solves this: when
a word of three letters or more finds nothing, in any of the two
directions, the results of its near spellings come after.  "amicuss"
finds *amicus*, "freind" finds "friend", and in Spanish "corazn" finds
"corazón".

It does not add a search of its own; it makes the normal search with
other spellings, so the analysis of WORDS stays the same.
`fuzzy.edits` makes the spellings at one change of the word: one letter
less, one more, one different, or two letters together exchanged.  For a
Latin word of seven letters this gives around 350, without j and v
except if the word has them, because these are looked up as i and u in
any case.

From Latin, each spelling is looked up as any word, and it stays only if
it is a word of the dictionary by itself, with stems and endings,
irregular forms, qu- pronouns and tackons, but without prefixes,
suffixes or tricks (with them, almost any string can be read as
something).  These searches don't use the cache, because some hundreds
for each unknown word would fill it; all together they take around ten milliseconds.  To Latin, a spelling stays
if it is a word of the index of the meanings that finds entries of the
part of speech asked.  The index keeps its words without capitals or
accents, so each one is written again as its meaning writes it.

The ones that stay are ordered by their best entry (the most frequent
from Latin, the best ranked to Latin), and then by how common is the
mistake: first two letters exchanged, or a letter doubled or not doubled.
The first three are shown.  The session, through which all the programs
search, decides when to act: the setting is on, nothing was found, and
the word is not a name with capital letter (when the unknown names are
ignored) nor one of the words that the search to Latin never looks for
("the", "la" ...).  The results of the near spellings come after a note,
`(near spellings: amicus)` or `(near words: friend)`, as if they were
written.  The
words of one or two letters are left out, because almost all of them are
at one change of another ("is": "as", "if", "in").

It is possible to turn it off in all the programs: with its own box next
to "Meanings in" in the window and in the web page, from the list of
parameters in the `#` dialogue and with F3 in the terminal, or with
`--no-fuzzy` in the command line.

8. What came from Collatinus
----------------------------

Collatinus, of Yves Ouvrard and Philippe Verkerk, is another Latin
lemmatiser, with its own lemmas, inflection models and translations.  It
is under the GPL, so in 2.16 py-words changed from the MIT License to
the GPL (version 3 or later) to be able to take from it.  Its lemmas
were matched with the entries of the dictionary by the citation form,
the part of speech and, for nouns, the genitive and the gender; an entry
claimed by two lemmas was left out.  From this came four new languages
of the meanings, French (23,044 entries), German (6,301), Catalan
(7,624) and Galician (7,699), with the rest of the results translated
too; Italian and Portuguese were left out, because Collatinus translated
them by machine from the French.

The second thing were the long vowels.  From the lemmas and models of
Collatinus I took the quantities of the stems of 20,297 entries
(`quantities.xml`) and of 731 endings (the attribute `long` in
`inflections.xml`), so the results show amīc-ōrum and am-ābat.
Collatinus marks the weight of the syllables, for verse, so the marks
before two consonants were left out, except before ns and nf; and an
ending was marked only where nine of ten of its forms agree.

Last, some ideas were written again in py-words: a more general reading
of the medieval spellings (michi, ecclesie, hystorie), the prodelision
of est (amatust), two words declined together that must agree
(rempublicam), six abbreviations and the form quaesumus.  The README
tells all of it in detail.

Testing
-------

The program has unit tests and regression tests (`tests/`), 269 in
total, that run with Python 3.11 (the oldest it supports) and with the
last Python.  The regression tests run the inputs inherited from the Ada
version and compare the output with expected files already revised.  The
editors are tested by using them as a user does, in a terminal and in a
window, and the languages with a Spanish file of their own.  The online
version was tried in a browser controlled by a script (searches in both
directions, the links of the results, the Back button, dark mode, the
Spanish interface, and the settings that stay after reloading), from a
local server and also in the published site.  The program has now 39
files, around 14,000 lines.
