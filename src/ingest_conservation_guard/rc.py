"""Combining exit codes is a supremum, not a maximum.

The precedence order over receipts is::

    RUPTURA (4)  >  COLISION (1)  >  NO_MEDIDO / VACIO (2)  >  CONSERVADO (0)

``max`` is the wrong operator for that order: ``max(1, 2) == 2``, so a case that
measured nothing would report the run as "not measured" and let a receipt with
silent merges leave the door as a legitimate-looking code. The two orders
disagree exactly on the pair ``(1, 2)`` — the pair that matters: blindness must
never cover a measurement.

Identical contract to ``fiber_ast_lint.rc`` by design: two small packages should
not depend on each other to share 40 lines, but they must not disagree either.
Properties (tested): commutative, associative, identity ``0``, and fail-closed —
an unknown code is normalised to ``4``, never to ``0``.
"""
from __future__ import annotations

CONSERVADO, COLISION, VACIO, RUPTURA = 0, 1, 2, 4

#: Higher precedence wins. A code outside the table is a rupture.
PRECEDENCIA = {CONSERVADO: 0, VACIO: 1, COLISION: 2, RUPTURA: 3}


def normalizar(rc: int) -> int:
    """Fail-closed: an unknown code is not clean, it is a rupture."""
    return rc if rc in PRECEDENCIA else RUPTURA


def precedencia(rc: int) -> int:
    return PRECEDENCIA[normalizar(rc)]


def combinar_rc(*rcs: int) -> int:
    """Supremum of the run's codes under ``4 > 1 > 2 > 0``; empty run is ``0``."""
    if not rcs:
        return CONSERVADO
    return max((normalizar(r) for r in rcs), key=precedencia)
