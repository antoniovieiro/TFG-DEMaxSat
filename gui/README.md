# DEMaxSAT GUI

Aplicacion de escritorio sencilla (Python + PySide6) que envuelve el solver
`demaxsat` (C). Permite seleccionar una instancia `.wcnf`, ajustar los
parametros del solver, ejecutarlo y pararlo, viendo la salida en vivo y la
solucion final.

**No modifica el codigo C**: lanza el binario `demaxsat` como subproceso,
captura su stdout y, al pulsar *Parar*, le envia SIGTERM (que es como el solver
entrega su mejor solucion).

## Requisitos

- Python 3.9+
- Sistemas UNIX (macOS / Linux)

## Instalacion

Desde esta carpeta (`gui/`):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ejecucion

```bash
python -m demaxsat_gui.main
```

## El binario `demaxsat`

La app busca el binario `demaxsat` en la raiz del proyecto (la carpeta que
contiene `gui/`). Si no lo encuentra, muestra un boton **Compilar** que ejecuta
`make`.

> En macOS, el `make` por defecto puede fallar porque el `Makefile` no incluye
> los flags de `argp` de Homebrew. En ese caso, compila manualmente, por
> ejemplo:
> ```bash
> gcc -g -o demaxsat main.c -lm -Wall \
>     -I/opt/homebrew/include -L/opt/homebrew/lib -largp
> ```

## Uso

1. Selecciona una instancia `.wcnf` con *Examinar...*.
2. Ajusta los parametros (tienen los mismos valores por defecto que el CLI).
3. Pulsa *Ejecutar*. Veras las lineas `o <coste>` segun mejora la solucion.
4. Con `gens = -1` el solver corre indefinidamente: pulsa *Parar* para obtener
   la solucion final (`s` / `o` / `v`).

El solver sigue generando su log de convergencia (`*_gens.log`) junto al
archivo `.wcnf`, igual que por linea de comandos.
