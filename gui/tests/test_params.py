"""Tests de demaxsat_gui.params.build_args().

Verifica que valores conocidos se convierten EXACTAMENTE en los flags esperados.
Complementa al harness GUI vs CLI: build_args() bien construido (aqui) +
SolverRunner no altera los args (harness).
"""

from demaxsat_gui import presets
from demaxsat_gui.params import build_args


def test_manual_defaults_exact():
    values = {
        "gens": -1, "pop": 100, "cr": 0.4, "f": 0.6, "lss": 0.01,
        "rw": 0.5, "hscope": "all", "maxlss": 100, "seed": -1,
    }
    assert build_args(values) == [
        "--gens=-1",
        "--pop=100",
        "--cr=0.40",
        "--f=0.60",
        "--lss=0.0100",
        "--rw=0.50",
        "--hscope=all",
        "--maxlss=100",
        "--seed=-1",
    ]


def test_order_follows_params_not_dict():
    # Aunque el dict venga desordenado, el orden de salida sigue PARAMS.
    values = {
        "seed": 7, "hscope": "best", "maxlss": -1, "rw": 0.5, "lss": 0.05,
        "f": 0.6, "cr": 0.4, "pop": 30, "gens": 50,
    }
    args = build_args(values)
    assert args[0] == "--gens=50"
    assert args[-1] == "--seed=7"
    assert args == [
        "--gens=50", "--pop=30", "--cr=0.40", "--f=0.60", "--lss=0.0500",
        "--rw=0.50", "--hscope=best", "--maxlss=-1", "--seed=7",
    ]


def test_paper_preset_values_serialize():
    # Preset del paper (MEDIUM/300): maxlss=-1, hscope=better_than_mean.
    values = dict(presets.paper_values(presets.instance.MEDIUM, 300))
    values["seed"] = -1  # el preset no fija seed; la UI aporta su valor
    args = build_args(values)
    assert "--maxlss=-1" in args
    assert "--hscope=better_than_mean" in args
    assert "--pop=10" in args
    assert "--lss=0.1000" in args
    assert "--cr=0.40" in args and "--f=0.60" in args and "--rw=0.50" in args
    assert "--gens=-1" in args


def test_float_and_negative_serialization():
    values = {"gens": -1, "maxlss": -1, "seed": -5, "cr": 0.4,
              "lss": 0.025, "pop": 5, "f": 0.6, "rw": 0.5, "hscope": "all"}
    args = build_args(values)
    assert "--gens=-1" in args and "--maxlss=-1" in args and "--seed=-5" in args
    assert "--lss=0.0250" in args   # 4 decimales
    assert "--cr=0.40" in args      # 2 decimales
