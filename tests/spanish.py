"""Una carpeta de datos para las pruebas de la elección de idioma: los
archivos de datos del programa (enlazados, o copiados donde no se pueden
hacer enlaces), con un archivo pequeño de significados en español
(languages/es.xml)."""

import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

SPANISH = '''<?xml version="1.0" encoding="UTF-8"?>
<language code="es" name="Spanish" native="Español">
  <meaning builtin="esse">ser; existir;</meaning>
</language>
'''


def datadir(folder: str) -> str:
    """Makes the data folder in FOLDER; returns it."""
    for name in os.listdir(DATA):
        source = os.path.join(DATA, name)
        if os.path.isfile(source):
            try:
                os.symlink(source, os.path.join(folder, name))
            except OSError:
                shutil.copy(source, folder)
    os.mkdir(os.path.join(folder, 'languages'))
    with open(os.path.join(folder, 'languages', 'es.xml'), 'w',
              encoding='utf-8') as f:
        f.write(SPANISH)
    return folder
