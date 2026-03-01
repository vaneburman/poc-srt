"""
Motor de Generación de archivos TXT posicionales.

Este módulo es el "músculo" del sistema. Genera archivos TXT con formato
posicional de longitud fija, aplicando padding, alineación y encoding
estrictos según los esquemas JSON de la normativa SRT.

El LLM NUNCA toca este código ni genera strings posicionales.
"""
from motor.utils import aplicar_padding
from motor.esquema_loader import cargar_esquema


def _resolver_valor(campo: dict, datos: dict) -> str:
    """
    Resuelve el valor de un campo según su fuente_dato.
    
    Fuentes soportadas:
        - constante:X → Retorna X directamente
        - endpoint:campo → Busca 'campo' en el dict de datos
        - calculado:formula → (futuro) Para campos derivados
    """
    fuente = campo.get("fuente_dato", "")
    
    if fuente.startswith("constante:"):
        return fuente.split(":", 1)[1]
    
    if fuente.startswith("endpoint:"):
        clave = fuente.split(":", 1)[1]
        valor = datos.get(clave, "")
        return str(valor) if valor is not None else ""
    
    # Default: buscar por nombre del campo en los datos
    return str(datos.get(campo["nombre"], ""))


def generar_registro(datos: dict, esquema: dict) -> str:
    """
    Genera una línea TXT posicional a partir de un dict de datos y un esquema.
    
    Args:
        datos: Dict con los datos crudos de un siniestro
        esquema: Esquema JSON completo (con metadata y campos)
    
    Returns:
        String de longitud fija exacta (una línea del archivo)
    
    Raises:
        ValueError: Si la línea generada no tiene la longitud esperada
    """
    partes = []
    
    for campo in esquema["campos"]:
        valor = _resolver_valor(campo, datos)
        formateado = aplicar_padding(
            valor=valor,
            longitud=campo["longitud"],
            padding_char=campo["padding_char"],
            alineacion=campo["alineacion"],
        )
        partes.append(formateado)
    
    linea = "".join(partes)
    
    longitud_esperada = esquema["metadata"].get("longitud_registro")
    if longitud_esperada and len(linea) != longitud_esperada:
        raise ValueError(
            f"Longitud generada ({len(linea)}) != esperada ({longitud_esperada}). "
            f"Revisar esquema: la suma de longitudes de campos debe ser {longitud_esperada}."
        )
    
    return linea


def generar_archivo(lista_datos: list[dict], tipo: str, operacion: str) -> bytes:
    """
    Genera el archivo TXT completo.
    
    Args:
        lista_datos: Lista de dicts con datos de siniestros
        tipo: 'AT' o 'EP'
        operacion: 'A' (alta) o 'B' (baja)
    
    Returns:
        Bytes del archivo TXT con encoding y separadores correctos
    """
    esquema = cargar_esquema(tipo, operacion)
    encoding = esquema["metadata"].get("encoding", "latin-1")
    separador = esquema["metadata"].get("line_separator", "\r\n")
    
    lineas = []
    for i, datos in enumerate(lista_datos):
        try:
            linea = generar_registro(datos, esquema)
            lineas.append(linea)
        except ValueError as e:
            raise ValueError(f"Error en registro #{i + 1}: {e}")
    
    contenido = separador.join(lineas)
    
    # Agregar separador final si hay registros
    if lineas:
        contenido += separador
    
    return contenido.encode(encoding)


def generar_archivo_con_resumen(
    lista_datos: list[dict], tipo: str, operacion: str
) -> dict:
    """
    Genera el archivo y retorna un resumen para el agente.
    
    Returns:
        Dict con: contenido_bytes, nombre_archivo, total_registros, 
        longitud_registro, norma
    """
    esquema = cargar_esquema(tipo, operacion)
    contenido = generar_archivo(lista_datos, tipo, operacion)
    
    operacion_nombre = "alta" if operacion.upper() == "A" else "baja"
    nombre = f"{tipo.lower()}_{operacion_nombre}_{len(lista_datos)}reg.txt"
    
    return {
        "contenido_bytes": contenido,
        "nombre_archivo": nombre,
        "total_registros": len(lista_datos),
        "longitud_registro": esquema["metadata"].get("longitud_registro"),
        "norma": esquema["metadata"].get("norma"),
    }
