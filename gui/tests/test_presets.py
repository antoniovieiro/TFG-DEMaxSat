"""Tests de demaxsat_gui.presets: las 6 configuraciones del paper.

Objetivo: evitar errores silenciosos en los valores extraidos del paper.
"""

import pytest

from demaxsat_gui import instance
from demaxsat_gui.presets import paper_values

# Tabla de la pagina 7 del paper: (categoria, timeout) -> (NP, LSS, HSCOPE).
EXPECTED = {
    (instance.LOW, 60): (30, 0.05, "all"),
    (instance.LOW, 300): (30, 0.10, "all"),
    (instance.MEDIUM, 60): (5, 0.025, "all"),
    (instance.MEDIUM, 300): (10, 0.10, "better_than_mean"),
    (instance.HIGH, 60): (5, 0.025, "better_than_mean"),
    (instance.HIGH, 300): (5, 0.075, "better_than_mean"),
}


@pytest.mark.parametrize("key, expected", list(EXPECTED.items()))
def test_paper_values(key, expected):
    category, timeout = key
    np_, lss, hscope = expected
    values = paper_values(category, timeout)

    # Seleccionados segun dificultad/timeout.
    assert values["pop"] == np_
    assert values["lss"] == lss
    assert values["hscope"] == hscope

    # Fijos en todos los experimentos del paper.
    assert values["cr"] == 0.4
    assert values["f"] == 0.6
    assert values["rw"] == 0.5

    # Ajustes de ejecucion del modo Paper.
    assert values["gens"] == -1
    assert values["maxlss"] == -1

    # seed NO se fija en el preset (queda editable).
    assert "seed" not in values


def test_all_six_combinations_present():
    assert len(EXPECTED) == 6


def test_invalid_timeout_raises():
    with pytest.raises(ValueError):
        paper_values(instance.LOW, 120)


def test_invalid_category_raises():
    with pytest.raises(ValueError):
        paper_values(instance.INVALID, 60)
