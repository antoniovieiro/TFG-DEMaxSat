"""Wrapper sobre QProcess para lanzar y controlar el binario `demaxsat`.

Se usa QProcess (en lugar de subprocess + hilos) porque se integra de forma
natural en el bucle de eventos de Qt y, en sistemas UNIX, `terminate()` envia
SIGTERM al proceso, que es justo lo que el solver necesita para imprimir su
solucion final (ver DESolver/sigterm_handler.c).
"""

import re
from typing import List, Optional

from PySide6.QtCore import QObject, QProcess, Signal

# Lineas de salida del solver que nos interesa interpretar (resto se vuelca tal cual):
#   "o <coste>"  -> nuevo mejor coste encontrado
#   "v <asignacion>" -> asignacion final (tras SIGTERM)
#   "s <estado>" -> estado final (p. ej. "s UNKNOWN")
_O_LINE = re.compile(r"^o\s+(-?\d+)\s*$")
_V_LINE = re.compile(r"^v\s+(.*)$")
_S_LINE = re.compile(r"^s\s+(.*)$")


class SolverRunner(QObject):
    """Lanza el binario demaxsat y emite senales con su salida."""

    output_line = Signal(str)        # cada linea de stdout, sin el salto final
    best_cost = Signal(int)          # nuevo mejor coste (lineas "o N")
    final_assignment = Signal(str)   # asignacion final (linea "v ...")
    status_line = Signal(str)        # estado final (linea "s ...")
    started = Signal()
    finished = Signal(int)           # codigo de salida
    error = Signal(str)              # fallo al arrancar el proceso

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._proc: Optional[QProcess] = None
        self._buffer = ""

    def is_running(self) -> bool:
        return (
            self._proc is not None
            and self._proc.state() != QProcess.ProcessState.NotRunning
        )

    def start(self, binary: str, wcnf_path: str, args: List[str]) -> None:
        """Arranca `binary <args...> wcnf_path`."""
        if self.is_running():
            return

        self._buffer = ""
        proc = QProcess(self)
        # Unificamos stdout/stderr para no perder mensajes del solver.
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.readyReadStandardOutput.connect(self._on_ready_read)
        proc.started.connect(self.started.emit)
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_error)

        proc.setProgram(binary)
        proc.setArguments([*args, wcnf_path])
        self._proc = proc
        proc.start()

    def stop(self) -> None:
        """Envia SIGTERM (terminate) para que el solver imprima su solucion."""
        if self.is_running():
            self._proc.terminate()

    def kill(self) -> None:
        """Mata el proceso sin esperar (SIGKILL). Uso al cerrar la app."""
        if self.is_running():
            self._proc.kill()

    # -- internos -----------------------------------------------------------

    def _on_ready_read(self) -> None:
        if self._proc is None:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        self._buffer += data
        # Procesamos solo lineas completas; el resto queda en el buffer.
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._emit_line(line)

    def _emit_line(self, line: str) -> None:
        self.output_line.emit(line)
        m = _O_LINE.match(line)
        if m:
            self.best_cost.emit(int(m.group(1)))
            return
        m = _V_LINE.match(line)
        if m:
            self.final_assignment.emit(m.group(1))
            return
        m = _S_LINE.match(line)
        if m:
            self.status_line.emit(m.group(1))

    def _flush_buffer(self) -> None:
        if self._buffer:
            self._emit_line(self._buffer)
            self._buffer = ""

    def _on_finished(self, exit_code: int, _exit_status) -> None:
        self._flush_buffer()
        self.finished.emit(exit_code)
        self._proc = None

    def _on_error(self, _err) -> None:
        if self._proc is not None:
            self.error.emit(self._proc.errorString())
