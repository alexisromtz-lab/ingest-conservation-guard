"""The migration certificate: the accounting identity, its two causes, its digests.

The fixture is a six-row export with an invented mix of hazards: the same phone
written two ways, accents that a careless projection folds, and one inactive row.
It is the smallest input that exercises every bucket at once.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ingest_conservation_guard.acta import (
    acta,
    cargar,
    proyector,
    resumen,
    sha256_de,
)
from ingest_conservation_guard.motor import COLISION, CONSERVADO

FIXTURE = Path(__file__).parent / "fixtures" / "migracion.csv"


def test_identity_closes_with_the_raw_key_on_the_projection():
    d = acta(FIXTURE, "telefono:digitos:ultimos10", crudo="telefono", validar="activo")
    e = d["ecuacion"]
    assert e["dominio"] == 6
    assert e["imagen"] == 3
    assert e["rechazos"] == 1
    assert e["sin_clave"] == 0
    assert e["colisiones_por_proyeccion"] == 2
    assert e["colisiones_por_repetido"] == 0
    suma = e["imagen"] + e["colisiones_por_proyeccion"] + e["colisiones_por_repetido"] \
        + e["rechazos"] + e["sin_clave"]
    assert suma == e["dominio"]
    assert d["perdidas_silenciosas"] == 0
    assert d["rc"] == COLISION


def test_the_same_lost_mass_is_attributed_to_the_other_cause():
    # Same rows, same lost mass, different raw key: the phone was normalised, not
    # repeated. This is the whole point of the split -- the repair happens in a
    # different place, so a certificate that could not tell them apart would be
    # useless even when the identity closed.
    d = acta(FIXTURE, "telefono:digitos:ultimos10", crudo="nombre:plano:lower",
             validar="activo")
    e = d["ecuacion"]
    assert e["colisiones_por_proyeccion"] == 0
    assert e["colisiones_por_repetido"] == 2
    assert d["perdidas_silenciosas"] == 0


def test_accent_stripping_merges_the_two_spellings():
    plano = proyector("nombre:plano:lower")
    assert plano({"nombre": "José  Ramírez".replace("  ", " ")}) == \
        plano({"nombre": "Jose Ramirez"})


def test_without_the_raw_key_the_split_is_not_measured():
    d = acta(FIXTURE, "telefono:digitos:ultimos10", validar="activo")
    assert d["ecuacion"] is None
    assert "NO_MEDIDA" in resumen(d)
    # The total still has to close, and it does: the missing piece is the split,
    # never the conservation.
    assert d["perdidas_silenciosas"] == 0


def test_an_injective_key_conserves():
    d = acta(FIXTURE, "id", crudo="id")
    assert d["rc"] == CONSERVADO
    assert d["ecuacion"]["imagen"] == 6
    assert d["perdidas_silenciosas"] == 0


def test_digests_name_both_ends():
    d1 = acta(FIXTURE, "telefono:digitos:ultimos10", crudo="telefono", validar="activo")
    d2 = acta(FIXTURE, "telefono:digitos:ultimos10", crudo="telefono", validar="activo")
    assert d1["entrada"]["sha256"] == sha256_de(FIXTURE)
    assert d1["salida"]["sha256"] == d2["salida"]["sha256"]
    assert resumen(d1) == resumen(d2)


def test_withheld_keys_keep_the_witnesses():
    d = acta(FIXTURE, "telefono:digitos:ultimos10", crudo="telefono",
             validar="activo", con_claves=False)
    assert d["colisiones"], "el acta debe seguir nombrando las filas pisadas"
    assert {c["clave"] for c in d["colisiones"]} == {"<omitida>"}
    assert d["colisiones"][0]["pisados"]


def test_unknown_transform_is_a_hard_error():
    # Silently ignoring a misspelt transform would certify a different projection
    # than the one the acta names.
    with pytest.raises(ValueError, match="transformacion desconocida"):
        proyector("telefono:digitoz")


def test_a_row_without_a_key_lands_in_its_own_bucket(tmp_path):
    # A missing column is not a loss: it is a bucket, and the identity still has
    # to close with it in.
    entrada = tmp_path / "sin_clave.json"
    entrada.write_text('[{"id": "A-1"}, {"id": ""}, {"otro": "x"}]', encoding="utf-8")
    d = acta(entrada, "id", crudo="id")
    assert d["ecuacion"]["sin_clave"] == 2
    assert d["ecuacion"]["imagen"] == 1
    assert d["perdidas_silenciosas"] == 0


def test_el_acta_nombra_el_binario_que_la_escribio():
    """Un recibo sin autor no se puede fechar: se confunde con uno alterado."""
    from ingest_conservation_guard import __version__
    from ingest_conservation_guard.acta import acta

    documento = acta(FIXTURE, "telefono:digitos:ultimos10", "telefono")
    assert documento["instrument"] == "ingest-conservation-guard"
    assert documento["instrument_version"] == __version__
