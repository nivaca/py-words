# Registro de cambios

Los cambios notables de py-words. Las releases, con el zip, la AppImage
y el RPM firmado, están en
[Codeberg](https://codeberg.org/nivaca/py-words/releases) y
[GitHub](https://github.com/nivaca/py-words/releases); el RPM para
Fedora está también en Copr, en `nivaca/py-words`. El repositorio
empieza en la 2.13 (2026-10-22); las versiones anteriores se resumen al
final, sin fechas, a partir de la lista "Versiones" del README.

## 3.26 — 2026-11-21

- Un manual de usuario en PDF, en español, inglés y latín medieval
  (`docs/MANUAL_es.pdf`, `docs/MANUAL_en.pdf`, `docs/MANUAL_la.pdf`, con
  sus fuentes en LaTeX, que compone `latexmk`): la instalación, los cuatro
  programas, cómo leer los resultados, Logeion, los ajustes, los editores
  y las teclas, con tablas de los códigos, las abreviaturas, las opciones
  y las teclas, y un índice.  El RPM los instala.
- La interfaz puede estar también en latín medieval
  (`data/interface/la.xml`; "Latina" en "Idioma de la interfaz",
  `--interface la`): los menús, botones, mensajes y ayuda.  Los
  significados siguen en inglés o en español.
- `README_la.md`: el README en latín medieval, con capturas en latín
  (`tools/screenshots.py` ahora también las toma).

## 3.25 — 2026-11-21

- `docs/LICENCES.md` y `docs/LICENCIAS_es.md` enumeran el software libre
  que usa py-words, con la licencia de cada uno: con qué funciona
  (Python, Tcl/Tk, ncurses), el código y los datos que incorporó (WORDS,
  Collatinus, py-logeion), lo que llevan o necesitan la AppImage y el
  RPM, y las herramientas con que se hace, se prueba y se publica.  Los
  README y las descripciones remiten a ellos, y el RPM los instala.
- `docs/DESCRIPCIÓN_es.md` ya no dice que el programa nunca necesita
  internet: Logeion sí lo necesita.

## 3.24 — 2026-11-20

- En una pantalla de alta resolución escalada al 200 %, el texto de las
  ventanas sigue la escala aunque fontconfig fije una resolución. Una
  regla de 96 DPI en la configuración de fontconfig del propio usuario
  dejaba el texto a la mitad de su tamaño con el Tk 9 del RPM; ahora las
  ventanas inician fontconfig con la configuración habitual más una
  regla que fija la resolución del escritorio.
- `packaging/build-rpm.sh` copia también el RPM más reciente en `dist/`,
  en lugar de los más viejos que haya allí.
- `docs/DESCRIPCIÓN_es.md` se ciñe a seis secciones (Análisis, Diseño,
  Implementación, Validación, Plataforma y Ambiente), de 4000 caracteres
  como máximo cada una, en tercera persona.

## 3.23 — 2026-11-18

- Cuando Logeion es la fuente, su diccionario es el DMLBS (el Dictionary
  of Medieval Latin from British Sources) mientras no se elija otro, en
  todos los programas; antes eran todos. Un diccionario ya elegido se
  conserva, y "All dictionaries" ("Todos los diccionarios") sigue en la
  lista.
- En la página web, "Search in" ("Buscar en") ofrece py-words o Logeion.

## 3.22 — 2026-11-18

- **La página web también puede mostrar las entradas de Logeion**, como
  ya podían la ventana, la terminal y la línea de órdenes. "Search in"
  ("Buscar en": Local o Logeion) y una lista de los diccionarios de
  Logeion están junto a "Meanings in" ("Significados en"). Cada palabra
  se analiza aquí primero, y su análisis va antes de las entradas de
  Logeion para sus lemas; los enlaces a otras palabras de Logeion las
  buscan en la página.
- Mientras tanto, la otra dirección, el idioma de los significados y la
  búsqueda aproximada quedan en gris, pues Logeion solo busca en latín.
- En un servidor público la elección es de cada visitante y se guarda en
  sus cookies, y a Logeion solo se le preguntan las primeras doce
  palabras de una búsqueda.
- El correo de contacto es ahora nicolasvaughan@proton.me.

## 3.21 — 2026-11-17

- La documentación ya no describe la versión que funcionaba en el
  navegador (Pyodide), que ya no existe: el apartado "Online" del README
  ("En línea" en `README_es.md`) y las descripciones de `docs/` hablan
  solo del servidor, <https://nivaca.pythonanywhere.com/>. El programa
  no cambia.

## 3.20 — 2026-11-14

- Se necesita Python 3.13 o posterior (antes, 3.11): lo dicen la
  verificación de `version.py`, el RPM, las pruebas en GitHub y los
  documentos. La AppImage lleva su propio Python 3.13, y todas las
  versiones de Fedora con soporte tienen uno más reciente.

## 3.19 — 2026-11-14

- La documentación y los comentarios del código están escritos de forma
  más llana, en inglés y en español; el código no cambió. Se corrigen
  datos que ya no valían: ya no hay sitio, la versión en el navegador se
  describe en pasado, y las 366 pruebas se corren con `tools/test.py`.

## 3.18 — 2026-11-13

- Con Logeion, cada palabra muestra primero su análisis, como lo da
  py-words pero sin sus significados (*dixi*: *dico, dicere, dixi,
  dictus*; *dix-ī 1SG.PRF.ACT.IND*), y luego las entradas de Logeion.
  Las entradas iguales salen una vez, con todas sus formas, y la página
  propia de una forma solo se muestra si Lewis y Short la tiene (*arma*,
  no *dixi*).
- La fuente, el diccionario de Logeion y la dirección elegidos por
  última vez se guardan para el próximo arranque de todos los programas
  (`[logeion]` y `[search]` en el archivo de configuración); `--local`,
  `--logeion`, `--dictionary` y `-e` los cambian para una ejecución.
- En el modo interactivo, `~G` cambia entre Local y Logeion y `~D` elige
  el diccionario de Logeion; también sirven en los archivos.
- En una terminal, los resultados más largos que la pantalla se abren en
  el paginador (`less`, o `$PAGER`), y los resultados de la línea de
  órdenes y de `words_tui.py` salen en color (`colours.py`; `NO_COLOR`
  lo desactiva).
- El sitio de `nicolasvaughan.org/py-words/` ya no existe, ni su código
  (`pages/`); el diccionario en línea está en nivaca.pythonanywhere.com.
  El workflow de GitHub solo corre las pruebas.
- `tools/test.py` ejecuta cada clase de pruebas en un proceso propio, en
  cerca de un minuto y medio en lugar de nueve. Las pruebas de la
  terminal esperan las respuestas de los programas en lugar de tiempos
  fijos.

## 3.17 — 2026-11-13

- **Logeion como segunda fuente.** La ventana ("Search in", "Buscar en":
  Local o Logeion), `words_tui.py` (F8) y la línea de órdenes
  (`--logeion`) pueden mostrar, en lugar de las entradas de este
  diccionario, las de Logeion (logeion.uchicago.edu) para los lemas de
  las palabras. py-words analiza primero las palabras, pues Logeion no
  analiza las formas flexionadas. Una lista junto a "Buscar en" (F5 en
  la terminal, `--dictionary` en la línea de órdenes) muestra solo uno
  de sus diccionarios (Lewis & Short, Gaffiot, Georges, Du Cange ...) o
  todos. Necesita internet.
- Mientras tanto, la otra dirección, el idioma de los significados, la
  búsqueda aproximada y el editor del diccionario quedan en gris.
- Ya no se hace el Flatpak, y la versión que funcionaba en el navegador
  ya no existe, ni su código (`pages/index.html`, `pages/app.js`,
  `pages/build.py --browser`).
- Las pruebas de las ventanas se ejecutan en una pantalla virtual propia
  (Xvfb), sin `xvfb-run`.
- Las listas de `words_tui.py` (F5, F6) muestran su título entero.

## 3.16 — 2026-11-13

- El texto seleccionado en los resultados de la ventana se puede leer.
  Se dibujaba con los colores de los resultados (un lema, en el modo
  claro, con el color mismo de la selección) y, donde los resultados no
  tenían el foco, en blanco sobre gris claro. Ahora es blanco sobre el
  color de la selección, en los dos modos.

## 3.15 — 2026-11-13

- La ventana tiene un menú Edit (Editar), con Cut, Copy y Paste (Cortar,
  Copiar y Pegar; Ctrl y X, C, V), para el cuadro de búsqueda y el de
  "Find in results" ("Buscar en los resultados"), o para copiar texto
  seleccionado en los resultados.
- En la terminal, F7 copia todos los resultados tal como son (sin
  cortarlos al ancho de la pantalla), con el programa de portapapeles
  del sistema (wl-copy, xclip, xsel, pbcopy, clip) o, si no lo hay, con
  la propia terminal (OSC 52). Cuando las teclas no caben en la última
  línea, como en 80 columnas, se omiten las que van entre F5 y F10, para
  que siempre se vean F1 y F10.
- El programa es también un Flatpak (`tools/bundle-flatpak.py`,
  `release.py --flatpak`), adjunto solo a las releases de 3.15 y 3.16.
  En el Flatpak el diccionario no se puede editar, y el programa lo dice.
- La versión que funcionaba en el navegador (Pyodide) ya no se publica:
  su dirección lleva también al servidor.

## 3.14 — 2026-11-13

- **La interfaz de terminal arranca en la AppImage.** El Python de la
  AppImage no podía leer cómo se describen la mayoría de las terminales
  (las de 256 colores, como en Fedora y en Debian 12 y posteriores), y
  el `tui` se detenía en seguida con "setupterm: could not find
  terminal". Ahora la AppImage lleva esas descripciones en una forma que
  su ncurses puede leer.

## 3.13 — 2026-11-13

- Cada entrada se muestra una vez por palabra, con todas sus formas
  debajo. Las formas de un verbo y las de sus participios salían bajo
  dos copias de la entrada (*concito*: *concio* y *concieo* dos veces
  cada una), y lo mismo las entradas de WORDS que se muestran igual:
  *qui* tiene una por género y número (*quae* mostraba cada pronombre
  hasta tres veces), y una forma irregular, una por caso (*eadem*).

## 3.12 — 2026-11-13

- Las entradas de una misma palabra que tienen las mismas formas, como
  una palabra de WORDS y su sentido medieval de Latham (*subsisto*,
  *cura*), muestran esas formas una vez, tras la última de ellas, como
  hacía WORDS.
- 114 entradas mostraban en inglés la misma definición de Lewis y Short
  que otra entrada de la misma palabra (*subsisto*, *agmen*), porque la
  3.3 había pasado por alto copias que solo se distinguían por las
  mayúsculas. Ahora solo la tiene la entrada a la que pertenece, y las
  demás vuelven a tener sus propios significados.
- La clave con que se firma el RPM queda fijada en
  `packaging/build-rpm.sh`, que firma solo con ella y, si falta, explica
  cómo importarla; `release.py --rpm` la busca antes que nada. Al día
  siguiente la reemplazó una clave nueva,
  `8187 0643 CA22 1AF9 0C30 554E BE68 32CD 3599 4948` (ed25519, válida
  hasta 2029), cuya clave pública está en
  `packaging/RPM-GPG-KEY-py-words`.

## 3.11 — 2026-11-11

- En una pantalla de alta resolución con el escritorio escalado (al
  200 % en Plasma, por ejemplo), las ventanas de la AppImage salían muy
  pequeñas: su Tk 8.6 no hacía caso de la escala que el escritorio da a
  los programas X11 (`Xft.dpi`). Ahora las ventanas la leen, y su texto
  y su tamaño crecen con ella. El RPM, con el Tk 9 del sistema, ya
  estaba bien.
- `tools/release.py --rpm` envía también el RPM fuente firmado a Copr
  (`--no-copr` lo omite), y los RPM se firman siempre. Los README dan
  primero la instalación desde Copr.

## 3.10 — 2026-11-11

- **Un paquete RPM para Fedora** (`packaging/`), firmado y adjunto a las
  releases con su clave pública. Instala el programa en
  `/usr/share/py-words`, la orden `py-words` (con las órdenes de la
  AppImage), los cuatro accesos del menú y el icono. `build-rpm.sh
  --sign` lo firma y se niega a empaquetar una clave privada, y
  `tools/release.py --rpm` lo construye y lo adjunta.
- La página web termina con el logo de la Universidad de los Andes
  (Facultad de Artes y Humanidades) y su aviso legal, como lo pidió la
  universidad.
- La antigua dirección del sitio, <https://nicolasvaughan.org/py-words/>,
  lleva a <https://nivaca.pythonanywhere.com/> con la búsqueda; la
  versión que funciona en el navegador está ahora en `browser/`.

## 3.9 — 2026-11-09

- `words_web.py` puede servir a todos: `public_app()` (la aplicación
  WSGI para un servidor web, como PythonAnywhere) y `--public` guardan
  los ajustes, los idiomas, el modo oscuro y las búsquedas anteriores de
  cada visitante en las cookies de su navegador, y no guardan nada en el
  servidor. Sin cookies, la página sigue el idioma del navegador.

## 3.8 — 2026-11-06

- En la ventana, cambiar el idioma de la interfaz ya no deja las partes
  de la ventana hechas antes atadas a los cambios del aspecto y de las
  fuentes, lo que daba errores tras cada cambio.
- Si el archivo de un idioma de la interfaz está mal, la ventana sigue
  en el idioma en que estaba y dice por qué en la barra de estado. Antes
  seguía en inglés sin decir nada.

## 3.7 — 2026-11-06

- `words_install.py --uninstall` quita en Linux solo los archivos
  `.desktop` y los iconos (`py-words.png` y `.svg`, en todos los tamaños
  instalados, incluso uno que el programa ya no tiene), y nada más.
  `icons/linux/uninstall.sh` quita lo mismo, por sus nombres exactos.
- Los títulos, la página web y los accesos del menú dicen "A Latin
  Dictionary" ("Un diccionario de latín" en español).

## 3.6 — 2026-11-05

- `words_install.py --only-gui` añade solo el acceso de la ventana al
  menú, y quita los otros tres si estaban.
- Los scripts que hacen el zip y la AppImage están ahora en `tools/`:
  `tools/bundle-zip.py` y `tools/bundle-appimage.py`.
- `tools/icons.py` hace todos los iconos de `icons/` a partir de
  `icons/py-words.svg`, con Inkscape y Pillow.

## 3.5 — 2026-11-03

- **Una AppImage para Linux**: un solo archivo, con un Python propio
  (con Tk), que funciona sin instalar nada. Abre la ventana, y un primer
  argumento elige otro programa (`cli`, `tui`, `web`, `edit` ...).
  `bundle-appimage.py` la hace, y un workflow de GitHub la añade a la
  release de cada tag que se sube.
- `bundle-zip.py` escribe el zip en `dist/`, y la AppImage va también
  ahí.
- El diccionario no se puede editar donde no se puede escribir en su
  carpeta de datos, como en la AppImage: "Edit dictionary…" ("Editar
  diccionario…") aparece en gris, y los editores dicen por qué en vez de
  fallar al guardar.
- La versión se muestra en el título de la ventana y de los editores, y
  al empezar el modo interactivo.
- `tools/release.py` hace una release en GitHub y en Codeberg.

## 3.4 — 2026-10-31

- Con las grafías medievales, la e de una palabra que se encuentra
  puede ser también ae u oe: *queruntur* da *queror*, y también
  *quaeruntur*, de *quaero*. Solo se añaden entradas frecuentes, y no
  para una e final, así que *esse*, *bene* o *ille* no dan nada más.
- Las ventanas se ven mejor. En Linux, el modo claro tiene los colores
  de la página web en lugar del tema gris sencillo de Tk; en los dos
  modos "Look up" ("Buscar") va en el color de acento, las casillas
  tienen una marca de verificación y los resultados tienen más espacio.
- La ventana busca las palabras que se le dan en su línea de órdenes
  (`python3 words_gui.py perspicio`; con `-e`, hacia el latín).
- Algunas palabras mostraban dos veces el mismo significado (*diligo*,
  *abnego*, *os*): una definición de De Miguel o de Lewis y Short se
  había dado a todas las entradas con las mismas raíces. Ahora solo la
  tiene la entrada a la que pertenece, y 1935 significados en español y
  1040 en inglés vuelven a ser los de sus propias entradas. El README
  pone esta corrección en la 3.3, pues se hizo antes de que cambiara el
  número de versión.
- En la búsqueda hacia el latín, los significados ya no muestran las
  barras (|) con que WORDS marca los sentidos adicionales de una
  palabra.
- También en la página web el commit de "About" ("Acerca de") es un
  enlace. El README presenta krunner-py-words, que pone el diccionario
  en KRunner.

## 3.3 — 2026-10-26

- "About" ("Acerca de"; en la ventana, la terminal, la página web, `~A`
  y `--version`) da el commit del que viene el programa, como la
  dirección de ese commit en GitHub; en la ventana es un enlace con el
  hash corto. El zip y el sitio web lo llevan en un archivo `COMMIT`.
- El menú Help (Ayuda) de la ventana tiene "Web page" ("Sitio web"),
  que abre la página del proyecto en GitHub.
- Los documentos, "Acerca de", la ayuda y `--help` dicen que WORDS fue
  el punto de partida, que su código y sus datos se rediseñaron, y que
  py-words incluye ahora un nuevo diccionario inglés (Lewis y Short) y
  dos nuevos diccionarios españoles (Echave-Sustaeta y De Miguel).

## 3.2 — 2026-10-25

Este tag incluye también la 3.1, que no tuvo tag propio.

### Nuevo

- **El diccionario tiene 93 370 entradas.** Lewis y Short aportó 6653
  palabras raras y 1783 nombres; el *Nuevo diccionario latino-español
  etimológico* (1867) de R. de Miguel, 25 149 palabras y nombres, y
  Latham, 16 995 palabras medievales más.
- Los significados en español vienen de De Miguel (50 678, sus
  definiciones enteras, con su ortografía) y de Echave-Sustaeta (168)
  donde tienen la palabra; los otros 42 515 son traducciones. Los
  resultados nombran la fuente tras el significado: "(De Miguel)".
- Los significados en inglés vienen de Lewis y Short (31 755) donde él
  tiene la palabra y el sentido; los demás son los de WORDS. Los
  resultados dicen "(Lewis and Short)" tras ellos.
- En la 3.1, la versión en línea arranca con una barra de carga, y su
  zip es más pequeño (3,2 MB en lugar de 4,4): los significados en
  francés, alemán, catalán y gallego se descargaban solo cuando se
  elegía su idioma.

### Cambios

- Solo quedan el inglés y el español como idiomas de los significados;
  se quitaron los significados en francés, alemán, catalán y gallego,
  tomados de Collatinus.
- Los ajustes son 18 en lugar de 33, en tres grupos: algunos se
  volvieron uno, otros están ahora siempre activos, otros recibieron
  nombres más claros. Se fueron `show_examples`, `unknowns_only` y
  `word_list_check`. Los archivos de configuración con los nombres
  antiguos se siguen leyendo.
- Las variables de entorno son ahora `$PY_WORDS_DATADIR`,
  `$PY_WORDS_CONFIG`, `$PY_WORDS_HISTORY` y `$PY_WORDS_CACHE`; las
  antiguas `$WHITAKERS_WORDS_...` siguen funcionando.
- Iconos nuevos. Las pruebas de las ventanas se ejecutan con Xvfb.

## 3.0 — 2026-10-23

Este tag incluye también la 2.16, que no tuvo tag propio; el nuevo primer
número señala los cambios de la 2.16.

### Nuevo

- **Las vocales largas.** Las formas las muestran en la raíz y en la
  desinencia (*amīc-ōrum*, *am-ābat*, *ros-ā*), a partir de los lemas y
  los modelos de Collatinus, de Yves Ouvrard y Philippe Verkerk. El
  nuevo archivo `data/quantities.xml` tiene las raíces, y las
  desinencias tienen un atributo `long` en `data/inflections.xml`; el
  parámetro `show_long_vowels` las oculta.
- Los significados pueden estar también en francés, alemán, catalán y
  gallego, tomados de los lemas de Collatinus.
- Las grafías medievales se reconocen de un modo más general (*michi*,
  *ecclesie*, *hystorie*), se entiende la prodelisión de est
  (*amatust*, *bonumst*), y dos palabras declinadas juntas
  (*rempublicam*) dan solo las formas que concuerdan. Se añadieron seis
  abreviaturas (*Agr.*, *Kalen.* ...) y la forma *quaesumus*: 44 386
  entradas.
- El programa dice de dónde viene su diccionario (WORDS, Latham,
  Echave-Sustaeta y Collatinus) y bajo qué licencia, en "About" ("Acerca
  de"), en una nueva última sección de la ayuda, "Sources and licence"
  ("Fuentes y licencia"), en el README y en `docs/`. Los diccionarios y
  las personas a quienes Collatinus agradece reciben aquí también el
  agradecimiento.

### Cambios

- **La licencia es ahora la Licencia Pública General de GNU, versión 3
  o posterior** (hasta la 2.15, la licencia MIT), para que py-words
  pueda tomar código y datos de Collatinus.
- Se quitaron los ajustes que escribían los archivos WORD.OUT, WORD.UNK
  y WORD.STA, junto con los archivos. `-o FILE` guarda los resultados en
  un archivo; un archivo de configuración que todavía tenga esos ajustes
  se lee sin quejas.
- El modo oscuro se elige con una luna (☾), que se vuelve un sol (☀)
  mientras la ventana o la página están oscuras, en lugar de la casilla
  "Dark mode" ("Modo oscuro").
- El botón "Usual settings" se llama ahora "Default settings" ("Ajustes
  por defecto").

## 2.15 — 2026-10-22

Este tag incluye también la 2.14.

- El diccionario se comparó con la lista de latín medieval de R. E.
  Latham, y ahora tiene 44 380 entradas (antes, 39 846), todas con sus
  significados en español: 2444 sentidos medievales de palabras que ya
  tenía, 21 significados corregidos, 1140 palabras y categorías
  gramaticales nuevas y 1204 variantes ortográficas, con el código de
  fuente M.
- En la 2.14, el diccionario se comparó con el vocabulario básico
  latín-español de J. Echave-Sustaeta: se corrigieron 321 entradas y se
  añadieron 254, en inglés y en español, con el nuevo código de fuente
  A.
- Una entrada puede tener varias fuentes (`source="O M"`), y los códigos
  las muestran con "+" (`[XXXCO+M]`); los editores del diccionario tienen
  un campo "otras fuentes", y `words_check.py` revisa cada una.
- Los menús de la ventana siguen también el modo oscuro.
- `tools/screenshots.py` hace las imágenes del README.

## 2.13 — 2026-10-22

- Primera versión en este repositorio: py-words, un diccionario
  latín-inglés-latín y latín-español-latín, hecho a partir de WORDS, el
  programa de William Whitaker, con su código y sus datos rediseñados en
  Python. Analiza palabras latinas y encuentra el latín de palabras
  inglesas o españolas, en una ventana (`words_gui.py`), en la línea de
  órdenes (`words.py`), a pantalla completa en la terminal
  (`words_tui.py`) y en un navegador web (`words_web.py`), con dos
  editores del diccionario.
- Los textos en español de los programas y del README tratan al usuario
  de usted, y no de tú.

## 1.0 a 2.12 — antes del 2026-10-22

Estas versiones son anteriores al repositorio y no tienen fechas.

- 2.12: la ventana es más fácil de leer: la palabra buscada va más
  grande, la forma de diccionario en negrita, y los códigos, las formas
  y las notas en otros colores. Un clic en la primera palabra de una
  entrada, o un doble clic en cualquier palabra, la busca; los códigos y
  los análisis se explican solos bajo el puntero. Tres menús en lugar de
  cuatro botones, un menú del botón derecho y Ctrl y F en los
  resultados. La página web tiene lo mismo, a partir de `layout.py`.
- 2.11: las palabras escritas con marcas de cantidad, breves, diéresis o
  las ligaduras æ y œ se leen bien (*amīcus* se buscaba como "am" y
  "cus").
- 2.10: "Fuzzy search" ("Búsqueda aproximada") es una casilla en la
  pantalla principal de la ventana y de la página web.
- 2.9: la versión en línea arranca más rápido, con la caché del
  diccionario guardada en el navegador (IndexedDB).
- 2.8: una ayuda en cada programa (`guide.py`): "Help" ("Ayuda"), F1,
  `~H` y `--guide`.
- 2.7: **una búsqueda aproximada**: cuando una palabra de tres letras o
  más no encuentra nada, la siguen los resultados de hasta tres grafías
  cercanas ("amicuss" encuentra *amicus*); `--no-fuzzy` la desactiva.
- 2.6: la versión en línea recoge una versión nueva en la visita
  siguiente.
- 2.5: el diccionario está en línea, en
  <https://nicolasvaughan.org/py-words/>, publicado en GitHub Pages con
  cada push.
- 2.4: una primera versión que funciona en el navegador, sin servidor
  (Pyodide).
- 2.3: las capturas de pantalla del README en español muestran los
  programas en español.
- 2.2: modo oscuro para las ventanas y la página web.
- 2.1: **todo el diccionario en español**, traducido del inglés, y la
  interfaz en español (`data/interface/es.xml`). Los editores editan
  también los significados en otro idioma. `README_es.md`.
- 2.0: los significados pueden estar en otros idiomas además del
  inglés, un archivo por idioma en `data/languages/`; cada entrada,
  forma irregular y afijo tiene un `id` estable.
- 1.8: `words_web.py`, el diccionario en un navegador web desde un
  pequeño servidor local; el análisis está escrito en Python llano, sin
  las estructuras que conservaba del programa en Ada.
- 1.7: `words_tui.py`, el diccionario a pantalla completa en la
  terminal.
- 1.6: las búsquedas se recuerdan entre sesiones, y las comparten la
  línea de órdenes y la ventana.
- 1.5: un diálogo "Settings…" ("Ajustes…") en la ventana; el parámetro
  `use_glosses`.
- 1.4: los análisis se escriben con las abreviaturas de las Leipzig
  Glossing Rules (`GEN.PL`, `2SG.PRF.ACT.IND`), guardadas en
  `data/gloss.xml`.
- 1.3: formas de diccionario corregidas de los numerales con una sola
  raíz y de los ejemplos ingleses del subjuntivo; más pruebas de
  regresión.
- 1.2: los dos editores del diccionario comparten una sola
  implementación (`editor.py`), y se corrigen tres de sus errores.
- 1.1: los editores del diccionario ya no pierden cambios; los nombres
  de las fuentes se guardan en `data/sources.xml`.
- 1.0: primera versión pública: WORDS, el diccionario latino de William
  Whitaker, en Python, a partir de su versión en Ada, con sus datos en
  XML.
