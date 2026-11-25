"""Migracion de cartera: 8 filas del CSV, ? pacientes en la base.

Corre con:  python examples/importar_pacientes.py
"""
from ingest_conservation_guard import auditar_mapeo
from ingest_conservation_guard.casos import (
    PACIENTES, clave_paciente, paciente_valido,
)

# Lo que el importador realmente escribe (aqui simulado con un dict).
ESCRITO: dict[str, dict] = {}


def importar(registros: list[dict]) -> dict:
    recibo = auditar_mapeo(registros, clave_paciente, validar_fn=paciente_valido,
                           testigo_fn=lambda p: p["id"])
    if recibo.rc != 0:
        # No se escribe una sola fila hasta que el recibo cierre.
        print(f"ABORTA: {recibo.estado} RC={recibo.rc}")
        for c in recibo.colisiones:
            print(f"  {c.clave}: se queda {c.conservado}, se pierde {','.join(c.pisados)}")
        return recibo.as_dict()
    for p in registros:
        if paciente_valido(p):
            ESCRITO[clave_paciente(p)] = p
    return recibo.as_dict()


if __name__ == "__main__":
    print(f"filas declaradas: {len(PACIENTES)}")
    recibo = importar(PACIENTES)
    print(f"estado={recibo['estado']} RC={recibo['rc']} masa_perdida={recibo['masa_perdida']}")
    print(f"escrito en la base: {len(ESCRITO)} claves")
    print("la cuenta cuadra:", recibo["dominio"] == sum(recibo["cubetas"].values()))
