"""Definicion declarativa de los parametros del solver DEMaxSAT.

Es la unica "fuente de verdad" de los parametros: refleja exactamente las
opciones definidas en `main.c` (struct argp_option / struct arguments) para que
la interfaz y la construccion de argumentos de linea de comandos no se
desincronicen.

Cada parametro se pasa al binario en forma larga `--flag=valor`. Se usa la forma
con `=` a proposito: evita que un valor negativo (p. ej. `--gens=-1`) sea
interpretado por argp como otra opcion.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Union

Number = Union[int, float]


@dataclass(frozen=True)
class Param:
    """Un parametro configurable del solver."""

    name: str          # clave interna (coincide con el long flag)
    flag: str          # nombre del flag largo de argp, sin "--"
    label: str         # etiqueta mostrada en la UI
    kind: str          # "int" | "float" | "choice"
    default: Number    # valor por defecto (igual que en main.c)
    help: str          # texto de ayuda (tooltip)
    minimum: Optional[Number] = None
    maximum: Optional[Number] = None
    decimals: int = 2  # solo para "float"
    step: Optional[Number] = None
    choices: List[str] = field(default_factory=list)  # solo para "choice"


# Orden y valores por defecto tomados de main.c (lineas 36-64 y 152-160).
PARAMS: List[Param] = [
    Param(
        name="gens", flag="gens", label="Generaciones (gens)", kind="int",
        default=-1, minimum=-1, maximum=2_147_483_647, step=1,
        help="Numero maximo de generaciones. Sin limite = -1. Por defecto = -1.\n"
             "Con -1 el solver corre indefinidamente: usa 'Parar' para obtener "
             "la solucion.",
    ),
    Param(
        name="pop", flag="pop", label="Poblacion (pop)", kind="int",
        default=100, minimum=1, maximum=1_000_000, step=1,
        help="Tamano de la poblacion. Por defecto = 100.",
    ),
    Param(
        name="cr", flag="cr", label="Cruce (cr)", kind="float",
        default=0.4, minimum=0.0, maximum=1.0, decimals=2, step=0.05,
        help="Probabilidad de cruce (crossover). Por defecto = 0.40.",
    ),
    Param(
        name="f", flag="f", label="Mutacion (f)", kind="float",
        default=0.6, minimum=0.0, maximum=1.0, decimals=2, step=0.05,
        help="Probabilidad de mutacion. Por defecto = 0.60.",
    ),
    Param(
        name="lss", flag="lss", label="Pasos busqueda local (lss)", kind="float",
        default=0.01, minimum=0.0, maximum=1.0, decimals=4, step=0.01,
        help="Numero de pasos de busqueda local, como porcentaje del numero de "
             "variables. Por defecto = 0.01.",
    ),
    Param(
        name="maxlss", flag="maxlss", label="Max. LSS (maxlss)", kind="int",
        default=100, minimum=-1, maximum=2_147_483_647, step=1,
        help="Maximo de pasos de busqueda local en cada llamada a las "
             "heuristicas. Sin limite = -1. Por defecto = 100.",
    ),
    Param(
        name="seed", flag="seed", label="Semilla (seed)", kind="int",
        default=-1, minimum=-1, maximum=2_147_483_647, step=1,
        help="Semilla de numeros aleatorios. Aleatoria = -1. Por defecto = -1.",
    ),
    Param(
        name="rw", flag="rw", label="RandomWalk (rw)", kind="float",
        default=0.5, minimum=0.0, maximum=1.0, decimals=2, step=0.05,
        help="Probabilidad de RandomWalk. Probabilidad de GSAT = (1 - rw). "
             "Por defecto = 0.50.",
    ),
    Param(
        name="hscope", flag="hscope", label="Ambito heuristicas (hscope)",
        kind="choice", default=0,
        choices=["all", "better_than_mean", "best"],
        help="Individuos afectados por la busqueda local: all, better_than_mean "
             "o best. Por defecto = all.",
    ),
]


def build_args(values: dict) -> List[str]:
    """Construye la lista de argumentos `--flag=valor` a partir de un dict
    {name: valor} con los valores actuales de la UI."""
    args: List[str] = []
    for p in PARAMS:
        if p.name not in values:
            continue
        value = values[p.name]
        if p.kind == "float":
            text = ("%.*f" % (p.decimals, float(value)))
        else:
            text = str(value)
        args.append("--%s=%s" % (p.flag, text))
    return args
