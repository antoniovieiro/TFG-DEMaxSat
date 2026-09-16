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
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from . import builder, instance, presets
from .instance import InstanceInfo
from .params import PARAMS, build_args
from .runner import SolverRunner

# Modos de la GUI.
MODE_MANUAL = "manual"
MODE_PAPER_60 = "paper60"
MODE_PAPER_300 = "paper300"
_MODE_BY_INDEX = [MODE_MANUAL, MODE_PAPER_60, MODE_PAPER_300]
_PAPER_TIMEOUT = {MODE_PAPER_60: 60, MODE_PAPER_300: 300}

# Categorias que el modo Paper sabe configurar.
_PAPER_CATEGORIES = (instance.LOW, instance.MEDIUM, instance.HIGH)


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DEMaxSAT")
        self.resize(900, 860)
        self.setMinimumSize(720, 520)

        self._runner = SolverRunner(self)
        self._make_proc: Optional[QProcess] = None
        self._editors: Dict[str, QWidget] = {}
        self._binary: Optional[Path] = builder.find_binary()
        self._mode = MODE_MANUAL
        self._manual_snapshot: Optional[Dict] = None
        self._instance_info: Optional[InstanceInfo] = None

        self._build_ui()
        self._connect_runner()
        self._refresh_binary_state()
        self._refresh_controls_enabled()

    # -- construccion de la UI ---------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        # Splitter vertical: arriba el formulario, abajo la salida/solucion.
        splitter = QSplitter(Qt.Orientation.Vertical)
        top = QWidget()
        root_top = QVBoxLayout(top)
        root_top.setContentsMargins(0, 0, 0, 0)

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
        root_top.addWidget(self._banner)

        # Selector de archivo .wcnf.
        file_box = QGroupBox("Instancia (.wcnf)")
        file_layout = QHBoxLayout(file_box)
        self._file_edit = QLineEdit()
        self._file_edit.setPlaceholderText("Selecciona un archivo .wcnf...")
        self._file_edit.textChanged.connect(self._on_file_changed)
        self._browse_btn = QPushButton("Examinar...")
        self._browse_btn.clicked.connect(self._on_browse)
        # El campo de ruta ocupa el ancho; el boton conserva su tamano natural.
        # Ambos con una altura comoda (no achatados) y alineados verticalmente.
        self._file_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._file_edit.setMinimumWidth(320)
        self._file_edit.setMinimumHeight(30)
        self._browse_btn.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self._browse_btn.setMinimumHeight(30)
        file_layout.addWidget(
            self._file_edit, 1, Qt.AlignmentFlag.AlignVCenter
        )
        file_layout.addWidget(
            self._browse_btn, 0, Qt.AlignmentFlag.AlignVCenter
        )
        root_top.addWidget(file_box)

        # Panel de informacion de la instancia.
        info_box = QGroupBox("Informacion de la instancia")
        info_form = QFormLayout(info_box)
        self._info_vars = QLabel("-")
        self._info_clauses = QLabel("-")
        self._info_d = QLabel("-")
        self._info_category = QLabel("-")
        self._info_format = QLabel("-")
        info_form.addRow("Variables:", self._info_vars)
        info_form.addRow("Clausulas:", self._info_clauses)
        info_form.addRow("Dificultad D = vars x clausulas:", self._info_d)
        info_form.addRow("Categoria:", self._info_category)
        info_form.addRow("Formato:", self._info_format)
        root_top.addWidget(info_box)

        # Selector de modo + nota de dificultad.
        mode_box = QGroupBox("Modo de configuracion")
        mode_layout = QVBoxLayout(mode_box)
        mode_row = QHBoxLayout()
        self._mode_combo = QComboBox()
        self._mode_combo.addItems([
            "Manual",
            "Configuracion segun el paper - 60 s",
            "Configuracion segun el paper - 300 s",
        ])
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(QLabel("Modo:"))
        mode_row.addWidget(self._mode_combo, 1)
        mode_layout.addLayout(mode_row)
        self._difficulty_label = QLabel("")
        self._difficulty_label.setWordWrap(True)
        self._difficulty_label.setStyleSheet("color: #444; font-style: italic;")
        mode_layout.addWidget(self._difficulty_label)
        root_top.addWidget(mode_box)

        # Seccion: parametros del algoritmo.
        algo_box = QGroupBox("Parametros DeMaxSAT")
        algo_form = QFormLayout(algo_box)
        for p in PARAMS:
            if p.group != "algorithm":
                continue
            editor = self._make_editor(p)
            editor.setToolTip(p.help)
            label = QLabel(p.label)
            label.setToolTip(p.help)
            self._editors[p.name] = editor
            algo_form.addRow(label, editor)
        root_top.addWidget(algo_box)

        # Seccion: opciones de ejecucion / avanzadas (maxlss, seed, timeout).
        exec_box = QGroupBox("Opciones de ejecucion / avanzadas")
        exec_form = QFormLayout(exec_box)
        for p in PARAMS:
            if p.group != "execution":
                continue
            editor = self._make_editor(p)
            editor.setToolTip(p.help)
            label = QLabel(p.label)
            label.setToolTip(p.help)
            self._editors[p.name] = editor
            exec_form.addRow(label, editor)
        # Control de timeout.
        timeout_row = QHBoxLayout()
        self._timeout_combo = QComboBox()
        self._timeout_combo.addItems(["Sin limite", "60 s", "300 s", "Personalizado"])
        self._timeout_combo.currentIndexChanged.connect(self._on_timeout_combo_changed)
        self._timeout_spin = QSpinBox()
        self._timeout_spin.setMinimum(1)
        self._timeout_spin.setMaximum(86_400)
        self._timeout_spin.setValue(60)
        self._timeout_spin.setSuffix(" s")
        timeout_row.addWidget(self._timeout_combo, 1)
        timeout_row.addWidget(self._timeout_spin, 0)
        timeout_widget = QWidget()
        timeout_widget.setLayout(timeout_row)
        exec_form.addRow(QLabel("Timeout:"), timeout_widget)
        # Boton de restablecer defaults de Manual.
        self._reset_btn = QPushButton("Restablecer valores por defecto")
        self._reset_btn.clicked.connect(self._reset_defaults)
        exec_form.addRow("", self._reset_btn)
        root_top.addWidget(exec_box)

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
        root_top.addLayout(controls)

        # --- Mitad inferior del splitter: salida + solucion + estado ---
        bottom = QWidget()
        root_bottom = QVBoxLayout(bottom)
        root_bottom.setContentsMargins(0, 0, 0, 0)

        # Consola de salida.
        out_box = QGroupBox("Salida")
        out_layout = QVBoxLayout(out_box)
        self._console = QPlainTextEdit()
        self._console.setReadOnly(True)
        self._console.setFont(QFont("Menlo", 11))
        self._console.setMaximumBlockCount(20000)
        # Altura util desde el inicio para leer varias lineas.
        self._console.setMinimumHeight(180)
        self._console.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        out_layout.addWidget(self._console)
        root_bottom.addWidget(out_box, 1)

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
        root_bottom.addWidget(result_box)

        # Barra de estado.
        self._status = QLabel()
        self._status.setStyleSheet("color: #555;")
        root_bottom.addWidget(self._status)

        # Panel superior dentro de un QScrollArea: si el formulario no cabe,
        # hace scroll en lugar de robar espacio a la consola o recortar controles.
        top_scroll = QScrollArea()
        top_scroll.setWidgetResizable(True)
        top_scroll.setWidget(top)
        top_scroll.setFrameShape(QFrame.Shape.NoFrame)
        top_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        top_scroll.setMinimumHeight(120)

        bottom.setMinimumHeight(240)

        # Ensamblar el splitter: ningun panel colapsable; el panel superior
        # puede encogerse (con scroll) y el crecimiento favorece a la consola.
        splitter.addWidget(top_scroll)
        splitter.addWidget(bottom)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([400, 500])
        root.addWidget(splitter)

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

    # -- lectura/escritura de editores -------------------------------------

    def _get_value(self, name: str):
        w = self._editors[name]
        if isinstance(w, (QSpinBox, QDoubleSpinBox)):
            return w.value()
        if isinstance(w, QComboBox):
            return w.currentText()
        return None

    def _set_value(self, name: str, value) -> None:
        w = self._editors[name]
        if isinstance(w, QSpinBox):
            w.setValue(int(value))
        elif isinstance(w, QDoubleSpinBox):
            w.setValue(float(value))
        elif isinstance(w, QComboBox):
            idx = w.findText(str(value))
            if idx >= 0:
                w.setCurrentIndex(idx)

    def _collect_values(self) -> Dict[str, object]:
        return {name: self._get_value(name) for name in self._editors}

    # -- timeout ------------------------------------------------------------

    def _current_timeout(self) -> Optional[int]:
        idx = self._timeout_combo.currentIndex()
        if idx == 0:
            return None
        if idx == 1:
            return 60
        if idx == 2:
            return 300
        return int(self._timeout_spin.value())

    def _set_timeout(self, secs: Optional[int]) -> None:
        self._timeout_combo.blockSignals(True)
        self._timeout_spin.blockSignals(True)
        if secs is None:
            self._timeout_combo.setCurrentIndex(0)
        elif secs == 60:
            self._timeout_combo.setCurrentIndex(1)
        elif secs == 300:
            self._timeout_combo.setCurrentIndex(2)
        else:
            self._timeout_combo.setCurrentIndex(3)
            self._timeout_spin.setValue(int(secs))
        self._timeout_combo.blockSignals(False)
        self._timeout_spin.blockSignals(False)

    def _on_timeout_combo_changed(self, _index: int) -> None:
        self._refresh_controls_enabled()

    # -- snapshot Manual ----------------------------------------------------

    def _take_snapshot(self) -> Dict:
        snap = self._collect_values()
        snap["__timeout__"] = self._current_timeout()
        return snap

    def _restore_snapshot(self, snap: Dict) -> None:
        for name in self._editors:
            if name in snap:
                self._set_value(name, snap[name])
        self._set_timeout(snap.get("__timeout__"))

    # -- estado del binario / controles ------------------------------------

    def _connect_runner(self) -> None:
        self._runner.output_line.connect(self._console.appendPlainText)
        self._runner.best_cost.connect(self._on_best_cost)
        self._runner.final_assignment.connect(self._on_final_assignment)
        self._runner.started.connect(self._on_started)
        self._runner.finished.connect(self._on_finished)
        self._runner.error.connect(self._on_runner_error)
        self._runner.timed_out.connect(self._on_timed_out)

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

    def _is_busy(self) -> bool:
        return self._runner.is_running() or self._make_proc is not None

    def _can_run(self) -> bool:
        if self._binary is None:
            return False
        info = self._instance_info
        if info is None or not info.supported:
            return False
        if self._mode != MODE_MANUAL and info.category not in _PAPER_CATEGORIES:
            return False
        return True

    def _refresh_controls_enabled(self) -> None:
        busy = self._is_busy()
        running = self._runner.is_running()
        paper = self._mode != MODE_MANUAL

        # Archivo, modo y restablecer: solo cuando no se esta ejecutando.
        self._file_edit.setEnabled(not busy)
        self._browse_btn.setEnabled(not busy)
        self._mode_combo.setEnabled(not busy)
        self._reset_btn.setEnabled(not busy and self._mode == MODE_MANUAL)

        # Editores de parametros.
        for name, w in self._editors.items():
            if busy:
                w.setEnabled(False)
            elif paper and name != "seed":
                w.setEnabled(False)  # bloqueado por la config del paper
            else:
                w.setEnabled(True)

        # Timeout: bloqueado si ejecutando o en modo Paper.
        timeout_editable = not busy and not paper
        self._timeout_combo.setEnabled(timeout_editable)
        self._timeout_spin.setEnabled(
            timeout_editable and self._timeout_combo.currentIndex() == 3
        )

        # Ejecutar / Parar.
        self._run_btn.setEnabled(self._can_run() and not busy)
        self._stop_btn.setEnabled(running)

    # -- instancia ----------------------------------------------------------

    def _on_file_changed(self, _text: str = "") -> None:
        path = self._file_edit.text().strip()
        if path and Path(path).is_file():
            self._instance_info = instance.parse_instance(path)
        else:
            self._instance_info = None
        self._update_instance_panel()
        if self._mode != MODE_MANUAL:
            # Reclasificar y reaplicar el preset a la nueva instancia.
            self._apply_paper_preset(_PAPER_TIMEOUT[self._mode])
        self._refresh_controls_enabled()

    def _update_instance_panel(self) -> None:
        info = self._instance_info
        if info is None:
            for lbl in (self._info_vars, self._info_clauses, self._info_d,
                        self._info_category, self._info_format):
                lbl.setText("-")
            return
        if info.supported:
            self._info_vars.setText(str(info.variables))
            self._info_clauses.setText(str(info.clauses))
            self._info_d.setText(str(info.difficulty_D))
            self._info_category.setText(info.category)
            self._info_format.setText(info.format_label)
        else:
            self._info_vars.setText("-")
            self._info_clauses.setText("-")
            self._info_d.setText("-")
            self._info_category.setText("-")
            self._info_format.setText(
                info.format_label + "  (el solver no puede ejecutar este archivo)"
            )

    # -- modo ---------------------------------------------------------------

    def _on_mode_changed(self, index: int) -> None:
        new_mode = _MODE_BY_INDEX[index]
        old_mode = self._mode
        if new_mode == old_mode:
            return

        entering_paper_from_manual = (
            old_mode == MODE_MANUAL and new_mode != MODE_MANUAL
        )
        if entering_paper_from_manual:
            self._manual_snapshot = self._take_snapshot()

        if new_mode == MODE_MANUAL:
            if self._manual_snapshot is not None:
                self._restore_snapshot(self._manual_snapshot)
                self._manual_snapshot = None
            self._mode = MODE_MANUAL
            self._difficulty_label.setText("")
        else:
            self._mode = new_mode
            # Solo al entrar desde Manual se reinicia la seed a -1;
            # en transiciones Paper<->Paper se conserva la seed escrita.
            if entering_paper_from_manual:
                self._set_value("seed", -1)
            self._apply_paper_preset(_PAPER_TIMEOUT[new_mode])

        self._refresh_controls_enabled()

    def _apply_paper_preset(self, timeout: int) -> None:
        info = self._instance_info
        if info is None or not info.supported or info.category not in _PAPER_CATEGORIES:
            self._set_timeout(timeout)
            self._difficulty_label.setText(
                "Carga una instancia soportada para aplicar la configuracion del "
                "paper (timeout %d s)." % timeout
            )
            return
        values = presets.paper_values(info.category, timeout)
        for name, value in values.items():
            self._set_value(name, value)
        self._set_timeout(timeout)
        self._difficulty_label.setText(
            "Dificultad detectada: %s -> NP=%s, LSS=%s, HSCOPE=%s "
            "(CR=0.4, F=0.6, PRW=0.5, gens=-1, maxlss=-1, timeout=%d s). "
            "seed editable."
            % (info.category, values["pop"], values["lss"], values["hscope"], timeout)
        )

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
            self._set_value(p.name, p.default if p.kind != "choice"
                            else p.choices[int(p.default)])
        self._set_timeout(None)
        self._refresh_controls_enabled()

    def _on_run(self) -> None:
        if not self._can_run():
            return
        wcnf = self._file_edit.text().strip()
        if not Path(wcnf).is_file():
            QMessageBox.warning(
                self, "Archivo no valido",
                "El archivo seleccionado no existe:\n%s" % wcnf,
            )
            return
        args = build_args(self._collect_values())
        timeout = self._current_timeout()
        self._console.clear()
        self._best_label.setText("Mejor coste: -")
        self._assignment_edit.clear()
        self._copy_btn.setEnabled(False)
        self._console.appendPlainText(
            "$ %s %s %s" % (self._binary, " ".join(args), wcnf)
        )
        if timeout is not None:
            self._console.appendPlainText("(timeout: %d s)" % timeout)
        self._runner.start(str(self._binary), wcnf, args, timeout_secs=timeout)

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
        self._set_status("Compilando...")
        self._refresh_controls_enabled()
        proc.start()

    def _on_copy_assignment(self) -> None:
        QGuiApplication.clipboard().setText(self._assignment_edit.text())
        self._set_status("Asignacion copiada al portapapeles.")

    # -- callbacks del runner ----------------------------------------------

    def _on_started(self) -> None:
        self._refresh_controls_enabled()
        self._set_status("Ejecutando...")

    def _on_best_cost(self, cost: int) -> None:
        self._best_label.setText("Mejor coste: %d" % cost)

    def _on_final_assignment(self, assignment: str) -> None:
        self._assignment_edit.setText(assignment)
        self._copy_btn.setEnabled(bool(assignment))

    def _on_timed_out(self) -> None:
        self._console.appendPlainText("(timeout alcanzado: enviando parada)")
        self._set_status("Timeout alcanzado.")

    def _on_finished(self, exit_code: int) -> None:
        self._refresh_controls_enabled()
        self._set_status("Terminado (codigo de salida %d)." % exit_code)

    def _on_runner_error(self, message: str) -> None:
        self._refresh_controls_enabled()
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
        self._refresh_controls_enabled()

    # -- util ---------------------------------------------------------------

    def _set_status(self, text: str) -> None:
        self._status.setText(text)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._runner.kill()
        if self._make_proc is not None:
            self._make_proc.kill()
        super().closeEvent(event)
