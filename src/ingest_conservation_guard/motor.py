"""The audit engine.

``auditar_mapeo`` builds the fiber ledger of a projection (which records share a
key), counts every bucket in its own pass, and — when the caller hands over the
mapping it actually wrote (``mapeo``) — compares that foreign object against the
declared domain. Without ``mapeo`` the fourth bucket is a statement about the
shape of the transformation; with it, the receipt is an audit of a real write,
because the mapping comes from outside this module and can disagree.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

CONSERVADO, COLISION, RUPTURA = 0, 1, 4
ESTADOS = {
    CONSERVADO: "CONSERVADO",
    COLISION: "COLISION_SILENCIOSA",
    RUPTURA: "RUPTURA_CONSERVACION",
}


@dataclass(frozen=True)
class Colision:
    """One fiber: the key that merged, who survived, who was overwritten."""
    clave: str
    conservado: str
    pisados: tuple[str, ...]

    @property
    def masa(self) -> int:
        return len(self.pisados)

    def as_dict(self) -> dict[str, Any]:
        return {"clave": self.clave, "conservado": self.conservado,
                "pisados": list(self.pisados)}


@dataclass
class Recibo:
    dominio: int = 0
    imagen: int = 0
    rechazos: int = 0
    sin_clave: int = 0
    colisiones: list[Colision] = field(default_factory=list)
    notas: list[str] = field(default_factory=list)
    mapeo_declarado: int | None = None
    mapeo_ajeno: bool = False
    colisiones_por_proyeccion: int | None = None

    @property
    def masa_perdida(self) -> int:
        return sum(c.masa for c in self.colisiones)

    @property
    def colisiones_por_repetido(self) -> int | None:
        """Rows lost to a raw value already present, not to the projection."""
        if self.colisiones_por_proyeccion is None:
            return None
        return self.masa_perdida - self.colisiones_por_proyeccion

    @property
    def cubetas(self) -> dict[str, int]:
        return {"imagen": self.imagen, "rechazos": self.rechazos,
                "sin_clave": self.sin_clave, "colisiones": self.masa_perdida}

    @property
    def suma(self) -> int:
        return sum(self.cubetas.values())

    @property
    def descuadre(self) -> int:
        return self.dominio - self.suma

    @property
    def cubetas_negativas(self) -> dict[str, int]:
        return {k: v for k, v in self.cubetas.items() if v < 0}

    @property
    def conserva(self) -> bool:
        return self.descuadre == 0 and not self.cubetas_negativas

    @property
    def rc(self) -> int:
        if self.cubetas_negativas or self.descuadre != 0:
            return RUPTURA
        if self.mapeo_declarado is not None and (
                self.mapeo_ajeno or self.mapeo_declarado != self.imagen):
            return RUPTURA
        if self.colisiones:
            return COLISION
        return CONSERVADO

    @property
    def estado(self) -> str:
        return ESTADOS[self.rc]

    def as_dict(self) -> dict[str, Any]:
        """Deterministic: no floats, no sets, sorted keys when serialised."""
        return {
            "estado": self.estado,
            "rc": self.rc,
            "dominio": self.dominio,
            "cubetas": self.cubetas,
            "suma": self.suma,
            "descuadre": self.descuadre,
            "conserva": self.conserva,
            "masa_perdida": self.masa_perdida,
            "colisiones_por_proyeccion": self.colisiones_por_proyeccion,
            "colisiones_por_repetido": self.colisiones_por_repetido,
            "colisiones": [c.as_dict() for c in self.colisiones],
            "mapeo_declarado": self.mapeo_declarado,
            "mapeo_ajeno": self.mapeo_ajeno,
            "notas": list(self.notas),
        }


def fibra(registros: Iterable[Any], clave_fn: Callable[[Any], str]) -> dict[str, list[Any]]:
    """Groups records by their projected key, keeping every member."""
    out: dict[str, list[Any]] = {}
    for r in registros:
        k = clave_fn(r)
        if k is None or k == "":
            continue
        out.setdefault(k, []).append(r)
    return out


def auditar_mapeo(registros: Iterable[Any],
                  clave_fn: Callable[[Any], str],
                  validar_fn: Callable[[Any], bool] | None = None,
                  testigo_fn: Callable[[Any], str] | None = None,
                  mapeo: dict[str, Any] | None = None,
                  crudo_fn: Callable[[Any], str] | None = None) -> Recibo:
    """Audits the projection ``clave_fn`` over ``registros``.

    ``mapeo`` is the dict the caller actually wrote. Supplying it turns the
    receipt into an audit of a real write: a mapping that holds a key the ledger
    never produced, or that holds fewer keys than the ledger explains, is a
    rupture even though nothing raised.

    ``testigo_fn`` names a record in the receipt. Without it the receipt uses the
    position, which is stable and never ambiguous; ``list.index`` would name the
    first equal record instead of the one that was overwritten.

    ``crudo_fn`` is the key *before* the projection. With it, the lost mass is
    split in two causes that get repaired in opposite places: a member whose raw
    value no earlier member of the same fiber carried is
    ``colisiones_por_proyeccion`` — the projection folded two different things,
    so the code changes; a member repeating a raw value already seen is
    ``colisiones_por_repetido`` — the export carried the row twice, so the input
    changes. Without it both stay ``None``: the split was not measured, and that
    is not the same as zero.
    """
    regs = list(registros)
    if testigo_fn is None:
        def nombra(pos: int, r: Any) -> str:
            return f"#{pos}"
    else:
        def nombra(pos: int, r: Any) -> str:
            return testigo_fn(r)
    recibo = Recibo(dominio=len(regs))

    validos: list[tuple[int, Any]] = []
    for pos, r in enumerate(regs):
        if validar_fn is not None and not validar_fn(r):
            recibo.rechazos += 1
            continue
        validos.append((pos, r))

    ledger: dict[str, list[tuple[int, Any]]] = {}
    for pos, r in validos:
        k = clave_fn(r)
        if k is None or k == "":
            recibo.sin_clave += 1
            continue
        ledger.setdefault(k, []).append((pos, r))

    recibo.imagen = len(ledger)
    for k in sorted(ledger):
        miembros = ledger[k]
        if len(miembros) > 1:
            recibo.colisiones.append(Colision(
                clave=k,
                conservado=nombra(*miembros[0]),
                pisados=tuple(nombra(*x) for x in miembros[1:])))

    if crudo_fn is not None:
        # Distinct raw values per fiber: every extra one is a merge the
        # projection created, and the rest are rows the source repeated.
        proyeccion = 0
        for k in sorted(ledger):
            crudos = {crudo_fn(r) for _, r in ledger[k]}
            if len(crudos) > 1:
                proyeccion += len(crudos) - 1
        recibo.colisiones_por_proyeccion = proyeccion

    if mapeo is not None:
        recibo.mapeo_declarado = len(mapeo)
        ajenas = sorted(set(mapeo) - set(ledger))
        faltan = sorted(set(ledger) - set(mapeo))
        if ajenas:
            recibo.notas.append(
                f"claves en el mapeo que la proyeccion no produce: {ajenas[:5]}")
        if faltan:
            recibo.notas.append(
                f"claves producidas por la proyeccion y ausentes del mapeo: {faltan[:5]}")
        recibo.mapeo_ajeno = bool(ajenas or faltan)
        if recibo.mapeo_ajeno:
            recibo.notas.append("el mapeo no es imagen de esta proyeccion")
    return recibo


def verificar_transversal(lista_blanca: Iterable[Any],
                          clave_fn: Callable[[Any], str]) -> dict[str, Any]:
    """Is ``lista_blanca`` a transversal of the partition induced by ``clave_fn``?

    True iff no two allowed inputs share a key. A whitelist of *outputs* can
    never be one while the projection has a non-trivial fiber inside it; a
    whitelist of *inputs* is one exactly when it picks at most one representative
    per fiber.
    """
    blancos = list(lista_blanca)
    grupos: dict[str, list[Any]] = {}
    for x in blancos:
        grupos.setdefault(clave_fn(x), []).append(x)
    choques = {k: v for k, v in grupos.items() if len(v) > 1}
    return {
        "transversal": not choques,
        "permitidos": len(blancos),
        "imagenes": len(grupos),
        "nucleo": sum(len(v) - 1 for v in grupos.values()),
        "colisiones": [{"clave": k, "preimagenes": [str(x) for x in v]}
                       for k, v in sorted(choques.items())],
    }
