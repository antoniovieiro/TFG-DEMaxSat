"""Configuracion de pytest: hace importable el paquete `demaxsat_gui`.

Anade la carpeta `gui/` (donde vive este archivo) a sys.path, de modo que los
tests funcionen tanto ejecutando `pytest tests/` desde `gui/` como
`pytest gui/tests/` desde la raiz del repositorio.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
