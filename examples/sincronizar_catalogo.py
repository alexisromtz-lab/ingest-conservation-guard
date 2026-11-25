"""Catalogo: dos tallas de la misma camisa, una sola clave.

Corre con:  python examples/sincronizar_catalogo.py
"""
from ingest_conservation_guard import auditar_mapeo
from ingest_conservation_guard.casos import (
    CATALOGO, clave_sku_completa, clave_sku_por_nombre,
)


def comparar(nombre: str, clave) -> None:
    r = auditar_mapeo(CATALOGO, clave, testigo_fn=lambda i: i["sku"])
    print(f"{nombre:10s} RC={r.rc} {r.estado:22s} SKU de origen={r.dominio}"
          f" -> SKU sincronizados={r.imagen}")
    for c in r.colisiones:
        print(f"    {c.clave}: sobrevive {c.conservado}, se pierde {','.join(c.pisados)}")


if __name__ == "__main__":
    comparar("por-nombre", clave_sku_por_nombre)
    comparar("completa", clave_sku_completa)
