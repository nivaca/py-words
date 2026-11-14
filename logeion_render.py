"""Turning the entries of Logeion into wrapped, styled lines of text (or JSON).

The dictionaries send their entries as HTML, or as XML of their own (TEI and
the like: <entry>, <sense>, <orth>...).  Elements the renderer does not know
are taken as inline text, so any dictionary can be shown.

From py-logeion 0.2.1 (https://github.com/nivaca/py-logeion), whose
engine py-words uses to show the entries of Logeion (see logeion.py).
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field
from typing import Iterator

from logeion_api import link_url
from logeion_dom import Node, parse_html
from logeion_entry import DICTIONARY, Entry, Options, Section, shown_sections
from logeion_text import clean_inline, display_width, strip_ansi


class Style:
    """ANSI styling; with enabled=False every method returns text unchanged.
    The TUI and the window turn these ANSI codes into their own attributes.
    Links are OSC 8 hyperlinks (made only if `links`, by default when
    enabled), which terminals that know them make clickable and the TUI and
    the window follow."""

    def __init__(self, enabled: bool, links: bool | None = None):
        self.on = enabled
        self.links = enabled if links is None else links

    def _w(self, code, s):
        return f"\033[{code}m{s}\033[0m" if self.on and s else s

    def title(self, s): return self._w("1;4", s)
    def section(self, s): return self._w("1;36", s)
    def headword(self, s): return self._w("1", s)
    def example(self, s): return self._w("32", s)
    def dim(self, s): return self._w("2", s)

    def inline(self, codes: str, s: str) -> str:
        """S in bold and/or italic (CODES: '1', '3' or '1;3'), within a line
        that keeps its own style around it."""
        if not self.on or not s:
            return s
        off = ";".join({"1": "22", "3": "23"}[c] for c in codes.split(";"))
        return f"\033[{codes}m{s}\033[{off}m"

    def link(self, url, s):
        return f"\033]8;;{url}\033\\{s}\033]8;;\033\\" if self.links and s else s


#  While an entry is rendered, a link is "\x02URL\x03text\x04" in the text
#  (control characters, which entries never have), so that it survives the
#  cleanup of the text; it becomes a Style.link when the text is wrapped.
#  Bold and italic text is marked the same way, with "\x01" and the codes
#  ('1', '3' or '1;3') in place of the URL.
MARK_OPEN, MARK_MID, MARK_CLOSE = "\x02", "\x03", "\x04"
STYLE = "\x01"
MARK_RE = re.compile("\x02([^\x02-\x04]*)\x03([^\x02-\x04]*)\x04")
STYLE_MARK_RE = re.compile("\x02\x01([^\x02-\x04]*)\x03([^\x02-\x04]*)\x04")
_NO_MARKERS = dict.fromkeys(map(ord, STYLE + MARK_OPEN + MARK_MID + MARK_CLOSE))


def split_marks(s: str) -> tuple[str, list[tuple[int, int, str]]]:
    """S without the marks, and the marked pieces in it as (start, end,
    URL or STYLE + codes), positions in the text without the marks."""
    plain: list[str] = []
    spans: list[tuple[int, int, str]] = []
    n = pos = 0

    def add(text):
        nonlocal n
        text = text.translate(_NO_MARKERS)       # (those of a broken mark)
        plain.append(text)
        n += len(text)

    for m in MARK_RE.finditer(s):
        add(s[pos:m.start()])
        start = n
        add(m.group(2))
        if n > start:
            spans.append((start, n, m.group(1)))
        pos = m.end()
    add(s[pos:])
    return "".join(plain), spans


def marked(payload: str, text: str) -> str:
    """TEXT marked with PAYLOAD (a URL, or STYLE + codes); spaces at its ends
    go outside the marks."""
    core = text.strip()
    if not core:
        return text
    lead = text[:len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    return f"{lead}{MARK_OPEN}{payload}{MARK_MID}{core}{MARK_CLOSE}{trail}"


SKIP_TAGS = {"style", "script", "link", "meta", "figure", "img", "audio", "video",
             "source", "noscript", "math", "annotation", "head", "title"}
BLOCK_TAGS = {"p", "div", "ul", "ol", "dl", "dd", "dt", "li", "table", "section",
              "blockquote", "center", "pre", "h1", "h2", "h3", "h4", "h5", "h6", "hr"}
BOLD_TAGS = {"b", "strong"}
ITALIC_TAGS = {"i", "em"}


def _style_of(n: Node) -> str:
    return n.attrs.get("style", "").replace(" ", "").lower()


class Renderer:
    """Accumulates rendered lines in self.lines."""

    def __init__(self, style: Style, width: int):
        self.s = style
        self.width = max(width, 40)
        self.lines: list[str] = []
        self.heading_end = 0    # (no blank line right under a heading)

    # ---- helpers ---------------------------------------------------------- #
    def skip(self, n: Node) -> bool:
        if n.tag in SKIP_TAGS:
            return True
        st = _style_of(n)
        return "display:none" in st

    def is_block(self, n: Node) -> bool:
        return n.tag in BLOCK_TAGS

    def has_block(self, n: Node) -> bool:
        return any(isinstance(c, Node) and not self.skip(c) and
                   (self.is_block(c) or self.has_block(c)) for c in n.children)

    @staticmethod
    def text_of(s: str) -> str:
        """A piece of text of the HTML: its line breaks are spaces (only <br>
        breaks a line)."""
        return s.replace("\r", " ").replace("\n", " ").replace("\t", " ")

    def runs(self, n: Node, leave: Node | None = None) -> Iterator[tuple[str, str | Node]]:
        """The children of N (but LEAVE), as ("text", inline text) for each
        stretch of inline content and ("block", node) for each block between
        them."""
        buf: list[str] = []
        for c in n.children:
            if isinstance(c, str):
                buf.append(self.text_of(c))
            elif c is leave or self.skip(c):
                continue
            elif c.tag == "br":
                buf.append("\n")
            elif self.is_block(c) or self.has_block(c):
                if buf:
                    yield "text", "".join(buf)
                    buf = []
                yield "block", c
            else:
                buf.append(self.piece(c))
        if buf:
            yield "text", "".join(buf)

    def inline(self, n: Node) -> str:
        parts = []
        for c in n.children:
            if isinstance(c, str):
                parts.append(self.text_of(c))
            elif self.skip(c):
                continue
            elif c.tag == "br":
                parts.append("\n")
            else:
                parts.append(self.piece(c))
        return "".join(parts)

    def piece(self, n: Node) -> str:
        """The text of the inline element N, marked as a link or as bold or
        italic if it is one."""
        if n.attrs.get("href") is not None and self.s.links:
            return self.anchor(n)
        text = self.inline(n)
        codes = self.codes(n)
        if not codes or not self.s.on:
            return text
        return self.styled(codes, text)

    @staticmethod
    def codes(n: Node) -> set[str]:
        st = _style_of(n)
        out = set()
        if n.tag in BOLD_TAGS or "font-weight:bold" in st:
            out.add("1")
        if n.tag in ITALIC_TAGS or "font-style:italic" in st:
            out.add("3")
        return out

    def styled(self, codes: set[str], text: str) -> str:
        """TEXT marked bold and/or italic.  Marks are not nested: if all of
        TEXT is already marked, the codes are put together; marks of parts
        of it give way to the new one; and links keep their place (the
        text is then left as it is)."""
        core = text.strip()
        whole = STYLE_MARK_RE.fullmatch(core)
        if whole:
            codes = codes | set(whole.group(1).split(";"))
            text = text.replace(core, whole.group(2))
        else:
            text = STYLE_MARK_RE.sub(r"\2", text)
        if MARK_OPEN in text:
            return text
        return marked(STYLE + ";".join(sorted(codes)), text)

    def anchor(self, a: Node) -> str:
        """The text of the link A, marked as a link if it leads somewhere."""
        text = STYLE_MARK_RE.sub(r"\2", self.inline(a))
        url = link_url(a.attrs.get("href", ""))
        if not url or not text.strip() or MARK_OPEN in text:
            return text
        return marked(url, text)

    def linked(self, plain: str, spans, start: int = 0) -> str:
        """PLAIN, a piece of a text beginning at START, with the marks of
        SPANS (positions in the whole text) made Style.links or styles."""
        if not spans:
            return plain
        end = start + len(plain)
        out, pos = [], 0
        for s, e, payload in spans:
            s, e = max(s, start) - start, min(e, end) - start
            if s >= e:
                continue
            out.append(plain[pos:s])
            if payload.startswith(STYLE):
                out.append(self.s.inline(payload[1:], plain[s:e]))
            else:
                out.append(self.s.link(payload, plain[s:e]))
            pos = e
        out.append(plain[pos:])
        return "".join(out)

    def emit(self, text: str, indent: str, hang: str | None = None, fmt=None):
        text = clean_inline(text)
        if not text:
            return
        hang = indent if hang is None else hang
        first = True
        for para in text.split("\n"):
            plain, spans = split_marks(para)
            lead = len(plain) - len(plain.lstrip())
            plain = plain.strip()
            if not plain:
                continue
            spans = [(s - lead, e - lead, u) for s, e, u in spans]
            prefix = indent if first else hang
            wrapped = textwrap.wrap(plain, width=self.width, initial_indent=prefix,
                                    subsequent_indent=hang, break_on_hyphens=False,
                                    break_long_words=False)
            first = False
            pos = 0
            for j, line in enumerate(wrapped):
                if spans:
                    # each line is a piece of the text (only the spaces where it
                    # was broken are left out): find it, to put its marks in
                    pre = prefix if j == 0 else hang
                    body = line[len(pre):]
                    at = plain.find(body, pos)
                    if at >= 0:
                        line = pre + self.linked(body, spans, at)
                        pos = at + len(body)
                if fmt:
                    pre = len(line) - len(line.lstrip())
                    line = line[:pre] + fmt(line[pre:])
                self.lines.append(line)

    def blank(self):
        if self.lines and self.lines[-1] != "" and len(self.lines) != self.heading_end:
            self.lines.append("")

    # ---- block walker ----------------------------------------------------- #
    def block(self, n: Node, indent: str, fmt=None):
        """Render the children of N: runs of inline content become paragraphs."""
        for kind, run in self.runs(n):
            if kind == "text":
                self.emit(run, indent, fmt=fmt)
            else:
                self.element(run, indent, fmt)

    def element(self, n: Node, indent: str, fmt=None):
        tag = n.tag
        if tag in ("ul", "ol"):
            self.list_(n, indent, ordered=(tag == "ol"), fmt=fmt)
        elif tag == "dl":
            for c in n.children:
                if isinstance(c, Node) and not self.skip(c):
                    if c.tag == "dt":
                        self.block(c, indent, fmt=self.s.headword)
                    else:
                        self.block(c, indent + "  ", fmt)
        elif tag == "table":
            self.table(n, indent)
        elif tag in ("p", "blockquote"):
            self.blank()
            self.block(n, indent + ("  " if tag == "blockquote" else ""), fmt)
            self.blank()
        elif tag == "li":                       # (one alone: an example of the corpus)
            self.blank()
            self.block(n, indent, fmt)
            self.blank()
        elif tag == "hr":
            self.blank()
        elif tag == "div" and "margin-left" in _style_of(n):
            self.block(n, indent + "  ", fmt)       # (Bailly's senses)
        else:
            self.block(n, indent, fmt)

    @staticmethod
    def bullet_of(li: Node) -> Node | None:
        """The <span class="bullet"> that gives an item of Lewis & Short or
        LSJ its letter or number (I, A, 1, a...)."""
        for c in li.children:
            if isinstance(c, Node):
                return c if "bullet" in c.classes else None
            if c.strip():
                return None
        return None

    def list_(self, n: Node, indent: str, ordered: bool, fmt=None):
        unmarked = "list-style-type:none" in _style_of(n) or "list-style:none" in _style_of(n)
        i = 0
        for li in n.children:
            if not isinstance(li, Node) or self.skip(li):
                continue
            if li.tag in ("ul", "ol"):          # (a list right in a list: LSJ, L&S)
                self.element(li, indent, fmt)
                continue
            if li.tag != "li":
                self.element(li, indent, fmt)
                continue
            i += 1
            bullet = self.bullet_of(li)
            if bullet is not None:
                mark = clean_inline(bullet.text())
                marker = f"{mark} " if mark else "• "
            elif not any(isinstance(c, str) and c.strip() or isinstance(c, Node) and
                         not self.skip(c) and c.tag not in ("ul", "ol") for c in li.children):
                # an item holding only lists: one level further in, no marker
                for c in li.children:
                    if isinstance(c, Node) and not self.skip(c):
                        self.element(c, indent + "  ", fmt)
                continue
            elif unmarked or "list-style-type:none" in _style_of(li):
                marker = ""
            else:
                marker = f"{i}. " if ordered else "• "
            hang = indent + " " * len(marker)
            # inline lead text of the item, then nested blocks; the marker
            # goes on the first line of whichever comes first
            first = True
            for kind, run in self.runs(li, leave=bullet):
                if kind == "text":
                    if clean_inline(split_marks(run)[0]):
                        self.emit(run, indent + marker if first else hang, hang, fmt)
                        first = False
                    continue
                start = len(self.lines)
                self.element(run, hang, fmt)
                if first and marker:
                    self.put_marker(start, indent, marker, hang)
                first = False

    def put_marker(self, start: int, indent: str, marker: str, hang: str):
        """Puts a list MARKER on the first line rendered since START (an
        item that starts with a block)."""
        while start < len(self.lines) and not self.lines[start].strip():
            del self.lines[start]
        if start < len(self.lines) and self.lines[start].startswith(hang):
            self.lines[start] = indent + marker + self.lines[start][len(hang):]
        else:
            self.lines.insert(start, (indent + marker).rstrip())

    def table(self, n: Node, indent: str):
        rows: list[list[str]] = []
        for tr in n.iter():
            if tr.tag != "tr" or self.skip(tr):
                continue
            # ignore rows of nested tables
            p = tr.parent
            while p is not None and p.tag != "table":
                p = p.parent
            if p is not n:
                continue
            cells = []
            for td in tr.children:
                if isinstance(td, Node) and td.tag in ("td", "th") and not self.skip(td):
                    cells.append(clean_inline(self.inline(td)).replace("\n", ", "))
            if any(cells):
                rows.append(cells)
        if not rows:
            return
        ncol = max(len(r) for r in rows)
        rows = [r + [""] * (ncol - len(r)) for r in rows]
        plain = [[split_marks(c)[0] for c in r] for r in rows]
        widths = [max(display_width(r[i]) for r in plain) for i in range(ncol)]
        total = len(indent) + sum(widths) + 2 * (ncol - 1)
        if total <= self.width + 20:
            for r in rows:
                cells = []
                for i, c in enumerate(r):
                    text, spans = split_marks(c)
                    cells.append(self.linked(text, spans).rstrip() if i == ncol - 1 else
                                 self.linked(text, spans) + " " * (widths[i] - display_width(text)))
                self.lines.append((indent + "  ".join(cells)).rstrip())
        else:  # too wide: one row per line
            for r in rows:
                self.emit(" | ".join(c for c in r if c), indent, indent + "    ")
        self.blank()

    # ---- sections --------------------------------------------------------- #
    def section_body(self, sec: Section, indent: str):
        """The content of a section."""
        self.block(parse_html(sec.html), indent)


# --------------------------------------------------------------------------- #
# Whole entries
# --------------------------------------------------------------------------- #
@dataclass
class Rendered:
    """A rendered entry.  toc holds (depth, title, line index), one for each
    section (all at depth 0); dictionary_lines the lines of the headings of
    the dictionaries."""
    lines: list[str]
    toc: list[tuple[int, str, int]] = field(default_factory=list)
    dictionary_lines: list[int] = field(default_factory=list)
    codes: list[str] = field(default_factory=list)     # (one per item of toc)
    _plain: list[str] | None = field(default=None, repr=False)

    @property
    def plain(self) -> list[str]:
        """The lines without ANSI codes."""
        if self._plain is None:
            self._plain = [strip_ansi(l) for l in self.lines]
        return self._plain

    def text(self) -> str:
        return "\n".join(self.lines)

    def toc_index(self, top: int) -> int | None:
        """The item of the contents being read when line TOP is the first
        shown (None if there are none)."""
        if not self.toc:
            return None
        idx = 0
        for i, (_, _, line) in enumerate(self.toc):
            if line > top + 1:
                break
            idx = i
        return idx

    def section_line(self, name: str) -> int | None:
        """The line of the heading of the section NAME (its name or code),
        if it is shown."""
        key = name.casefold()
        for (_, title, line), code in zip(self.toc, self.codes):
            if key in (title.casefold(), code.casefold()):
                return line
        return None


def render_sections(title: str, sections: list[Section], style: Style,
                    width: int) -> Rendered:
    """A title line, then each section: its heading, and its content."""
    r = Renderer(style, width)
    toc: list[tuple[int, str, int]] = []
    dict_lines: list[int] = []
    codes: list[str] = []
    r.lines.append(style.title(title))
    for sec in sections:
        r.blank()
        if sec.kind == DICTIONARY:
            dict_lines.append(len(r.lines))
        toc.append((0, sec.name, len(r.lines)))
        codes.append(sec.code)
        r.lines.append(style.section(sec.name))
        r.heading_end = len(r.lines)
        r.section_body(sec, "  ")
        r.blank()

    # strip trailing spaces and collapse runs of blank lines, remapping positions
    keep: list[str] = []
    remap: dict[int, int] = {}
    for i, line in enumerate(r.lines):
        line = line.rstrip()
        if line == "" and keep and keep[-1] == "":
            remap[i] = len(keep) - 1
            continue
        remap[i] = len(keep)
        keep.append(line)
    while keep and keep[-1] == "":
        keep.pop()
    return Rendered(
        lines=keep,
        toc=[(d, t, remap.get(ln, ln)) for d, t, ln in toc],
        dictionary_lines=[remap.get(ln, ln) for ln in dict_lines],
        codes=codes,
    )


def render_entry(entry: Entry, spec: str, style: Style, width: int,
                 options: Options | None = None, preferred=()) -> Rendered:
    """The sections of ENTRY that SPEC (the dictionary filter) and OPTIONS
    choose, rendered."""
    sections = shown_sections(entry, spec, options or Options(), preferred)
    return render_sections(entry.title(), sections, style, width)


def section_text(sec: Section) -> str:
    r = Renderer(Style(False), 10_000)
    r.section_body(sec, "")
    return "\n".join(l.rstrip() for l in r.lines).strip()


def entry_to_json(entry: Entry, sections: list[Section]) -> dict:
    return {
        "query": entry.query, "word": entry.word, "url": entry.url,
        "sections": [{"name": s.name, "code": s.code, "kind": s.kind,
                      "text": section_text(s)} for s in sections],
    }
