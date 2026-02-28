"""
Carga y cacheo de esquemas JSON de formatos posicionales.
"""
import json
from pathlib import Path
from functools import lru_cache

import config


@lru_cache(maxsize=16)
def cargar_esquema(tipo: str, operacion: str) -> dict:
    """
    Carga un esquema JSON desde el filesystem.
    
    Args:
        tipo: 'AT' o 'EP'
        operacion: 'A' (alta) o 'B' (baja)
    
    Returns:
        Dict con metadata y campos del esquema
    
    Raises:
        FileNotFoundError: Si el esquema no existe
        ValueError: Si el tipo u operación no son válidos
    """
    tipo = tipo.upper()
    operacion = operacion.upper()
    
    if tipo not in ("AT", "EP"):
        raise ValueError(f"Tipo inválido: {tipo}. Debe ser 'AT' o 'EP'.")
    if operacion not in ("A", "B"):
        raise ValueError(f"Operación inválida: {operacion}. Debe ser 'A' (alta) o 'B' (baja).")
    
    operacion_nombre = "alta" if operacion == "A" else "baja"
    norma = "3326" if tipo == "AT" else "3327"
    
    nombre_archivo = f"{tipo.lower()}_{norma}_{operacion_nombre}.json"
    ruta = config.SCHEMAS_PATH / nombre_archivo
    
    if not ruta.exists():
        raise FileNotFoundError(
            f"Esquema no encontrado: {ruta}. "
            f"Asegurate de haber creado el archivo en schemas/"
        )
    
    with open(ruta, "r", encoding="utf-8") as f:
        esquema = json.load(f)
    
    _validar_esquema(esquema, nombre_archivo)
    return esquema


def _validar_esquema(esquema: dict, nombre: str) -> None:
    """Validaciones básicas de estructura del esquema."""
    if "metadata" not in esquema:
        raise ValueError(f"Esquema {nombre} sin sección 'metadata'")
    if "campos" not in esquema:
        raise ValueError(f"Esquema {nombre} sin sección 'campos'")
    if not isinstance(esquema["campos"], list) or len(esquema["campos"]) == 0:
        raise ValueError(f"Esquema {nombre}: 'campos' debe ser un array no vacío")
    
    campos_requeridos = {"nombre", "longitud", "tipo", "padding_char", "alineacion", "posicion_inicio"}
    for i, campo in enumerate(esquema["campos"]):
        faltantes = campos_requeridos - set(campo.keys())
        if faltantes:
            raise ValueError(
                f"Esquema {nombre}, campo #{i} ({campo.get('nombre', '?')}): "
                f"faltan atributos: {faltantes}"
            )


def listar_esquemas_disponibles() -> list[dict]:
    """Lista todos los esquemas JSON disponibles en el directorio de esquemas."""
    esquemas = []
    for archivo in config.SCHEMAS_PATH.glob("*.json"):
        if archivo.name == "README.md":
            continue
        try:
            with open(archivo, "r", encoding="utf-8") as f:
                data = json.load(f)
            esquemas.append({
                "archivo": archivo.name,
                "tipo": data.get("metadata", {}).get("tipo", "?"),
                "operacion": data.get("metadata", {}).get("operacion", "?"),
                "norma": data.get("metadata", {}).get("norma", "?"),
                "cantidad_campos": len(data.get("campos", [])),
            })
        except (json.JSONDecodeError, KeyError):
            continue
    return esquemas
