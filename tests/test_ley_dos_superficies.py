"""The law is published on two surfaces and both must answer the same.

``Recibo.as_dict()`` is the library surface; the acta is the receipt. Both
publish ``conserva`` and its three factors, and they compute them by different
paths on purpose: the recibo collapses the loss into the single ``colisiones``
bucket, while the acta re-derives the residual from the raw split
(``colisiones_por_proyeccion + colisiones_por_repetido``). Two implementations
of one law are only safe while something compares them -- mutant evidence: with
``Recibo.conserva`` reduced to ``residuo_cero`` the whole suite stayed green,
while the library would have published ``conserva: true`` over an empty domain.
"""

from __future__ import annotations

import pathlib

import pytest

from ingest_conservation_guard.acta import acta, cargar, proyector
from ingest_conservation_guard.motor import auditar_mapeo

CLAVE = "telefono:digitos:ultimos10"
CRUDO = "telefono"
FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _recibo_dict(ruta: pathlib.Path) -> dict:
    """The library surface over the same file, without ``--validar``."""
    return auditar_mapeo(
        cargar(ruta), proyector(CLAVE), crudo_fn=proyector(CRUDO),
        testigo_fn=lambda r: str(next(iter(r.values()), "?")),
    ).as_dict()


@pytest.mark.parametrize("nombre", ["export-vacio.csv", "migracion.csv"])
def test_las_dos_superficies_publican_la_misma_ley(nombre: str) -> None:
    ruta = FIXTURES / nombre
    documento = acta(ruta, CLAVE, CRUDO)
    recibo = _recibo_dict(ruta)

    assert recibo["condiciones"] == documento["conserva_condiciones"]
    assert recibo["conserva"] == documento["conserva"]
    assert documento["conserva"] == all(documento["conserva_condiciones"].values())


def test_el_dominio_vacio_es_el_unico_caso_donde_difieren_de_un_pase() -> None:
    """Both surfaces say ``false``, and the factor both name is the same one."""
    ruta = FIXTURES / "export-vacio.csv"
    documento = acta(ruta, CLAVE, CRUDO)
    recibo = _recibo_dict(ruta)

    assert recibo["conserva"] is False
    assert documento["conserva"] is False
    assert recibo["condiciones"]["dominio_no_vacio"] is False
    assert documento["conserva_condiciones"]["dominio_no_vacio"] is False
    assert recibo["descuadre"] == documento["perdidas_silenciosas"] == 0
