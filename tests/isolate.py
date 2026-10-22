"""Imported first by every test module: the tests (and the programs they
run) use no cache and an empty settings folder, so that neither the
user's cache nor their config.toml changes the results, and the tests
change neither."""

import atexit
import os
import shutil
import tempfile

os.environ['WHITAKERS_WORDS_CACHE'] = ''
CONFIG = tempfile.mkdtemp(prefix='py-words-config-')
os.environ['WHITAKERS_WORDS_CONFIG'] = CONFIG
atexit.register(shutil.rmtree, CONFIG, ignore_errors=True)
#  (and the history of the searches is the tests' own)
os.environ['WHITAKERS_WORDS_HISTORY'] = os.path.join(CONFIG, 'history')
