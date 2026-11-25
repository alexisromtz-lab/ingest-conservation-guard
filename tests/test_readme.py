"""The README as an executable claim (A0.12 blind spot).

Three readings, all of them cheap and all of them things that had no reader:
the migration table is recomputed with the real engine, the executable cases the
README names are exercised through the CLI, and the file is forbidden from
pinning a test count that rots on the next commit.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from ingest_conservation_guard.acta import acta
from ingest_conservation_guard.cli import CASOS, main
from ingest_conservation_guard.motor import COLISION, CONSERVADO, RUPTURA

RAIZ = Path(__file__).resolve().parents[1]
README = (RAIZ / "README.md").read_text(encoding="utf-8")
FIXTURE = RAIZ / "tests" / "fixtures" / "migracion.csv"

COLUMNAS = ["domain", "image", "by projection", "by repeated row",
            "rejects", "silent losses", "rc"]


def _filas_migracion() -> list[tuple[str, str, list[str]]]:
    filas, dentro = [], False
    for linea in README.splitlines():
        if linea.startswith("## Migrations"):
            dentro = True
            continue
        if dentro and linea.startswith("## "):
            break
        if dentro and linea.startswith("| `"):
            celdas = [c.strip().strip("`") for c in linea.strip().strip("|").split("|")]
            filas.append((celdas[0], celdas[1], celdas[2:]))
    return filas


def test_migration_table_matches_the_engine() -> None:
    filas = _filas_migracion()
    assert len(filas) == 3, f"la tabla de migracion cambio de forma: {filas}"
    for clave, crudo, celdas in filas:
        d = acta(FIXTURE, clave, crudo=crudo,
                 validar="activo" if clave.startswith("telefono") else None)
        e = d["ecuacion"]
        real = [e["dominio"], e["imagen"], e["colisiones_por_proyeccion"],
                e["colisiones_por_repetido"], e["rechazos"],
                d["perdidas_silenciosas"], d["rc"]]
        publicado = [int(c) for c in celdas]
        assert publicado == real, f"README desactualizado en {clave}/{crudo}: " \
                                  f"{dict(zip(COLUMNAS, zip(publicado, real)))}"


def test_every_executable_case_still_runs() -> None:
    # The README claims three executable cases. Which three is decided here.
    assert set(CASOS) == {"pacientes", "sku", "sku-completa", "ruptura"}
    vista = {"pacientes": COLISION, "sku": COLISION, "sku-completa": CONSERVADO,
             "ruptura": RUPTURA}
    for nombre, esperado in vista.items():
        assert main([nombre, "--json"]) == esperado


def test_readme_does_not_pin_a_test_count() -> None:
    # A hand-written "N passed" is stale on the next commit and no reader noticed.
    m = re.search(r"`\d+ passed`", README)
    assert m is None, f"README vuelve a fijar un conteo que envejece: {m.group(0) if m else ''}"


def test_readme_publishes_the_no_medido_row() -> None:
    # The caveat that no client data has been audited is a claim, and it must
    # survive edits: a green table with no such row would read as universal.
    assert "NO_MEDIDO" in README


def test_cli_receipt_requires_a_declared_projection(capsys) -> None:
    with pytest.raises(SystemExit):
        main(["--receipt", str(FIXTURE)])


def test_cli_receipt_is_deterministic_json(capsys) -> None:
    rc = main(["--receipt", str(FIXTURE), "--clave", "telefono:digitos:ultimos10",
               "--crudo", "telefono", "--validar", "activo", "--json"])
    primero = capsys.readouterr().out
    main(["--receipt", str(FIXTURE), "--clave", "telefono:digitos:ultimos10",
          "--crudo", "telefono", "--validar", "activo", "--json"])
    assert primero == capsys.readouterr().out
    d = json.loads(primero)
    assert d["perdidas_silenciosas"] == 0
    assert rc == COLISION
