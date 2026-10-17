# py-words 1.2: descripción

## Análisis

py-words es un diccionario latín-inglés con análisis morfológico. A partir de una palabra latina flexionada (por ejemplo, *amicorum*), identifica la entrada del diccionario a la que pertenece (*amicus, amici*) y la forma gramatical exacta (genitivo plural). También busca equivalentes latinos de palabras inglesas.

El punto de partida fue WORDS, el programa de William Whitaker (1936-2010), en su versión en Ada mantenida en mk270/whitakers-words. Del análisis de ese programa se derivaron los requisitos:

- **Mismos análisis que el original:** conservar los resultados de WORDS, que son su valor lingüístico. Eso incluye las reglas de raíces y desinencias, las formas irregulares, los prefijos, sufijos y enclíticos, las variantes ortográficas, la síncopa, los numerales romanos y los tiempos compuestos.
- **Datos legibles y editables:** sustituir los archivos de texto de columnas fijas del original por un formato estándar que se pueda leer, validar y editar.
- **Uso para cualquier usuario:** ofrecer uso desde la terminal y desde una ventana, editores del diccionario que no exijan conocer el formato interno, y una instalación sencilla sin dependencias externas.
- **Opciones del original:** mantener sus parámetros y modos de desarrollo y sus archivos de salida, y conservar la configuración entre sesiones.

## Diseño

**Arquitectura.** La aplicación se organiza en módulos con una sola responsabilidad cada uno:

- **Modelo de datos:** `model.py` define los códigos gramaticales como enumeraciones y los registros inmutables (entradas, formas, desinencias).
- **Acceso a datos:** `xmldata.py` lee y escribe los archivos XML.
- **Índices en memoria:** `lexicon.py` organiza raíces, desinencias, formas irregulares y afijos en diccionarios de Python, consultados directamente.
- **Análisis:** `analyzer.py` combina raíces y desinencias, reconoce los pronombres *qu-*, los afijos y los tiempos compuestos; `tricks.py` aplica variantes ortográficas, síncopa y numerales romanos.
- **Presentación:** `results.py` ordena y depura los resultados, `forms.py` produce las formas de citación y la gramática en palabras, y `render.py` el texto de salida.
- **Configuración:** `settings.py` y `config.py`.
- **Interfaces:** línea de órdenes (`words.py`), ventana (`words_gui.py`), editores del diccionario en ventana y en terminal, verificador de datos, conversor del formato original e instalador de accesos en el menú del sistema.

**Datos.** Cinco archivos XML, descritos por un esquema XML (`words.xsd`):

- `dictionary.xml`: 39 335 entradas.
- `inflections.xml`: 1 797 desinencias.
- `uniques.xml`: 79 formas irregulares.
- `addons.xml`: 343 prefijos, sufijos y enclíticos.
- `sources.xml`: las 26 fuentes (diccionarios, gramáticas, listas de palabras) que representan los códigos de fuente de las entradas, como el Oxford Latin Dictionary o Du Cange.

Los códigos gramaticales se mantienen como en el original, para que cualquier conocedor de WORDS pueda leer las entradas.

**Rendimiento y configuración.** Para un arranque rápido, los datos leídos se guardan en una caché que se regenera sola cuando cambian los archivos. La configuración del usuario (parámetros, modos, fuentes de las ventanas, carpeta de datos) se guarda en un archivo TOML legible en la carpeta estándar de configuración de cada sistema.

## Implementación

- **Lenguaje y dependencias:** está escrito en Python 3.11 o superior y usa solo la biblioteca estándar, sin paquetes externos. Son 24 archivos, unas 8 000 líneas.
- **Recursos del lenguaje:** clases de datos inmutables con `slots`, anotaciones de tipos, `match`/`case`, f-strings y `tomllib` para la configuración.
- **Interfaces:**
  - La ventana y el editor gráfico usan Tkinter, con fuentes ajustables y acercamiento con Ctrl y +/−.
  - El editor de terminal usa `curses`.
  - La línea de órdenes usa `argparse` y tiene un modo interactivo.
- **Proceso:** el desarrollo tuvo cuatro etapas:
  1. una traducción fiel, línea por línea, del programa en Ada, que sirvió de referencia;
  2. la conversión de los datos a XML con su esquema;
  3. un rediseño completo en Python idiomático;
  4. la incorporación de herramientas: ventana, editores, verificador, caché, configuración e instalador.
- **Distribución:** el código se gestiona con git, en un único repositorio publicado en GitHub (`github.com/nivaca/py-words`) y en Codeberg.

## Validación

- **Comparación con el original:** el rediseño se comparó con la traducción fiel sobre un corpus de 133 671 palabras: todas las raíces del diccionario, formas generadas y las entradas de prueba. El 99,2 % dio resultados idénticos. Cada diferencia restante se examinó una por una; todas resultaron ser cambios deliberados o errores del original corregidos, documentados en el README.
- **Pruebas automáticas:** 124 en total, que se ejecutan con `python3 -m unittest discover -s tests`:
  - **Pruebas unitarias:** del análisis, el léxico, la configuración, la caché, el verificador, el conversor y el instalador.
  - **Pruebas de regresión:** comparan la salida completa del programa con resultados esperados y revisados, entre ellos 735 versos de la *Eneida*.
  - **Pruebas de los editores:** se manejan como lo haría un usuario, en una terminal simulada y en una ventana real.
- **Versiones de Python:** las pruebas se ejecutan en Python 3.11 (la versión mínima) y en 3.14.
- **Verificación visual:** las ventanas se comprobaron también visualmente con capturas de pantalla. Las versiones de Python más antiguas reciben un mensaje claro en lugar de un error.

## Plataforma

- **Sistemas operativos:** Linux (y otros sistemas tipo Unix con menús freedesktop), Windows y macOS.
- **Requisitos:** Python 3.11 o superior con Tkinter, incluido en los instaladores de python.org. En algunas distribuciones de Linux es un paquete aparte, como `python3-tkinter` o `python3-tk`. En Windows, el editor de terminal requiere además el paquete `windows-curses`.
- **Uso local:** es una aplicación de escritorio y de terminal, sin servidor ni conexión a internet.

## Ambiente

**Ambiente de desarrollo:**

- Fedora Linux 44 con escritorio KDE Plasma.
- Python 3.14 para el trabajo diario y Python 3.11 para verificar la compatibilidad mínima.
- Control de versiones con git, con repositorios en GitHub y Codeberg.

**Ambiente de ejecución:**

- No requiere instalación: la carpeta del programa se copia o descomprime y se ejecuta (`python3 words.py`, `python3 words_gui.py`).
- Opcionalmente, `python3 words_install.py` añade accesos al menú de aplicaciones del sistema, con su icono, sin permisos de administrador.
- Los ajustes del usuario se guardan en su carpeta de configuración (`~/.config/py-words/config.toml` en Linux), y la caché en su carpeta de caché.
