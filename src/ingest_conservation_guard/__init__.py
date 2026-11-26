"""Receipts for data ingestion: does the declared domain survive the transform?

Every migration, catalogue sync or API ingest is a function from a declared
population to a stored one. The failure this package exists for is not a crash:
it is a *silent merge* — two distinct records projected onto one key, one of them
overwritten, no error raised, and a final count that looks plausible.

The law, with strict positivity:

    dominio_declarado == imagen + rechazos + sin_clave + colisiones
    toda cubeta >= 0

A bucket defined by subtraction closes in the integers even when the counts are
incompatible (``68 + 0 + (-1) = 67``): the arithmetic agrees and the census lies.
That is why every bucket is counted by its own pass and why the positivity check
is not optional.
"""
from .motor import Colision, Recibo, auditar_mapeo, fibra, verificar_transversal
from .rc import combinar_rc, precedencia

__version__ = "0.4.4"
__all__ = ["Colision", "Recibo", "auditar_mapeo", "fibra", "verificar_transversal",
           "combinar_rc", "precedencia", "__version__"]
