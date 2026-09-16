"""Informacion de la instancia y clasificacion de dificultad.

`parse_instance()` replica **exactamente** el comportamiento del parser C actual
(`WCNFParser/wcnf_parser.c`) para decidir si el solver aceptaria el fichero:
la regla es `supported == True` si y solo si el parser C leeria correctamente la
cabecera inicial. No es ni mas permisivo ni mas estricto.

Esta logica esta encapsulada aqui para poder ampliar el parser a otros formatos
(p. ej. WCNF 2022+/Partial) en una fase futura sin tocar la interfaz grafica.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

# El parser C usa LiteralMax = INT_MAX (int de 32 bits) para variable_count.
INT_MAX = 2**31 - 1

# Umbrales de dificultad D = variables x clausulas (pagina 7 del paper).
#   LOW:    1 <= D < 200000
#   MEDIUM: 200000 <= D < 10000000
#   HIGH:   D >= 10000000
LOW_MAX = 200_000
MEDIUM_MAX = 10_000_000

# Categorias posibles devueltas por classify().
LOW = "LOW"
MEDIUM = "MEDIUM"
HIGH = "HIGH"
INVALID = "INVALID"

FORMAT_SUPPORTED = "legacy (soportado)"
FORMAT_UNSUPPORTED = "desconocido / no soportado"


@dataclass(frozen=True)
class InstanceInfo:
    supported: bool
    format_label: str
    variables: Optional[int] = None
    clauses: Optional[int] = None
    top: Optional[int] = None
    difficulty_D: Optional[int] = None
    category: Optional[str] = None


def classify(D: int) -> str:
    """Clasifica una dificultad D en LOW/MEDIUM/HIGH.

    El paper define LOW desde D >= 1, por lo que D <= 0 NO se clasifica
    silenciosamente como LOW: se devuelve la categoria especial INVALID.
    """
    if D < 1:
        return INVALID
    if D < LOW_MAX:
        return LOW
    if D < MEDIUM_MAX:
        return MEDIUM
    return HIGH


def _unsupported() -> InstanceInfo:
    return InstanceInfo(supported=False, format_label=FORMAT_UNSUPPORTED)


def _scan_int(s: str, i: int) -> Tuple[Optional[int], int]:
    """Emula una conversion `%zd` de fscanf: salta blancos, admite signo
    opcional y lee digitos decimales. Devuelve (valor, nueva_posicion) o
    (None, pos) si no hay entero."""
    n = len(s)
    while i < n and s[i].isspace():
        i += 1
    start = i
    if i < n and s[i] in "+-":
        i += 1
    digits_start = i
    while i < n and s[i].isdigit():
        i += 1
    if i == digits_start:  # ningun digito -> conversion fallida
        return None, start
    return int(s[start:i]), i


def _parse_p_line(s: str, pos: int) -> InstanceInfo:
    """Replica read_p_line: fscanf("p wcnf %zd %zd %zd").

    `s[pos]` es 'p'. El espacio del formato casa con cero o mas blancos, luego
    el literal 'wcnf', luego tres enteros. Se acepta si las tres conversiones
    tienen exito y variable_count <= INT_MAX; el contenido que venga despues
    (las clausulas) es normal y se ignora aqui.
    """
    n = len(s)
    i = pos + 1  # tras la 'p'
    while i < n and s[i].isspace():  # el ' ' del formato: cero o mas blancos
        i += 1
    if not s.startswith("wcnf", i):
        return _unsupported()
    i += 4

    values = []
    for _ in range(3):
        val, i = _scan_int(s, i)
        if val is None:
            break
        values.append(val)
    if len(values) < 3:  # match_count != 3 -> NULL -> error
        return _unsupported()

    variables, clauses, top = values
    if variables < 0 or variables > INT_MAX:  # variable_count > LiteralMax -> NULL
        return _unsupported()

    D = variables * clauses
    return InstanceInfo(
        supported=True,
        format_label=FORMAT_SUPPORTED,
        variables=variables,
        clauses=clauses,
        top=top,
        difficulty_D=D,
        category=classify(D),
    )


def parse_instance(path: str) -> InstanceInfo:
    """Determina si el solver aceptaria `path` y extrae datos de la cabecera.

    Emula el flujo de read_file(): salta blancos, consume comentarios `c ...`
    (que deben terminar en '\\n'), y localiza la cabecera `p wcnf V C TOP` antes
    de cualquier clausula. Cualquier desviacion respecto a lo que el parser C
    aceptaria produce supported=False.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            data = fh.read()
    except OSError:
        return _unsupported()

    n = len(data)
    pos = 0
    while True:
        while pos < n and data[pos].isspace():
            pos += 1
        if pos >= n:
            # EOF sin encontrar cabecera ni clausulas -> el C aborta.
            return _unsupported()
        c = data[pos]
        if c == "c":
            nl = data.find("\n", pos)
            if nl == -1:  # comentario sin '\n' al EOF -> read_c_line false -> error
                return _unsupported()
            pos = nl + 1
            continue
        if c == "p":
            return _parse_p_line(data, pos)
        # Un digito (clausula antes de la cabecera) o cualquier otro caracter
        # inesperado hacen que el parser C nunca produzca un CNF valido.
        return _unsupported()
