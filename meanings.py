#!/usr/bin/env python3
"""py-words showing only dictionary forms and meanings:
python3 meanings.py"""

from version import check_python
check_python()          # (before the modules that need it)

from words import meanings

meanings()
