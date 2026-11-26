"""El recibo se confirma con shasum y wc, sin nuestro binario.

Publicar una tabla que sólo nuestro código puede reproducir deja al auditor del
cliente instalando el instrumento que viene a auditar. Estas tres celdas se
miden con las herramientas del sistema, y por eso el README puede publicarlas.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from ingest_conservation_guard.acta import acta

RAIZ = Path(__file__).resolve().parents[1]
README = (RAIZ / "README.md").read_text(encoding="utf-8")
FIXTURE = RAIZ / "tests" / "fixtures" / "migracion.csv"

SHA_ENTRADA = "d706d9297093104b22c20301e2e74f92ff83f2c5352c6ea6e4326c7108935581"
SHA_ARCHIVO = "ede784ce0813c547178cf900cf1e3e9fa5b963f38b83c03ffb0803d03105b042"


def _sha(ruta: Path) -> str:
    return subprocess.run(["shasum", "-a", "256", str(ruta)], capture_output=True,
                          text=True, check=True).stdout.split()[0]


def _lineas(ruta: Path) -> int:
    with ruta.open("rb") as fh:
        return int(subprocess.run(["wc", "-l"], stdin=fh, capture_output=True,
                                  text=True, check=True).stdout.split()[0])


def _acto(tmp_path: Path) -> dict:
    return acta(FIXTURE, clave="telefono:digitos:ultimos10", crudo="telefono",
                exportar=tmp_path / "paso1.csv")


def test_el_digest_de_entrada_lo_reproduce_shasum():
    assert _sha(FIXTURE) == SHA_ENTRADA


def test_el_digest_del_artefacto_lo_reproduce_shasum(tmp_path):
    documento = _acto(tmp_path)
    assert _sha(tmp_path / "paso1.csv") == documento["salida"]["sha256_archivo"]
    assert documento["salida"]["sha256_archivo"] == SHA_ARCHIVO


def test_el_artefacto_tiene_exactamente_las_claves_que_declara(tmp_path):
    documento = _acto(tmp_path)
    assert _lineas(tmp_path / "paso1.csv") == documento["salida"]["claves"] + 1


def test_la_ecuacion_se_suma_con_los_cinco_destinos(tmp_path):
    ecuacion = _acto(tmp_path)["ecuacion"]
    destinos = {k: v for k, v in ecuacion.items() if k != "dominio"}
    assert sum(destinos.values()) == ecuacion["dominio"]
    assert ecuacion["dominio"] == 6 and ecuacion["imagen"] == 3


def test_los_digests_publicados_son_los_medidos():
    assert "### Verifying a receipt without our code" in README
    assert SHA_ENTRADA in README, "el README publica un digest de entrada que shasum no da"
    assert SHA_ARCHIVO in README, "el README publica un digest de salida que shasum no da"
    assert "4` = 3 claves + cabecera" in README, "la celda de wc -l no está publicada"
