"""Re-derive `censo.json` from the export it names.

The census pins a file by SHA-256, and this script is the reader that makes the
pin worth something: it fetches the file, refuses to measure anything if the
digest is not the pinned one, and then recomputes every cell of the published
table -- output digest included.

    python bench/replay_censo.py                  # temp dir, deleted at the end
    python bench/replay_censo.py --dir /tmp/censo --keep
    python bench/replay_censo.py --csv local.csv  # no network
    python bench/replay_censo.py --escribir       # re-derive and write the census back

Exit codes follow the ladder the package already uses, extended with the case
where the premise itself broke:

    0  every row reproduced exactly
    1  a published cell did not reproduce
    2  NO_MEDIDO -- the export could not be obtained, nothing was checked
    4  the pin ruptured -- the bytes on disk are not the export the census names,
       so no divergence below them can be interpreted
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from ingest_conservation_guard.acta import acta  # noqa: E402
from ingest_conservation_guard import __version__  # noqa: E402
from ingest_conservation_guard.rc import (  # noqa: E402
    COLISION, RUPTURA, VACIO, combinar_rc)

CENSO = RAIZ / "censo.json"
UA = {"User-Agent": "ingest-conservation-guard-censo-replay/1"}

# The verdicts are this package's own codes, not a private ladder: a divergent
# cell is a COLISION, a missing export is VACIO, a broken pin is RUPTURA, and the
# operator is the one the CLI already uses so two rows compose as they do there.
OK, DIVERGE, NO_MEDIDO = 0, COLISION, VACIO
VEREDICTO = {OK: "REPLAY IDENTICO", DIVERGE: "REPLAY CON DIVERGENCIA",
             NO_MEDIDO: "NO_MEDIDO", RUPTURA: "PIN ROTO"}


def _descargar(url: str, destino: Path) -> int:
    peticion = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(peticion, timeout=120) as r, destino.open("wb") as f:
            shutil.copyfileobj(r, f)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"  NO_MEDIDO: no se pudo descargar el export: {exc}")
        return NO_MEDIDO
    return OK


def _medir(ruta: Path, fila: dict) -> dict:
    d = acta(ruta, fila["projection"], crudo=fila["raw_key"],
             nombre_caso=fila["projection"])
    e = d["ecuacion"] or {}
    cubetas = d["cubetas"]
    return {
        "domain": d["entrada"]["filas"],
        "image": cubetas["imagen"],
        "by_projection": e.get("colisiones_por_proyeccion"),
        "by_repeated_row": e.get("colisiones_por_repetido"),
        "rejects": cubetas["rechazos"],
        "no_key": cubetas["sin_clave"],
        "silent_losses": d["perdidas_silenciosas"],
        "rc": d["rc"],
        "state": d["estado"],
        "output_sha256": d["salida"]["sha256"],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Replay the ingest census from its export.")
    ap.add_argument("--dir", help="cache directory (default: a temporary one)")
    ap.add_argument("--keep", action="store_true", help="do not delete the cache")
    ap.add_argument("--csv", help="use this file instead of downloading the pinned one")
    ap.add_argument("--censo", help="read this census file instead of ./censo.json")
    ap.add_argument("--escribir", action="store_true",
                    help="write the measured rows and the running instrument version back")
    a = ap.parse_args(argv)

    censo = json.loads(Path(a.censo or CENSO).read_text(encoding="utf-8"))
    datos = censo["dataset"]

    propio = a.dir is None and not a.csv
    base = Path(a.dir) if a.dir else Path(tempfile.mkdtemp(prefix="censo-"))
    base.mkdir(parents=True, exist_ok=True)
    ruta = Path(a.csv) if a.csv else base / "export.csv"

    try:
        if not a.csv:
            rc = _descargar(datos["source"], ruta)
            if rc:
                print(f"\n{VEREDICTO[rc]} · 0 filas medidas")
                return rc

        real = hashlib.sha256(ruta.read_bytes()).hexdigest()
        if real != datos["sha256"]:
            print(f"  RUPTURA: sha256 {real[:16]} != pin {datos['sha256'][:16]}")
            print(f"           el fichero mide {ruta.stat().st_size} B, el pin "
                  f"declara {datos['bytes']} B")
            print(f"\n{VEREDICTO[RUPTURA]} · 0 filas medidas")
            return RUPTURA
        print(f"export verificado: {datos['name']} {datos['bytes']} B {real[:16]}...")

        peor = OK
        medidas_por_fila = []
        for fila in censo["rows"]:
            medidas = _medir(ruta, fila)
            nueva = {"projection": fila["projection"], "raw_key": fila["raw_key"]}
            nueva.update({k: medidas[k] for k in fila if k in medidas})
            medidas_por_fila.append(nueva)
            difs = {k: (medidas[k], fila.get(k)) for k in medidas if medidas[k] != fila.get(k)}
            if difs:
                print(f"  DIVERGE {fila['projection']}: "
                      + ", ".join(f"{k} medido={m} pin={p}" for k, (m, p) in difs.items()))
                peor = combinar_rc(peor, DIVERGE)
            else:
                print(f"  identico {fila['projection']}: "
                      + " ".join(f"{k}={v}" for k, v in medidas.items()))

        if a.escribir:
            if peor != OK:
                print("  ESCRITURA NEGADA: un censo divergente no se escribe; "
                      "se mide, o se declara la ruptura del pin")
            else:
                destino = Path(a.censo or CENSO)
                nuevo = dict(censo)
                nuevo["instrument_version"] = __version__
                nuevo["measured_at"] = datetime.date.today().isoformat()
                nuevo["status"] = ("MEDIDO_EN_FIXTURE" if a.csv
                                   else "MEDIDO_EN_EXPORTACION_PUBLICA")
                nuevo["rows"] = medidas_por_fila
                destino.write_text(json.dumps(nuevo, indent=2, ensure_ascii=False) + "\n",
                                   encoding="utf-8")
                print(f"  ESCRITO {destino} · instrumento {__version__}"
                      f" · {len(medidas_por_fila)} filas")

        pineada = censo["instrument_version"]
        deriva = "" if pineada == __version__ else f" (censo pineado a {pineada})"
        print(f"\n{VEREDICTO[peor]} · {len(censo['rows'])} filas"
              f" · instrumento {__version__}{deriva}"
              f" · estado {censo['status']}")
        return peor
    finally:
        if propio:
            shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
