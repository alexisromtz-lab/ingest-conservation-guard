"""The measured export is a claim about a file, not about this machine.

`censo.json` pins the input digest, so anyone holding that file can re-derive
every cell. These tests keep the README table and the JSON in step, and refuse a
pin that is incomplete.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
CENSO = json.loads((RAIZ / "censo.json").read_text(encoding="utf-8"))
README = (RAIZ / "README.md").read_text(encoding="utf-8")


def _num(texto: str) -> int:
    return int(texto.replace(" ", "").replace("\u00a0", ""))


def _tabla() -> list[list[str]]:
    """The last table with this header: the fixture one comes first in the file."""
    lineas = README.splitlines()
    inicio = max(i for i, l in enumerate(lineas)
                 if l.startswith("| projection | raw key | domain |"))
    filas = []
    for linea in lineas[inicio + 1:]:
        if not linea.startswith("|"):
            break
        celdas = [c.strip().replace("**", "").replace("`", "")
                  for c in linea.strip().strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in celdas):
            continue
        if celdas[0] == "projection":
            continue
        filas.append(celdas)
    return filas


def test_pin_is_complete():
    datos = CENSO["dataset"]
    assert len(datos["sha256"]) == 64 and int(datos["sha256"], 16) >= 0
    assert datos["rows"] > 0 and datos["bytes"] > 0
    assert datos["source"].startswith("https://")
    assert CENSO["status"] == "MEDIDO_EN_EXPORTACION_PUBLICA"
    assert "MEDIDO_EN_PRODUCCION" in CENSO["not_measured"]
    for r in CENSO["rows"]:
        assert len(r["output_sha256"]) == 64, r
        assert r["domain"] == datos["rows"], r


def test_identity_closes_in_every_row():
    for r in CENSO["rows"]:
        suma = r["image"] + r["rejects"] + r["no_key"]
        if r["by_projection"] is not None:
            suma += r["by_projection"] + r["by_repeated_row"]
        assert suma == r["domain"], r
        assert r["silent_losses"] == r["domain"] - suma


def test_readme_table_matches_censo():
    filas = _tabla()
    assert len(filas) == len(CENSO["rows"]) == 3 - 1
    for celdas, r in zip(filas, CENSO["rows"]):
        proyeccion, crudo, dominio, imagen, proy, repe, rech, sin_clave, perdidas, rc = celdas
        assert proyeccion == r["projection"]
        assert (crudo if crudo != "—" else None) == r["raw_key"]
        assert (_num(dominio), _num(imagen), _num(rech), _num(sin_clave),
                _num(perdidas), _num(rc)) == (r["domain"], r["image"], r["rejects"],
                                              r["no_key"], r["silent_losses"], r["rc"])
        for leido, esperado in ((proy, r["by_projection"]), (repe, r["by_repeated_row"])):
            assert (None if leido == "—" else _num(leido)) == esperado


def test_replay_against_the_pinned_export():
    """Offline replay: skipped loudly unless the export is on disk."""
    ruta = os.environ.get("INGEST_CENSO_CSV")
    if not ruta:
        pytest.skip("INGEST_CENSO_CSV no declarada: censo no re-ejecutado (NO_MEDIDO)")
    crudo = Path(ruta).read_bytes()
    assert hashlib.sha256(crudo).hexdigest() == CENSO["dataset"]["sha256"], \
        "el fichero en disco no es el exportado que el censo declara"
    for r in CENSO["rows"]:
        args = [sys.executable, "-m", "ingest_conservation_guard", "--receipt", ruta,
                "--clave", r["projection"], "--json"]
        if r["raw_key"]:
            args += ["--crudo", r["raw_key"]]
        p = subprocess.run(args, capture_output=True, text=True)
        d = json.loads(p.stdout)
        assert d["entrada"]["filas"] == r["domain"]
        assert d["salida"]["sha256"] == r["output_sha256"]
        assert d["rc"] == r["rc"]
        assert d["perdidas_silenciosas"] == r["silent_losses"]
        assert d["cubetas"]["imagen"] == r["image"]

def test_instrument_version_is_the_package_version():
    """A pin that names a version which never produced it is a testimony.

    If this fails, re-run the census with the new code; never edit the version
    in `censo.json` to match.
    """
    import ingest_conservation_guard

    assert CENSO["instrument_version"] == ingest_conservation_guard.__version__
