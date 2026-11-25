"""Three executable cases, kept in the package so an installed wheel can run them.

They are the same three situations the law exists for, in the domain where the
loss is expensive: a patient/customer import, a catalogue sync, and a writer that
silently drops a record.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable


def _plano(texto: str) -> str:
    """Accents out, lowercase, single spaces: the projection every import uses."""
    sin = unicodedata.normalize("NFKD", texto)
    sin = "".join(c for c in sin if not unicodedata.combining(c))
    return " ".join(sin.lower().split())


def slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _plano(texto)).strip("-")


def digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto)


def clave_paciente(p: dict[str, Any]) -> str:
    """Name plus the last ten digits: the normalisation a CRM migration does."""
    return f"{slug(p['nombre'])}|{digitos(p['telefono'])[-10:]}"


def paciente_valido(p: dict[str, Any]) -> bool:
    return bool(p.get("nombre")) and len(digitos(p.get("telefono", ""))) >= 10


PACIENTES: list[dict[str, Any]] = [
    {"id": "A-1", "nombre": "José Ramírez", "telefono": "+52 777 123 4567"},
    {"id": "A-2", "nombre": "Jose  Ramirez", "telefono": "7771234567"},
    {"id": "A-3", "nombre": "María López", "telefono": "(777) 555 0101"},
    {"id": "A-4", "nombre": "Ana Ruiz", "telefono": "+52 777 555 0199"},
    {"id": "A-5", "nombre": "  ana  ruiz ", "telefono": "777-555-0199"},
    {"id": "A-6", "nombre": "Beto Sansón", "telefono": "777 000 1111"},
    {"id": "A-7", "nombre": "", "telefono": "777 000 2222"},
    {"id": "A-8", "nombre": "Carla Núñez", "telefono": ""},
]

CATALOGO: list[dict[str, Any]] = [
    {"sku": "CAM-MR-BL-M", "nombre": "Camisa Moon & Rain Blanca", "talla": "M"},
    {"sku": "CAM-MR-BL-L", "nombre": "Camisa Moon & Rain Blanca", "talla": "L"},
    {"sku": "CUA-MR-AZ", "nombre": "Cuadro Moon & Rain Azul", "talla": ""},
]


def clave_sku_por_nombre(item: dict[str, Any]) -> str:
    """The bug: two sizes of the same shirt are one slug."""
    return slug(item["nombre"])


def clave_sku_completa(item: dict[str, Any]) -> str:
    return f"{slug(item['nombre'])}-{slug(item['talla'])}".rstrip("-")


def clave_sin_normalizar(p: dict[str, Any]) -> str:
    """No projection at all: the identity of the row is its own key."""
    return str(p["id"])


def caso_pacientes() -> tuple[list[dict[str, Any]], Callable, Callable, None]:
    return PACIENTES, clave_paciente, paciente_valido, None


def caso_sku(proyeccion: str = "nombre") -> tuple[list[dict[str, Any]], Callable, None, None]:
    clave = clave_sku_por_nombre if proyeccion == "nombre" else clave_sku_completa
    return CATALOGO, clave, None, None


def caso_ruptura() -> tuple[list[dict[str, Any]], Callable, None, dict[str, Any]]:
    """A writer that reports six keys and stores five: one row vanished."""
    mapeo = {clave_paciente(p): p for p in PACIENTES}
    mapeo.pop(clave_paciente(PACIENTES[5]))  # Beto Sanson nunca llega a la base
    return PACIENTES, clave_paciente, None, mapeo
