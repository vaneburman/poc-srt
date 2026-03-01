"""
Motor de Validación de archivos TXT posicionales.

Valida archivos contra los esquemas JSON y genera reportes de errores
estructurados que el LLM puede interpretar y explicar al usuario.
"""
from motor.utils import extraer_valor_campo, validar_tipo
from motor.esquema_loader import cargar_esquema


def validar_archivo(contenido: bytes | str, tipo: str, operacion: str) -> list[dict]:
    """
    Valida un archivo TXT posicional contra el esquema correspondiente.
    
    Args:
        contenido: Bytes o string del archivo TXT
        tipo: 'AT' o 'EP'
        operacion: 'A' (alta) o 'B' (baja)
    
    Returns:
        Lista de errores. Lista vacía = archivo válido.
        Cada error: {fila, campo, posicion, valor_encontrado, error, 
                     referencia_norma, severidad}
    """
    esquema = cargar_esquema(tipo, operacion)
    encoding = esquema["metadata"].get("encoding", "latin-1")
    separador = esquema["metadata"].get("line_separator", "\r\n")
    longitud_esperada = esquema["metadata"].get("longitud_registro")
    
    # Decodificar si viene como bytes
    if isinstance(contenido, bytes):
        try:
            texto = contenido.decode(encoding)
        except UnicodeDecodeError as e:
            return [{
                "fila": 0,
                "campo": "archivo",
                "posicion": "N/A",
                "valor_encontrado": "N/A",
                "error": f"Error de encoding: no se pudo decodificar como {encoding}. {e}",
                "referencia_norma": esquema["metadata"].get("norma", ""),
                "severidad": "FATAL",
            }]
    else:
        texto = contenido
    
    # Separar en líneas
    lineas = texto.split(separador)
    
    # Remover última línea si está vacía (trailing separator)
    if lineas and lineas[-1].strip() == "":
        lineas = lineas[:-1]
    
    if not lineas:
        return [{
            "fila": 0,
            "campo": "archivo",
            "posicion": "N/A",
            "valor_encontrado": "(vacío)",
            "error": "El archivo está vacío",
            "referencia_norma": "",
            "severidad": "FATAL",
        }]
    
    errores = []
    
    for num_fila, linea in enumerate(lineas, start=1):
        # Validar longitud de línea
        if longitud_esperada and len(linea) != longitud_esperada:
            errores.append({
                "fila": num_fila,
                "campo": "registro_completo",
                "posicion": f"1-{len(linea)}",
                "valor_encontrado": f"longitud={len(linea)}",
                "error": f"Longitud de registro incorrecta. "
                         f"Esperada: {longitud_esperada}, encontrada: {len(linea)}",
                "referencia_norma": esquema["metadata"].get("norma", ""),
                "severidad": "ERROR",
            })
            continue  # No seguir validando campos si la longitud es incorrecta
        
        # Validar cada campo
        for campo in esquema["campos"]:
            valor = extraer_valor_campo(linea, campo["posicion_inicio"], campo["longitud"])
            
            # Validar tipo de dato
            if not validar_tipo(valor, campo["tipo"]):
                errores.append({
                    "fila": num_fila,
                    "campo": campo["nombre"],
                    "posicion": f"{campo['posicion_inicio']}-"
                               f"{campo['posicion_inicio'] + campo['longitud'] - 1}",
                    "valor_encontrado": repr(valor),
                    "error": f"Tipo de dato inválido. Esperado: {campo['tipo']} "
                             f"({'numérico' if campo['tipo'] == 'N' else 'fecha YYYYMMDD' if campo['tipo'] == 'F' else 'alfanumérico'})",
                    "referencia_norma": f"{esquema['metadata'].get('norma', '')}, "
                                       f"Campo: {campo.get('descripcion', campo['nombre'])}",
                    "severidad": "ERROR",
                })
            
            # Validar obligatoriedad
            if campo.get("obligatorio") and valor.strip() == "":
                errores.append({
                    "fila": num_fila,
                    "campo": campo["nombre"],
                    "posicion": f"{campo['posicion_inicio']}-"
                               f"{campo['posicion_inicio'] + campo['longitud'] - 1}",
                    "valor_encontrado": "(vacío)",
                    "error": "Campo obligatorio vacío",
                    "referencia_norma": f"{esquema['metadata'].get('norma', '')}, "
                                       f"Campo: {campo.get('descripcion', campo['nombre'])}",
                    "severidad": "ERROR",
                })
            
            # Validar valores permitidos
            valores_validos = campo.get("valores_validos")
            if valores_validos and valor.strip() and valor.strip() not in valores_validos:
                errores.append({
                    "fila": num_fila,
                    "campo": campo["nombre"],
                    "posicion": f"{campo['posicion_inicio']}-"
                               f"{campo['posicion_inicio'] + campo['longitud'] - 1}",
                    "valor_encontrado": valor.strip(),
                    "error": f"Valor no permitido. Valores válidos: {', '.join(valores_validos[:10])}"
                             + (f" (y {len(valores_validos) - 10} más)" if len(valores_validos) > 10 else ""),
                    "referencia_norma": f"{esquema['metadata'].get('norma', '')}, "
                                       f"Campo: {campo.get('descripcion', campo['nombre'])}",
                    "severidad": "ERROR",
                })
    
    return errores


def generar_resumen_validacion(errores: list[dict]) -> dict:
    """
    Genera un resumen de validación para el agente.
    
    Returns:
        Dict con: es_valido, total_errores, errores_por_tipo, errores
    """
    if not errores:
        return {
            "es_valido": True,
            "total_errores": 0,
            "errores_por_tipo": {},
            "errores": [],
        }
    
    errores_por_tipo = {}
    for error in errores:
        tipo = error["campo"]
        errores_por_tipo[tipo] = errores_por_tipo.get(tipo, 0) + 1
    
    return {
        "es_valido": False,
        "total_errores": len(errores),
        "errores_por_tipo": errores_por_tipo,
        "errores": errores[:50],  # Limitar para no saturar el contexto del LLM
    }
