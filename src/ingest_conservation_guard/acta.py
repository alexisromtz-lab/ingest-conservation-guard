"""Migration certificate: a receipt of an ingest anybody can re-check.

``acta`` reads a real tabular export (CSV or JSON), applies a declared key
projection to every row, and emits one deterministic document that closes the
accounting identity

    dominio == imagen + colisiones_por_proyeccion + colisiones_por_repetido
               + rechazos + sin_clave

with ``perdidas_silenciosas`` computed as the residual of that equation, never
asserted. A non-zero residual is a rupture (RC 4), not a rounding issue: it means
rows entered the export and no bucket accounts for them.

Both ends of the act are digested with SHA-256, so the certificate names the
bytes it audited and the image it produced. It carries no data values beyond the
keys that collided, and the keys themselves can be withheld with
``--sin-claves`` when they are personal data.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import unicodedata
from pathlib import Path
from typing import Any, Callable

from .motor import auditar_mapeo

ACTA_RC_RUPTURA = 4


def _plano(texto: str) -> str:
    """Accents off: 'Jose' and 'José' must land on the same key, or the act lies."""
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def _slug(texto: str) -> str:
    limpio = _plano(texto).lower()
    salida = [c if c.isalnum() else "-" for c in limpio]
    return "-".join(p for p in "".join(salida).split("-") if p)


TRANSFORMAS: dict[str, Callable[[str], str]] = {
    "identidad": lambda v: v,
    "strip": lambda v: v.strip(),
    "lower": lambda v: v.lower(),
    "upper": lambda v: v.upper(),
    "plano": _plano,
    "slug": _slug,
    "digitos": lambda v: "".join(c for c in v if c.isdigit()),
    "ultimos10": lambda v: "".join(c for c in v if c.isdigit())[-10:],
}


def sha256_de(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def sha256_de_json(objeto: Any) -> str:
    canonico = json.dumps(objeto, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def cargar(ruta: Path) -> list[dict[str, Any]]:
    """CSV by suffix, JSON otherwise. Both become a list of flat dicts."""
    texto = ruta.read_text(encoding="utf-8-sig")
    if ruta.suffix.lower() == ".csv":
        filas = list(csv.DictReader(io.StringIO(texto)))
        return [dict(f) for f in filas]
    datos = json.loads(texto)
    if isinstance(datos, dict):
        datos = datos.get("registros", datos.get("rows", []))
    if not isinstance(datos, list):
        raise ValueError("el JSON debe ser una lista de objetos")
    return [dict(d) for d in datos]


def proyector(espec: str) -> Callable[[dict[str, Any]], str]:
    """``campo`` or ``campo:trans1:trans2``. Unknown transforms are a hard error.

    Silently ignoring a misspelt transform would audit a different projection
    than the one the certificate names -- the exact failure this package exists
    to catch, one level up.
    """
    partes = espec.split(":")
    campo, nombres = partes[0], partes[1:] or ["identidad"]
    for n in nombres:
        if n not in TRANSFORMAS:
            raise ValueError(f"transformacion desconocida: {n!r} "
                             f"(validas: {', '.join(sorted(TRANSFORMAS))})")
    pasos = [TRANSFORMAS[n] for n in nombres]

    def aplica(registro: dict[str, Any]) -> str:
        valor = registro.get(campo)
        if valor is None:
            return ""
        texto = str(valor)
        for paso in pasos:
            texto = paso(texto)
        return texto

    return aplica


def _verdadero(valor: Any) -> bool:
    return str(valor).strip().lower() not in ("", "0", "false", "no", "n", "")


def acta(ruta: Path, clave: str, crudo: str | None = None,
         validar: str | None = None, con_claves: bool = True,
         nombre_caso: str | None = None) -> dict[str, Any]:
    registros = cargar(ruta)
    clave_fn = proyector(clave)
    crudo_fn = proyector(crudo) if crudo else None
    validar_fn = (lambda r: _verdadero(r.get(validar))) if validar else None

    recibos = auditar_mapeo(registros, clave_fn, validar_fn=validar_fn,
                            crudo_fn=crudo_fn,
                            testigo_fn=lambda r: str(next(iter(r.values()), "?")))
    d = recibos.as_dict()

    imagen: dict[str, str] = {}
    for r in registros:
        if validar_fn is not None and not validar_fn(r):
            continue
        k = clave_fn(r)
        if not k:
            continue
        imagen.setdefault(k, str(next(iter(r.values()), "?")))

    proy = d["colisiones_por_proyeccion"]
    repe = d["colisiones_por_repetido"]
    if proy is None or repe is None:
        # Without the raw key the split was not measured; the identity still has
        # to close over the total, so the certificate declares the split absent.
        perdidas = recibos.dominio - (d["cubetas"]["imagen"] + d["cubetas"]["rechazos"]
                                      + d["cubetas"]["sin_clave"] + d["cubetas"]["colisiones"])
        ecuacion = None
    else:
        perdidas = recibos.dominio - (d["cubetas"]["imagen"] + d["cubetas"]["rechazos"]
                                      + d["cubetas"]["sin_clave"] + proy + repe)
        ecuacion = {
            "dominio": recibos.dominio,
            "imagen": d["cubetas"]["imagen"],
            "colisiones_por_proyeccion": proy,
            "colisiones_por_repetido": repe,
            "rechazos": d["cubetas"]["rechazos"],
            "sin_clave": d["cubetas"]["sin_clave"],
        }

    documento: dict[str, Any] = {
        "acta": "migracion",
        "caso": nombre_caso or ruta.name,
        "estado": d["estado"],
        "rc": d["rc"] if perdidas == 0 else ACTA_RC_RUPTURA,
        "entrada": {"archivo": ruta.name, "sha256": sha256_de(ruta), "filas": recibos.dominio},
        "proyeccion": {"clave": clave, "crudo": crudo, "validar": validar},
        "ecuacion": ecuacion,
        "cubetas": d["cubetas"],
        "perdidas_silenciosas": perdidas,
        "conserva": perdidas == 0 and d["conserva"],
        "salida": {"claves": len(imagen), "sha256": sha256_de_json(imagen)},
        "colisiones": d["colisiones"] if con_claves else [
            {"clave": "<omitida>", "conservado": c["conservado"], "pisados": c["pisados"]}
            for c in d["colisiones"]],
    }
    if perdidas != 0:
        documento["notas"] = ["el residuo de la ecuacion no es cero: hay filas sin cubeta"]
    return documento


def resumen(d: dict[str, Any]) -> str:
    """The same act, one line per fact, for a human signing it."""
    e = d["ecuacion"]
    lineas = [
        f"ACTA DE MIGRACION  {d['caso']}",
        f"  entrada   {d['entrada']['archivo']}  filas={d['entrada']['filas']}"
        f"  sha256={d['entrada']['sha256'][:16]}...",
        f"  clave     {d['proyeccion']['clave']}"
        + (f"  crudo={d['proyeccion']['crudo']}" if d["proyeccion"]["crudo"] else ""),
    ]
    if e is None:
        lineas.append("  ecuacion  NO_MEDIDA (falta --crudo para separar las dos causas)")
    else:
        lineas.append(
            f"  ecuacion  {e['dominio']} = {e['imagen']} + {e['colisiones_por_proyeccion']}"
            f" + {e['colisiones_por_repetido']} + {e['rechazos']} + {e['sin_clave']}")
    lineas += [
        f"  perdidas  {d['perdidas_silenciosas']}",
        f"  salida    claves={d['salida']['claves']}  sha256={d['salida']['sha256'][:16]}...",
        f"  estado    {d['estado']}  RC={d['rc']}",
    ]
    for c in d["colisiones"]:
        lineas.append(f"  COLISION  {c['clave']} conservado={c['conservado']}"
                      f" pisados={','.join(c['pisados'])}")
    return "\n".join(lineas)
