"""Ventana principal de la GUI de DEMaxSAT."""

from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import Qt, QProcess
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import builder
from .params import PARAMS, build_args
from .runner import SolverRunner


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DEMaxSAT")
        self.resize(820, 680)

        self._runner = SolverRunner(self)
        self._make_proc: Optional[QProcess] = None
        self._editors: Dict[str, QWidget] = {}
        self._binary: Optional[Path] = builder.find_binary()

        self._build_ui()
        self._connect_runner()
        self._refresh_binary_state()

    # -- construccion de la UI ---------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # Banner de compilacion (visible solo si falta el binario).
        self._banner = QFrame()
        self._banner.setObjectName("banner")
        self._banner.setStyleSheet(
            "#banner { background: #fff3cd; border: 1px solid #ffe69c;"
            " border-radius: 6px; }"
        )
        banner_layout = QHBoxLayout(self._banner)
        self._banner_label = QLabel()
        self._banner_label.setWordWrap(True)
        self._compile_btn = QPushButton("Compilar (make)")
        self._compile_btn.clicked.connect(self._on_compile)
        banner_layout.addWidget(self._banner_label, 1)
        banner_layout.addWidget(self._compile_btn, 0, Qt.AlignmentFlag.AlignRight)
        root.addWidget(self._banner)

        # Selector de archivo .wcnf.
        file_box = QGroupBox("Instancia (.wcnf)")
        file_layout = QHBoxLayout(file_box)
        self._file_edit = QLineEdit()
        self._file_edit.setPlaceholderText("Selecciona un archivo .wcnf...")
        self._file_edit.textChanged.connect(self._update_run_enabled)
        browse_btn = QPushButton("Examinar...")
        browse_btn.clicked.connect(self._on_browse)
        file_layout.addWidget(self._file_edit, 1)
        file_layout.addWidget(browse_btn, 0)
        root.addWidget(file_box)

        # Formulario de parametros.
        params_box = QGroupBox("Parametros")
        form = QFormLayout(params_box)
        for p in PARAMS:
            editor = self._make_editor(p)
            editor.setToolTip(p.help)
            label = QLabel(p.label)
            label.setToolTip(p.help)
            self._editors[p.name] = editor
            form.addRow(label, editor)
        reset_btn = QPushButton("Restablecer valores por defecto")
        reset_btn.clicked.connect(self._reset_defaults)
        form.addRow("", reset_btn)
        root.addWidget(params_box)

        # Botones de ejecucion.
        controls = QHBoxLayout()
        self._run_btn = QPushButton("Ejecutar")
        self._run_btn.clicked.connect(self._on_run)
        self._stop_btn = QPushButton("Parar")
        self._stop_btn.clicked.connect(self._runner.stop)
        self._stop_btn.setEnabled(False)
        self._best_label = QLabel("Mejor coste: -")
        self._best_label.setStyleSheet("font-weight: bold;")
        controls.addWidget(self._run_btn)
        controls.addWidget(self._stop_btn)
        controls.addStretch(1)
        controls.addWidget(self._best_label)
        root.addLayout(controls)

        # Consola de salida.
        out_box = QGroupBox("Salida")
        out_layout = QVBoxLayout(out_box)
        self._console = QPlainTextEdit()
        self._console.setReadOnly(True)
        self._console.setFont(QFont("Menlo", 11))
        self._console.setMaximumBlockCount(20000)
        out_layout.addWidget(self._console)
        root.addWidget(out_box, 1)

        # Panel de resultado final (asignacion v).
        result_box = QGroupBox("Solucion final")
        result_layout = QHBoxLayout(result_box)
        self._assignment_edit = QLineEdit()
        self._assignment_edit.setReadOnly(True)
        self._assignment_edit.setPlaceholderText(
            "La asignacion aparece al terminar o al pulsar Parar."
        )
        self._copy_btn = QPushButton("Copiar")
        self._copy_btn.clicked.connect(self._on_copy_assignment)
        self._copy_btn.setEnabled(False)
        result_layout.addWidget(self._assignment_edit, 1)
        result_layout.addWidget(self._copy_btn, 0)
        root.addWidget(result_box)

        # Barra de estado.
        self._status = QLabel()
        self._status.setStyleSheet("color: #555;")
        root.addWidget(self._status)

    def _make_editor(self, p) -> QWidget:
        if p.kind == "int":
            w = QSpinBox()
            if p.minimum is not None:
                w.setMinimum(int(p.minimum))
            if p.maximum is not None:
                w.setMaximum(int(p.maximum))
            if p.step:
                w.setSingleStep(int(p.step))
            w.setValue(int(p.default))
            return w
        if p.kind == "float":
            w = QDoubleSpinBox()
            w.setDecimals(p.decimals)
            if p.minimum is not None:
                w.setMinimum(float(p.minimum))
            if p.maximum is not None:
                w.setMaximum(float(p.maximum))
            if p.step:
                w.setSingleStep(float(p.step))
            w.setValue(float(p.default))
            return w
        if p.kind == "choice":
            w = QComboBox()
            w.addItems(p.choices)
            w.setCurrentIndex(int(p.default))
            return w
        raise ValueError("Tipo de parametro desconocido: %s" % p.kind)

    # -- estado del binario -------------------------------------------------

    def _connect_runner(self) -> None:
        self._runner.output_line.connect(self._console.appendPlainText)
        self._runner.best_cost.connect(self._on_best_cost)
        self._runner.final_assignment.connect(self._on_final_assignment)
        self._runner.started.connect(self._on_started)
        self._runner.finished.connect(self._on_finished)
        self._runner.error.connect(self._on_runner_error)

    def _refresh_binary_state(self) -> None:
        self._binary = builder.find_binary()
        if self._binary is not None:
            self._banner.hide()
            self._set_status("Binario: %s" % self._binary)
        else:
            self._banner.show()
            if builder.has_makefile():
                self._banner_label.setText(
                    "No se encontro el binario 'demaxsat'. Pulsa 'Compilar' para "
                    "ejecutar 'make' en la raiz del proyecto."
                )
                self._compile_btn.setEnabled(True)
            else:
                self._banner_label.setText(
                    "No se encontro el binario 'demaxsat' ni el Makefile. "
                    "Compila el solver manualmente."
                )
                self._compile_btn.setEnabled(False)
            self._set_status("Binario no encontrado.")
        self._update_run_enabled()

    def _update_run_enabled(self) -> None:
        ready = (
            self._binary is not None
            and bool(self._file_edit.text().strip())
            and not self._runner.is_running()
            and self._make_proc is None
        )
        self._run_btn.setEnabled(ready)

    # -- acciones -----------------------------------------------------------

    def _on_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecciona una instancia", "",
            "Instancias WCNF (*.wcnf);;Todos los archivos (*)",
        )
        if path:
            self._file_edit.setText(path)

    def _reset_defaults(self) -> None:
        for p in PARAMS:
            editor = self._editors[p.name]
            if isinstance(editor, QSpinBox):
                editor.setValue(int(p.default))
            elif isinstance(editor, QDoubleSpinBox):
                editor.setValue(float(p.default))
            elif isinstance(editor, QComboBox):
                editor.setCurrentIndex(int(p.default))

    def _collect_values(self) -> Dict[str, object]:
        values: Dict[str, object] = {}
        for p in PARAMS:
            editor = self._editors[p.name]
            if isinstance(editor, QSpinBox):
                values[p.name] = editor.value()
            elif isinstance(editor, QDoubleSpinBox):
                values[p.name] = editor.value()
            elif isinstance(editor, QComboBox):
                values[p.name] = editor.currentText()
        return values

    def _on_run(self) -> None:
        if self._binary is None:
            return
        wcnf = self._file_edit.text().strip()
        if not Path(wcnf).is_file():
            QMessageBox.warning(
                self, "Archivo no valido",
                "El archivo seleccionado no existe:\n%s" % wcnf,
            )
            return
        args = build_args(self._collect_values())
        self._console.clear()
        self._best_label.setText("Mejor coste: -")
        self._assignment_edit.clear()
        self._copy_btn.setEnabled(False)
        self._console.appendPlainText(
            "$ %s %s %s" % (self._binary, " ".join(args), wcnf)
        )
        self._runner.start(str(self._binary), wcnf, args)

    def _on_compile(self) -> None:
        if self._make_proc is not None:
            return
        self._console.clear()
        self._console.appendPlainText("$ make")
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.setWorkingDirectory(str(builder.repo_root()))
        proc.setProgram("make")
        proc.readyReadStandardOutput.connect(
            lambda: self._console.appendPlainText(
                bytes(proc.readAllStandardOutput())
                .decode("utf-8", errors="replace")
                .rstrip("\n")
            )
        )
        proc.finished.connect(self._on_make_finished)
        proc.errorOccurred.connect(
            lambda _e: self._console.appendPlainText(
                "Error al ejecutar make: %s" % proc.errorString()
            )
        )
        self._make_proc = proc
        self._compile_btn.setEnabled(False)
        self._set_status("Compilando...")
        proc.start()

    def _on_copy_assignment(self) -> None:
        QGuiApplication.clipboard().setText(self._assignment_edit.text())
        self._set_status("Asignacion copiada al portapapeles.")

    # -- callbacks del runner ----------------------------------------------

    def _on_started(self) -> None:
        self._stop_btn.setEnabled(True)
        self._update_run_enabled()
        self._set_status("Ejecutando...")

    def _on_best_cost(self, cost: int) -> None:
        self._best_label.setText("Mejor coste: %d" % cost)

    def _on_final_assignment(self, assignment: str) -> None:
        self._assignment_edit.setText(assignment)
        self._copy_btn.setEnabled(bool(assignment))

    def _on_finished(self, exit_code: int) -> None:
        self._stop_btn.setEnabled(False)
        self._update_run_enabled()
        self._set_status("Terminado (codigo de salida %d)." % exit_code)

    def _on_runner_error(self, message: str) -> None:
        self._stop_btn.setEnabled(False)
        self._update_run_enabled()
        self._console.appendPlainText("Error al lanzar el solver: %s" % message)
        self._set_status("Error al lanzar el solver.")

    def _on_make_finished(self, exit_code: int, _status) -> None:
        self._make_proc = None
        if exit_code == 0:
            self._set_status("Compilacion correcta.")
        else:
            self._console.appendPlainText(
                "\n'make' fallo (codigo %d). Si estas en macOS puede deberse a "
                "argp (Homebrew): compila manualmente con los flags adecuados."
                % exit_code
            )
            self._set_status("La compilacion fallo.")
        self._refresh_binary_state()

    # -- util ---------------------------------------------------------------

    def _set_status(self, text: str) -> None:
        self._status.setText(text)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._runner.kill()
        if self._make_proc is not None:
            self._make_proc.kill()
        super().closeEvent(event)
