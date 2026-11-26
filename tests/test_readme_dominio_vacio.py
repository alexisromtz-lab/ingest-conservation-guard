"""El bloque `### An empty domain certifies nothing` se ejecuta, no se copia.

Un bloque de consola sin lector envejece: basta cambiar el orden de una linea
para que el README ensene una salida que el binario ya no produce. Aqui cada
comando del bloque se corre desde la raiz del repo y su salida se compara linea
por linea — stdout primero, stderr despues, que es el orden en que se leen.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
README = (RAIZ / "README.md").read_text(encoding="utf-8")
TITULO = "### An empty domain certifies nothing"


def _seccion() -> str:
    inicio = README.index(TITULO)
    resto = README[inicio + len(TITULO):]
    corte = re.search(r"^#{2,3} ", resto, flags=re.MULTILINE)
    return resto[:corte.start()] if corte else resto


def _comando(lineas: list[str]) -> tuple[str, list[str]]:
    """La linea `$ ` mas sus continuaciones con `\\`, y el resto como esperado."""
    partes, i = [], 0
    while i < len(lineas):
        texto = lineas[i][2:] if lineas[i].startswith("$ ") else lineas[i]
        if texto.rstrip().endswith("\\"):
            partes.append(texto.rstrip()[:-1].strip())
            i += 1
            continue
        partes.append(texto.strip())
        i += 1
        break
    return " ".join(p for p in partes if p), lineas[i:]


def _bloques() -> list[tuple[str, list[str]]]:
    return [_comando(cuerpo.rstrip("\n").splitlines())
            for cuerpo in re.findall(r"```console\n(.*?)```", _seccion(), flags=re.DOTALL)]


def test_el_bloque_de_consola_muestra_lo_que_el_binario_imprime() -> None:
    bloques = _bloques()
    assert len(bloques) == 2, f"la seccion cambio de forma: {len(bloques)} bloques"
    ejecutable = " ".join((shlex.quote(sys.executable), "-m", "ingest_conservation_guard"))
    for comando, esperadas in bloques:
        assert comando, "bloque sin comando: no se puede re-ejecutar"
        # El README nombra el comando instalado; aqui corre el modulo del arbol.
        hecho = subprocess.run(comando.replace("ingest-conservation-guard", ejecutable, 1),
                               shell=True, cwd=RAIZ, capture_output=True, text=True,
                               env={**os.environ, "PYTHONPATH": "src"})
        reales = (hecho.stdout + hecho.stderr).rstrip("\n").splitlines()
        assert reales == esperadas, f"README desactualizado para: {comando}"
