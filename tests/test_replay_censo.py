"""The ingest replay reader must be able to say four different things.

Driven offline with a copy of the census and a tampered export, so the ladder is
exercised without network: identical (0), divergent (1), ruptured pin (4). The
`NO_MEDIDO` case is the download failure, which cannot be produced offline
without lying to urllib, so it is checked by the script's own message instead.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / "bench" / "replay_censo.py"
CSV = RAIZ / "tests" / "fixtures" / "migracion.csv"


def _correr(csv: Path, censo: Path) -> tuple[int, str]:
    p = subprocess.run([sys.executable, str(SCRIPT), "--csv", str(csv),
                        "--censo", str(censo)], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def _censo_fixture(tmp_path: Path) -> Path:
    """A census about the fixture: measured here, then written down."""
    from ingest_conservation_guard.acta import acta

    d = acta(CSV, "telefono:digitos:ultimos10", crudo="telefono")
    e = d["ecuacion"]
    fila = {"projection": "telefono:digitos:ultimos10", "raw_key": "telefono",
            "domain": e["dominio"], "image": e["imagen"],
            "by_projection": e["colisiones_por_proyeccion"],
            "by_repeated_row": e["colisiones_por_repetido"],
            "rejects": e["rechazos"], "no_key": e["sin_clave"],
            "silent_losses": d["perdidas_silenciosas"], "rc": d["rc"],
            "state": d["estado"], "output_sha256": d["salida"]["sha256"]}
    datos = {"instrument_version": "0.4.1", "status": "MEDIDO_EN_FIXTURE",
             "rows": [fila],
             "dataset": {"name": "migracion.csv", "source": "file://fixture",
                         "bytes": CSV.stat().st_size, "sha256": d["entrada"]["sha256"]}}
    ruta = tmp_path / "censo.json"
    ruta.write_text(json.dumps(datos, indent=2), encoding="utf-8")
    return ruta


def test_identical_then_divergent(tmp_path: Path) -> None:
    censo = _censo_fixture(tmp_path)
    rc, salida = _correr(CSV, censo)
    assert rc == 0, salida
    assert "REPLAY IDENTICO" in salida

    datos = json.loads(censo.read_text())
    datos["rows"][0]["image"] += 1
    censo.write_text(json.dumps(datos, indent=2), encoding="utf-8")
    rc, salida = _correr(CSV, censo)
    assert rc == 1, salida
    assert "DIVERGE" in salida


def test_a_ruptured_pin_stops_before_measuring(tmp_path: Path) -> None:
    censo = _censo_fixture(tmp_path)
    otro = tmp_path / "otro.csv"
    otro.write_bytes(CSV.read_bytes() + b"fila,extra,1\n")
    rc, salida = _correr(otro, censo)
    assert rc == 4, salida
    assert "RUPTURA" in salida and "0 filas medidas" in salida


def test_the_writer_declares_the_running_instrument_version(tmp_path: Path) -> None:
    """The census names the instrument that produced it, so bumping the package
    must move that name — and the only sanctioned way is to measure again."""
    from ingest_conservation_guard import __version__

    censo = _censo_fixture(tmp_path)
    antes = json.loads(censo.read_text())
    p = subprocess.run([sys.executable, str(SCRIPT), "--csv", str(CSV),
                        "--censo", str(censo), "--escribir"],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    assert __version__ in p.stdout, p.stdout
    despues = json.loads(censo.read_text())
    assert despues["instrument_version"] == __version__
    assert despues["status"] == "MEDIDO_EN_FIXTURE"
    assert despues["rows"] == antes["rows"]
    assert despues["dataset"] == antes["dataset"]


def test_the_writer_refuses_a_divergent_census(tmp_path: Path) -> None:
    """A writer that would rewrite the pin to match a divergence destroys the
    only evidence the divergence ever existed."""
    censo = _censo_fixture(tmp_path)
    datos = json.loads(censo.read_text())
    datos["rows"][0]["image"] += 1
    censo.write_text(json.dumps(datos, indent=2), encoding="utf-8")
    antes = censo.read_text()
    p = subprocess.run([sys.executable, str(SCRIPT), "--csv", str(CSV),
                        "--censo", str(censo), "--escribir"],
                       capture_output=True, text=True)
    assert p.returncode == 1, p.stdout + p.stderr
    assert "ESCRITURA NEGADA" in p.stdout
    assert censo.read_text() == antes
