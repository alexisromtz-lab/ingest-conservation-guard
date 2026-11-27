"""La versión como una sola igualdad sobre cuatro superficies.

`pyproject.toml` y `__init__.__version__` decían lo mismo por mano, y nada lo
comprobaba: subir una y olvidar la otra produce un paquete que se presenta con dos
números. La cita añade dos superficies más al mismo predicado, así que el lector
compara las cuatro de una vez en lugar de tres pares sueltos.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import ingest_conservation_guard

RAIZ = Path(__file__).resolve().parents[1]
CFF = (RAIZ / "CITATION.cff").read_text(encoding="utf-8")
ZENODO = json.loads((RAIZ / ".zenodo.json").read_text(encoding="utf-8"))


def _escalar_cff(clave: str) -> str:
    encontrado = re.search(r"^%s:\s*(.+?)\s*$" % re.escape(clave), CFF, re.MULTILINE)
    assert encontrado is not None, "CITATION.cff no declara `%s:`" % clave
    return encontrado.group(1).strip().strip('"')


def _version_pyproject() -> str:
    texto = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    encontrado = re.search(r'^version\s*=\s*"([^"]+)"', texto, re.MULTILINE)
    assert encontrado is not None, "pyproject.toml no declara version"
    return encontrado.group(1)


def test_la_version_es_la_misma_en_las_cuatro_superficies():
    declarada = _version_pyproject()
    assert ingest_conservation_guard.__version__ == declarada
    assert _escalar_cff("version") == declarada
    assert ZENODO["version"] == declarada


def test_las_dos_superficies_de_cita_coinciden_en_el_titulo():
    assert _escalar_cff("title") == ZENODO["title"]


def test_las_dos_superficies_señalan_el_mismo_repositorio():
    assert _escalar_cff("repository-code") == ZENODO["related_identifiers"][0]["identifier"]
