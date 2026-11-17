How py-words was made
=====================

py-words is a Latin-English-Latin and Latin-Spanish-Latin dictionary.
Nicolas Vaughan made it in 2026.  Its starting point was WORDS, the
Latin-English dictionary program that Colonel William Whitaker (1936-2010)
wrote, in the Ada version maintained at
[mk270/whitakers-words](https://github.com/mk270/whitakers-words); but
both the code and the data have been redesigned, and it now includes a new
English dictionary (Lewis and Short) and two new Spanish ones
(Echave-Sustaeta and De Miguel).  Here I explain how it was made, in eight
stages.

The dictionary has six sources: WORDS, by William Whitaker, the starting
point of the program and of the entries; R. E. Latham's *Revised Medieval
Latin Word-List from British and Irish Sources*, for medieval senses,
words and spellings; J. Echave-Sustaeta's *Lengua latina. Vocabulario
básico*, for senses and words in English and in Spanish; Lewis and Short's
*A Latin Dictionary*, in the text of the Perseus Digital Library (CC BY-SA
4.0), for 8,436 rare words and names and most of the English meanings; R.
de Miguel and the Marqués de Morante's *Nuevo diccionario latino-español
etimológico*, for 25,149 words and proper names and for most of the
Spanish meanings; and Collatinus, by Yves Ouvrard and Philippe Verkerk,
for the long vowels (Collatinus, in its turn, built its lexicon from the
dictionaries of Gaffiot, Jeanneau, Du Cange and Lewis and Short, among
others, and the README names all the sources and people it thanks).
py-words is free software, under the GNU General Public License, version 3
or later; the data of WORDS are free for any use, by permission of
Whitaker.

Nicolas Vaughan is Associate Professor of Literature at the School of Arts
and Humanities of the Universidad de los Andes, Bogotá, Colombia.

1. A faithful translation
-------------------------

The first version was a translation, line by line, of the Ada program.
Its modules followed the Ada packages closely, and it copied Ada's
behaviour exactly, with all its peculiarities: fixed-length strings padded
with blanks, arrays indexed from 1 (or from whatever bound the Ada code
declared), exceptions used for control flow, as Ada did with
`Constraint_Error` and `End_Error`, column-based output as with Ada's
`Text_IO`, and the dictionary kept in sorted files of stems, searched by
binary search through an index of their first two letters.

The goal was output identical, byte for byte, to that of the Ada program,
and the yardstick was the Ada version's own regression tests, whose inputs
include 735 lines of the *Aeneid*.  As a reference it was useful.  But
really it was Ada written in Python: around 10,300 lines in 26 modules,
hard to read and harder to change.

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
`NOM`, `PRES`, the declensions as "2 1" ...), so anyone who knows WORDS
can read an entry.  An XML Schema, `words.xsd`, describes the format, so
an XML editor can check the files as you write.  `words_convert.py`
converts files in the original format to XML, and `words_check.py` reports
mistakes in hand-edited files, with their line numbers.

3. A redesign in idiomatic Python
---------------------------------

With the translation as a reference, I rewrote the program in ordinary
Python.  What had to survive was what WORDS finds for a word; almost all
the rest could go.  The grammatical codes became enumerations, and the
entries, endings and forms became immutable records (dataclasses) that
mirror the XML.  Instead of the sorted files and the binary searches there
are now in-memory dictionaries, so the stems, endings and irregular forms
are looked up directly, with u/v and i/j as the same letter.  The analysis
now returns structured results, which are ordered and trimmed with an
ordinary sort, instead of filling shared arrays, and the settings are
passed explicitly instead of being changed for a moment as a way of
passing arguments.  There is no shared mutable state.

The output got a new, easier-to-read layout, and the command line a modern
one (`argparse`).  What users actually use was kept: the settings files
WORD.MOD and WORD.MDV, in their original format, with the `#` and `!`
dialogues, and the developer modes.  (The output files WORD.OUT, WORD.UNK
and WORD.STA were kept at first, and taken out later.)  The result has
around 6,700 lines, in modules organised by task (see "How it works" in
the README).

Checking the redesign
~~~~~~~~~~~~~~~~~~~~~

I compared the new analyser with the faithful translation on a corpus of
133,671 words: all the stems of the dictionary, forms generated from the
stems and the endings, and the inputs of the regression tests.  For each
word, the results of both versions were reduced to comparable records
(entry, stem, ending, grammatical form, and the affix or spelling trick
used, if any), and then compared.  99.2% of the words gave the same
results.  I reviewed every one of the other differences.  Each was a
deliberate change or a bug in the original that the redesign does not
repeat: stems matched with unrelated entries, results attributed to the
wrong enclitic, malformed Roman numerals accepted, a spelling rule that
could never apply.  They are listed in "Changes from the original program"
in the README.  The searches from English to Latin were checked in the
same way.

4. Tools and refinements
------------------------

On top of this base came the tools.  There is a window for the dictionary
(`words_gui.py`, with Tk, from the standard library), and two dictionary
editors, one in a window (`words_edit_gui.py`) and one in the terminal
(`words_edit.py`), for adding, correcting and deleting entries without
touching the XML.  They explain each code, show the entry as WORDS will
show it, and let you try a word with the edited dictionary before saving.
`dictionary.xml` got an easier layout to read, one element per line, which
the editors and the converter respect.

Startup got faster: the XML is read as a stream, and what is read goes to
a cache, so the program starts in around a quarter of a second.  The
organisation is simple (the programs in one folder, the data in `data/`),
and there is nothing to install apart from Python 3.13 or later.  The code
was updated to Python 3.11 (modern type annotations, f-strings, `match`,
dataclasses with slots), and each program says clearly when the Python
running it is too old.

The dictionary also works full-screen in the terminal (`words_tui.py`,
with `curses`) and in a web browser (`words_web.py`, a small
standard-library web server that, by default, only this computer can
access).  A configuration file, `config.toml`, keeps the settings, the
fonts and the data folder, and all the programs share the same history of
searches.  The analyses can use the abbreviations of the Leipzig Glossing
Rules (`GEN.PL`, `3SG.PRF.ACT.IND`), kept in `gloss.xml`, or be written
out in words.

Each program also has a help guide (`guide.py`): "Help" in the window and
on the web page, F1 in the terminal, `~H` or `--guide` on the command
line.  It explains how to search and how to read the results, including
the codes in brackets after an entry (`[XXXBO]`: age, area, region,
frequency and source) and the abbreviations of the analyses.  Its example,
its tables of codes and its list of abbreviations come directly from the
program and its data (`sources.xml`, `gloss.xml`), so the help cannot go
out of date.

In 2.12 the window and the web page got a better look.  The results are
the same text as in the command line, but each line is shown according to
what it is (the word looked up, an entry, a meaning, a form, a note),
which `layout.py` recognizes from the layout of the results, without Tk,
so the online version can use it too.  The first word of an entry is a
link, a double click looks up any word, and the codes in brackets and the
analyses explain themselves when you hover the mouse over them, or tap
them on a phone.  The window also has menus, a find bar and a right-click
menu.

Later I found that words with long marks were not understood: each marked
letter split the word, so amīcus was looked up as "am" and "cus".  The
same happened with breves, diaereses and the ligatures æ and œ.  Now,
before the search, the marks and accents are stripped from the line and
the ligatures are written ae and oe (`plain_letters` in `analyzer.py`), so
a text copied from a school edition works without changes.  Typed marks do
not yet help to choose between forms, but since 2.16 the results show the
long vowels themselves (see "8. What came from Collatinus").

The window, the terminal and the command line can also show the entries of
Logeion (logeion.uchicago.edu), the dictionaries of the University of
Chicago, instead of py-words' own ("Search in" in the window, F8 in the
terminal, `--logeion`).  Logeion does not analyse inflected forms, so
py-words analyses each word and asks Logeion for its lemmas, the first of
the principal parts of each entry found (and for the form itself, shown
only if it is a headword of Lewis and Short, like *arma*), and shows first
its own analysis of the word (the entries and the forms, as *dix-ī
1SG.PRF.ACT.IND*), without its meanings; the irregular pronouns, which
have no principal parts here, get their nominatives (*mihi*: *ego*;
*quae*: *qui* and *quis*).  The part that asks Logeion and renders its
entries (`logeion_*.py`) comes from py-logeion; the results are kept in
memory, wrapped to the width of the window or the terminal, and the links
in them to other words look those words up.  A list beside "Search in" (F5
in the terminal, `--dictionary` on the command line) shows only one of
Logeion's dictionaries, or all of them; changing it shows the results
again without asking Logeion.

5. Other languages of the meanings
----------------------------------

WORDS gives its meanings in English.  To show them in other languages
without copying the dictionary, each language has its own file in
`data/languages/` (`es.xml` ...), with the meaning in that language of
each entry, irregular form and affix that it translates.  For this, each
entry, irregular form and affix got an `id`, a number that does not move
when others are added, moved or deleted, so a translation is not lost when
the dictionary changes; the editors keep the ids, and `words_check.py`
checks them.  What a language does not translate is shown in English,
marked `[en]`.

A language file can also translate the rest of the results: the grammar in
words (noun, 2nd declension), the labels, and the notes about spelling
tricks and compound tenses.  These texts are identified by their English,
which can be a pattern (`Word mod {1}/{2}`).  The search from the meanings
to Latin works in the language chosen and ignores the accents ("corazon"
finds "corazón").  You choose the language in all the programs (a list in
the window and on the web page, a key in the terminal, `--language` on the
command line), and the choice is remembered.  The dictionary editors edit
the meanings in English and, if one is chosen, in another language, and
save each one in its own file.

The interface (menus, buttons, messages and help) can also be in Spanish.
Every text in the programs passes through one function, `tr`, which looks
it up by its English in `data/interface/es.xml`; the language of the
interface is a separate setting from the language of the meanings.  A test
makes sure that every text is translated and that every translation is
used.  The Spanish of the interface was also written with the help of
Claude.

The Spanish translation
~~~~~~~~~~~~~~~~~~~~~~~

The whole dictionary was translated into Spanish (`es.xml`) with the help
of Claude, the large language model of Anthropic (the model Claude Opus
5.5, `claude-opus-5-5`), in October 2026, at the request and under the
direction of Nicolas Vaughan: the 39,592 entries, the 79 irregular forms,
the 343 prefixes, suffixes and enclitics, and the texts of the results.

It was made in batches, by meaning, so a meaning shared by several entries
was translated only once.  The conventions were decided at the start.  The
senses and their order were kept (separated by `;`), as were the source
codes and abbreviations (L+S, OLD, Ecc, PASS, GEN ...) and the Latin in
brackets, of which only the English side is translated.  "w/" becomes
"c/", BC and AD become "a. C." and "d. C.", and the measures are metric.
The English is followed closely, even where it is strange, and corrected
only where it is clearly wrong (for example, the capacities of the Hebrew
ephah and omer were exaggerated around thirty times).

A second revision read every translated entry together with its English
and corrected around 260 of them: repeated senses, ambiguous or wrong
words ("de nuevo" for "newly", "librería" for "bookcase"), and spelling
mistakes.  Like any translation of this size, it surely still has some
mistakes; the editors make them easy to correct.

Later the dictionary was compared with two more lists, also with the help
of Claude: the Latin-Spanish basic vocabulary of J. Echave-Sustaeta, which
corrected 321 entries and added 254, and the medieval word-list of R. E.
Latham, which added its medieval senses (2,444 entries), corrected 21
meanings, and added 1,140 missing words and parts of speech and 1,204
spelling variants, all with their Spanish meanings.  After that, 3,060
rare words of Lewis and Short's *A Latin Dictionary* that WORDS did not
have were added from the text of the Perseus Digital Library: their
grammar came from what Lewis and Short gives, each entry was kept only if
the analyzer reads its headword back, and the meanings were revised and
translated into Spanish.  Then, in the same way, 12,918 words and proper
names of the Latin-Spanish dictionary of R. de Miguel and the Marqués de
Morante (1867) were added, with their English meanings translated from the
Spanish.  Last, the Spanish meanings of the entries that De Miguel or
Echave-Sustaeta also have (50,846 of them) were rewritten in those
dictionaries' own words, and some 31,000 more words that the three new
sources still had were added, among them 16,995 medieval words of Latham,
12,000 words and names of De Miguel and 5,400 words and names of Lewis and
Short; the English meanings of the entries Lewis and Short has (30,601)
are now his definitions.  The dictionary now has 93,370 entries.  The
README tells how it was done.

6. Online
---------

After that, the dictionary went online, so it could be used without
installing anything.  It runs on a public server, at
<https://nivaca.pythonanywhere.com/>: the page that `words_web.py` serves,
whose WSGI application is the same program.  The searches are made by the
server, and each visitor keeps their own settings and earlier searches.

7. A fuzzy search
-----------------

WORDS looks up a word as it was written, with u/v and i/j as the same
letter and with its spelling tricks (medieval spellings, syncope ...), but
a single typo is enough to find nothing.  The fuzzy search, the parameter
`fuzzy_search` (on unless you untick it), solves this: when a word of
three letters or more finds nothing, in either direction, the results for
its near spellings follow.  "amicuss" finds *amicus*, "freind" finds
"friend", and in Spanish "corazn" finds "corazón".

It does not add a search of its own; it runs the normal search on other
spellings, so the analysis of WORDS stays the same.  `fuzzy.edits` makes
the spellings one change away from the word: one letter less, one more,
one different, or two adjacent letters swapped.  For a Latin word of seven
letters this gives around 350, without j and v unless the word has them,
because these are looked up as i and u anyway.

From Latin, each spelling is looked up like any word, and it is kept only
if it is a dictionary word by itself, with stems and endings, irregular
forms, qu- pronouns and tackons, but without prefixes, suffixes or tricks
(with them, almost any string can be read as something).  These searches
don't use the cache, because a few hundred for each unknown word would
fill it; all together they take around ten milliseconds.  To Latin, a
spelling is kept if it is a word in the index of the meanings that finds
entries of the part of speech asked for.  The index keeps its words
without capitals or accents, so each one is written back as its meaning
spells it.

The ones kept are ordered by their best entry (the most frequent from
Latin, the best ranked to Latin), and then by how common the mistake is:
first two letters swapped, or a letter doubled or not doubled.  The first
three are shown.  The session, through which all the programs search,
decides when to act: the setting is on, nothing was found, and the word is
neither a capitalised name (when unknown names are ignored) nor one of the
words that the search to Latin never looks for ("the", "la" ...).  The
results of the near spellings come after a note, `(near spellings:
amicus)` or `(near words: friend)`, as if they had been typed.  Words of
one or two letters are left out, because almost all of them are one change
away from another ("is": "as", "if", "in").

It can be turned off in all the programs: with its own box next to
"Meanings in" in the window and on the web page, from the list of
parameters in the `#` dialogue and with F3 in the terminal, or with
`--no-fuzzy` on the command line.

8. What came from Collatinus
----------------------------

Collatinus, by Yves Ouvrard and Philippe Verkerk, is another Latin
lemmatiser, with its own lemmas, inflection models and translations.  It
is under the GPL, so in 2.16 py-words changed from the MIT License to the
GPL (version 3 or later) so that it could take from it.  Its lemmas were
matched with the entries of the dictionary by the citation form, the part
of speech and, for nouns, the genitive and the gender; an entry claimed by
two lemmas was left out.  From this came, for a while, four new languages
of the meanings (French, German, Catalan and Galician); they were taken
out after 3.1, to keep only English and Spanish.

The second thing was the long vowels.  From the lemmas and models of
Collatinus I took the quantities of the stems of 20,297 entries
(`quantities.xml`) and of 731 endings (the attribute `long` in
`inflections.xml`), so the results show amīc-ōrum and am-ābat.  Collatinus
marks the weight of the syllables, for verse, so the marks before two
consonants were left out, except before ns and nf; and an ending was
marked only where nine out of ten of its forms agree.

Last, some ideas were written again in py-words: a more general reading
of the medieval spellings (michi, ecclesie, hystorie), the prodelision
of est (amatust), two words declined together that must agree
(rempublicam), six abbreviations and the form quaesumus.  The README
tells all of it in detail.

Testing
-------

The program has unit tests and regression tests (`tests/`), 366 in total,
that run with Python 3.13 (the oldest it supports) and with the latest
Python; `tools/test.py` runs them all at once, each class of tests in a
process of its own, in about a minute and a half.  The regression tests
run the inputs inherited from the Ada version and compare the output with
expected files already reviewed.  The editors are tested by using them as
a user does, in a terminal and in a window, and the languages with a
Spanish file of their own.  The online version was tried in a browser
controlled by a script (searches in both directions, the links of the
results, the Back button, dark mode, the Spanish interface, and the
settings that stay after reloading), from a local server and also on the
site then published.  The program now has 44 files, around 17,000 lines.
