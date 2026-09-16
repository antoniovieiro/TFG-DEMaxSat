"""Configuraciones "segun el paper" (Framil/Cabalar/Santos, MSE 2021).

Valores extraidos literalmente de la pagina 7 del articulo. NO se inventan.

- Parametros fijos en todos los experimentos: CR=0.4, F=0.6, PRW(rw)=0.5.
- Segun la dificultad de la instancia (LOW/MEDIUM/HIGH) y el timeout (60/300 s),
  se seleccionan NP (pop), LSS (lss) y HSCOPE (hscope).

Nota: se denomina "Configuracion segun el paper", no "reproduccion exacta": el
paper ademas promedia multiples ejecuciones independientes, protocolo que la GUI
no garantiza. `maxlss=-1` reproduce la definicion de LSS del paper (N =
ceil(LSS x #vars)) sin el tope adicional de la implementacion; no implica que los
experimentos historicos se ejecutaran con ese valor concreto.
"""

from typing import Dict

from . import instance

# Timeouts contemplados por el paper (segundos).
TIMEOUTS = (60, 300)

# Parametros fijos en todos los experimentos del paper.
FIXED: Dict[str, float] = {"cr": 0.4, "f": 0.6, "rw": 0.5}

# (categoria, timeout) -> {pop (NP), lss (LSS), hscope (HSCOPE)}.
PAPER_CONFIGS: Dict = {
    (instance.LOW, 60): {"pop": 30, "lss": 0.05, "hscope": "all"},
    (instance.LOW, 300): {"pop": 30, "lss": 0.10, "hscope": "all"},
    (instance.MEDIUM, 60): {"pop": 5, "lss": 0.025, "hscope": "all"},
    (instance.MEDIUM, 300): {"pop": 10, "lss": 0.10, "hscope": "better_than_mean"},
    (instance.HIGH, 60): {"pop": 5, "lss": 0.025, "hscope": "better_than_mean"},
    (instance.HIGH, 300): {"pop": 5, "lss": 0.075, "hscope": "better_than_mean"},
}


def paper_values(category: str, timeout: int) -> Dict:
    """Devuelve los valores a volcar en la UI para (categoria, timeout).

    Combina los fijos del paper, la configuracion seleccionada y los ajustes de
    ejecucion `gens=-1` y `maxlss=-1`. NO incluye `seed` (queda editable; su
    default sigue siendo -1 desde params/Manual).
    """
    if timeout not in TIMEOUTS:
        raise ValueError("Timeout no contemplado por el paper: %r" % (timeout,))
    if (category, timeout) not in PAPER_CONFIGS:
        raise ValueError("Categoria no clasificable para el paper: %r" % (category,))

    config = PAPER_CONFIGS[(category, timeout)]
    values: Dict = {}
    values.update(FIXED)
    values.update(config)
    values["gens"] = -1
    values["maxlss"] = -1
    return values
