"""
Funciones utilitarias para formateo posicional.
Son el corazón determinístico del sistema — sin LLM, sin magia.
"""


def aplicar_padding(valor: str, longitud: int, padding_char: str, alineacion: str) -> str:
    """
    Aplica padding a un valor según las reglas del campo.
    
    Args:
        valor: Valor crudo a formatear
        longitud: Longitud exacta esperada
        padding_char: Carácter de relleno ('0' o ' ')
        alineacion: 'left' o 'right'
    
    Returns:
        String con la longitud exacta especificada
    """
    valor = str(valor) if valor is not None else ""
    
    # Truncar si excede la longitud
    if len(valor) > longitud:
        valor = valor[:longitud]
    
    if alineacion == "right":
        return valor.rjust(longitud, padding_char)
    else:
        return valor.ljust(longitud, padding_char)


def validar_tipo(valor: str, tipo: str) -> bool:
    """
    Valida que un valor cumpla con su tipo esperado.
    
    Args:
        valor: Valor extraído (sin padding)
        tipo: 'N' (numérico), 'A' (alfanumérico), 'F' (fecha YYYYMMDD)
    
    Returns:
        True si el valor es válido para su tipo
    """
    valor_limpio = valor.strip().lstrip("0") or "0"
    
    if tipo == "N":
        return valor.strip() == "" or valor.replace("0", "").strip() == "" or valor_limpio.isdigit()
    elif tipo == "F":
        if len(valor.strip()) == 0 or valor.strip() == "0" * len(valor):
            return True  # Fecha vacía permitida (campo no obligatorio)
        if len(valor.strip()) != 8:
            return False
        try:
            year = int(valor[:4])
            month = int(valor[4:6])
            day = int(valor[6:8])
            return 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31
        except ValueError:
            return False
    elif tipo == "A":
        return True  # Alfanumérico acepta cualquier carácter
    
    return False


def extraer_valor_campo(linea: str, posicion_inicio: int, longitud: int) -> str:
    """
    Extrae un campo de una línea posicional.
    
    Args:
        linea: Línea completa del archivo TXT
        posicion_inicio: Posición 1-indexed
        longitud: Longitud del campo
    
    Returns:
        Substring extraído
    """
    inicio = posicion_inicio - 1  # Convertir a 0-indexed
    return linea[inicio:inicio + longitud]
