"""Wrapper sobre QProcess para lanzar y controlar el binario `demaxsat`.

Se usa QProcess (en lugar de subprocess + hilos) porque se integra de forma
natural en el bucle de eventos de Qt y, en sistemas UNIX, `terminate()` envia
SIGTERM al proceso, que es justo lo que el solver necesita para imprimir su
solucion final (ver DESolver/sigterm_handler.c).
"""

import re
from typing import List, Optional

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

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
    timed_out = Signal()             # el timeout vencio y se envio SIGTERM

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._proc: Optional[QProcess] = None
        self._buffer = ""
        self._timeout_secs: Optional[int] = None
        self._timer: Optional[QTimer] = None

    def is_running(self) -> bool:
        return (
            self._proc is not None
            and self._proc.state() != QProcess.ProcessState.NotRunning
        )

    def start(
        self, binary: str, wcnf_path: str, args: List[str],
        timeout_secs: Optional[int] = None,
    ) -> None:
        """Arranca `binary <args...> wcnf_path`.

        Si `timeout_secs` no es None, el conteo NO empieza aqui: arranca cuando
        QProcess emite `started`, para medir el tiempo efectivo de ejecucion.
        """
        if self.is_running():
            return

        self._buffer = ""
        self._timeout_secs = timeout_secs
        proc = QProcess(self)
        # Unificamos stdout/stderr para no perder mensajes del solver.
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.readyReadStandardOutput.connect(self._on_ready_read)
        proc.started.connect(self._on_started)
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_error)

        proc.setProgram(binary)
        proc.setArguments([*args, wcnf_path])
        self._proc = proc
        proc.start()

    def stop(self) -> None:
        """Envia SIGTERM (terminate) para que el solver imprima su solucion."""
        self._cancel_timer()
        if self.is_running():
            self._proc.terminate()

    def kill(self) -> None:
        """Mata el proceso sin esperar (SIGKILL). Uso al cerrar la app."""
        self._cancel_timer()
        if self.is_running():
            self._proc.kill()

    # -- internos -----------------------------------------------------------

    def _on_started(self) -> None:
        # El timeout se cuenta desde que el proceso arranca realmente.
        if self._timeout_secs is not None and self._timeout_secs > 0:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._on_timeout)
            timer.start(int(self._timeout_secs * 1000))
            self._timer = timer
        self.started.emit()

    def _on_timeout(self) -> None:
        self.timed_out.emit()
        self.stop()  # SIGTERM: el solver imprime su mejor solucion y termina

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def _drain_stdout(self) -> None:
        """Lee lo que quede en stdout y procesa las lineas completas."""
        if self._proc is None:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        self._buffer += data
        # Procesamos solo lineas completas; el fragmento incompleto se conserva.
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._emit_line(line)

    def _on_ready_read(self) -> None:
        self._drain_stdout()

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

    def _on_finished(self, exit_code: int, _exit_status) -> None:
        self._cancel_timer()
        # Consumir todo el stdout pendiente antes de dar por terminado: la
        # senal finished puede llegar antes del ultimo readyReadStandardOutput.
        self._drain_stdout()
        # Procesar tambien el fragmento final que no termina en '\n'
        # (p. ej. una linea "v ..." muy larga sin salto final).
        if self._buffer:
            self._emit_line(self._buffer)
            self._buffer = ""
        self.finished.emit(exit_code)
        self._proc = None

    def _on_error(self, _err) -> None:
        if self._proc is not None:
            self.error.emit(self._proc.errorString())
