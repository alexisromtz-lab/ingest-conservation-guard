import json
import subprocess
import sys

from ingest_conservation_guard.cli import main


def test_sku_completa_sale_en_cero():
    assert main(["sku-completa"]) == 0


def test_sku_por_nombre_reporta_la_colision():
    assert main(["sku"]) == 1


def test_la_ruptura_manda_sobre_la_colision():
    assert main(["ruptura"]) == 4


def test_caso_desconocido_no_admite_arranque():
    try:
        main(["inventado"])
    except SystemExit as e:
        assert e.code == 2
    else:
        raise AssertionError("argparse debe rechazar un caso desconocido")


def test_json_es_parseable_y_lleva_el_caso(capsys):
    main(["pacientes", "--json"])
    salida = json.loads(capsys.readouterr().out)
    assert salida[0]["caso"] == "pacientes"
    assert salida[0]["rc"] == 1


def test_modulo_ejecutable_sin_pythonpath_previo():
    # El wheel tiene que traer el punto de entrada, no depender de PYTHONPATH.
    proc = subprocess.run([sys.executable, "-m", "ingest_conservation_guard", "sku-completa"],
                          capture_output=True, text=True,
                          env={"PYTHONPATH": "src", "PATH": "/usr/bin:/bin"})
    assert proc.returncode == 0, proc.stderr
    assert "CONSERVADO" in proc.stdout
