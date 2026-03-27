"""
Validador de archivos de respuesta (RES) de la SRT.

Los archivos RES tienen el mismo formato posicional que los archivos ART/EP
enviados, pero con códigos de error agregados al final de cada línea
(posiciones 988-997 para AT, o equivalente para EP).
"""
from motor.errores_srt import obtener_descripcion_error, cargar_catalogo_errores
from motor.utils import extraer_valor_campo


def parsear_respuesta_srt(
    contenido: bytes | str,
    longitud_registro_original: int = 987,
    encoding: str = "latin-1",
    separador: str = "\r\n",
) -> list[dict]:
    """
    Parsea un archivo de respuesta (RES) de la SRT.

    Los archivos RES contienen los mismos registros enviados pero con
    códigos de error de 2 caracteres al final (después de la posición 987),
    o embebidos en las últimas posiciones del registro.

    Args:
        contenido: Bytes o string del archivo RES
        longitud_registro_original: Longitud del registro original (987 para AT alta)
        encoding: Encoding del archivo
        separador: Separador de líneas

    Returns:
        Lista de dicts con info de cada registro y sus errores
    """
    if isinstance(contenido, bytes):
        try:
            texto = contenido.decode(encoding)
        except UnicodeDecodeError as e:
            return [{
                "fila": 0,
                "error_parseo": f"Error de encoding: {e}",
                "codigos_error": [],
            }]
    else:
        texto = contenido

    lineas = texto.split(separador)
    if lineas and lineas[-1].strip() == "":
        lineas = lineas[:-1]

    resultados = []

    for num_fila, linea in enumerate(lineas, start=1):
        registro = _parsear_linea_respuesta(linea, num_fila, longitud_registro_original)
        resultados.append(registro)

    return resultados


def _parsear_linea_respuesta(
    linea: str, num_fila: int, longitud_original: int
) -> dict:
    """
    Parsea una línea individual del archivo RES.

    Estrategia de detección de errores:
    1. Si la línea tiene exactamente longitud_original + 10, los últimos
       10 chars contienen el código de error (2 chars + 8 espacios de padding).
    2. Si la línea tiene exactamente longitud_original, busca el código
       de error en las últimas posiciones del campo de relato.
    3. Para otros largos, intenta extraer el error del final.
    """
    resultado = {
        "fila": num_fila,
        "longitud_linea": len(linea),
        "codigos_error": [],
        "siniestro_nro": "",
        "trabajador": "",
        "categoria": "",
        "estado": "OK",
    }

    if len(linea) < 84:
        resultado["estado"] = "LINEA_CORTA"
        return resultado

    # Extraer datos básicos del registro
    resultado["siniestro_nro"] = linea[5:25].strip()
    resultado["trabajador"] = linea[83:123].strip()
    resultado["categoria"] = linea[50:52].strip()

    # Detectar código de error al final de la línea
    # Los archivos RES tienen el código de error en los últimos caracteres
    # antes del padding con espacios
    codigo_error = _extraer_codigo_error(linea, longitud_original)

    if codigo_error:
        descripcion = obtener_descripcion_error(codigo_error)
        resultado["codigos_error"].append({
            "codigo": codigo_error,
            "descripcion": descripcion,
        })
        resultado["estado"] = "ERROR"
    else:
        resultado["estado"] = "ACEPTADO"

    return resultado


def _extraer_codigo_error(linea: str, longitud_original: int) -> str | None:
    """
    Extrae el código de error del final de una línea RES.

    Los códigos de error de la SRT son de 2 caracteres alfanuméricos.
    Se ubican al final del registro, después del contenido original,
    o en las últimas posiciones con contenido significativo.
    """
    # Buscar desde el final de la línea, ignorando espacios trailing
    linea_stripped = linea.rstrip()

    if len(linea_stripped) < 2:
        return None

    # Los últimos 2 caracteres no-espacio suelen ser el código de error
    # Solo si son alfanuméricos (códigos como LP, W5, B8, AM, etc.)
    ultimo_bloque = linea_stripped.rstrip()
    if len(ultimo_bloque) < 2:
        return None

    # Tomar los últimos 2 caracteres
    posible_codigo = ultimo_bloque[-2:]

    # Validar que sea un código alfanumérico válido
    if posible_codigo.isalnum() and len(posible_codigo) == 2:
        # Verificar que existe en el catálogo de errores
        try:
            catalogo = cargar_catalogo_errores()
            if posible_codigo in catalogo:
                return posible_codigo
        except FileNotFoundError:
            # Si no hay catálogo, igual retornamos el código
            return posible_codigo

    return None


def generar_resumen_respuesta(registros: list[dict]) -> dict:
    """
    Genera un resumen del archivo de respuesta SRT.

    Args:
        registros: Lista de registros parseados

    Returns:
        Dict con resumen: total, aceptados, rechazados, errores por código
    """
    total = len(registros)
    aceptados = sum(1 for r in registros if r["estado"] == "ACEPTADO")
    rechazados = sum(1 for r in registros if r["estado"] == "ERROR")
    errores_parseo = sum(1 for r in registros if r["estado"] == "LINEA_CORTA")

    # Agrupar errores por código
    errores_por_codigo = {}
    for reg in registros:
        for err in reg.get("codigos_error", []):
            codigo = err["codigo"]
            if codigo not in errores_por_codigo:
                errores_por_codigo[codigo] = {
                    "codigo": codigo,
                    "descripcion": err["descripcion"],
                    "cantidad": 0,
                    "registros_afectados": [],
                }
            errores_por_codigo[codigo]["cantidad"] += 1
            errores_por_codigo[codigo]["registros_afectados"].append({
                "fila": reg["fila"],
                "siniestro": reg["siniestro_nro"],
                "trabajador": reg["trabajador"],
            })

    # Registros con error para detalle
    detalle_errores = [
        {
            "fila": reg["fila"],
            "siniestro": reg["siniestro_nro"],
            "trabajador": reg["trabajador"],
            "categoria": reg["categoria"],
            "errores": reg["codigos_error"],
        }
        for reg in registros
        if reg["estado"] == "ERROR"
    ]

    return {
        "total_registros": total,
        "aceptados": aceptados,
        "rechazados": rechazados,
        "errores_parseo": errores_parseo,
        "tasa_rechazo": f"{(rechazados / total * 100):.1f}%" if total > 0 else "0%",
        "errores_por_codigo": list(errores_por_codigo.values()),
        "detalle_errores": detalle_errores[:50],  # Limitar para no saturar el LLM
    }
