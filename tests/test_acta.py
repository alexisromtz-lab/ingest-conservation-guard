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
from ingest_conservation_guard.rc import VACIO

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


def test_sin_export_la_salida_no_nombra_ningun_archivo():
    """Sin artefacto la salida es una abstraccion: se declara, no se inventa."""
    d = acta(FIXTURE, "telefono:digitos:ultimos10", "telefono")
    assert "archivo" not in d["salida"]
    assert "sha256_archivo" not in d["salida"]


def test_el_export_digiere_los_bytes_que_quedaron_en_disco(tmp_path):
    """La costura sólo existe si el digest es el del archivo, no el del mapa."""
    uno = tmp_path / "paso1.csv"
    dos = tmp_path / "paso1-otra-vez.csv"
    d1 = acta(FIXTURE, "telefono:digitos:ultimos10", "telefono", exportar=uno)
    d2 = acta(FIXTURE, "telefono:digitos:ultimos10", "telefono", exportar=dos)

    assert d1["salida"]["archivo"] == "paso1.csv"
    assert d1["salida"]["sha256_archivo"] == sha256_de(uno)
    assert uno.read_bytes() == dos.read_bytes(), "dos corridas, un solo fichero"
    assert d1["salida"]["sha256_archivo"] == d2["salida"]["sha256_archivo"]
    filas = uno.read_text(encoding="utf-8").count("\n")
    assert filas == d1["salida"]["claves"] + 1, "cabecera + una fila por clave"


def test_el_export_importa_mas_no_cambia_el_acta(tmp_path):
    """Exportar añade una costura; no mueve un solo sumando de la ecuacion."""
    sin = acta(FIXTURE, "telefono:digitos:ultimos10", "telefono")
    con = acta(FIXTURE, "telefono:digitos:ultimos10", "telefono", exportar=tmp_path / "x.csv")
    assert sin["ecuacion"] == con["ecuacion"]
    assert sin["cubetas"] == con["cubetas"]
    assert sin["perdidas_silenciosas"] == con["perdidas_silenciosas"]
    assert sin["salida"]["sha256"] == con["salida"]["sha256"]


def test_exportar_y_ocultar_las_claves_es_un_acto_imposible(tmp_path):
    with pytest.raises(ValueError, match="--export exige las claves"):
        acta(FIXTURE, "telefono:digitos:ultimos10", "telefono",
             con_claves=False, exportar=tmp_path / "y.csv")


def test_la_salida_de_un_acto_es_la_entrada_del_siguiente(tmp_path):
    """Dos actos encadenados: la costura se mide, no se supone."""
    paso1 = tmp_path / "paso1.csv"
    a = acta(FIXTURE, "telefono:digitos:ultimos10", "telefono", exportar=paso1)
    b = acta(paso1, "clave", "clave")

    assert b["entrada"]["sha256"] == a["salida"]["sha256_archivo"]
    assert b["ecuacion"]["dominio"] == a["cubetas"]["imagen"] == 3
    assert b["perdidas_silenciosas"] == 0
    resto_a = sum(v for k, v in a["ecuacion"].items() if k not in ("dominio", "imagen"))
    resto_b = sum(v for k, v in b["ecuacion"].items() if k not in ("dominio", "imagen"))
    assert a["ecuacion"]["dominio"] == b["ecuacion"]["imagen"] + resto_a + resto_b


VACIO_FIXTURE = Path(__file__).parent / "fixtures" / "export-vacio.csv"


def test_un_dominio_vacio_cierra_la_ecuacion_y_no_certifica_nada():
    """0 = 0 + 0 + 0 + 0 + 0 is arithmetic, not an audit.

    The residual is zero and every bucket is zero, so a receipt that only
    published the sum would report CONSERVADO over an empty population. The
    boolean is the conjunction of three factors and the failing one is named.
    """
    d = acta(VACIO_FIXTURE, "telefono:digitos:ultimos10", "telefono", validar="activo")
    assert d["perdidas_silenciosas"] == 0
    assert d["conserva_condiciones"] == {
        "cubetas_no_negativas": True,
        "dominio_no_vacio": False,
        "residuo_cero": True,
    }
    assert d["conserva"] is False
    assert (d["rc"], d["estado"]) == (VACIO, "NO_MEDIDO")
    assert "no conserva  dominio_no_vacio" in resumen(d)


def test_la_ley_se_rehace_desde_los_numeros_publicados():
    """`perdidas_silenciosas` es el residuo de las cubetas *publicadas*.

    Dos caminos: la ecuacion suma sus familias, las cubetas se cuentan cada una
    en su pasada. Si alguna vez dejan de cuadrar, el recibo miente sobre si
    mismo y nadie lo notaria leyendo solo una de las dos lineas.
    """
    for clave, crudo in [("telefono:digitos:ultimos10", "telefono"),
                         ("telefono:digitos:ultimos10", "nombre:plano:lower"),
                         ("id", None)]:
        d = acta(FIXTURE, clave, crudo=crudo, validar="activo" if crudo else None)
        assert d["perdidas_silenciosas"] == \
            d["entrada"]["filas"] - sum(d["cubetas"].values())
        assert d["conserva"] == all(d["conserva_condiciones"].values())
