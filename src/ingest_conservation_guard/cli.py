"""Command line: ``ingest-conservation-guard [caso]``.

The exit code is the worst receipt of the run: 0 conserved, 1 a merge, 4 a
rupture. A tool that reports a lost record as success is worse than no tool.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .casos import caso_pacientes, caso_ruptura, caso_sku
from .motor import auditar_mapeo

CASOS: dict[str, Any] = {
    "pacientes": caso_pacientes,
    "sku": caso_sku,
    "sku-completa": lambda: caso_sku("completa"),
    "ruptura": caso_ruptura,
}


def _uno(nombre: str) -> dict[str, Any]:
    registros, clave, validar, mapeo = CASOS[nombre]()
    recibo = auditar_mapeo(registros, clave, validar_fn=validar,
                           testigo_fn=lambda p: str(p.get("id") or p.get("sku") or "?"),
                           mapeo=mapeo)
    d = recibo.as_dict()
    d["caso"] = nombre
    return d


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ingest-conservation-guard", description=__doc__)
    p.add_argument("caso", nargs="?", default="todos", choices=[*CASOS, "todos"])
    p.add_argument("--json", action="store_true", help="salida JSON determinista")
    args = p.parse_args(argv)

    nombres = list(CASOS) if args.caso == "todos" else [args.caso]
    recibos = [_uno(n) for n in nombres]
    if args.json:
        print(json.dumps(recibos, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        for d in recibos:
            print(f"{d['caso']:12s} {d['estado']:22s} RC={d['rc']}"
                  f"  dominio={d['dominio']} = imagen={d['cubetas']['imagen']}"
                  f" + rechazos={d['cubetas']['rechazos']}"
                  f" + sin_clave={d['cubetas']['sin_clave']}"
                  f" + colisiones={d['cubetas']['colisiones']}")
            for c in d["colisiones"]:
                print(f"    COLISION clave={c['clave']} conservado={c['conservado']}"
                      f" pisados={','.join(c['pisados'])}")
            for nota in d["notas"]:
                print(f"    NOTA {nota}")
    rc = max(d["rc"] for d in recibos)
    if rc == 4:
        print("RUPTURA: el recibo no conserva el dominio declarado", file=sys.stderr)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
