#!/usr/bin/env python3
"""Harness de transparencia: compara DEMaxSAT por CLI vs por la logica de la GUI.

Objetivo: demostrar que la GUI es un *wrapper transparente* del solver, NO medir
rendimiento. Ejecuta el mismo binario, sobre la misma instancia (mismos bytes,
verificados por hash), con los mismos 9 parametros, seed fija, gens finito y
SIN timeout, por dos vias:

  - CLI    : subprocess directo del binario.
  - Runner : la misma clase `SolverRunner` que usa la GUI (bajo QCoreApplication,
             sin necesidad de plugin de plataforma Qt), reutilizando el mismo
             `build_args()`.

Compara y reporta PASS/FAIL por criterio: argumentos efectivos, codigo de salida,
secuencia de lineas `o`, coste final, asignacion `v` y el `*_gens.log`
(contenido determinista, ignorando el nombre con timestamp).

No forma parte de pytest (requiere el binario compilado). Uso:

    python gui/tools/compare_gui_cli.py <instancia.wcnf[.gz]> \
        [--binary ./demaxsat] [--gens 50] [--seed 1] [--pop 100] ...
"""

import argparse
import gzip
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from glob import glob
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Hacer importable el paquete demaxsat_gui (gui/ es el abuelo de este script).
_GUI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_GUI_DIR))

from demaxsat_gui import builder  # noqa: E402
from demaxsat_gui.params import PARAMS, build_args  # noqa: E402

_O_LINE = re.compile(r"^o\s+(-?\d+)\s*$")
_V_LINE = re.compile(r"^v\s+(.*)$")
_S_LINE = re.compile(r"^s\s+(.*)$")


# --------------------------------------------------------------- utilidades

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _materialize_once(src: Path, dst: Path) -> None:
    """Descomprime (si .gz) o copia `src` a `dst` una sola vez."""
    if src.suffix == ".gz":
        with gzip.open(src, "rb") as fin, open(dst, "wb") as fout:
            shutil.copyfileobj(fin, fout)
    else:
        shutil.copyfile(src, dst)


def _parse_output(text: str) -> Tuple[List[int], Optional[str], Optional[str]]:
    """Extrae (secuencia de `o`, asignacion `v`, estado `s`) de la salida."""
    o_seq: List[int] = []
    v_line: Optional[str] = None
    s_line: Optional[str] = None
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        m = _O_LINE.match(line)
        if m:
            o_seq.append(int(m.group(1)))
            continue
        m = _V_LINE.match(line)
        if m:
            v_line = m.group(1)
            continue
        m = _S_LINE.match(line)
        if m:
            s_line = m.group(1)
    return o_seq, v_line, s_line


def _find_log(directory: Path) -> Optional[Path]:
    logs = sorted(glob(str(directory / "*_gens.log")))
    return Path(logs[0]) if logs else None


# --------------------------------------------------------------- ejecuciones

def run_cli(binary: str, args: List[str], inst: Path) -> dict:
    proc = subprocess.run(
        [binary, *args, str(inst)],
        capture_output=True, text=True,
    )
    o_seq, v_line, s_line = _parse_output(proc.stdout)
    return {
        "argv": [binary, *args, str(inst)],
        "exit": proc.returncode,
        "o_seq": o_seq,
        "v": v_line,
        "s": s_line,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "log": _find_log(inst.parent),
    }


def run_runner(binary: str, args: List[str], inst: Path) -> dict:
    # Import diferido: solo la rama Runner necesita Qt.
    from PySide6.QtCore import QCoreApplication
    from demaxsat_gui.runner import SolverRunner

    app = QCoreApplication.instance() or QCoreApplication([])
    runner = SolverRunner()
    lines: List[str] = []
    captured = {"exit": None, "error": None, "argv": None}

    runner.output_line.connect(lines.append)
    runner.finished.connect(lambda code: captured.__setitem__("exit", code))
    runner.finished.connect(lambda _c: app.quit())
    runner.error.connect(lambda msg: captured.__setitem__("error", msg))
    runner.error.connect(lambda _m: app.quit())

    runner.start(binary, str(inst), args, timeout_secs=None)
    # program()+arguments() efectivos del QProcess (para verificar args).
    if runner._proc is not None:
        captured["argv"] = [runner._proc.program(), *runner._proc.arguments()]
    app.exec()

    text = "\n".join(lines)
    o_seq, v_line, s_line = _parse_output(text)
    return {
        "argv": captured["argv"],
        "exit": captured["exit"],
        "o_seq": o_seq,
        "v": v_line,
        "s": s_line,
        "stdout": text,
        "stderr": "(runner usa MergedChannels: stderr va incluido en stdout)",
        "error": captured["error"],
        "log": _find_log(inst.parent),
    }


# --------------------------------------------------------------- comparacion

def _read_log(path: Optional[Path]) -> Optional[str]:
    if path is None or not path.is_file():
        return None
    return path.read_text()


def compare(cli: dict, gui: dict, args: List[str]) -> Tuple[bool, List[str]]:
    report: List[str] = []
    ok = True

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        ok = ok and cond
        report.append("  [%s] %s%s" % (
            "PASS" if cond else "FAIL", name,
            "" if cond else "  -> " + detail,
        ))

    # 1. Argumentos efectivos (sin la ruta de instancia, que difiere por diseño).
    cli_flags = args
    gui_flags = gui["argv"][1:-1] if gui["argv"] else None
    check("argumentos efectivos (9 flags identicos)",
          gui_flags == cli_flags,
          "cli=%r runner=%r" % (cli_flags, gui_flags))

    # 2. Codigo de salida.
    check("codigo de salida", cli["exit"] == gui["exit"],
          "cli=%r runner=%r" % (cli["exit"], gui["exit"]))

    # 3. Secuencia de lineas `o`.
    check("secuencia de lineas o", cli["o_seq"] == gui["o_seq"],
          "cli=%r runner=%r" % (cli["o_seq"], gui["o_seq"]))

    # 4. Coste final (ultimo `o`).
    cli_cost = cli["o_seq"][-1] if cli["o_seq"] else None
    gui_cost = gui["o_seq"][-1] if gui["o_seq"] else None
    check("coste final", cli_cost == gui_cost,
          "cli=%r runner=%r" % (cli_cost, gui_cost))

    # 5. Asignacion `v`.
    check("asignacion v", cli["v"] == gui["v"],
          "cli=%r runner=%r" % (cli["v"], gui["v"]))

    # 6. `*_gens.log`: presencia + contenido determinista (ignorando el nombre).
    cli_log, gui_log = cli["log"], gui["log"]
    present = cli_log is not None and gui_log is not None
    content_eq = present and _read_log(cli_log) == _read_log(gui_log)
    check("gens.log presente en ambas ramas", present,
          "cli=%r runner=%r" % (cli_log, gui_log))
    check("gens.log contenido determinista identico", content_eq,
          "difiere el contenido CSV (count,best,mean)")

    return ok, report


# --------------------------------------------------------------- main

def _default_values() -> Dict[str, object]:
    vals: Dict[str, object] = {}
    for p in PARAMS:
        vals[p.name] = p.choices[int(p.default)] if p.kind == "choice" else p.default
    return vals


def main() -> int:
    defaults = _default_values()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("instance", help="ruta a la instancia .wcnf o .wcnf.gz (legacy)")
    ap.add_argument("--binary", default=None, help="ruta al binario demaxsat")
    ap.add_argument("--gens", type=int, default=50, help="gens FINITO (default 50)")
    ap.add_argument("--seed", type=int, default=1, help="seed FIJA (default 1)")
    ap.add_argument("--pop", type=int, default=defaults["pop"])
    ap.add_argument("--cr", type=float, default=defaults["cr"])
    ap.add_argument("--f", type=float, default=defaults["f"])
    ap.add_argument("--lss", type=float, default=defaults["lss"])
    ap.add_argument("--rw", type=float, default=defaults["rw"])
    ap.add_argument("--maxlss", type=int, default=defaults["maxlss"])
    ap.add_argument("--hscope", default=defaults["hscope"])
    a = ap.parse_args()

    if a.gens < 0:
        ap.error("--gens debe ser finito (>=0) para una comparacion determinista")

    binary = a.binary or (str(builder.find_binary()) if builder.find_binary() else None)
    if not binary or not Path(binary).is_file():
        print("ERROR: no se encontro el binario demaxsat (usa --binary).")
        return 2

    src = Path(a.instance).expanduser()
    if not src.is_file():
        print("ERROR: instancia no encontrada: %s" % src)
        return 2

    values = {
        "gens": a.gens, "pop": a.pop, "cr": a.cr, "f": a.f, "lss": a.lss,
        "rw": a.rw, "hscope": a.hscope, "maxlss": a.maxlss, "seed": a.seed,
    }
    args = build_args(values)

    with tempfile.TemporaryDirectory(prefix="demaxsat_cmp_") as tmp:
        tmp = Path(tmp)
        canonical = tmp / "canonical.wcnf"
        _materialize_once(src, canonical)

        cli_dir = tmp / "cli"
        run_dir = tmp / "runner"
        cli_dir.mkdir()
        run_dir.mkdir()
        inst_cli = cli_dir / "inst.wcnf"
        inst_run = run_dir / "inst.wcnf"
        shutil.copyfile(canonical, inst_cli)
        shutil.copyfile(canonical, inst_run)

        # Garantia de bytes identicos antes de ejecutar.
        h_cli, h_run = _sha256(inst_cli), _sha256(inst_run)
        if h_cli != h_run:
            print("ERROR: los ficheros de instancia difieren (%s != %s)" % (h_cli, h_run))
            return 2

        print("Binario   : %s" % binary)
        print("Instancia : %s" % src)
        print("SHA-256   : %s (identico en cli/ y runner/)" % h_cli)
        print("Args      : %s" % " ".join(args))
        print("Ejecutando CLI...")
        cli = run_cli(binary, args, inst_cli)
        print("Ejecutando Runner (logica GUI)...")
        gui = run_runner(binary, args, inst_run)

    ok, report = compare(cli, gui, args)
    print("\n=== Comparacion GUI(Runner) vs CLI ===")
    print("\n".join(report))
    print("\nRESULTADO: %s" % ("PASS (wrapper transparente)" if ok else "FAIL"))

    if not ok:
        print("\n--- CLI stdout ---\n%s" % cli["stdout"])
        print("--- CLI stderr ---\n%s" % cli["stderr"])
        print("--- Runner salida (stdout+stderr) ---\n%s" % gui["stdout"])
        if gui.get("error"):
            print("--- Runner error ---\n%s" % gui["error"])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
