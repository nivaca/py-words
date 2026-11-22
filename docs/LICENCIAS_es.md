Software libre que usa py-words
===============================

py-words está bajo la Licencia Pública General de GNU, versión 3 o
posterior (GPL-3.0-or-later; véase [LICENCE.txt](../LICENCE.txt)).  Esta
lista da el resto del software libre y de código abierto que usa, con la
licencia de cada uno, con su identificador SPDX cuando lo tiene.  Los
libros y datos de los que viene el diccionario (Lewis y Short, De Miguel,
Echave-Sustaeta, Latham...) no son software; el README los enumera, con
sus licencias, en "Fuentes".

Las licencias se tomaron del archivo de licencia o de los metadatos de
paquete de cada proyecto, en noviembre de 2026.  Si alguno cambia de
licencia, lo que vale es lo que digan sus propios archivos.


1.  Lo que el programa necesita para funcionar
---------------------------------------------

Sin esto py-words no funciona, se use el zip, el RPM, el .deb o una copia del
repositorio. py-words no lo incluye: viene con Python o con el sistema.
(La AppImage y los instaladores sí lo incluyen; véanse las secciones 3 y 4.)

| Software | Para qué lo usa py-words | Licencia |
|---|---|---|
| [Python](https://www.python.org) 3.13 o posterior, con su biblioteca estándar | todo: py-words solo usa la biblioteca estándar, sin otros paquetes de Python | Licencia de la Python Software Foundation, versión 2 (`Python-2.0.1`); algunos módulos de la biblioteca estándar tienen sus propias licencias permisivas (MIT, BSD, Apache-2.0...) |
| [Tcl/Tk](https://www.tcl-lang.org), mediante `tkinter` | la ventana (`words_gui.py`) y el editor del diccionario en una ventana (`words_edit_gui.py`) | licencia de Tcl/Tk (`TCL`), de tipo BSD |
| [ncurses](https://invisible-island.net/ncurses/), mediante `curses` (Linux y macOS) | la pantalla completa de la terminal (`words_tui.py`) y el editor de terminal (`words_edit.py`) | de tipo MIT (`MIT-open-group`) |
| [windows-curses](https://github.com/zephyrproject-rtos/windows-curses) (solo en Windows; se instala aparte) | `curses` en Windows, para esos mismos dos programas | Licencia de la Python Software Foundation; está hecho sobre PDCurses, que es de dominio público |


2.  Código y datos incorporados a py-words
-----------------------------------------

Partes de estos están dentro de py-words, en su código o en `data/`.

| Software | Qué tomó py-words de él | Licencia |
|---|---|---|
| [WORDS](https://github.com/mk270/whitakers-words), de William Whitaker (1936-2010), en la versión en Ada que mantiene mk270 | el punto de partida: los análisis, las flexiones, las formas irregulares y las entradas originales del diccionario | el permiso de Whitaker "for any and all use of program and data" (citado entero en LICENCE.txt) |
| [Collatinus](https://github.com/biblissima/collatinus) 11, de Yves Ouvrard y Philippe Verkerk | las vocales largas de los temas y de las desinencias (de sus modelos de flexión), seis abreviaturas, la forma quaesumus y la idea de algunos trucos | GNU GPL: sus archivos fuente dicen versión 2 o posterior, y el proyecto lo distribuye ahora bajo la versión 3 |
| [py-logeion](https://github.com/nivaca/py-logeion) 0.2.1, de Nicolas Vaughan | el código que consulta Logeion y muestra sus entradas (`logeion_api.py`, `logeion_entry.py`, `logeion_render.py`, `logeion_dom.py`, `logeion_text.py`) | GNU GPL, versión 3 o posterior (`GPL-3.0-or-later`) |


3.  Dentro de la AppImage
------------------------

La AppImage lleva su propio Python, así que contiene copias de lo
siguiente.

| Software | Qué es en la AppImage | Licencia |
|---|---|---|
| Python, compilado por [python-appimage](https://github.com/niess/python-appimage) | el Python 3.13 de la AppImage, con Tcl/Tk y ncurses | Python, bajo la licencia de la Python Software Foundation; la herramienta python-appimage, bajo la GNU GPL, versión 3 (`GPL-3.0`), y su `AppRun` y otros archivos, bajo la licencia MIT |
| Tcl/Tk y ncurses, dentro de ese Python | como en la sección 1 | `TCL`; `MIT-open-group` |
| las descripciones de terminales (terminfo) de ncurses | se copian del sistema al hacer la AppImage, para que su ncurses, más antiguo, pueda leerlas | `MIT-open-group` |
| [appimagetool](https://github.com/AppImage/appimagetool) y el [runtime de AppImage](https://github.com/AppImage/type2-runtime) | la herramienta que hace la AppImage, y el pequeño programa del comienzo que la monta y la ejecuta | licencia MIT (`MIT`) |


4.  Dentro de los instaladores
------------------------------

Los instaladores para Windows, macOS y Linux (`tools/bundle-installer.py`)
también llevan su propio Python, así que contienen copias de lo
siguiente.

| Software | Qué es en los instaladores | Licencia |
|---|---|---|
| Python, compilado por [python-build-standalone](https://github.com/astral-sh/python-build-standalone) | el Python 3.13 de los instaladores, con Tcl/Tk (y ncurses, salvo en Windows) | Python, bajo la licencia de la Python Software Foundation (`Python-2.0.1`); los scripts de compilación de python-build-standalone, bajo la Mozilla Public License 2.0 (`MPL-2.0`) |
| las bibliotecas dentro de ese Python: Tcl/Tk, ncurses y sus descripciones de terminales, OpenSSL, SQLite, zlib, libffi, expat, bzip2, xz, mpdecimal... | lo que necesita la biblioteca estándar de Python | cada una la suya: `TCL`; `MIT-open-group`; OpenSSL, bajo la licencia Apache 2.0 (`Apache-2.0`); SQLite, en el dominio público; las demás, bajo licencias permisivas (`Zlib`, `MIT`, `bzip2-1.0.6`, `0BSD`, `BSD-2-Clause`...) |
| [certifi](https://github.com/certifi/python-certifi) | los certificados raíz para las conexiones con Logeion, cuando no se encuentran los del sistema | Mozilla Public License 2.0 (`MPL-2.0`) |
| [windows-curses](https://github.com/zephyrproject-rtos/windows-curses) (solo Windows) | `curses` en Windows, como en la sección 1 | como en la sección 1 |
| [Inno Setup](https://jrsoftware.org/isinfo.php) (solo Windows) | la herramienta que hace el instalador para Windows, y los programas de instalación y desinstalación que pone en él | Inno Setup License, una licencia permisiva propia (cualquier uso, conservando sus avisos de copyright) |

`pkgbuild` y `productbuild`, que hacen el `.pkg` para macOS, son parte de
las herramientas de línea de órdenes de Xcode, de Apple, y no van en el
paquete; el instalador para Linux es un script de shell y un tar.gz,
hechos con la biblioteca estándar de Python.


5.  El RPM y el .deb
-------------------

El RPM y el .deb instalan solo py-words; lo que necesitan lo ponen Fedora,
Debian o Ubuntu.  El .deb se arma solo con la biblioteca estándar de
Python, así que no necesita herramientas de Debian.

| Software | Para qué | Licencia |
|---|---|---|
| python3 y python3-tkinter (Fedora) | los necesita el RPM, como en la sección 1 | `Python-2.0.1`; Tcl/Tk: `TCL` |
| [hicolor-icon-theme](https://gitlab.freedesktop.org/xdg/default-icon-theme) | lo necesita el RPM: las carpetas de los iconos | GNU GPL, versión 2 o posterior (`GPL-2.0-or-later`) |
| [rpm-build](https://rpm.org) y rpm-sign | hacer el RPM y firmarlo | `GPL-2.0-or-later` |
| [desktop-file-utils](https://www.freedesktop.org/wiki/Software/desktop-file-utils/) | instalar y comprobar las entradas del menú al hacer el RPM | `GPL-2.0-or-later` |
| [GnuPG](https://gnupg.org) | la clave que firma el RPM | GNU GPL, versión 3 o posterior (`GPL-3.0-or-later`), con partes bajo la LGPL y otras licencias libres |
| [copr-cli](https://github.com/fedora-copr/copr) | enviar el RPM a compilar en Copr, de Fedora | `GPL-2.0-or-later` |
| python3 y python3-tk (Debian, Ubuntu) | los necesita el .deb, como en la sección 1 | `Python-2.0.1`; Tcl/Tk: `TCL` |
| hicolor-icon-theme (Debian, Ubuntu) | lo recomienda el .deb: las carpetas de los iconos | `GPL-2.0-or-later` |
| GnuPG | la firma aparte del .deb, con la misma clave | `GPL-3.0-or-later` |


6.  Herramientas con las que se hace py-words
--------------------------------------------

Se usan solo para desarrollar, probar y publicar py-words; ninguna va en
lo que se distribuye.

| Software | Para qué | Licencia |
|---|---|---|
| [Xvfb](https://www.x.org) (X.Org) | una pantalla virtual para las pruebas de las ventanas y para las capturas | licencia MIT y GNU GPL, versión 2 (`MIT AND GPL-2.0-only`) |
| [tmux](https://github.com/tmux/tmux) | ejecutar los programas de terminal fuera de la vista para las capturas | licencia ISC (`ISC`) |
| [ImageMagick](https://imagemagick.org) | tomar, unir y recortar las capturas | licencia de ImageMagick (`ImageMagick`), basada en la Apache License 2.0 |
| [Inkscape](https://inkscape.org) | dibujar los iconos en todos los tamaños a partir de `icons/py-words.svg` | GNU GPL, versión 3 o posterior, para el programa entero (la mayor parte de su código está bajo la versión 2 o posterior) |
| [Pillow](https://python-pillow.org) | armar el icono de Windows (`.ico`) | licencia MIT-CMU (`MIT-CMU`) |
| [Git](https://git-scm.com) | la historia del código | GNU GPL, versión 2 (`GPL-2.0-only`) |
| [GitHub CLI](https://github.com/cli/cli) (`gh`) | publicar las versiones en GitHub | licencia MIT (`MIT`) |
| [tea](https://gitea.com/gitea/tea) | publicar las versiones en Codeberg | licencia MIT (`MIT`) |
| [actions/checkout](https://github.com/actions/checkout) y [actions/setup-python](https://github.com/actions/setup-python) | las pruebas en GitHub con cada envío | licencia MIT (`MIT`) |
| [fuentes DejaVu](https://dejavu-fonts.github.io) | las fuentes de las pruebas de las ventanas en GitHub | licencia de Bitstream Vera, y dominio público para los cambios de DejaVu |

`tools/screenshots.py` usa además un navegador Chrome para la captura de
la página web.  Google Chrome no es software libre; Chromium, bajo la
licencia BSD-3-Clause y otras, funciona igual, y el script lo usa cuando
no está Chrome.


Logeion
-------

Las entradas de [Logeion](https://logeion.uchicago.edu) que muestra
py-words se le piden a ese servicio, de la Universidad de Chicago, por
internet.  Con py-words no se distribuye ningún software ni dato de
Logeion; sus diccionarios (Lewis y Short, Gaffiot, el DMLBS...) están
bajo las condiciones de sus propios editores.
