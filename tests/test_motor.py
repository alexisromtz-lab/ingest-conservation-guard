import json

from ingest_conservation_guard import Recibo, auditar_mapeo, fibra, verificar_transversal
from ingest_conservation_guard.casos import (
    PACIENTES, caso_pacientes, caso_ruptura, caso_sku, clave_paciente, clave_sku_completa,
    clave_sku_por_nombre, slug,
)


def test_conservacion_cierra_en_el_caso_de_pacientes():
    registros, clave, validar, _ = caso_pacientes()
    r = auditar_mapeo(registros, clave, validar_fn=validar,
                      testigo_fn=lambda p: p["id"])
    assert r.dominio == 8
    assert r.cubetas == {"imagen": 4, "rechazos": 2, "sin_clave": 0, "colisiones": 2}
    assert r.dominio == r.suma
    assert not r.cubetas_negativas
    assert r.masa_perdida == 2
    assert r.rc == 1
    assert r.estado == "COLISION_SILENCIOSA"


def test_testigos_nombran_al_pisado_y_no_al_igual():
    registros, clave, validar, _ = caso_pacientes()
    r = auditar_mapeo(registros, clave, validar_fn=validar,
                      testigo_fn=lambda p: p["id"])
    por_clave = {c.clave: c for c in r.colisiones}
    assert por_clave["ana-ruiz|7775550199"].conservado == "A-4"
    assert por_clave["ana-ruiz|7775550199"].pisados == ("A-5",)
    assert por_clave["jose-ramirez|7771234567"].pisados == ("A-2",)


def test_sin_testigo_la_posicion_es_estable():
    r = auditar_mapeo([{"k": "x"}, {"k": "x"}], lambda d: d["k"])
    assert r.colisiones[0].conservado == "#0"
    assert r.colisiones[0].pisados == ("#1",)


def test_proyeccion_inyectiva_conserva():
    registros, clave, _, _ = caso_sku("completa")
    r = auditar_mapeo(registros, clave, testigo_fn=lambda i: i["sku"])
    assert clave is clave_sku_completa
    assert r.rc == 0
    assert r.estado == "CONSERVADO"
    assert r.imagen == 3 and r.colisiones == []


def test_dos_tallas_del_mismo_nombre_son_una_clave():
    registros, clave, _, _ = caso_sku()
    r = auditar_mapeo(registros, clave, testigo_fn=lambda i: i["sku"])
    assert clave is clave_sku_por_nombre
    assert r.imagen == 2 and r.dominio == 3
    assert r.colisiones[0].clave == slug("Camisa Moon & Rain Blanca")
    assert r.rc == 1


def test_mapeo_que_pierde_una_fila_es_ruptura():
    registros, clave, _, mapeo = caso_ruptura()
    r = auditar_mapeo(registros, clave, mapeo=mapeo)
    assert r.mapeo_ajeno
    assert r.mapeo_declarado == 5
    assert r.rc == 4
    assert r.estado == "RUPTURA_CONSERVACION"
    assert any("ausentes del mapeo" in n for n in r.notas)


def test_mapeo_con_clave_ajena_es_ruptura():
    mapeo = {"inventada": 1, "ana-ruiz|7775550199": 2}
    r = auditar_mapeo(PACIENTES[:5], clave_paciente, mapeo=mapeo)
    assert r.mapeo_ajeno
    assert r.rc == 4
    assert any("no produce" in n for n in r.notas)


def test_cubeta_negativa_no_cierra_el_recibo():
    # 68 + 0 + (-1) = 67: la aritmetica cuadra y el censo miente.
    r = Recibo(dominio=67, imagen=68, sin_clave=-1)
    assert r.dominio == r.suma
    assert r.cubetas_negativas == {"sin_clave": -1}
    assert r.rc == 4


def test_rechazos_y_sin_clave_se_cuentan_aparte():
    registros = [{"n": "a"}, {"n": ""}, {"n": "b"}]
    r = auditar_mapeo(registros, lambda d: d["n"],
                      validar_fn=lambda d: d["n"] != "a")
    assert r.dominio == 3
    assert r.rechazos == 1
    assert r.sin_clave == 1
    assert r.imagen == 1
    assert r.dominio == r.suma
    assert r.rc == 0


def test_recibo_es_determinista():
    a = auditar_mapeo(PACIENTES, clave_paciente, testigo_fn=lambda p: p["id"]).as_dict()
    b = auditar_mapeo(PACIENTES, clave_paciente, testigo_fn=lambda p: p["id"]).as_dict()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert json.loads(json.dumps(a, sort_keys=True))["cubetas"]["imagen"] == 6


def test_fibra_agrupa_sin_perder():
    f = fibra(PACIENTES[:5], clave_paciente)
    assert sorted(len(v) for v in f.values()) == [1, 2, 2]
    assert sum(len(v) for v in f.values()) == 5


def test_lista_blanca_de_salidas_no_es_transversal():
    # Una lista blanca de nombres permitidos se lee como guarda, pero sobre las
    # entradas deja dos fibras completas dentro: "jose ramirez" y "ana ruiz"
    # aparecen dos veces cada una.
    nombres = {slug(p["nombre"]) for p in PACIENTES[:5]}
    permitidos = [p for p in PACIENTES[:5] if slug(p["nombre"]) in nombres]
    assert len(permitidos) == 5
    v = verificar_transversal(permitidos, lambda p: slug(p["nombre"]))
    assert v["transversal"] is False
    assert v["imagenes"] == 3 and v["permitidos"] == 5
    assert v["nucleo"] == 2
    assert [c["clave"] for c in v["colisiones"]] == ["ana-ruiz", "jose-ramirez"]


def test_lista_blanca_de_entradas_inyectiva_es_transversal():
    permitidos = [PACIENTES[0], PACIENTES[2], PACIENTES[5]]
    v = verificar_transversal(permitidos, clave_paciente)
    assert v["transversal"] is True
    assert v["nucleo"] == 0


def test_sin_crudo_la_particion_de_la_masa_es_no_medida():
    registros, clave, _, _ = caso_sku()
    r = auditar_mapeo(registros, clave)
    assert r.colisiones_por_proyeccion is None
    assert r.colisiones_por_repetido is None
    assert r.as_dict()["colisiones_por_proyeccion"] is None


def test_la_masa_perdida_se_parte_en_proyeccion_y_repetido():
    # Two identical titles are the export repeating a row; "camisa-blanca" is a
    # different raw string that the slug folds onto the same key.
    filas = [{"titulo": "Camisa Blanca"}, {"titulo": "Camisa Blanca"},
             {"titulo": "camisa-blanca"}]
    r = auditar_mapeo(filas, lambda f: slug(f["titulo"]),
                      crudo_fn=lambda f: f["titulo"])
    assert r.masa_perdida == 2
    assert r.colisiones_por_proyeccion == 1
    assert r.colisiones_por_repetido == 1
    assert r.colisiones_por_proyeccion + r.colisiones_por_repetido == r.masa_perdida
    assert r.rc == 1


def test_una_exportacion_con_filas_repetidas_no_acusa_a_la_proyeccion():
    filas = [{"titulo": "Camisa Blanca"}] * 4
    r = auditar_mapeo(filas, lambda f: slug(f["titulo"]),
                      crudo_fn=lambda f: f["titulo"])
    assert r.masa_perdida == 3
    assert r.colisiones_por_proyeccion == 0
    assert r.colisiones_por_repetido == 3
