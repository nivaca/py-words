"""The structure of a page: its sections (the dictionaries, and what Logeion
shows beside them), the dictionary filter and the options.

From py-logeion 0.2.1 (https://github.com/nivaca/py-logeion), whose
engine py-words uses to show the entries of Logeion (see logeion.py).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

from logeion_api import corpus_url, normal_word, page_url

# --------------------------------------------------------------------------- #
# The dictionaries
# --------------------------------------------------------------------------- #
#  Logeion's name of a dictionary (its "dname") -> (code, name shown).  The
#  code is short, for the filter (-d ls,lsj); dictionaries not listed here
#  get one made from their name.
DICTIONARIES = {
    # Latin
    "LewisShort": ("ls", "Lewis & Short"),
    "Lewis": ("lewis", "Lewis (Elementary)"),
    "Georges": ("georges", "Georges"),
    "Gaffiot 2016": ("gaffiot", "Gaffiot 2016"),
    "DMLBS": ("dmlbs", "DMLBS"),
    "DMLBSx": ("dmlbs", "DMLBS"),
    "LaNe": ("lane", "LaNe"),
    "Latino-Sinicum": ("sinicum", "Latino-Sinicum"),
    "DuCange": ("ducange", "Du Cange"),
    "Lana-Michelone": ("lana", "Lana-Michelone"),
    "FriezeDennisonVergil": ("frieze", "Frieze-Dennison (Vergil)"),
    # Greek
    "LSJ": ("lsj", "LSJ"),
    "Middle Liddell": ("ml", "Middle Liddell"),
    "DGE": ("dge", "DGE"),
    "Brill-Montanari": ("montanari", "Brill-Montanari"),
    "Bailly 2024": ("bailly", "Bailly 2024"),
    "Grieks Nederlands": ("gn", "Grieks-Nederlands"),
    "Pape": ("pape", "Pape"),
    "Cunliffe Homer": ("cunliffe", "Cunliffe (Homer)"),
    "Autenrieth Homer": ("autenrieth", "Autenrieth (Homer)"),
    "Slater Pindar": ("slater", "Slater (Pindar)"),
    "Abbott-Smith NT": ("as", "Abbott-Smith (New Testament)"),
    "LMPG": ("lmpg", "LMPG"),
    # reference works
    "Harpers": ("harpers", "Harper's Dictionary of Classical Antiquities"),
    "Antiquities": ("antiquities", "Smith's Dictionary of Antiquities"),
    "Biography": ("biography", "Smith's Dictionary of Biography"),
    "Perseus Encyclopedia": ("encyclopedia", "Perseus Encyclopedia"),
}

#  Logeion's name of the examples taken from its corpus (a "dictionary" in
#  its answers)
EXAMPLES_DNAME = "Examples from the corpus"

# Kinds of sections.
SUMMARY = "summary"          # the short definition, the forms
DICTIONARY = "dictionary"    # a dictionary's entry
EXAMPLES = "examples"        # examples from the corpus
INFO = "info"                # frequency, collocations, BWL, textbooks, links


def slug(name: str) -> str:
    """'Gaffiot 2016' -> 'gaffiot2016': a name as it is compared."""
    return re.sub(r"[\W_]+", "", name.casefold())


def dictionary_names(dname: str) -> tuple[str, str]:
    """(code, name shown) of the dictionary Logeion calls DNAME."""
    dname = dname.strip().strip("'\"").strip()
    return DICTIONARIES.get(dname, (slug(dname), dname))


@dataclass
class Section:
    """One part of a page: a dictionary's entry, or one of Logeion's
    panels.  HTML is its content (the renderer makes text of it)."""
    name: str               # "Lewis & Short", "Short definition"
    code: str               # "ls", "short"
    kind: str               # SUMMARY, DICTIONARY, EXAMPLES or INFO
    html: str
    aliases: tuple = ()     # other names it answers to (Logeion's dname...)

    def label(self) -> str:
        return f"{self.name} ({self.code})" if self.kind == DICTIONARY else self.name

    def matches(self, wanted: str) -> bool:
        """Whether WANTED (as typed, e.g. 'ls', 'Lewis & Short') names it."""
        w = slug(wanted)
        return bool(w) and w in {slug(self.name), slug(self.code), *map(slug, self.aliases)}


@dataclass
class Entry:
    """What is shown of a word."""
    query: str                       # what was looked up ('rosae')
    word: str                        # the headword shown ('rosa')
    sections: list[Section]

    @property
    def dictionaries(self) -> list[Section]:
        return [s for s in self.sections if s.kind == DICTIONARY]

    @property
    def url(self) -> str:
        return page_url(self.word)

    def title(self) -> str:
        return self.word if self.word == self.query else f"{self.query} → {self.word}"


# --------------------------------------------------------------------------- #
# From Logeion's answers to sections
# --------------------------------------------------------------------------- #
def esc(s) -> str:
    return html.escape(str(s), quote=True)


def word_link(word: str, text: str | None = None) -> str:
    """HTML of a link to the page of WORD."""
    return f'<a href="{esc(page_url(word))}">{esc(text or word)}</a>'


def joined(pieces) -> str:
    """The HTML of a list of entries of Logeion ('es' is a list of strings)."""
    if isinstance(pieces, str):
        return pieces
    return "<br>".join(str(p) for p in pieces or [] if p)


def _summary(page: dict) -> list[Section]:
    out = []
    d = page["detail"]
    defs = [str(x) for x in d.get("shortdef") or [] if str(x).strip()]
    if defs:
        out.append(Section("Short definition", "short", SUMMARY,
                           "<ul>" + "".join(f"<li>{esc(' '.join(x.split()))}</li>"
                                            for x in defs) + "</ul>",
                           ("short definitions", "shortdef", "definition")))
    parses = page.get("parses") or []
    if parses:
        items = []
        lemmas = page.get("lemmas") or []
        lemmas = sorted(lemmas, key=lambda l: l != page["word"])   # (the one shown first)
        for lemma in lemmas:
            forms = [str(p.get("parse") or "") for p in parses
                     if normal_word(str(p.get("lemma") or "")) == lemma]
            parts = [" ".join(x.split()).strip(" -") for f in forms for x in f.split(",")]
            parts = [p for p in dict.fromkeys(parts) if p]
            items.append(f"<li>{word_link(lemma)}"
                         + (f": {esc('; '.join(parts))}" if parts else "") + "</li>")
        title = f"Forms of {page['query']}"
        out.append(Section(title, "forms", SUMMARY, "<ul>" + "".join(items) + "</ul>",
                           ("forms", "parses", "parse", "morphology")))
    return out


def _dictionaries(page: dict) -> tuple[list[Section], list[Section]]:
    """The dictionaries' entries, and the examples from the corpus."""
    dicts, examples = [], []
    d = page["detail"]
    for dico in d.get("dicos") or []:
        if not isinstance(dico, dict):
            continue
        dname = str(dico.get("dname") or "").strip().strip("'\"").strip()
        content = joined(dico.get("es"))
        if not dname or not content.strip():
            continue
        if dname == EXAMPLES_DNAME:
            examples.append(Section("Examples from the corpus", "examples", EXAMPLES,
                                    content, ("examples", "corpus")))
            continue
        code, name = dictionary_names(dname)
        if any(s.code == code for s in dicts):   # (DMLBS and DMLBSx)
            continue
        dicts.append(Section(name, code, DICTIONARY, content, (dname,)))
    frieze = [str(x) for x in d.get("friezeD") or [] if str(x).strip()]
    if frieze:
        code, name = DICTIONARIES["FriezeDennisonVergil"]
        dicts.append(Section(name, code, DICTIONARY, "<br>".join(frieze),
                             ("FriezeDennisonVergil", "Frieze-Dennison", "vergil")))
    return dicts, examples


def _info(page: dict) -> list[Section]:
    out = []
    info, d, word = page["info"], page["detail"], page["word"]
    freq = [f for f in info.get("frequency") or [] if isinstance(f, dict)]
    body = []
    for f in freq:
        if f.get("rank"):
            body.append(f"<p>{esc(f.get('word') or word)} is {esc(f['rank'])}.</p>")
        authors = [a for a in f.get("authorList") or [] if isinstance(a, dict)]
        if authors:
            body.append("<p>Most frequent in: " + ", ".join(
                f'<a href="{esc(a.get("authorSearch") or "")}">{esc(a.get("author") or "")}</a>'
                for a in authors) + ".</p>")
    if body:
        body.append(f'<p><a href="{esc(corpus_url(word))}">Search the corpus for '
                    f'this lemma</a>.</p>')
        out.append(Section("Frequency", "frequency", INFO, "".join(body),
                           ("rank", "freq")))
    colls = info.get("collocations") or {}
    if isinstance(colls, dict) and any(colls.values()):
        body = []
        for lemma, items in colls.items():
            items = [c for c in items or [] if isinstance(c, dict) and c.get("word")]
            if not items:
                continue
            lead = f"{esc(lemma)}: " if len(colls) > 1 else ""
            body.append("<p>" + lead + ", ".join(
                f"{word_link(normal_word(str(c['word'])), str(c['word']))} ({esc(c.get('count', ''))})"
                for c in items) + ".</p>")
        if body:
            out.append(Section("Collocations", "collocations", INFO, "".join(body)))
    bwl = [str(x) for x in d.get("bwl") or [] if str(x).strip()]
    if bwl:
        out.append(Section("BWL", "bwl", INFO, joined(bwl), ("usage", "sentences")))
    books = [" ".join(str(t).split()) for t in info.get("textbooks") or [] if str(t).strip()]
    if books:
        out.append(Section("Textbooks", "textbooks", INFO,
                           "<ul>" + "".join(f"<li>{esc(t)}</li>" for t in books) + "</ul>",
                           ("textbook",)))
    links = [l for l in info.get("links") or [] if isinstance(l, dict) and l.get("link")]
    if links:
        out.append(Section("Links", "links", INFO, "<ul>" + "".join(
            f'<li><a href="{esc(l["link"])}">{esc(l.get("dico") or l["link"])}</a></li>'
            for l in links) + "</ul>", ("external links",)))
    return out


def page_entry(page: dict) -> Entry:
    """The Entry of a page (as api.Client.page gives it): the short
    definition and the forms, the dictionaries in Logeion's order, the
    examples from the corpus, then the information on the word."""
    dicts, examples = _dictionaries(page)
    return Entry(page["query"], page["word"],
                 _summary(page) + dicts + examples + _info(page))


# --------------------------------------------------------------------------- #
# Choosing what to show
# --------------------------------------------------------------------------- #
def parse_spec(spec: str) -> list[str] | None:
    """'ls, LSJ' -> ['ls', 'LSJ']; 'all' -> None (no filter)."""
    if spec.strip().lower() in ("all", ""):
        return None
    return [x.strip() for x in spec.split(",") if x.strip()]


def select_dictionaries(sections: list[Section], spec: str,
                        preferred: list[str] | tuple = ()) -> list[Section]:
    """The sections to show with the dictionary filter SPEC (codes or names
    of dictionaries, or 'all'): the dictionaries it names, in the page's
    order, except those of PREFERRED, which come first in their order; the
    other sections stay in their places."""
    wanted = parse_spec(spec)
    dicts = [s for s in sections if s.kind == DICTIONARY and
             (wanted is None or any(s.matches(w) for w in wanted))]
    if preferred:
        pref = [p for p in preferred if p.strip()]

        def rank(s: Section) -> int:
            return next((i for i, p in enumerate(pref) if s.matches(p)), len(pref))
        dicts.sort(key=rank)          # stable: the page's order within a rank
    out: list[Section] = []
    placed = False
    for s in sections:
        if s.kind != DICTIONARY:
            out.append(s)
        elif not placed:
            out.extend(dicts)
            placed = True
    return out


def available_dictionaries(sections: list[Section]) -> str:
    return ", ".join(s.label() for s in sections if s.kind == DICTIONARY) or "none"


def parse_section_list(s: str | None) -> list[str] | None:
    if not s:
        return None
    return [x.strip() for x in s.split(",") if x.strip()]


@dataclass
class Options:
    """What to show of an entry."""
    include: list[str] | None = None   # only these sections, by name or code (None = all)
    exclude: list[str] = field(default_factory=list)
    show_examples: bool = True         # the examples from the corpus
    show_info: bool = True             # frequency, collocations, BWL, textbooks, links
    brief: bool = False                # the short definition and the forms only

    @classmethod
    def build(cls, only: str | None = None, exclude: str | None = None,
              brief: bool = False, base: "Options | None" = None) -> "Options":
        """From comma-separated section lists, as given on the command line,
        on top of BASE (e.g. the user's settings).  'examples' and 'info' in
        EXCLUDE hide the examples and the information on the word."""
        base = base or cls()
        exc = parse_section_list(exclude) or []
        slugs = {slug(x) for x in exc}
        return cls(parse_section_list(only), exc + base.exclude,
                   show_examples=base.show_examples and "examples" not in slugs,
                   show_info=base.show_info and "info" not in slugs,
                   brief=brief)

    def shows(self, s: Section) -> bool:
        """Whether section S is shown (the dictionary filter aside)."""
        if any(s.matches(x) for x in self.exclude):
            return False
        if self.include is not None:
            return any(s.matches(x) for x in self.include)
        if self.brief:
            return s.kind == SUMMARY
        if s.kind == EXAMPLES:
            return self.show_examples
        if s.kind == INFO:
            return self.show_info
        return True


def shown_sections(entry: Entry, spec: str, options: Options,
                   preferred: list[str] | tuple = ()) -> list[Section]:
    """The sections of ENTRY to show, in order.  In brief mode, an entry
    without a short definition shows its first dictionary instead."""
    chosen = select_dictionaries(entry.sections, spec, preferred)
    out = [s for s in chosen if options.shows(s)]
    if options.brief and options.include is None and \
            not any(s.code == "short" for s in out):
        first = next((s for s in chosen if s.kind == DICTIONARY and
                      not any(s.matches(x) for x in options.exclude)), None)
        if first is not None:
            out.append(first)
    return out
