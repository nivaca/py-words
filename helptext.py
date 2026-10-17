"""Help for the settings, shown when '?' is answered in the # and ! menus."""

HELP = {
    # Parameters (#, [parameters] in config.toml)
    'trim_output':
        'Leave out the least likely results: forms that are only possible '
        'in theory, and archaic, medieval or uncommon ones when more common '
        'results were found (see the developer modes omit_archaic, '
        'omit_medieval and omit_uncommon).  A note says when something was '
        'left out.  In English-to-Latin lookups, show only the best six '
        'results.  Poets use unusual words and forms, so these can be '
        'trimmed wrongly.',
    'have_output_file':
        'Create the file WORD.OUT (in the current directory), which can '
        'receive the results instead of the screen; see '
        'write_output_to_file.  An existing WORD.OUT is overwritten.',
    'write_output_to_file':
        'Send the results to WORD.OUT instead of the screen.  It can be '
        'turned on and off during a session, to keep only some results.  '
        'Only offered when have_output_file is on.',
    'do_unknowns_only':
        'Show only the words that are not found.  Useful with '
        'write_unknowns_to_file, to check a text for words missing from the '
        'dictionary.',
    'write_unknowns_to_file':
        'Write the words that are not found to the file WORD.UNK (in the '
        'current directory), with their line and word numbers.',
    'ignore_unknown_names':
        'Do not try spelling tricks on an unknown word that is capitalized: '
        'it is probably a name.',
    'do_compounds':
        'Read a participle followed by a form of esse as a compound tense '
        '(laudatus est: perfect passive).',
    'do_fixes':
        'When a word is not in the dictionary, try it as a known word with '
        'a prefix or suffix.  The results may be less reliable than those '
        'found directly.',
    'do_tricks':
        'When a word is still not found, try other spellings (ae for e, '
        'ph for f, assimilated prefixes ...), syncopated forms and two words '
        'written as one.  Such results are marked as such.',
    'do_dictionary_forms':
        'Show each entry with its principal parts and grammar (amicus, '
        'amici  noun, 2nd declension, masculine).',
    'show_age':
        'Always show when a word or form was used (archaic, classical, '
        'medieval ...), not only when it is not "always".',
    'show_frequency':
        'Always show how frequent a word or form is, not only when it is '
        'uncommon.',
    'do_examples':
        'Show an English pattern for each form ("~\'s; of ~" for a '
        'genitive), with ~ standing for the meaning.',
    'use_glosses':
        'Write the analyses of the forms in glossing abbreviations, as in '
        'the Leipzig Glossing Rules (GEN.PL, 2SG.PRF.ACT.IND); if not, in '
        'words (genitive plural, 2nd person singular perfect active '
        'indicative).  The abbreviations are those of data/gloss.xml.',
    'do_only_meanings':
        'Show only the entries and their meanings, without the forms.',
    'do_stems_for_unknown':
        'For an unknown word, list the dictionary entries near where it '
        'would be.  This can catch a word whose stem is in the dictionary '
        'under another part of speech.',
    'save':
        'Save these settings in the configuration file, config.toml (on '
        'Linux in ~/.config/py-words), to be used at the next start.  It is '
        'plain text and can also be edited; words.py --config shows where '
        'it is.',

    # Developer modes (!, [developer] in config.toml)
    'have_statistics_file':
        'Create the file WORD.STA (in the current directory) for statistics '
        'on the tricks and affixes used; see write_statistics_file.',
    'write_statistics_file':
        'Write the statistics to WORD.STA.  It can be turned on and off '
        'during a session.  Only offered when have_statistics_file is on.',
    'show_dictionary':
        'Show which dictionary (general or special) each entry is from.',
    'show_dictionary_line':
        'Show the number of each entry in its dictionary file.',
    'show_dictionary_codes':
        'Show the codes of each entry: age, area, geography, frequency and '
        'source, as in [XXXBO].',
    'do_pearse_codes':
        'Start each line of the results with a code saying what it is (01 a '
        'form, 02 an entry, 03 a meaning, 05 an affix, 06 a trick, 00 an '
        'unknown word), for programs that read the output.',
    'do_only_initial_word':
        'Analyse only the first word of each line, for checking word lists.',
    'for_word_list_check':
        'With do_only_initial_word: accept only dictionary forms (nominative '
        'singular, first person present ...).',
    'do_only_fixes':
        'Find words only with prefixes and suffixes.',
    'do_fixes_anyway':
        'Try prefixes and suffixes even when the word was found without '
        'them.',
    'use_prefixes': 'Use prefixes when analysing words.',
    'use_suffixes': 'Use suffixes when analysing words.',
    'use_tackons': 'Use enclitics (-que, -ne, -cumque ...).',
    'do_medieval_tricks':
        'With do_tricks, also try medieval spellings (e for ae, y for i, '
        'single for doubled consonants ...).',
    'do_syncope':
        'Try syncopated perfects (amasti for amavisti).',
    'do_two_words':
        'With do_tricks, try an unknown word as two words written together.',
    'include_unknown_context':
        'Write the whole line, as well as the word, to WORD.UNK.',
    'omit_archaic':
        'With trim_output, leave out archaic forms when others were found.',
    'omit_medieval':
        'With trim_output, leave out medieval forms when others were found.',
    'omit_uncommon':
        'With trim_output, leave out uncommon forms when others were found.',
    'pause_in_screen_output':
        'In interactive use, pause after each screenful of results.',
    'characters':
        'The characters that start a command at the beginning of a line: '
        'reading a file (@), the parameters (#) and the developer modes (!).  '
        'They must be punctuation, and different from each other and from ~.',
}
