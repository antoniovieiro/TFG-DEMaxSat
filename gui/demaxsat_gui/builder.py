"""Localizacion y compilacion del binario `demaxsat`.

La GUI no toca el codigo C: solo busca el binario ya compilado y, si no existe,
permite invocar `make` (el mismo que usaria el usuario por consola).
"""

import os
from pathlib import Path
from typing import Optional

# Nombre del binario producido por el Makefile (variable MAIN).
BINARY_NAME = "demaxsat"


def repo_root() -> Path:
    """Raiz del repositorio: el padre de la carpeta gui/.

    Estructura esperada: <repo>/gui/demaxsat_gui/builder.py
    """
    return Path(__file__).resolve().parents[2]


def find_binary() -> Optional[Path]:
    """Devuelve la ruta del binario `demaxsat` si existe y es ejecutable,
    o None en caso contrario."""
    candidate = repo_root() / BINARY_NAME
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate
    return None


def has_makefile() -> bool:
    return (repo_root() / "Makefile").is_file()
