"""
Catálogo de códigos de error de la SRT.

Carga los códigos desde el CSV y provee funciones de búsqueda
para interpretar archivos de respuesta (RES).
"""
import csv
from pathlib import Path
from functools import lru_cache


# Ruta por defecto al CSV de errores
_ERRORES_CSV_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "errores_srt.csv"


@lru_cache(maxsize=1)
def cargar_catalogo_errores(csv_path: str | Path | None = None) -> dict[str, str]:
    """
    Carga el catálogo de errores SRT desde un archivo CSV.

    Args:
        csv_path: Ruta al CSV. Si es None, busca en data/errores_srt.csv

    Returns:
        Dict {codigo: descripcion}
    """
    path = Path(csv_path) if csv_path else _ERRORES_CSV_DEFAULT

    if not path.exists():
        raise FileNotFoundError(
            f"No se encontró el catálogo de errores SRT en: {path}. "
            f"Copiá el archivo 'Errores SRT (1).csv' a {path}"
        )

    catalogo = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            codigo = row.get("codigo", "").strip()
            descripcion = row.get("descripcion", "").strip()
            if codigo:
                catalogo[codigo] = descripcion

    return catalogo


def obtener_descripcion_error(codigo: str, csv_path: str | Path | None = None) -> str:
    """
    Obtiene la descripción de un código de error SRT.

    Args:
        codigo: Código de error (ej: "LP", "W5", "B8")
        csv_path: Ruta al CSV de errores (opcional)

    Returns:
        Descripción del error o mensaje de código desconocido
    """
    catalogo = cargar_catalogo_errores(csv_path)
    codigo = codigo.strip()

    if codigo in catalogo:
        return catalogo[codigo]

    return f"Código de error desconocido: {codigo}"


def obtener_errores_multiples(codigos: list[str], csv_path: str | Path | None = None) -> list[dict]:
    """
    Obtiene descripciones para múltiples códigos de error.

    Args:
        codigos: Lista de códigos de error
        csv_path: Ruta al CSV (opcional)

    Returns:
        Lista de dicts {codigo, descripcion, conocido}
    """
    catalogo = cargar_catalogo_errores(csv_path)
    resultados = []

    for codigo in codigos:
        codigo = codigo.strip()
        if codigo in catalogo:
            resultados.append({
                "codigo": codigo,
                "descripcion": catalogo[codigo],
                "conocido": True,
            })
        else:
            resultados.append({
                "codigo": codigo,
                "descripcion": f"Código desconocido: {codigo}",
                "conocido": False,
            })

    return resultados


# Errores frecuentes en siniestralidad AT/EP con contexto de resolución
ERRORES_FRECUENTES_SINIESTRALIDAD = {
    "08": "Registro Incompleto",
    "47": "CUIL inválida",
    "49": "Sexo distinto de M - F",
    "50": "Código de Naturaleza de la lesión inválido",
    "53": "Zona de cuerpo inválida",
    "54": "Forma de accidente inválida",
    "55": "Código Postal o CPA incorrecto",
    "59": "Diagnóstico inválido",
    "75": "Fecha de Cese ILT y/o Código de Egreso vacío",
    "77": "Fecha de nacimiento inválida",
    "90": "Apellido y Nombre no corresponden a la CUIL informada",
    "91": "CUIL inexistente en padrones ANSeS/AFIP",
    "AM": "Código de Localidad Inválido",
    "B6": "Si SB/CB con Secuelas Incapacitantes, Egreso debe ser P o A",
    "B8": "Los campos Fecha Fin ILT y Forma de Egreso deben estar ambos completos",
    "BT": "Patología trazadora sin ROAM o viceversa",
    "C0": "Faltan valores obligatorios (Forma Accid., Zona Cuerpo, etc.)",
    "E0": "Patología trazadora distinto de S - N",
    "FB": "Campo Ocurrencia vía Pública inválido",
    "FC": "Campo Secuelas Incapacitantes inválido",
    "FD": "Fecha de Rechazo ausente (obligatorio para RE)",
    "FF": "Motivo de Rechazo ausente (obligatorio para RE)",
    "FG": "Se deben completar Fecha y Motivo de Rechazo",
    "FO": "Si Intercurrencia es S, el nro de siniestro de intercurrencia es obligatorio",
    "FP": "Si Intercurrencia es N, el nro de siniestro de intercurrencia no debe completarse",
    "FH": "Campo Fecha Estimada de alta Médica Ausente",
    "FL": "Campo Recalificación Ausente",
    "FX": "Si tiene Secuelas Incapacitantes, Ingreso Base debe ser mayor a 0",
    "FY": "Si es accidente in itinere debe estar habilitado Ocurrencia Vía Pública",
    "GK": "Inconsistencia entre zona de cuerpo y diagnóstico",
    "GN": "Campo Código de establecimiento se encuentra vacío",
    "LC": "La fecha de Inicio Inasistencia no puede ser mayor a la de Toma Conocimiento",
    "LJ": "Campo Forma de Ingreso de la Denuncia es inválido",
    "LK": "Campo Forma de Ingreso de la Denuncia es obligatorio",
    "LM": "Para casos Mortales el campo Fecha de Defunción es obligatorio",
    "LN": "Campo Fecha de Defunción es incorrecto",
    "LÑ": "Campo Tipo Prestador Médico 1ra atención es inválido",
    "LO": "Campo Tipo Prestador Médico 1ra atención es obligatorio",
    "LP": "El código de Prestador Médico 1ra Atención no está activo o no es válido para la ART",
    "LR": "El campo Prestador Médico 1ra Atención es obligatorio",
    "LS": "Los campos Prestador Médico y Tipo prestador médico deben estar completos",
    "LT": "El campo Descripción del Siniestro debe estar completo",
    "W5": "La fecha de ocurrencia no es coherente con las demás fechas",
    "W6": "La fecha de inicio de inasistencia no es coherente con las demás fechas",
    "DG": "La fecha de Cese ILT supera 1 año desde la ocurrencia",
    "JT": "Categoría SB no debe tener fecha de cese ILT",
    "W7": "La fecha de Cese ILT no es coherente con las demás fechas",
}
