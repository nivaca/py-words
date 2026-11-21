#!/usr/bin/env python3
"""Corre a la vez las pruebas de py-words: python3 tools/test.py [-j N] [-v]
[NAME ...]

Cada clase de pruebas (tests/test_*.py) corre en un proceso propio, tantos
a la vez como procesadores tenga el computador (-j lo cambia), primero los
archivos más lentos; así, la suite entera tarda más o menos lo que su
clase más lenta y no la suma de todas.  Cada proceso tiene su propia
carpeta de ajustes y su pantalla virtual (tests/isolate.py), y todos
comparten una caché del diccionario, hecha una sola vez antes de empezar.

Los NAME eligen qué correr: un archivo (test_cli), una clase
(test_editor.TranslationTests) o un patrón de ellos (test_gui_*).  Al final
aparecen las clases que fallaron, con su salida, y los totales; -v muestra
además cada clase a medida que termina.  El código de salida es 1 si falló
alguna prueba.  (python3 -m unittest discover -s tests las corre una tras
otra, como antes.)
"""

import argparse
import ast
import fnmatch
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, 'tests')
#  Los archivos que más tardan, que arrancan primero (los demás siguen en
#  orden alfabético)
SLOW = ('test_editor', 'test_tui', 'test_lexicon', 'test_logeion',
        'test_history', 'test_fonts', 'test_languages', 'test_fuzzy',
        'test_cli', 'test_regression')


def classes(path: str) -> list[str]:
    """The classes of tests of the file PATH: those with test methods, or
    whose bases (in the file) have them."""
    with open(path, encoding='utf-8') as f:
        tree = ast.parse(f.read())
    found: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        own = any(isinstance(n, ast.FunctionDef) and
                  n.name.startswith('test') for n in node.body)
        inherited = any(isinstance(b, ast.Name) and b.id in found
                        for b in node.bases)
        if own or inherited:
            found.append(node.name)
    return found


def units(names: list[str]) -> list[str]:
    """What to run, as module.Class, the slowest files first."""
    modules = sorted(os.path.basename(p)[:-3] for p in
                     glob.glob(os.path.join(TESTS, 'test_*.py')))
    modules.sort(key=lambda m: SLOW.index(m) if m in SLOW else len(SLOW))
    out = []
    for module in modules:
        for name in classes(os.path.join(TESTS, module + '.py')):
            unit = f'{module}.{name}'
            if not names or any(fnmatch.fnmatch(unit, n) or
                                fnmatch.fnmatch(module, n) for n in names):
                out.append(unit)
    return out


def run(unit: str, env: dict) -> tuple[str, int, str, float]:
    """Runs UNIT: (unit, exit status, output, seconds)."""
    start = time.time()
    done = subprocess.run([sys.executable, '-m', 'unittest', unit],
                          cwd=TESTS, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True,
                          errors='replace')
    return unit, done.returncode, done.stdout, time.time() - start


def counts(output: str) -> tuple[int, int]:
    """(tests run, tests skipped) of the output of unittest."""
    ran = re.search(r'^Ran (\d+) tests?', output, re.M)
    skipped = re.search(r'skipped=(\d+)', output)
    return (int(ran.group(1)) if ran else 0,
            int(skipped.group(1)) if skipped else 0)


def warm(env: dict):
    """Makes the cache of the dictionary once, before the tests (so that
    they do not all read the XML at once)."""
    subprocess.run([sys.executable, '-c',
                    'import isolate; from lexicon import Lexicon; '
                    f'Lexicon.load({os.path.join(ROOT, "data")!r})'],
                   cwd=TESTS, env={**env, 'PYTHONPATH': ROOT},
                   check=False)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='tools/test.py',
        description='Run the tests of py-words, each class of tests in a '
                    'process of its own, at once.')
    parser.add_argument('names', nargs='*', metavar='NAME',
                        help='files, classes or patterns to run (default: '
                             'all)')
    parser.add_argument('-j', '--jobs', type=int,
                        default=os.cpu_count() or 2,
                        help='how many at a time (default: the processors)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show each class as it ends')
    args = parser.parse_args(argv)
    todo = units(args.names)
    if not todo:
        sys.exit('tools/test.py: no tests match ' + ' '.join(args.names))
    cache = tempfile.mkdtemp(prefix='py-words-test-cache-')
    env = {**os.environ, 'PY_WORDS_TEST_CACHE': cache}
    start = time.time()
    failed: list[tuple[str, str]] = []
    total = skipped = 0
    try:
        warm(env)
        with ThreadPoolExecutor(max(1, args.jobs)) as pool:
            jobs = [pool.submit(run, unit, env) for unit in todo]
            for n, job in enumerate(as_completed(jobs), 1):
                unit, status, output, seconds = job.result()
                ran, skip = counts(output)
                total += ran
                skipped += skip
                if status != 0:
                    failed.append((unit, output))
                if args.verbose or status != 0:
                    mark = 'ok' if status == 0 else 'FAILED'
                    print(f'[{n}/{len(todo)}] {unit}: {ran} tests, '
                          f'{seconds:.1f}s, {mark}', flush=True)
    finally:
        shutil.rmtree(cache, ignore_errors=True)
    for unit, output in failed:
        print(f'\n{"=" * 70}\n{unit}\n{"=" * 70}\n{output.rstrip()}')
    seconds = time.time() - start
    print(f'\nRan {total} tests ({len(todo)} classes) in {seconds:.1f}s'
          + (f', {skipped} skipped' if skipped else '') + ': '
          + (f'FAILED ({len(failed)} classes)' if failed else 'OK'))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
