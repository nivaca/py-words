// py-words in the browser: the page of words_web.py (its WSGI app,
// WebApp) running in Pyodide, with no server anywhere.
//
// We catch the page's links and forms here, hand them to WebApp as
// requests, and swap in whatever page comes back.  Settings and history
// (config.toml and the history file, in Pyodide's file system) are kept
// in localStorage between visits; the dictionary's cache (see lexicon.py)
// goes in IndexedDB, so only the first visit has to read the XML.
// py-words.zip downloads while Pyodide does.

'use strict';

//  TODO: probar un Pyodide más nuevo (¿arranca más rápido?).  Si se cambia,
//  cambiar también python-version en .github/workflows/pages.yml.
const PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/';
const HOME = '/py-words';               // (the program, in Pyodide's files)
const STATE = '/state';                 // (the settings and the history)
const CACHE = '/cache';                 // (the dictionary's, in IndexedDB)
const KEPT = ['config/config.toml', 'history'];   // (in localStorage)

const started = performance.now();
let pyodide, call;

function status(text) {
  const p = document.getElementById('status');
  if (p) p.textContent = text;
}

function seconds() {
  return ((performance.now() - started) / 1000).toFixed(1) + ' s';
}

// The loading bar.  Each stage of the start has its share of the bar, as
// long as it took at the last visit (kept in localStorage), or a guess.
// The download of the zip moves it by its bytes, and the loading of
// Python by the time it is expected to take.  While Python unpacks and
// reads the dictionary the page cannot run, so the bar is sent then with
// a CSS transition to near the end of the stage, in the time expected:
// the browser animates it all the same.  A new zip (a new version) makes
// the dictionary's cache new as well, and reading it takes longer: that
// time is kept apart (readFresh), by the size of the zip.

const TIMING = 'py-words/timing';
const GUESS = {start: 6, unpack: 1, read: 6};   // (seconds)

function lastTiming() {
  try {
    return JSON.parse(localStorage.getItem(TIMING)) || {};
  } catch (e) {
    return {};
  }
}

const bar = {
  shares: {}, done: 0,
  plan(times) {
    const total = times.start + times.unpack + times.read;
    for (const stage in times) this.shares[stage] = times[stage] / total;
  },
  set(fraction, seconds = 0.2) {
    const fill = document.getElementById('bar');
    if (!fill) return;
    fill.style.transition = 'transform ' + seconds + 's linear';
    fill.style.transform = 'scaleX(' + fraction + ')';
    fill.parentNode.setAttribute('aria-valuenow',
                                 Math.round(fraction * 100));
  },
  part(stage, fraction) {               // (FRACTION of STAGE is done)
    this.set(this.done + this.shares[stage] * Math.min(fraction, 0.97));
  },
  slide(stage, seconds) {               // (nothing to measure in STAGE)
    this.set(this.done + this.shares[stage] * 0.95, seconds);
  },
  end(stage) {
    this.done += this.shares[stage];
    this.set(this.done);
  },
};

function painted() {
  //  (the bar's new transition starts before Python keeps the page busy;
  //  not waiting long in a tab in the background, which paints nothing)
  return Promise.race([
    new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))),
    new Promise(r => setTimeout(r, 100))]);
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.onload = resolve;
    script.onerror = () => reject(new Error('cannot load ' + src));
    document.head.appendChild(script);
  });
}

// The settings and history: localStorage <-> Pyodide's files

function restore() {
  for (const name of KEPT) {
    const text = localStorage.getItem('py-words/' + name);
    if (text === null) continue;
    const path = STATE + '/' + name;
    pyodide.FS.mkdirTree(path.slice(0, path.lastIndexOf('/')));
    pyodide.FS.writeFile(path, text);
  }
}

function keep() {
  for (const name of KEPT) {
    try {
      const text = pyodide.FS.readFile(STATE + '/' + name,
                                       {encoding: 'utf8'});
      localStorage.setItem('py-words/' + name, text);
    } catch (e) {
      localStorage.removeItem('py-words/' + name);   // (cleared)
    }
  }
}

// The cache of the dictionary: Pyodide's folder CACHE <-> IndexedDB

let cached = false;                     // (whether CACHE is in IndexedDB)
let saving = null;

function sync(populate) {
  return new Promise((resolve, reject) =>
    pyodide.FS.syncfs(populate, e => e ? reject(e) : resolve()));
}

async function openCache() {
  try {
    pyodide.FS.mkdirTree(CACHE);
    pyodide.FS.mount(pyodide.FS.filesystems.IDBFS, {}, CACHE);
    await sync(true);                   // (what earlier visits kept)
    cached = true;
  } catch (e) {                         // (no IndexedDB: no cache)
    console.warn('py-words: no cache: ' + e);
  }
}

function save() {
  //  (in the background, once at a time; changed files only)
  if (!cached || saving) return;
  saving = sync(false).catch(e => console.warn('py-words: ' + e))
                      .finally(() => { saving = null; });
}

// Requests to WebApp

//  Ojo: the files must keep their dates from the zip, because the cache
//  compares them.  unpackArchive les pone a todos la hora de la visita, y
//  así la caché nunca coincidía.
const UNPACK = `
import os, time, zipfile
with zipfile.ZipFile('/py-words.zip') as z:
    z.extractall('${HOME}')
    for info in z.infolist():
        t = time.mktime(info.date_time + (0, 0, -1))
        os.utime(os.path.join('${HOME}', info.filename), (t, t))
os.remove('/py-words.zip')
`;

const BOOT = `
import io, os, sys
os.environ['WHITAKERS_WORDS_CONFIG'] = '${STATE}/config'
os.environ['WHITAKERS_WORDS_HISTORY'] = '${STATE}/history'
os.environ['WHITAKERS_WORDS_CACHE'] = CACHE_FOLDER
os.chdir('${HOME}')
sys.path.insert(0, '${HOME}')
import interface, words_web
from settings import ensure_config
ensure_config()
interface.use_configured()
app = words_web.WebApp('${HOME}/data')

def call(method, path, query, body):
    """The answer of WebApp to a request: (status, Location, page)."""
    body = body.encode()
    environ = {'REQUEST_METHOD': method, 'PATH_INFO': path,
               'QUERY_STRING': query, 'HTTP_HOST': 'localhost',
               'CONTENT_LENGTH': str(len(body)),
               'wsgi.input': io.BytesIO(body)}
    got = {}

    def start(status, headers):
        got['status'], got['headers'] = status, dict(headers)
    page = b''.join(app(environ, start)).decode('utf-8', 'replace')
    return got['status'], got['headers'].get('Location', ''), page
`;

function request(method, path, query, body, push) {
  const answer = call(method, path, query, body || '');
  const [code, location, page] = answer.toJs();
  answer.destroy();
  keep();
  save();                               // (a language read for the first
                                        // time adds to the cache)
  if (code.startsWith('303')) {         // (after a form: the search page)
    const target = new URL(location, 'http://x');
    return request('GET', target.pathname, target.search.slice(1), '',
                   true);
  }
  show(page);
  if (method === 'GET' && path === '/') {
    const url = query ? '?' + query : window.location.pathname;
    if (push) history.pushState(null, '', url);
    else history.replaceState(null, '', url);
  }
}

function show(html) {
  const page = new DOMParser().parseFromString(html, 'text/html');
  for (const name of ['lang', 'data-theme']) {
    const value = page.documentElement.getAttribute(name);
    if (value === null) document.documentElement.removeAttribute(name);
    else document.documentElement.setAttribute(name, value);
  }
  //  (the icon beside the page: the site may not be at the server's root)
  const icon = page.querySelector('link[rel=icon]');
  if (icon) icon.setAttribute('href', 'icon.png');
  document.head.innerHTML = page.head.innerHTML;
  document.body.innerHTML = page.body.innerHTML;
  for (const old of document.body.querySelectorAll('script')) {
    //  (a new element, so that it runs; in a block of its own, as it runs
    //  again with each page, and declares constants)
    const script = document.createElement('script');
    script.textContent = '{\n' + old.textContent + '\n}';
    old.replaceWith(script);
  }
  const box = document.querySelector('input[name=q]');
  if (box && !box.value) box.focus();
}

// The page's links and forms

document.addEventListener('click', event => {
  const link = event.target.closest('a[href]');
  if (!link || !call) return;
  const href = link.getAttribute('href');
  if (href !== '/' && !href.startsWith('/?')) return;  // (others: as usual)
  event.preventDefault();
  request('GET', '/', href.slice(2), '', true);
});

function sendForm(form, submitter) {
  const action = form.getAttribute('action') || '/';
  const fields = new URLSearchParams(new FormData(form, submitter));
  if ((form.getAttribute('method') || 'get').toLowerCase() === 'post') {
    request('POST', action, '', fields.toString(), true);
  } else {
    request('GET', action, fields.toString(), '', true);
  }
}

document.addEventListener('submit', event => {
  if (event.defaultPrevented || !call) return;   // (cancelled by the page)
  event.preventDefault();
  sendForm(event.target, event.submitter);
});

// (the page's script submits some forms itself, which fires no event)
HTMLFormElement.prototype.submit = function () { sendForm(this); };

window.addEventListener('popstate', () => {
  if (call) request('GET', '/', location.search.slice(1), '', false);
});

// Starting

async function download(name, progress, tries = 3) {
  //  (a download cut off, by the network or the browser, is tried again;
  //  a copy the browser kept is used only if the server says it is
  //  current, so that a new version is seen at once.  PROGRESS is told
  //  the part downloaded, if the server gives the size)
  for (let i = 1; ; i++) {
    try {
      const answer = await fetch(name, {cache: 'no-cache'});
      if (!answer.ok) throw new Error('cannot load ' + name + ': ' +
                                      answer.status);
      const size = Number(answer.headers.get('Content-Length'));
      if (!size || !answer.body) return await answer.arrayBuffer();
      const reader = answer.body.getReader();
      const chunks = [];
      let got = 0;
      for (;;) {
        const {done, value} = await reader.read();
        if (done) break;
        chunks.push(value);
        got += value.length;
        progress(Math.min(got / size, 1));
      }
      const all = new Uint8Array(got);
      let at = 0;
      for (const chunk of chunks) {
        all.set(chunk, at);
        at += chunk.length;
      }
      return all.buffer;
    } catch (e) {
      if (i >= tries) throw e;
      await new Promise(r => setTimeout(r, 500 * i));
    }
  }
}

async function main() {
  const last = lastTiming();
  const times = {};
  for (const stage in GUESS) times[stage] = last[stage] || GUESS[stage];
  bar.plan(times);
  let zipPart = null, pythonReady = false;
  const ticking = setInterval(() => {
    const python = pythonReady ? 1 :
      (performance.now() - started) / 1000 / times.start;
    bar.part('start', zipPart === null ? python : Math.min(python, zipPart));
  }, 100);
  const took = {};
  let mark = started;
  function lap(stage) {
    const now = performance.now();
    took[stage] = (now - mark) / 1000;
    mark = now;
    bar.end(stage);
  }
  try {
    status('Loading Python…');
    const zip = download('py-words.zip',            // (at the same time)
                         part => { zipPart = part; });
    zip.catch(() => {});                // (its error is reported below)
    await loadScript(PYODIDE + 'pyodide.js');
    pyodide = await loadPyodide({indexURL: PYODIDE});
    pythonReady = true;
    status('Loading the dictionary…  (' + seconds() + ')');
    const bytes = new Uint8Array(await zip);
    clearInterval(ticking);
    lap('start');
    bar.slide('unpack', times.unpack);
    await painted();
    pyodide.FS.writeFile('/py-words.zip', bytes);
    await pyodide.runPythonAsync(UNPACK);
    pyodide.FS.mkdirTree(STATE + '/config');
    restore();
    await openCache();
    lap('unpack');
    status('Reading the dictionary…  (' + seconds() + ')');
    const fresh = last.size !== bytes.length;
    took.size = bytes.length;
    took.readFresh = last.readFresh;
    bar.slide('read', fresh ? last.readFresh || Math.max(times.read,
                                                         GUESS.read)
                            : times.read);
    await painted();                    // (to show the message and the bar)
    pyodide.globals.set('CACHE_FOLDER', cached ? CACHE : '');
    await pyodide.runPythonAsync(BOOT);
    call = pyodide.globals.get('call');
    lap('read');
    if (fresh) took.readFresh = took.read;
    try {
      localStorage.setItem(TIMING, JSON.stringify(took));
    } catch (e) {}                      // (no localStorage: guesses)
    console.log('py-words ready in ' + seconds());
    request('GET', '/', location.search.slice(1), '', false);
  } catch (e) {
    clearInterval(ticking);
    status('');
    document.querySelector('.bar')?.remove();
    const p = document.createElement('p');
    p.className = 'error';
    p.textContent = 'py-words could not start: ' + e;
    document.querySelector('.loading').appendChild(p);
    console.error(e);
  }
}

main();
