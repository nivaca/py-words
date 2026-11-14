"""Talking to Logeion (logeion.uchicago.edu), through the API its web
page uses (anastrophe.uchicago.edu/logeion-api):

    /detail?w=WORD&type=normal   the entries of the dictionaries, the short
                                 definitions and the information on the word
                                 (frequency, collocations, textbooks, links)
    /find?w=FORM                 the parses of an inflected form, with their
                                 lemmas
    /search?q=PREFIX             headwords beginning so (Greek may be typed
                                 in Latin letters: 'logo' finds λόγος)

From py-logeion 0.2.1 (https://github.com/nivaca/py-logeion), whose
engine py-words uses to show the entries of Logeion (see logeion.py).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from version import NAME, VERSION

SITE = "https://logeion.uchicago.edu/"
API = "https://anastrophe.uchicago.edu/logeion-api"
USER_AGENT = f"{NAME}/{VERSION} (a Latin dictionary, with Logeion's entries; Python urllib)"
TIMEOUT = 20

# Errors callers should treat as "could not reach Logeion".
NetworkError = (urllib.error.URLError, OSError)


class NotFound(Exception):
    """No dictionary has the word.  CLOSEST is the headword next to it in
    the alphabet, as Logeion proposes it (or None)."""

    def __init__(self, word: str, closest: str | None = None):
        super().__init__(word)
        self.word = word
        self.closest = closest


def _get(endpoint: str, params: dict) -> dict:
    url = f"{API}/{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = resp.read()
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504) and attempt < 3:
                try:
                    delay = float(e.headers.get("Retry-After", ""))
                except ValueError:
                    delay = 2 ** attempt
                time.sleep(min(max(delay, 1), 10))
                continue
            raise
    try:
        out = json.loads(data.decode("utf-8", "replace"))
    except ValueError:
        raise urllib.error.URLError(f"Logeion sent something that is not JSON ({url})") \
            from None
    if not isinstance(out, dict):
        raise urllib.error.URLError(f"Logeion sent an unexpected answer ({url})")
    return out


def normal_word(word: str) -> str:
    """WORD as Logeion looks it up: without spaces at its ends, nor the index
    number of homographs ('ὅτι2' -> 'ὅτι': all of them share one page)."""
    word = " ".join(word.split())
    stripped = re.sub(r"\d+$", "", word).strip()
    return stripped or word


def page_url(word: str) -> str:
    """The page of WORD on Logeion's site."""
    return SITE + urllib.parse.quote(normal_word(word), safe="")


def corpus_url(word: str) -> str:
    """A search of Logeion's corpus (PhiloLogic) for the lemma WORD."""
    corpus = "Greek" if is_greek(word) else "Latin"
    return ("https://artflsrv03.uchicago.edu/philologic4/%s/query?report=concordance"
            "&method=phrase&q=%s&start=0&end=0" % (
                corpus, urllib.parse.quote("lemma:" + normal_word(word), safe=":")))


def is_greek(word: str) -> bool:
    return any("Ͱ" <= c <= "Ͽ" or "ἀ" <= c <= "῿" for c in word)


def link_url(href: str) -> str | None:
    """The URL of a link of an entry (the href of an <a>), or None for links
    not worth following (mailto:, javascript:, anchors in the page...)."""
    href = (href or "").strip()
    if href.startswith("//"):
        href = "https:" + href
    if href.startswith(("https://", "http://")) and \
            not any(c <= " " or c == "\x7f" for c in href):
        return href
    return None


def entry_target(url: str) -> tuple[str, str | None] | None:
    """(word, section) of a link to a page of Logeion ('…/rosa#lsj' ->
    ('rosa', 'lsj')); None for any other link (to open in the browser)."""
    for site in (SITE, "http://logeion.uchicago.edu/"):
        if url.startswith(site):
            break
    else:
        return None
    path, _, frag = url[len(site):].partition("#")
    word = urllib.parse.unquote(path).strip()
    if not word or "/" in word or word.startswith(("#", "?")) or "." in word:
        return None                     # (the site's own pages: about, index.html...)
    return word, urllib.parse.unquote(frag) or None


# --------------------------------------------------------------------------- #
# The three requests
# --------------------------------------------------------------------------- #
def get_detail(word: str) -> dict:
    return _get("detail", {"w": word, "type": "normal"})


def get_find(word: str) -> dict:
    return _get("find", {"w": word})


def search(query: str, limit: int = 10) -> list[str]:
    """Headwords beginning with QUERY (also Greek typed in Latin letters)."""
    query = query.strip()
    if not query:
        return []
    words = _get("search", {"q": query}).get("words") or []
    out: list[str] = []
    for w in words:
        if isinstance(w, str) and w.strip() and w not in out:
            out.append(w)
    return out[:limit]


def suggestions(word: str, limit: int = 8, closest: str | None = None) -> list[str]:
    """Alternatives for a word that has no entry (CLOSEST, the one Logeion
    proposes, first); empty on network errors."""
    out = [closest] if closest and closest != word else []
    try:
        out += [s for s in search(word, limit=limit) if s != word and s not in out]
    except NetworkError:
        pass
    return out[:limit]


def has_entries(detail: dict) -> bool:
    """Whether the /detail answer DETAIL has anything to show."""
    d = detail.get("detail") or {}
    return any(d.get(k) for k in ("dicos", "shortdef", "friezeD", "bwl"))


def common_prefix(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a.casefold(), b.casefold()):
        if x != y:
            break
        n += 1
    return n


def lemmas_of(parses: list[dict]) -> list[str]:
    """The lemmas of the parses of a form, each once, in their order."""
    out: list[str] = []
    for p in parses:
        lemma = normal_word(str(p.get("lemma") or ""))
        if lemma and lemma not in out:
            out.append(lemma)
    return out


def best_lemma(form: str, lemmas: list[str]) -> str | None:
    """The lemma of FORM to show first: the one that begins most like it
    ('rosae' -> rosa rather than rodo); among equals, Logeion's order."""
    if not lemmas:
        return None
    return max(lemmas, key=lambda l: (common_prefix(form, l), -lemmas.index(l)))


# --------------------------------------------------------------------------- #
# Pages: what is shown of a word, cached
# --------------------------------------------------------------------------- #
def fetch_page(word: str) -> dict:
    """Everything shown for WORD: {"query", "word" (the headword shown: WORD,
    or the lemma of an inflected form), "detail", "info", "parses",
    "lemmas"}.  Raises NotFound, or a NetworkError."""
    query = normal_word(word)
    detail = get_detail(query)
    try:
        found = get_find(query)
    except NetworkError:
        found = {}                      # (the parses are an extra)
    parses = [p for p in found.get("parses") or [] if isinstance(p, dict)]
    lemmas = lemmas_of(parses)
    shown = query
    if not has_entries(detail):
        lemma = best_lemma(query, [l for l in lemmas if l != query])
        if lemma:
            detail = get_detail(lemma)
            shown = lemma
        if not has_entries(detail):
            closest = None if parses else found.get("word")
            raise NotFound(query, closest if isinstance(closest, str) else None)
    return {"query": query, "word": shown,
            "detail": detail.get("detail") or {}, "info": detail.get("info") or {},
            "parses": parses, "lemmas": lemmas}


class Client:
    """Fetches pages, caching them in memory (missing ones included) and,
    when cache_dir is given, keeping them on disk for max_age_days so that
    repeated lookups do not ask Logeion again."""

    def __init__(self, on_fetch: Callable[[str], None] | None = None,
                 cache_dir: Path | None = None, max_age_days: float = 0):
        self._cache: dict[str, dict | NotFound] = {}
        self.on_fetch = on_fetch  # called with the word before a network fetch
        self.cache_dir = Path(cache_dir) / "pages" if cache_dir and max_age_days > 0 else None
        self.max_age = max_age_days * 86400

    # ---- disk cache ------------------------------------------------------- #
    def _disk_path(self, key: str) -> Path | None:
        if self.cache_dir is None:
            return None
        return self.cache_dir / (hashlib.sha1(key.encode("utf-8")).hexdigest() + ".json.gz")

    def _disk_read(self, key: str) -> dict | None:
        path = self._disk_path(key)
        try:
            if path and time.time() - path.stat().st_mtime < self.max_age:
                data = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
                return data if isinstance(data, dict) and "detail" in data else None
        except (OSError, EOFError, gzip.BadGzipFile, UnicodeDecodeError, ValueError):
            pass
        return None

    def _disk_write(self, key: str, data: dict):
        path = self._disk_path(key)
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
            tmp.write_bytes(gzip.compress(json.dumps(data, ensure_ascii=False).encode("utf-8")))
            os.replace(tmp, path)
        except OSError:
            pass  # the disk cache is only an optimisation

    # ---- pages ------------------------------------------------------------ #
    def page(self, word: str) -> dict:
        """The page of WORD (see fetch_page); raises NotFound, or a
        NetworkError on failure."""
        key = normal_word(word)
        if key not in self._cache:
            data = self._disk_read(key)
            if data is None:
                if self.on_fetch:
                    self.on_fetch(key)
                try:
                    data = fetch_page(key)
                except NotFound as e:
                    self._cache[key] = e
                else:
                    self._disk_write(key, data)
            if data is not None:
                self._cache[key] = data
        found = self._cache[key]
        if isinstance(found, NotFound):
            raise found
        return found

    def forget(self, word: str) -> None:
        """Drop a page from both caches, so the next request downloads it again."""
        key = normal_word(word)
        self._cache.pop(key, None)
        path = self._disk_path(key)
        if path:
            try:
                path.unlink()
            except OSError:
                pass


def _cached_files(cache_dir: Path, suffixes: tuple[str, ...]) -> list[tuple[Path, int]]:
    """The files of the disk cache ending in SUFFIXES, with their sizes."""
    pages = Path(cache_dir) / "pages"
    if not pages.is_dir():
        return []
    out = []
    for f in pages.iterdir():
        if f.name.endswith(suffixes):
            try:
                out.append((f, f.stat().st_size))
            except OSError:
                pass
    return out


def clear_disk_cache(cache_dir: Path) -> tuple[int, int]:
    """Delete cached pages. Returns (files removed, bytes freed)."""
    n = size = 0
    for f, f_size in _cached_files(cache_dir, (".json.gz", ".tmp")):
        try:
            f.unlink()
        except OSError:
            continue
        n += 1
        size += f_size
    return n, size


def disk_cache_usage(cache_dir: Path) -> tuple[int, int]:
    """(number of cached pages, total bytes)."""
    files = _cached_files(cache_dir, (".json.gz",))
    return len(files), sum(size for _, size in files)
