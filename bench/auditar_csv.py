"""Audit a real CSV export without writing anything.

    python bench/auditar_csv.py export.csv --columna titulo --clave slug
    python bench/auditar_csv.py export.csv --columna telefono --clave digitos10

Prints the receipt as JSON and exits with its code, so it can gate a migration
in a shell pipeline. The column is both the raw key and the input of the
projection, which is what lets the receipt split the lost mass into rows the
projection merged and rows the export repeated.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ingest_conservation_guard import auditar_mapeo  # noqa: E402
from ingest_conservation_guard.casos import digitos, slug  # noqa: E402

CLAVES = {
    "slug": slug,
    "digitos": digitos,
    "digitos10": lambda t: digitos(t)[-10:],
    "tal_cual": lambda t: t,
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Certificate of conservation for a CSV column")
    p.add_argument("ruta")
    p.add_argument("--columna", required=True)
    p.add_argument("--clave", default="slug", choices=sorted(CLAVES))
    p.add_argument("--delimitador", default=",")
    args = p.parse_args(argv)

    with open(args.ruta, newline="", encoding="utf-8") as fh:
        filas = list(csv.DictReader(fh, delimiter=args.delimitador))
    if not filas or args.columna not in filas[0]:
        print(f"NO_MEDIDO: ninguna fila con la columna {args.columna!r}", file=sys.stderr)
        return 2

    clave = CLAVES[args.clave]

    def crudo(fila: dict) -> str:
        return fila[args.columna]

    recibo = auditar_mapeo(filas, lambda f: clave(crudo(f)), crudo_fn=crudo)
    print(json.dumps(recibo.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return recibo.rc


if __name__ == "__main__":
    raise SystemExit(main())
