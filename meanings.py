#!/usr/bin/env python3
"""py-words con solo las formas de diccionario y los significados:
python3 meanings.py"""

from version import check_python
check_python()          # (antes de los módulos que lo necesitan)

from words import meanings

meanings()
