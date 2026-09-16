# DEMaxSAT GUI

Aplicacion de escritorio (Python + PySide6) que envuelve el solver `demaxsat`
(C). Permite seleccionar una instancia `.wcnf`, ajustar los parametros del
solver, ejecutarlo y pararlo, viendo la salida en vivo y la solucion final.

**No modifica el codigo C**: lanza el binario `demaxsat` como subproceso,
captura su stdout y, al pulsar *Parar* (o al vencer un *timeout*), le envia
SIGTERM (que es como el solver entrega su mejor solucion).

## Requisitos

- **Python 3.12 recomendado/testado.** Entorno funcional verificado: Python
  3.12.7, PySide6 6.10.3, macOS 14.5, Apple M1 (arm64).
- Sistemas UNIX (macOS / Linux).

> **Ubicacion del entorno virtual (macOS)**: crea el venv **fuera de `Desktop`,
> iCloud o carpetas sincronizadas**. En este equipo, un venv dentro de `Desktop`
> dejaba los plugins Qt en un estado problematico; el entorno recomendado es
> **`~/.venvs/demaxsat`** con Python 3.12.7 + PySide6 6.10.3, que funciona
> correctamente. (No se aplican hacks del tipo `chflags`; es una recomendacion de
> ubicacion.) Ademas, `python3` puede apuntar al Python 3.9 del sistema: usa
> explicitamente `python3.12`.

## Instalacion

```bash
python3.12 -m venv ~/.venvs/demaxsat
source ~/.venvs/demaxsat/bin/activate
pip install -r gui/requirements.txt
```

`requirements.txt` fija `PySide6==6.10.3` (la version 6.11.2 rompia la
inicializacion del plugin Cocoa en este equipo).

## Ejecucion

```bash
python -m demaxsat_gui.main
```

## Tests

Instala las dependencias de desarrollo y ejecuta `pytest`. Las rutas dependen
del directorio actual:

```bash
pip install -r requirements-dev.txt

# desde gui/
pytest tests/

# desde la raiz del repositorio
pytest gui/tests/
```

## Harness de transparencia GUI vs CLI

`gui/tools/compare_gui_cli.py` comprueba que la GUI es un *wrapper transparente*
del solver: ejecuta el **mismo binario** sobre la **misma instancia** (mismos
bytes, verificados por SHA-256) con los **mismos 9 parametros**, `seed` fija,
`gens` finito y **sin timeout**, por dos vias —CLI directo y la misma logica de
ejecucion de la GUI (`SolverRunner`)— y compara PASS/FAIL: argumentos efectivos,
codigo de salida, secuencia de lineas `o`, coste final, asignacion `v` y el
`*_gens.log` (contenido determinista, ignorando el nombre con timestamp).

No forma parte de `pytest` (necesita el binario compilado). Ejemplo:

```bash
python gui/tools/compare_gui_cli.py "benchmarks/funcionan inicial/maxcut-140-630-0.7-28.wcnf" \
    --gens 50 --seed 1
```

Acepta `.wcnf` o `.wcnf.gz` (las `.gz` se descomprimen a un temporal; los
originales de `benchmarks/` no se tocan). Muestra la muestra recomendada
(non-partial legacy) en el propio informe de auditoria.

> Nota: este harness es la **Suite A** (equivalencia GUI/CLI, solo instancias
> legacy non-partial). La validacion negativa de formatos no soportados
> (**Suite B**) y el estudio de Partial MaxSAT (**Suite C**) son separados.

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

1. Selecciona una instancia `.wcnf` con *Examinar...*. El panel **Informacion de
   la instancia** muestra variables, clausulas, `D = variables x clausulas`, la
   categoria de dificultad (LOW/MEDIUM/HIGH) y el formato. Si el formato no es el
   que soporta el solver, se muestra "desconocido / no soportado" y *Ejecutar*
   queda deshabilitado.
2. Elige el **modo de configuracion**:
   - **Manual**: todos los parametros editables, con los valores por defecto de
     la implementacion.
   - **Configuracion segun el paper - 60 s / 300 s**: segun la dificultad
     detectada se rellenan automaticamente NP, LSS, HSCOPE (y los fijos CR=0.4,
     F=0.6, PRW=0.5, gens=-1, maxlss=-1) y el timeout, quedando de solo lectura.
     `seed` sigue siendo editable para reproducir una corrida concreta.
3. Ajusta el **timeout** si procede (Sin limite / 60 s / 300 s / Personalizado).
4. Pulsa *Ejecutar*. Veras las lineas `o <coste>` segun mejora la solucion.
   Con `gens = -1` el solver corre indefinidamente: pulsa *Parar* (o deja que
   venza el timeout) para obtener la solucion final (`s` / `o` / `v`).

El solver sigue generando su log de convergencia (`*_gens.log`) junto al
archivo `.wcnf`, igual que por linea de comandos.

## Nota sobre formatos

Esta version trabaja con el formato WCNF que acepta hoy DeMaxSAT (cabecera
`p wcnf V C TOP`). La compatibilidad con WCNF 2022+ / Partial MaxSAT se
abordara en una fase posterior; la logica de deteccion esta aislada en
`demaxsat_gui/instance.py` para poder ampliarla sin cambiar la interfaz.
