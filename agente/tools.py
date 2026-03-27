"""
Definición e implementación de herramientas del agente.

Cada tool tiene:
1. Una DEFINICIÓN (dict) para el LLM (function calling)
2. Una IMPLEMENTACIÓN (función Python) que ejecuta la lógica real
"""
import json
from pathlib import Path

import config
from motor.generador import generar_archivo_con_resumen
from motor.validador import validar_archivo, generar_resumen_validacion
from motor.validador_respuesta import parsear_respuesta_srt, generar_resumen_respuesta
from motor.errores_srt import obtener_descripcion_error, obtener_errores_multiples


# ============================================================
# DEFINICIONES DE TOOLS (para el LLM)
# ============================================================

TOOLS_DEFINITION = [
    {
        "name": "consultar_normativa",
        "description": (
            "Busca información en la normativa SRT (Resoluciones 3326/2014, "
            "3327/2014 y modificatorias) para responder preguntas sobre campos, "
            "códigos, formatos posicionales, plazos y requisitos."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pregunta": {
                    "type": "string",
                    "description": (
                        "La pregunta a buscar en la normativa. Debe ser específica. "
                        "Ej: 'longitud del campo CUIL en AT alta', "
                        "'códigos de provincia válidos', "
                        "'formato de fecha de siniestro'"
                    ),
                }
            },
            "required": ["pregunta"],
        },
    },
    {
        "name": "generar_txt",
        "description": (
            "Genera un archivo TXT con formato posicional de longitud fija "
            "para declarar ante la SRT. Los datos se obtienen del sistema interno."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": ["AT", "EP"],
                    "description": "AT = Accidente de Trabajo, EP = Enfermedad Profesional",
                },
                "operacion": {
                    "type": "string",
                    "enum": ["A", "B"],
                    "description": "A = Alta (nuevo siniestro), B = Baja (cierre)",
                },
                "fecha_desde": {
                    "type": "string",
                    "description": "Fecha inicio del período, formato YYYY-MM-DD",
                },
                "fecha_hasta": {
                    "type": "string",
                    "description": "Fecha fin del período, formato YYYY-MM-DD",
                },
            },
            "required": ["tipo", "operacion", "fecha_desde", "fecha_hasta"],
        },
    },
    {
        "name": "validar_txt",
        "description": (
            "Valida un archivo TXT posicional contra el formato oficial de "
            "la SRT y reporta errores encontrados con referencia a la norma. "
            "Incluye validaciones cruzadas (coherencia de fechas, reglas por "
            "categoría, prestadores, establecimiento, etc.)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "archivo_path": {
                    "type": "string",
                    "description": "Ruta al archivo TXT a validar",
                },
                "tipo": {
                    "type": "string",
                    "enum": ["AT", "EP"],
                    "description": "Tipo de declaración del archivo",
                },
                "operacion": {
                    "type": "string",
                    "enum": ["A", "B"],
                    "description": "Operación del archivo (A=alta, B=baja)",
                },
            },
            "required": ["archivo_path", "tipo", "operacion"],
        },
    },
    {
        "name": "validar_respuesta_srt",
        "description": (
            "Valida un archivo de respuesta (RES) recibido de la SRT. "
            "Parsea los códigos de error de cada registro y los traduce "
            "a descripciones legibles con recomendaciones de corrección."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "archivo_path": {
                    "type": "string",
                    "description": "Ruta al archivo RES de respuesta SRT",
                },
                "tipo": {
                    "type": "string",
                    "enum": ["AT", "EP"],
                    "description": "Tipo de declaración original (AT o EP)",
                },
            },
            "required": ["archivo_path", "tipo"],
        },
    },
    {
        "name": "consultar_error_srt",
        "description": (
            "Consulta la descripción de uno o más códigos de error de la SRT. "
            "Útil para entender qué significa un código de rechazo específico."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "codigos": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Lista de códigos de error SRT a consultar. "
                        "Ej: ['LP', 'W5', 'B8']"
                    ),
                },
            },
            "required": ["codigos"],
        },
    },
]


# ============================================================
# IMPLEMENTACIONES DE TOOLS (lógica Python real)
# ============================================================

def ejecutar_tool(tool_name: str, tool_args: dict) -> str:
    """
    Router central de herramientas.

    Args:
        tool_name: Nombre de la tool a ejecutar
        tool_args: Argumentos extraídos por el LLM

    Returns:
        String JSON con el resultado (para devolver al LLM)
    """
    ejecutores = {
        "consultar_normativa": _ejecutar_consultar_normativa,
        "generar_txt": _ejecutar_generar_txt,
        "validar_txt": _ejecutar_validar_txt,
        "validar_respuesta_srt": _ejecutar_validar_respuesta_srt,
        "consultar_error_srt": _ejecutar_consultar_error_srt,
    }

    ejecutor = ejecutores.get(tool_name)
    if not ejecutor:
        return json.dumps({"error": f"Herramienta desconocida: {tool_name}"})

    try:
        resultado = ejecutor(**tool_args)
        return json.dumps(resultado, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": f"Error ejecutando {tool_name}: {str(e)}"})


def _ejecutar_consultar_normativa(pregunta: str) -> dict:
    """Busca en el index FAISS y devuelve chunks relevantes."""
    try:
        from rag.search import buscar_normativa
        resultados = buscar_normativa(pregunta, top_k=config.RAG_TOP_K)
        return {
            "resultados": resultados,
            "cantidad": len(resultados),
        }
    except Exception as e:
        return {
            "error": f"RAG no disponible: {e}. Respondé con tu conocimiento general.",
            "resultados": [],
        }


def _ejecutar_generar_txt(
    tipo: str, operacion: str, fecha_desde: str, fecha_hasta: str
) -> dict:
    """Obtiene datos y genera el archivo TXT posicional."""
    datos = _obtener_datos_siniestros(tipo, operacion, fecha_desde, fecha_hasta)

    if not datos:
        return {
            "error": "No se encontraron siniestros para los filtros indicados.",
            "tipo": tipo,
            "operacion": operacion,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
        }

    resultado = generar_archivo_con_resumen(datos, tipo, operacion)

    output_path = config.OUTPUT_PATH / resultado["nombre_archivo"]
    with open(output_path, "wb") as f:
        f.write(resultado["contenido_bytes"])

    return {
        "nombre_archivo": resultado["nombre_archivo"],
        "ruta": str(output_path),
        "total_registros": resultado["total_registros"],
        "longitud_registro": resultado["longitud_registro"],
        "norma": resultado["norma"],
    }


def _ejecutar_validar_txt(archivo_path: str, tipo: str, operacion: str) -> dict:
    """Valida un archivo TXT contra el esquema correspondiente."""
    path = Path(archivo_path)
    if not path.exists():
        return {"error": f"Archivo no encontrado: {archivo_path}"}

    contenido = path.read_bytes()
    errores = validar_archivo(contenido, tipo, operacion)
    return generar_resumen_validacion(errores)


def _ejecutar_validar_respuesta_srt(archivo_path: str, tipo: str) -> dict:
    """
    Parsea y analiza un archivo de respuesta (RES) de la SRT.

    Extrae los códigos de error de cada registro rechazado y genera
    un resumen con descripciones y recomendaciones.
    """
    path = Path(archivo_path)
    if not path.exists():
        return {"error": f"Archivo RES no encontrado: {archivo_path}"}

    contenido = path.read_bytes()

    # Determinar longitud según tipo
    longitud_original = 987 if tipo.upper() == "AT" else 978

    registros = parsear_respuesta_srt(
        contenido,
        longitud_registro_original=longitud_original,
    )

    resumen = generar_resumen_respuesta(registros)

    return resumen


def _ejecutar_consultar_error_srt(codigos: list[str]) -> dict:
    """Consulta descripciones de códigos de error SRT."""
    resultados = obtener_errores_multiples(codigos)
    return {
        "codigos_consultados": len(codigos),
        "resultados": resultados,
    }


def _obtener_datos_siniestros(
    tipo: str, operacion: str, fecha_desde: str, fecha_hasta: str
) -> list[dict]:
    """
    Obtiene datos de siniestros del endpoint Java o mock.

    En la PoC usa mock data. Al migrar a AWS, cambiar a requests.get()
    apuntando al endpoint Java real.
    """
    if config.USE_MOCK_DATA:
        return _cargar_mock_data(tipo, operacion)
    else:
        return _llamar_endpoint_java(tipo, operacion, fecha_desde, fecha_hasta)


def _cargar_mock_data(tipo: str, operacion: str) -> list[dict]:
    """Carga datos de prueba desde archivos JSON locales."""
    operacion_nombre = "alta" if operacion.upper() == "A" else "baja"
    archivo = config.MOCK_DATA_PATH / f"siniestros_{tipo.lower()}_{operacion_nombre}.json"

    if not archivo.exists():
        return []

    with open(archivo, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("resultado", data if isinstance(data, list) else [])


def _llamar_endpoint_java(
    tipo: str, operacion: str, fecha_desde: str, fecha_hasta: str
) -> list[dict]:
    """
    Llama al endpoint Java real.

    TODO: Implementar al conectar con el entorno Dev.
    """
    import requests

    params = {
        "tipo": tipo,
        "estado": operacion,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
    }

    response = requests.get(
        f"{config.JAVA_ENDPOINT_URL}",
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    return data.get("resultado", [])
