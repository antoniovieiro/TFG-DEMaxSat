"""GUI de escritorio para el solver DEMaxSAT.

Esta aplicacion es un wrapper sobre el binario `demaxsat` (C): lo lanza como
subproceso, captura su salida y permite pararlo (SIGTERM) para obtener la
solucion final. No modifica nada del codigo C.
"""

__version__ = "0.1.0"
