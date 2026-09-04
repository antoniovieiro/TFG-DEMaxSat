"""Punto de entrada de la GUI de DEMaxSAT.

Uso (desde la carpeta gui/):
    python -m demaxsat_gui.main
"""

import os
import sys
from pathlib import Path


def _ensure_qt_plugin_path() -> None:
    """Apunta Qt a la carpeta de plugins de PySide6.

    Con algunos interpretes de Python (p. ej. el framework de las Command Line
    Tools de Xcode en macOS), Qt busca sus plugins junto al ejecutable en lugar
    de dentro de PySide6 y no encuentra el plugin de plataforma 'cocoa'. Fijar
    estas variables antes de crear la QApplication lo resuelve.
    """
    import PySide6

    plugins = Path(PySide6.__file__).resolve().parent / "Qt" / "plugins"
    if plugins.is_dir():
        os.environ.setdefault("QT_PLUGIN_PATH", str(plugins))
        os.environ.setdefault(
            "QT_QPA_PLATFORM_PLUGIN_PATH", str(plugins / "platforms")
        )


_ensure_qt_plugin_path()

from PySide6.QtWidgets import QApplication  # noqa: E402

from .main_window import MainWindow  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("DEMaxSAT")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
