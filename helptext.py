"""Help for the settings, shown when '?' is answered in the # and ! menus
(and in the window's Settings); it is translated where it is shown."""

from interface import N_

HELP = {
    # Parameters (#, [parameters] in config.toml): what the results show
    'show_dictionary_forms':
        N_('Show each entry with its principal parts and grammar (amicus, '
           'amici  noun, 2nd declension, masculine).'),
    'show_only_meanings':
        N_('Show only the entries and their meanings, without the forms.'),
    'use_glosses':
        N_('Write the analyses of the forms in glossing abbreviations, as '
           'in the Leipzig Glossing Rules (GEN.PL, 2SG.PRF.ACT.IND); if '
           'not, in words (genitive plural, 2nd person singular perfect '
           'active indicative).  The abbreviations are those of '
           'data/gloss.xml.'),
    'show_long_vowels':
        N_('Mark the long vowels of the stems and endings in the forms '
           '(amīc-ōrum), where they are known.  Vowels long before two '
           'consonants are not marked, but for those before ns and nf.'),
    'show_codes':
        N_('Show the codes of each entry: age, area, geography, frequency '
           'and source, as in [XXXBO].'),
    'explain_codes':
        N_('Always say in words when a word or form was used (archaic, '
           'classical, medieval ...) and how frequent it is, not only when '
           'it is unusual.'),
    'trim_output':
        N_('Leave out the least likely results: forms that are only '
           'possible in theory, and archaic or uncommon ones when more '
           'common results were found.  A note says when something was '
           'left out.  In the search to Latin, show only the best six '
           'results.  Poets use unusual words and forms, so these can be '
           'trimmed wrongly.'),
    'trim_medieval':
        N_('With trim_output, leave out also medieval forms when others '
           'were found.'),
    # ... and how words are looked up
    'fuzzy_search':
        N_('When a word finds nothing as it is typed, look for the words '
           'one change away from it (a letter left out, added or changed, '
           'or two letters swapped), and show the nearest three: amicuss '
           'finds amicus, and, in the search to Latin, freind finds '
           'friend and wolfs finds wolf.  Exact results are shown as '
           'before.'),
    'use_affixes':
        N_('When a word is not in the dictionary, try it as a known word '
           'with a prefix or suffix.  The results may be less reliable '
           'than those found directly.'),
    'use_tricks':
        N_('When a word is still not found, try other spellings (ae for e, '
           'ph for f, assimilated prefixes ...) and two words written as '
           'one.  Such results are marked as such.'),
    'medieval_spellings':
        N_('With use_tricks, also try medieval spellings (e for ae, y for '
           'i, michi for mihi, single for doubled consonants ...).'),
    'read_compounds':
        N_('Read a participle followed by a form of esse as a compound '
           'tense (laudatus est: perfect passive).'),
    'ignore_unknown_names':
        N_('Do not try spelling tricks on an unknown word that is '
           'capitalized: it is probably a name.'),
    'near_entries':
        N_('For an unknown word, list the dictionary entries near where it '
           'would be.  This can catch a word whose stem is in the '
           'dictionary under another part of speech.'),
    'language':
        N_('The language of the meanings, and of the rest of the results '
           '(en, es ...).  The search to Latin is from this language.'),
    'interface':
        N_('The language of the menus, buttons, messages and help of the '
           'programs (en, es).'),
    'save':
        N_('Save these settings in the configuration file, config.toml (on '
           'Linux in ~/.config/py-words), to be used at the next start.  '
           'It is plain text and can also be edited; words.py --config '
           'shows where it is.'),
    # Developer modes (!, [developer] in config.toml)
    'show_entry_source':
        N_('Show which dictionary (general or special) each entry is from, '
           'and its number in that file.'),
    'pearse_codes':
        N_('Start each line of the results with a code saying what it is '
           '(01 a form, 02 an entry, 03 a meaning, 05 an affix, 06 a '
           'trick, 00 an unknown word), for programs that read the output.'),
    'pause_in_screen_output':
        N_('In interactive use, pause after each screenful of results.'),
    'characters':
        N_('The characters that start a command at the beginning of a '
           'line: reading a file (@), the parameters (#) and the developer '
           'modes (!).  They must be punctuation, and different from each '
           'other and from ~.'),
}
