"""Tests de demaxsat_gui.instance: classify() y parse_instance().

parse_instance() debe aceptar exactamente lo que aceptaria el parser C actual
(WCNFParser/wcnf_parser.c), ni mas ni menos.
"""

import pytest

from demaxsat_gui import instance
from demaxsat_gui.instance import (
    HIGH,
    INT_MAX,
    INVALID,
    LOW,
    MEDIUM,
    classify,
    parse_instance,
)


# ---------------------------------------------------------------- classify

@pytest.mark.parametrize("D, expected", [
    (0, INVALID),        # el paper define LOW desde D >= 1
    (-5, INVALID),
    (1, LOW),
    (199_999, LOW),
    (200_000, MEDIUM),   # borde exacto -> MEDIUM
    (9_999_999, MEDIUM),
    (10_000_000, HIGH),  # borde exacto -> HIGH
    (50_000_000, HIGH),
])
def test_classify(D, expected):
    assert classify(D) == expected


# ---------------------------------------------------------- parse_instance

def _write(tmp_path, text, name="inst.wcnf"):
    p = tmp_path / name
    p.write_text(text)
    return str(p)


def test_valid_header_with_clauses(tmp_path):
    text = (
        "c comentario\n"
        "p wcnf 3 4 10\n"
        "10 1 -2 0\n"
        "3 -1 2 3 0\n"
        "5 2 -3 0\n"
        "2 1 3 0\n"
    )
    info = parse_instance(_write(tmp_path, text))
    assert info.supported is True
    assert (info.variables, info.clauses, info.top) == (3, 4, 10)
    assert info.difficulty_D == 12
    assert info.category == LOW
    assert info.format_label == instance.FORMAT_SUPPORTED


def test_comments_and_blanks_before_header(tmp_path):
    text = "\n\nc uno\nc dos\n   \np wcnf 100 100 5\n1 1 0\n"
    info = parse_instance(_write(tmp_path, text))
    assert info.supported is True
    assert info.difficulty_D == 10_000
    assert info.category == LOW


def test_header_integers_split_across_lines(tmp_path):
    # fscanf salta blancos (incluidos saltos) entre las conversiones %zd.
    text = "p wcnf\n3\n4 10\n10 1 0\n"
    info = parse_instance(_write(tmp_path, text))
    assert info.supported is True
    assert (info.variables, info.clauses, info.top) == (3, 4, 10)


def test_two_integers_only_not_supported(tmp_path):
    # Solo 2 enteros y nada mas: la tercera conversion %zd falla -> unsupported.
    info = parse_instance(_write(tmp_path, "p wcnf 3 4\n"))
    assert info.supported is False
    assert info.format_label == instance.FORMAT_UNSUPPORTED


def test_two_integers_then_non_digit_not_supported(tmp_path):
    # "p wcnf 3 4" seguido de un comentario: el tercer %zd topa con 'c' y falla.
    info = parse_instance(_write(tmp_path, "p wcnf 3 4\nc foo\n"))
    assert info.supported is False


def test_fscanf_reads_top_from_next_line(tmp_path):
    # Fidelidad a fscanf: con solo 2 enteros en la linea 'p' pero un tercer
    # entero disponible despues (el peso de la primera clausula), el parser C
    # lo lee como TOP. parse_instance debe replicarlo (no ser mas estricto).
    info = parse_instance(_write(tmp_path, "p wcnf 3 4\n10 1 0\n"))
    assert info.supported is True
    assert (info.variables, info.clauses, info.top) == (3, 4, 10)


def test_digit_before_header_not_supported(tmp_path):
    text = "10 1 0\np wcnf 3 4 10\n"
    info = parse_instance(_write(tmp_path, text))
    assert info.supported is False


def test_no_valid_header_not_supported(tmp_path):
    info = parse_instance(_write(tmp_path, "hello world\nfoo bar\n"))
    assert info.supported is False


def test_comment_without_newline_at_eof_not_supported(tmp_path):
    # read_c_line devuelve false si no encuentra '\n' -> el C aborta.
    info = parse_instance(_write(tmp_path, "c comentario sin salto final"))
    assert info.supported is False


def test_variable_count_over_int_max_not_supported(tmp_path):
    text = "p wcnf %d 4 10\n1 1 0\n" % (INT_MAX + 1)
    info = parse_instance(_write(tmp_path, text))
    assert info.supported is False


def test_variable_count_exactly_int_max_supported(tmp_path):
    text = "p wcnf %d 4 10\n1 1 0\n" % INT_MAX
    info = parse_instance(_write(tmp_path, text))
    assert info.supported is True
    assert info.variables == INT_MAX
    assert info.category == HIGH  # D = INT_MAX * 4 es enorme


def test_missing_file_not_supported(tmp_path):
    info = parse_instance(str(tmp_path / "no_existe.wcnf"))
    assert info.supported is False
