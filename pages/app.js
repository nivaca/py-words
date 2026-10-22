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

async function download(name, tries = 3) {
  //  (a download cut off, by the network or the browser, is tried again;
  //  a copy the browser kept is used only if the server says it is
  //  current, so that a new version is seen at once)
  for (let i = 1; ; i++) {
    try {
      const answer = await fetch(name, {cache: 'no-cache'});
      if (!answer.ok) throw new Error('cannot load ' + name + ': ' +
                                      answer.status);
      return await answer.arrayBuffer();
    } catch (e) {
      if (i >= tries) throw e;
      await new Promise(r => setTimeout(r, 500 * i));
    }
  }
}

async function main() {
  try {
    status('Loading Python…');
    const zip = download('py-words.zip');      // (at the same time)
    zip.catch(() => {});                // (its error is reported below)
    await loadScript(PYODIDE + 'pyodide.js');
    pyodide = await loadPyodide({indexURL: PYODIDE});
    status('Loading the dictionary…  (' + seconds() + ')');
    pyodide.FS.writeFile('/py-words.zip', new Uint8Array(await zip));
    await pyodide.runPythonAsync(UNPACK);
    pyodide.FS.mkdirTree(STATE + '/config');
    restore();
    await openCache();
    status('Reading the dictionary…  (' + seconds() + ')');
    await new Promise(r => setTimeout(r, 0));  // (to show the message)
    pyodide.globals.set('CACHE_FOLDER', cached ? CACHE : '');
    await pyodide.runPythonAsync(BOOT);
    call = pyodide.globals.get('call');
    console.log('py-words ready in ' + seconds());
    request('GET', '/', location.search.slice(1), '', false);
  } catch (e) {
    status('');
    const p = document.createElement('p');
    p.className = 'error';
    p.textContent = 'py-words could not start: ' + e;
    document.querySelector('.loading').appendChild(p);
    console.error(e);
  }
}

main();
