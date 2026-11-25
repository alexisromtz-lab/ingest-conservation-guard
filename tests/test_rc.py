"""Combining receipts: the supremum of ``4 > 1 > 2 > 0``, never ``max``.

The defect this file pins: ``max(1, 2) == 2``, so a case that measured nothing
would report the run as "not measured" while another case had silent merges.
"""
from __future__ import annotations

import itertools

import pytest

from ingest_conservation_guard import cli
from ingest_conservation_guard.rc import combinar_rc, normalizar, precedencia

CODIGOS = (0, 1, 2, 4)


def test_el_par_que_discrepa_de_max():
    assert combinar_rc(1, 2) == 1
    assert combinar_rc(2, 1) == 1
    assert combinar_rc(2, 0) == 2
    assert combinar_rc(4, 1) == 4


def test_conmutativa_y_asociativa():
    for a, b in itertools.product(CODIGOS, repeat=2):
        assert combinar_rc(a, b) == combinar_rc(b, a)
    for a, b, c in itertools.product(CODIGOS, repeat=3):
        assert combinar_rc(combinar_rc(a, b), c) == combinar_rc(a, combinar_rc(b, c))


def test_neutro_e_idempotencia():
    for a in CODIGOS:
        assert combinar_rc(a, 0) == a
        assert combinar_rc(a, a) == a
    assert combinar_rc() == 0


def test_precedencia_declarada():
    assert precedencia(4) > precedencia(1) > precedencia(2) > precedencia(0)


@pytest.mark.parametrize("ajeno", [3, 9, -1, 127])
def test_codigo_desconocido_es_ruptura(ajeno):
    assert normalizar(ajeno) == 4
    assert combinar_rc(0, ajeno) == 4


def test_el_cli_no_enmascara_una_colision_con_un_vacio(monkeypatch):
    """End-to-end: receipt 1 must survive a receipt 2 in the same run."""
    recibos = {"sin_datos": {"rc": 2}, "con_merge": {"rc": 1}}
    monkeypatch.setattr(cli, "CASOS", {k: (lambda: ()) for k in recibos})
    monkeypatch.setattr(cli, "_uno", lambda nombre: {
        "caso": nombre, "estado": "X", "rc": recibos[nombre]["rc"],
        "dominio": 0, "cubetas": {"imagen": 0, "rechazos": 0,
                                  "sin_clave": 0, "colisiones": 0},
        "colisiones": [], "notas": []})
    assert cli.main(["todos"]) == 1
