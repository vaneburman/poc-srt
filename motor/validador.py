"""
Motor de Validación de archivos TXT posicionales.

Valida archivos contra los esquemas JSON y genera reportes de errores
estructurados que el LLM puede interpretar y explicar al usuario.

Incluye:
- Validación por campo (tipo, valores permitidos)
- Obligatoriedad inteligente: O (obligatorio), OD (diferible - no se valida),
  OC (condicional - se valida en cruzadas)
- Validaciones cruzadas entre campos (coherencia de fechas, reglas por categoría)
- Referencias a códigos de error SRT equivalentes
- Hints de resolución para cada error
"""
from datetime import datetime, timedelta

from motor.utils import extraer_valor_campo, validar_tipo
from motor.esquema_loader import cargar_esquema


# ── Campos obligatorios diferibles ──
# No se validan como obligatorios en la carga inicial.
# Son campos que la SRT acepta vacíos en la primera presentación
# y se completan en una modificación posterior.
CAMPOS_DIFERIBLES = {
    "fecha_cese_ilt",
    "secuelas_incapacitantes",
    "motivo_cese_ilt",
    "fecha_alta_medica",
    "fecha_declaracion_ilp",
    "tipo_incapacidad",
    "pct_incapacidad",
    "gran_invalidez",
    "fecha_dictamen",
    "expediente_comision_medica",
    "tratamiento_medico_asistencial_pendiente",
}

# ── Campos obligatorios condicionales ──
# No se validan en el chequeo básico de obligatoriedad.
# Se validan en las validaciones cruzadas según la categoría
# y otros campos del registro.
CAMPOS_CONDICIONALES = {
    "tipo_prestador_medico_de_la_1ra_atencion",
    "prestador_medico_de_la_1ra_atencion",
    "fecha_estimada_de_alta_medica",
    "ingreso_base",
    "fecha_rechazo",
    "motivo_rechazo",
    "fecha_de_defuncion",
}


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
                     referencia_norma, severidad, codigo_srt, resolucion}
    """
    esquema = cargar_esquema(tipo, operacion)
    encoding = esquema["metadata"].get("encoding", "latin-1")
    separador = esquema["metadata"].get("line_separator", "\r\n")
    longitud_esperada = esquema["metadata"].get("longitud_registro")
    norma = esquema["metadata"].get("norma", "")

    # Decodificar si viene como bytes
    if isinstance(contenido, bytes):
        try:
            texto = contenido.decode(encoding)
        except UnicodeDecodeError as e:
            return [_error(0, "archivo", "N/A", "N/A",
                          f"Error de encoding: no se pudo decodificar como {encoding}. {e}",
                          norma, "FATAL")]
    else:
        texto = contenido

    # Separar en líneas
    lineas = texto.split(separador)
    if lineas and lineas[-1].strip() == "":
        lineas = lineas[:-1]

    if not lineas:
        return [_error(0, "archivo", "N/A", "(vacío)",
                       "El archivo está vacío", "", "FATAL")]

    # Indexar campos por nombre para acceso rápido
    campos_por_nombre = {c["nombre"]: c for c in esquema["campos"]}

    errores = []

    for num_fila, linea in enumerate(lineas, start=1):
        # Validar longitud de línea
        if longitud_esperada and len(linea) != longitud_esperada:
            errores.append(_error(
                num_fila, "registro_completo", f"1-{len(linea)}",
                f"longitud={len(linea)}",
                f"Longitud de registro incorrecta. Esperada: {longitud_esperada}, encontrada: {len(linea)}",
                norma, "ERROR", "08"))
            continue

        # --- Validación campo por campo ---
        for campo in esquema["campos"]:
            valor = extraer_valor_campo(linea, campo["posicion_inicio"], campo["longitud"])
            pos_str = f"{campo['posicion_inicio']}-{campo['posicion_inicio'] + campo['longitud'] - 1}"
            ref = f"{norma}, Campo: {campo.get('descripcion', campo['nombre'])}"

            # Tipo de dato (solo si tiene valor)
            if valor.strip() and not validar_tipo(valor, campo["tipo"]):
                tipo_desc = {'N': 'numérico', 'F': 'fecha YYYYMMDD', 'A': 'alfanumérico'}.get(campo['tipo'], campo['tipo'])
                errores.append(_error(
                    num_fila, campo["nombre"], pos_str, repr(valor),
                    f"Tipo de dato inválido. Esperado: {campo['tipo']} ({tipo_desc})",
                    ref, "ERROR"))

            # Obligatoriedad: solo para campos "O" (obligatorios puros)
            # Se excluyen diferibles (OD) y condicionales (OC)
            if campo.get("obligatorio") and valor.strip() == "":
                nombre = campo["nombre"]
                if nombre not in CAMPOS_DIFERIBLES and nombre not in CAMPOS_CONDICIONALES:
                    errores.append(_error(
                        num_fila, campo["nombre"], pos_str, "(vacío)",
                        "Campo obligatorio vacío", ref, "ERROR"))

            # Valores permitidos
            valores_validos = campo.get("valores_validos")
            if valores_validos and valor.strip() and valor.strip() not in valores_validos:
                txt = ', '.join(valores_validos[:10])
                extra = f" (y {len(valores_validos) - 10} más)" if len(valores_validos) > 10 else ""
                errores.append(_error(
                    num_fila, campo["nombre"], pos_str, valor.strip(),
                    f"Valor no permitido. Valores válidos: {txt}{extra}",
                    ref, "ERROR"))

        # --- Validaciones cruzadas (solo para alta AT/EP) ---
        if operacion.upper() == "A":
            errores.extend(_validaciones_cruzadas(
                linea, num_fila, campos_por_nombre, norma, tipo))

    return errores


def _validaciones_cruzadas(
    linea: str, num_fila: int, campos: dict, norma: str, tipo_archivo: str
) -> list[dict]:
    """
    Validaciones que involucran múltiples campos del mismo registro.
    Implementa las reglas de negocio definidas y los controles
    equivalentes a los códigos de error SRT.

    Incluye validaciones de:
    - Obligatoriedad condicional (por categoría)
    - Coherencia de fechas
    - Reglas específicas por categoría (SB, CB, MT, RE, etc.)
    - Campos ROAM (caso crónico, intercurrencia, recalificación)
    """
    errores = []

    # Extraer valores clave
    def _val(nombre: str) -> str:
        campo = campos.get(nombre)
        if not campo:
            return ""
        return extraer_valor_campo(linea, campo["posicion_inicio"], campo["longitud"]).strip()

    def _fecha(nombre: str) -> datetime | None:
        val = _val(nombre)
        if not val or val == "0" * len(val):
            return None
        try:
            return datetime.strptime(val, "%Y%m%d")
        except ValueError:
            return None

    categoria = _val("categoria_del_registro")
    fecha_ocurrencia = _fecha("fecha_de_ocurrencia")
    fecha_inicio_inasistencia = _fecha("fecha_inicio_inasistencia")
    fecha_cese_ilt = _fecha("fecha_cese_ilt")
    fecha_alta_medica = _fecha("fecha_alta_medica")
    fecha_estimada_alta = _fecha("fecha_estimada_de_alta_medica")
    fecha_toma_conocimiento = _fecha("fecha_toma_conocimiento")
    secuelas = _val("secuelas_incapacitantes")
    ingreso_base_raw = _val("ingreso_base")
    tipo_siniestro = _val("tipo_de_siniestro")
    ocurrencia_via_publica = _val("ocurrencia_en_via_publica")
    tipo_prestador = _val("tipo_prestador_medico_de_la_1ra_atencion")
    prestador = _val("prestador_medico_de_la_1ra_atencion")
    codigo_establecimiento = _val("codigo_establecimiento")
    motivo_cese_ilt = _val("motivo_cese_ilt")
    patologia_trazadora = _val("patologia_trazadora")
    nro_denuncia_roam = _val("n__denuncia_roam")
    ano_denuncia_roam = _val("ano_denuncia_roam")
    fecha_rechazo = _fecha("fecha_rechazo")
    motivo_rechazo = _val("motivo_rechazo")
    fecha_defuncion = _fecha("fecha_de_defuncion")
    caso_cronico = _val("caso_cronico")
    recalificacion = _val("recalificacion")
    intercurrencia = _val("intercurrencia")
    nro_intercurrencia = _val("n__de_reg_del_at_con_el_que_se_produce_la_intercu")
    relato = _val("descripcion_del_siniestro")

    # Categorías con baja laboral
    CATEGORIAS_CON_BAJA = {"CB", "MT", "IN"}
    CATEGORIAS_SIN_BAJA = {"SB", "CO"}

    # ═══════════════════════════════════════════════════════════
    # CÓDIGO DE ESTABLECIMIENTO (pos 53-62) - Código SRT: GN
    # ═══════════════════════════════════════════════════════════
    if not codigo_establecimiento or codigo_establecimiento == "0" * len(codigo_establecimiento):
        errores.append(_error(
            num_fila, "codigo_establecimiento",
            _pos(campos, "codigo_establecimiento"),
            codigo_establecimiento or "(vacío)",
            "Código de establecimiento vacío. La sede del empleador debe estar "
            "tipificada para la SRT.",
            norma, "ERROR", "GN",
            "Cambiar la SEDE o el tipo de SEDE del siniestro por una que esté "
            "registrada en la SRT."))

    # ═══════════════════════════════════════════════════════════
    # CÓDIGO PRIMERA ASISTENCIA (pos 480-487) - Códigos SRT: LR, LP, LO, LS
    # Obligatorio para CB y MT. Debe empezar con 155.
    # ═══════════════════════════════════════════════════════════
    if categoria in CATEGORIAS_CON_BAJA:
        # Tipo prestador obligatorio
        if not tipo_prestador or tipo_prestador == "0":
            errores.append(_error(
                num_fila, "tipo_prestador_medico_de_la_1ra_atencion",
                _pos(campos, "tipo_prestador_medico_de_la_1ra_atencion"),
                tipo_prestador or "(vacío)",
                f"Para categoría {categoria}, el tipo de prestador médico "
                f"de 1ra atención es obligatorio.",
                norma, "ERROR", "LO",
                "Asignar un prestador médico de primera asistencia al siniestro."))

        # Código prestador obligatorio
        if not prestador or prestador == "0" * len(prestador) or prestador == "00000000":
            errores.append(_error(
                num_fila, "prestador_medico_de_la_1ra_atencion",
                _pos(campos, "prestador_medico_de_la_1ra_atencion"),
                prestador or "(vacío)",
                f"Para categoría {categoria}, el código de prestador médico "
                f"de 1ra atención es obligatorio.",
                norma, "ERROR", "LR",
                "Asignar un centro médico de primera asistencia al siniestro."))
        elif not prestador.lstrip("0").startswith("155"):
            # El código de prestador para CB debe empezar con 155
            errores.append(_error(
                num_fila, "prestador_medico_de_la_1ra_atencion",
                _pos(campos, "prestador_medico_de_la_1ra_atencion"),
                prestador,
                f"Para categoría {categoria}, el código de prestador de 1ra "
                f"atención debe comenzar con 155 (código vigente). "
                f"Se informó: {prestador}. Puede ser un código antiguo.",
                norma, "ERROR", "LP",
                "Cambiar el centro médico de primera asistencia por uno con "
                "código vigente (que empiece con 155). Corregir en el log por BD "
                "si es necesario."))

        # Ambos campos deben estar completos juntos
        tiene_tipo = tipo_prestador and tipo_prestador != "0"
        tiene_prestador = prestador and prestador != "0" * len(prestador) and prestador != "00000000"
        if tiene_tipo != tiene_prestador:
            errores.append(_error(
                num_fila, "prestador_medico_de_la_1ra_atencion",
                _pos(campos, "prestador_medico_de_la_1ra_atencion"),
                f"tipo={tipo_prestador}, prestador={prestador}",
                "Los campos Tipo Prestador Médico y Prestador Médico 1ra "
                "Atención deben estar ambos completos o ambos vacíos.",
                norma, "ERROR", "LS",
                "Completar ambos campos: tipo de prestador y código de prestador "
                "de primera asistencia."))

    # ═══════════════════════════════════════════════════════════
    # FECHAS: Ocurrencia vs Inicio Inasistencia (pos 140-155) - Código SRT: W6
    # CB: inasistencia = ocurrencia + 1 día
    # SB: inasistencia = ocurrencia
    # ═══════════════════════════════════════════════════════════
    if fecha_ocurrencia and fecha_inicio_inasistencia and categoria:
        if categoria in CATEGORIAS_CON_BAJA:
            esperada = fecha_ocurrencia + timedelta(days=1)
            if fecha_inicio_inasistencia != esperada:
                errores.append(_error(
                    num_fila, "fecha_inicio_inasistencia",
                    _pos(campos, "fecha_inicio_inasistencia"),
                    _val("fecha_inicio_inasistencia"),
                    f"Para categoría {categoria} (con baja), la fecha de inicio "
                    f"de inasistencia debe ser ocurrencia + 1 día "
                    f"({esperada.strftime('%Y%m%d')}), "
                    f"pero se informó {_val('fecha_inicio_inasistencia')}.",
                    norma, "ERROR", "W6",
                    "Cambiar las fechas en Detalle de Siniestros → General."))
        elif categoria in CATEGORIAS_SIN_BAJA:
            if fecha_inicio_inasistencia != fecha_ocurrencia:
                errores.append(_error(
                    num_fila, "fecha_inicio_inasistencia",
                    _pos(campos, "fecha_inicio_inasistencia"),
                    _val("fecha_inicio_inasistencia"),
                    f"Para categoría {categoria} (sin baja), la fecha de inicio "
                    f"de inasistencia debe ser igual a la fecha de ocurrencia "
                    f"({_val('fecha_de_ocurrencia')}), "
                    f"pero se informó {_val('fecha_inicio_inasistencia')}.",
                    norma, "ERROR", "W6",
                    "Cambiar las fechas en Detalle de Siniestros → General."))

    # ═══════════════════════════════════════════════════════════
    # FECHA CESE ILT (pos 191-198) - Códigos SRT: W7, JT
    # SB: debe ser igual a fecha de inasistencia
    # CB: debe ser posterior a fecha de inicio de inasistencia
    # ═══════════════════════════════════════════════════════════
    if fecha_cese_ilt:
        # Cese ILT no anterior a ocurrencia
        if fecha_ocurrencia and fecha_cese_ilt < fecha_ocurrencia:
            errores.append(_error(
                num_fila, "fecha_cese_ilt",
                _pos(campos, "fecha_cese_ilt"),
                _val("fecha_cese_ilt"),
                f"Fecha cese ILT ({_val('fecha_cese_ilt')}) es anterior a "
                f"fecha de ocurrencia ({_val('fecha_de_ocurrencia')}). "
                f"Debe ser posterior.",
                norma, "ERROR", "W7",
                "Corregir la fecha de cese ILT en Detalle de Siniestros → General."))

        # SB: fecha cese = fecha inasistencia
        if categoria in CATEGORIAS_SIN_BAJA and fecha_inicio_inasistencia:
            if fecha_cese_ilt != fecha_inicio_inasistencia:
                errores.append(_error(
                    num_fila, "fecha_cese_ilt",
                    _pos(campos, "fecha_cese_ilt"),
                    _val("fecha_cese_ilt"),
                    f"Para categoría {categoria} (sin baja), la fecha de cese ILT "
                    f"debe ser igual a la fecha de inicio de inasistencia "
                    f"({_val('fecha_inicio_inasistencia')}), "
                    f"pero se informó {_val('fecha_cese_ilt')}.",
                    norma, "ERROR", "W7",
                    "Corregir la fecha de cese ILT en Detalle de Siniestros → General."))

        # SB no debe tener fecha de cese ILT informada
        if categoria in CATEGORIAS_SIN_BAJA:
            errores.append(_error(
                num_fila, "fecha_cese_ilt",
                _pos(campos, "fecha_cese_ilt"),
                _val("fecha_cese_ilt"),
                f"Categoría {categoria} (sin baja) no debe tener fecha de cese ILT informada.",
                norma, "ERROR", "JT",
                "Quitar la fecha de cese ILT o cambiar la categoría del siniestro."))

        # CB: fecha cese > fecha inicio inasistencia
        if categoria in CATEGORIAS_CON_BAJA and fecha_inicio_inasistencia:
            if fecha_cese_ilt <= fecha_inicio_inasistencia:
                errores.append(_error(
                    num_fila, "fecha_cese_ilt",
                    _pos(campos, "fecha_cese_ilt"),
                    _val("fecha_cese_ilt"),
                    f"Para categoría {categoria} (con baja), la fecha de cese ILT "
                    f"debe ser posterior a la fecha de inicio de inasistencia "
                    f"({_val('fecha_inicio_inasistencia')}), "
                    f"pero se informó {_val('fecha_cese_ilt')}.",
                    norma, "ERROR", "W7",
                    "Corregir la fecha de cese ILT en Detalle de Siniestros → General."))

    # SB no debe tener días de ILT (si tiene fecha cese y es SB, ya se validó arriba)
    # Pero si es SB y NO tiene fecha_cese, no es error (diferible)

    # ═══════════════════════════════════════════════════════════
    # FECHA ALTA MÉDICA (pos 249) - Código SRT: W5
    # Debe ser posterior a fecha de ocurrencia
    # ═══════════════════════════════════════════════════════════
    if fecha_alta_medica and fecha_ocurrencia:
        if fecha_alta_medica < fecha_ocurrencia:
            errores.append(_error(
                num_fila, "fecha_alta_medica",
                _pos(campos, "fecha_alta_medica"),
                _val("fecha_alta_medica"),
                f"Fecha alta médica ({_val('fecha_alta_medica')}) es anterior a "
                f"fecha de ocurrencia ({_val('fecha_de_ocurrencia')}). "
                f"Nunca debe ser anterior.",
                norma, "ERROR", "W5",
                "Corregir la fecha de alta médica en Detalle de Siniestros."))

    # ═══════════════════════════════════════════════════════════
    # FECHA PROBABLE FIN ILT (pos 420) - Código SRT: FH
    # Obligatoria para CB
    # ═══════════════════════════════════════════════════════════
    if categoria in CATEGORIAS_CON_BAJA and not fecha_estimada_alta:
        errores.append(_error(
            num_fila, "fecha_estimada_de_alta_medica",
            _pos(campos, "fecha_estimada_de_alta_medica"),
            _val("fecha_estimada_de_alta_medica") or "(vacío)",
            f"Para categoría {categoria}, la fecha probable de fin de ILT "
            f"(fecha estimada de alta médica) es obligatoria.",
            norma, "ERROR", "FH",
            "Volver a asignar el mismo CIE10 para que recalcule la fecha, "
            "o verificar si es un CIE10 nuevo que agregaron por base."))

    # ═══════════════════════════════════════════════════════════
    # SECUELAS INCAPACITANTES (pos 199) - Código SRT: FC
    # Debe ser S o N. Si no tiene fecha de cese, debe ser N.
    # ═══════════════════════════════════════════════════════════
    if secuelas and secuelas not in ("S", "N"):
        errores.append(_error(
            num_fila, "secuelas_incapacitantes",
            _pos(campos, "secuelas_incapacitantes"),
            secuelas,
            "El campo Secuelas Incapacitantes debe ser 'S' o 'N'.",
            norma, "ERROR", "FC",
            "Corregir el valor de secuelas incapacitantes a S o N."))

    if not fecha_cese_ilt and secuelas and secuelas != "N":
        errores.append(_error(
            num_fila, "secuelas_incapacitantes",
            _pos(campos, "secuelas_incapacitantes"),
            secuelas,
            "Si no tiene fecha de cese ILT, el campo Secuelas Incapacitantes "
            "debe ser 'N'.",
            norma, "ERROR", "FC",
            "Cambiar Secuelas Incapacitantes a 'N' o completar la fecha de cese ILT."))

    # ═══════════════════════════════════════════════════════════
    # MOTIVO CESE ILT (pos 200) - Código SRT: B8
    # SB: debe ser L (Alta Laboral).
    # Si no tiene fecha de cese: debe estar en blanco.
    # ═══════════════════════════════════════════════════════════
    if categoria in CATEGORIAS_SIN_BAJA and motivo_cese_ilt and motivo_cese_ilt != "L":
        errores.append(_error(
            num_fila, "motivo_cese_ilt",
            _pos(campos, "motivo_cese_ilt"),
            motivo_cese_ilt,
            f"Para categoría {categoria} (sin baja), el motivo de cese ILT "
            f"debe ser 'L' (Alta Laboral). Se informó: '{motivo_cese_ilt}'.",
            norma, "ERROR", "B8",
            "Cambiar el motivo de cese ILT a 'L' (Alta Laboral) en Detalle de Siniestros."))

    if not fecha_cese_ilt and motivo_cese_ilt and motivo_cese_ilt.strip() != "":
        errores.append(_error(
            num_fila, "motivo_cese_ilt",
            _pos(campos, "motivo_cese_ilt"),
            motivo_cese_ilt,
            "Si no tiene fecha de cese ILT, el motivo de cese debe estar en blanco.",
            norma, "ERROR", "B8",
            "Dejar el motivo de cese ILT en blanco o completar la fecha de cese ILT."))

    # Fecha cese ILT y motivo cese deben estar ambos completos o ambos vacíos
    tiene_fecha_cese = fecha_cese_ilt is not None
    tiene_motivo_cese = motivo_cese_ilt and motivo_cese_ilt not in ("0", "")
    if tiene_fecha_cese != tiene_motivo_cese:
        errores.append(_error(
            num_fila, "fecha_cese_ilt / motivo_cese_ilt",
            f"{_pos(campos, 'fecha_cese_ilt')} / {_pos(campos, 'motivo_cese_ilt')}",
            f"fecha_cese={_val('fecha_cese_ilt')}, motivo={motivo_cese_ilt}",
            "Los campos Fecha Fin ILT y Forma de Egreso (motivo cese ILT) "
            "deben estar ambos completos o ambos vacíos.",
            norma, "ERROR", "B8",
            "Completar ambos campos (fecha de cese y motivo) o dejar ambos vacíos."))

    # ═══════════════════════════════════════════════════════════
    # PATOLOGÍA TRAZADORA (pos 248) - Código SRT: BT
    # Si es S, deben estar completos nro y año de denuncia ROAM
    # ═══════════════════════════════════════════════════════════
    if patologia_trazadora == "S":
        tiene_roam = (nro_denuncia_roam and nro_denuncia_roam != "0" * len(nro_denuncia_roam))
        tiene_ano_roam = (ano_denuncia_roam and ano_denuncia_roam != "0" * len(ano_denuncia_roam))
        if not tiene_roam or not tiene_ano_roam:
            errores.append(_error(
                num_fila, "patologia_trazadora / ROAM",
                _pos(campos, "patologia_trazadora"),
                f"trazadora={patologia_trazadora}, roam={nro_denuncia_roam}, año={ano_denuncia_roam}",
                "Si patología trazadora es 'S', se deben informar número y año "
                "de denuncia ROAM.",
                norma, "ERROR", "BT",
                "Completar número y año de denuncia ROAM, o cambiar patología trazadora a 'N'."))

    # ═══════════════════════════════════════════════════════════
    # ROAM: CASO CRÓNICO, INTERCURRENCIA, RECALIFICACIÓN (pos 429-432)
    # Si alguna es S, verificar campos obligatorios relacionados
    # ═══════════════════════════════════════════════════════════

    # Caso crónico: si es S, verificar campos asociados
    if caso_cronico == "S":
        # Caso crónico requiere ROAM
        tiene_roam = (nro_denuncia_roam and nro_denuncia_roam != "0" * len(nro_denuncia_roam))
        tiene_ano_roam = (ano_denuncia_roam and ano_denuncia_roam != "0" * len(ano_denuncia_roam))
        if not tiene_roam or not tiene_ano_roam:
            errores.append(_error(
                num_fila, "caso_cronico / ROAM",
                _pos(campos, "caso_cronico"),
                f"caso_cronico=S, roam={nro_denuncia_roam}, año={ano_denuncia_roam}",
                "Si Caso Crónico es 'S', se deben informar número y año de denuncia ROAM.",
                norma, "ERROR", "BT",
                "Completar número y año de denuncia ROAM para el caso crónico."))

    # Recalificación: si es S, verificar campos asociados
    if recalificacion == "S":
        tiene_roam = (nro_denuncia_roam and nro_denuncia_roam != "0" * len(nro_denuncia_roam))
        tiene_ano_roam = (ano_denuncia_roam and ano_denuncia_roam != "0" * len(ano_denuncia_roam))
        if not tiene_roam or not tiene_ano_roam:
            errores.append(_error(
                num_fila, "recalificacion / ROAM",
                _pos(campos, "recalificacion"),
                f"recalificacion=S, roam={nro_denuncia_roam}, año={ano_denuncia_roam}",
                "Si Recalificación es 'S', se deben informar número y año de denuncia ROAM.",
                norma, "ERROR", "FL",
                "Completar número y año de denuncia ROAM para la recalificación."))

    # Intercurrencia: si es S, nro siniestro obligatorio
    if intercurrencia == "S" and (not nro_intercurrencia or nro_intercurrencia == "0" * len(nro_intercurrencia)):
        errores.append(_error(
            num_fila, "n__de_reg_del_at_con_el_que_se_produce_la_intercu",
            _pos(campos, "n__de_reg_del_at_con_el_que_se_produce_la_intercu"),
            nro_intercurrencia or "(vacío)",
            "Si Intercurrencia es 'S', el número de siniestro de "
            "intercurrencia es obligatorio.",
            norma, "ERROR", "FO",
            "Completar el número de siniestro del AT con el que se produce la intercurrencia."))

    # Intercurrencia: si es N, nro siniestro debe estar vacío
    if intercurrencia == "N" and nro_intercurrencia and nro_intercurrencia != "0" * len(nro_intercurrencia):
        errores.append(_error(
            num_fila, "n__de_reg_del_at_con_el_que_se_produce_la_intercu",
            _pos(campos, "n__de_reg_del_at_con_el_que_se_produce_la_intercu"),
            nro_intercurrencia,
            "Si Intercurrencia es 'N', el número de siniestro de "
            "intercurrencia no debe completarse.",
            norma, "ERROR", "FP",
            "Vaciar el número de siniestro de intercurrencia o cambiar Intercurrencia a 'S'."))

    # ═══════════════════════════════════════════════════════════
    # INGRESO BASE (pos 452-461) - Código SRT: FX
    # Si secuelas incapacitantes = S, ingreso base > 0.00
    # ═══════════════════════════════════════════════════════════
    if secuelas == "S":
        try:
            ingreso_base = float(ingreso_base_raw) if ingreso_base_raw else 0.0
        except ValueError:
            ingreso_base = 0.0
        if ingreso_base <= 0:
            errores.append(_error(
                num_fila, "ingreso_base",
                _pos(campos, "ingreso_base"),
                ingreso_base_raw or "(vacío)",
                f"Si secuelas incapacitantes es 'S', el ingreso base debe ser "
                f"mayor a 0.00. Se informó: {ingreso_base_raw or '0'}.",
                norma, "ERROR", "FX",
                "Ir al drawer del siniestro y colocar el ingreso base, "
                "o corregir por BD."))

    # ═══════════════════════════════════════════════════════════
    # ACCIDENTE IN ITINERE - Código SRT: FY
    # ═══════════════════════════════════════════════════════════
    if tipo_siniestro == "I" and ocurrencia_via_publica != "S":
        errores.append(_error(
            num_fila, "ocurrencia_en_via_publica",
            _pos(campos, "ocurrencia_en_via_publica"),
            ocurrencia_via_publica,
            "Para accidentes in itinere (tipo I), el campo Ocurrencia "
            "Vía Pública debe ser 'S'.",
            norma, "ERROR", "FY",
            "Cambiar Ocurrencia Vía Pública a 'S' en Detalle de Siniestros."))

    # ═══════════════════════════════════════════════════════════
    # CATEGORÍA RE (Rechazo) - Códigos SRT: FD, FF
    # Fecha y motivo de rechazo obligatorios
    # ═══════════════════════════════════════════════════════════
    if categoria == "RE":
        if not fecha_rechazo:
            errores.append(_error(
                num_fila, "fecha_rechazo",
                _pos(campos, "fecha_rechazo"),
                _val("fecha_rechazo") or "(vacío)",
                "Para categoría RE (Rechazo), la fecha de rechazo es obligatoria.",
                norma, "ERROR", "FD",
                "Completar la fecha de rechazo en el siniestro."))
        if not motivo_rechazo or motivo_rechazo == "0":
            errores.append(_error(
                num_fila, "motivo_rechazo",
                _pos(campos, "motivo_rechazo"),
                motivo_rechazo or "(vacío)",
                "Para categoría RE (Rechazo), el motivo de rechazo es obligatorio.",
                norma, "ERROR", "FF",
                "Completar el motivo de rechazo en el siniestro."))

    # ═══════════════════════════════════════════════════════════
    # CATEGORÍA MT (Mortal) - Código SRT: LM
    # Fecha de defunción obligatoria
    # ═══════════════════════════════════════════════════════════
    if categoria == "MT" and not fecha_defuncion:
        errores.append(_error(
            num_fila, "fecha_de_defuncion",
            _pos(campos, "fecha_de_defuncion"),
            _val("fecha_de_defuncion") or "(vacío)",
            "Para categoría MT (Mortal), la fecha de defunción es obligatoria.",
            norma, "ERROR", "LM",
            "Completar la fecha de defunción en el siniestro."))

    # ═══════════════════════════════════════════════════════════
    # FECHA INICIO INASISTENCIA > TOMA CONOCIMIENTO - Código SRT: LC
    # ═══════════════════════════════════════════════════════════
    if fecha_inicio_inasistencia and fecha_toma_conocimiento:
        if fecha_inicio_inasistencia > fecha_toma_conocimiento:
            errores.append(_error(
                num_fila, "fecha_inicio_inasistencia",
                _pos(campos, "fecha_inicio_inasistencia"),
                _val("fecha_inicio_inasistencia"),
                f"La fecha de inicio de inasistencia ({_val('fecha_inicio_inasistencia')}) "
                f"no puede ser posterior a la fecha de toma de conocimiento "
                f"({_val('fecha_toma_conocimiento')}).",
                norma, "ERROR", "LC",
                "Corregir las fechas en Detalle de Siniestros → General."))

    # ═══════════════════════════════════════════════════════════
    # DESCRIPCIÓN DEL SINIESTRO (relato) - Código SRT: LT
    # ═══════════════════════════════════════════════════════════
    if not relato:
        errores.append(_error(
            num_fila, "descripcion_del_siniestro",
            _pos(campos, "descripcion_del_siniestro"),
            "(vacío)",
            "El campo Descripción del Siniestro (relato) es obligatorio.",
            norma, "ERROR", "LT",
            "Completar el relato del siniestro en el sistema."))

    # ═══════════════════════════════════════════════════════════
    # COHERENCIA FECHAS GENERALES - Código SRT: W5
    # ═══════════════════════════════════════════════════════════
    if fecha_ocurrencia and fecha_inicio_inasistencia:
        if fecha_inicio_inasistencia < fecha_ocurrencia:
            errores.append(_error(
                num_fila, "fecha_de_ocurrencia",
                _pos(campos, "fecha_de_ocurrencia"),
                _val("fecha_de_ocurrencia"),
                f"La fecha de inicio de inasistencia ({_val('fecha_inicio_inasistencia')}) "
                f"es anterior a la fecha de ocurrencia ({_val('fecha_de_ocurrencia')}). "
                f"No es coherente.",
                norma, "ERROR", "W5",
                "Corregir las fechas en Detalle de Siniestros → General."))

    # ═══════════════════════════════════════════════════════════
    # FECHA CESE ILT NO EXCEDER 1 AÑO - Código SRT: DG
    # ═══════════════════════════════════════════════════════════
    if categoria in CATEGORIAS_CON_BAJA and fecha_cese_ilt and fecha_ocurrencia:
        un_anio = fecha_ocurrencia + timedelta(days=365)
        if fecha_cese_ilt > un_anio:
            errores.append(_error(
                num_fila, "fecha_cese_ilt",
                _pos(campos, "fecha_cese_ilt"),
                _val("fecha_cese_ilt"),
                f"Para categoría {categoria}, la fecha de cese ILT no puede "
                f"superar 1 año desde la ocurrencia del siniestro original.",
                norma, "ERROR", "DG",
                "Verificar si corresponde cerrar el ILT o si hay un error en las fechas."))

    # ═══════════════════════════════════════════════════════════
    # FORMA DE INGRESO DE LA DENUNCIA - Código SRT: LK, LJ
    # ═══════════════════════════════════════════════════════════
    forma_ingreso = _val("forma_de_ingreso_de_la_denuncia")
    if not forma_ingreso or forma_ingreso == "0" * len(forma_ingreso):
        errores.append(_error(
            num_fila, "forma_de_ingreso_de_la_denuncia",
            _pos(campos, "forma_de_ingreso_de_la_denuncia"),
            forma_ingreso or "(vacío)",
            "El campo Forma de Ingreso de la Denuncia es obligatorio.",
            norma, "ERROR", "LK",
            "Completar la forma de ingreso de la denuncia en el sistema."))
    elif forma_ingreso not in ("TL", "CD", "EM", "PR", "ME", "ST", "PE"):
        errores.append(_error(
            num_fila, "forma_de_ingreso_de_la_denuncia",
            _pos(campos, "forma_de_ingreso_de_la_denuncia"),
            forma_ingreso,
            f"Forma de ingreso de la denuncia inválida: '{forma_ingreso}'. "
            f"Valores válidos: TL, CD, EM, PR, ME, ST, PE.",
            norma, "ERROR", "LJ",
            "Corregir la forma de ingreso de la denuncia en el sistema."))

    # ═══════════════════════════════════════════════════════════
    # CUIL TRABAJADOR - Código SRT: 47
    # Validar formato y dígito verificador
    # ═══════════════════════════════════════════════════════════
    cuil = _val("cuil_trabajador")
    if cuil:
        if not cuil.isdigit() or len(cuil) != 11:
            errores.append(_error(
                num_fila, "cuil_trabajador",
                _pos(campos, "cuil_trabajador"),
                cuil,
                f"CUIL inválida: debe ser numérico de 11 dígitos. Se informó: '{cuil}'.",
                norma, "ERROR", "47",
                "Corregir la CUIL del trabajador en el sistema."))
        elif not _validar_cuit_cuil(cuil):
            errores.append(_error(
                num_fila, "cuil_trabajador",
                _pos(campos, "cuil_trabajador"),
                cuil,
                f"CUIL inválida: dígito verificador incorrecto para '{cuil}'.",
                norma, "ERROR", "47",
                "Verificar la CUIL del trabajador. El dígito verificador no es correcto."))

    # CUIT empleador - también validar
    cuit_emp = _val("cuit_empleador")
    if cuit_emp:
        if not cuit_emp.isdigit() or len(cuit_emp) != 11:
            errores.append(_error(
                num_fila, "cuit_empleador",
                _pos(campos, "cuit_empleador"),
                cuit_emp,
                f"CUIT empleador inválida: debe ser numérico de 11 dígitos.",
                norma, "ERROR", "47",
                "Corregir la CUIT del empleador en el sistema."))
        elif not _validar_cuit_cuil(cuit_emp):
            errores.append(_error(
                num_fila, "cuit_empleador",
                _pos(campos, "cuit_empleador"),
                cuit_emp,
                f"CUIT empleador inválida: dígito verificador incorrecto para '{cuit_emp}'.",
                norma, "ERROR", "47",
                "Verificar la CUIT del empleador."))

    # ═══════════════════════════════════════════════════════════
    # SEXO - Código SRT: 49
    # ═══════════════════════════════════════════════════════════
    sexo = _val("sexo")
    if sexo and sexo not in ("M", "F"):
        errores.append(_error(
            num_fila, "sexo",
            _pos(campos, "sexo"),
            sexo,
            f"Sexo inválido: '{sexo}'. Debe ser 'M' (Masculino) o 'F' (Femenino).",
            norma, "ERROR", "49",
            "Corregir el sexo del trabajador en el sistema."))

    # ═══════════════════════════════════════════════════════════
    # NATURALEZA DE LA LESIÓN 1 - Código SRT: 50
    # Debe ser numérico de 2 dígitos, distinto de 00
    # ═══════════════════════════════════════════════════════════
    nat1 = _val("naturaleza_de_la_lesion_1")
    if nat1 and nat1 != "00":
        if not nat1.isdigit() or len(nat1) != 2:
            errores.append(_error(
                num_fila, "naturaleza_de_la_lesion_1",
                _pos(campos, "naturaleza_de_la_lesion_1"),
                nat1,
                f"Código de Naturaleza de la Lesión inválido: '{nat1}'. "
                f"Debe ser numérico de 2 dígitos.",
                norma, "ERROR", "50",
                "Corregir la naturaleza de la lesión en el siniestro."))
    elif nat1 == "00" and categoria:
        # 00 no es válido si el campo es obligatorio (tiene diagnóstico)
        diag1 = _val("diagnostico_1__cie_10")
        if diag1 and diag1.strip():
            errores.append(_error(
                num_fila, "naturaleza_de_la_lesion_1",
                _pos(campos, "naturaleza_de_la_lesion_1"),
                nat1,
                "Código de Naturaleza de la Lesión no puede ser '00' si hay diagnóstico informado.",
                norma, "ERROR", "50",
                "Completar la naturaleza de la lesión correspondiente al diagnóstico."))

    # ═══════════════════════════════════════════════════════════
    # ZONA DEL CUERPO 1 - Código SRT: 53
    # Debe ser numérico de 3 dígitos, distinto de 000
    # ═══════════════════════════════════════════════════════════
    zona1 = _val("zona_del_cuerpo_1")
    if zona1 and zona1 != "000":
        if not zona1.isdigit() or len(zona1) != 3:
            errores.append(_error(
                num_fila, "zona_del_cuerpo_1",
                _pos(campos, "zona_del_cuerpo_1"),
                zona1,
                f"Código de Zona del Cuerpo inválido: '{zona1}'. "
                f"Debe ser numérico de 3 dígitos.",
                norma, "ERROR", "53",
                "Corregir la zona del cuerpo afectada en el siniestro."))
    elif zona1 == "000":
        diag1 = _val("diagnostico_1__cie_10")
        if diag1 and diag1.strip():
            errores.append(_error(
                num_fila, "zona_del_cuerpo_1",
                _pos(campos, "zona_del_cuerpo_1"),
                zona1,
                "Código de Zona del Cuerpo no puede ser '000' si hay diagnóstico informado.",
                norma, "ERROR", "53",
                "Completar la zona del cuerpo correspondiente al diagnóstico."))

    # ═══════════════════════════════════════════════════════════
    # FORMA DEL ACCIDENTE - Código SRT: 54
    # Debe ser numérico de 3 dígitos, distinto de 000
    # ═══════════════════════════════════════════════════════════
    forma_acc = _val("forma_del_accidente")
    if forma_acc and forma_acc != "000":
        if not forma_acc.isdigit() or len(forma_acc) != 3:
            errores.append(_error(
                num_fila, "forma_del_accidente",
                _pos(campos, "forma_del_accidente"),
                forma_acc,
                f"Código de Forma del Accidente inválido: '{forma_acc}'. "
                f"Debe ser numérico de 3 dígitos.",
                norma, "ERROR", "54",
                "Corregir la forma del accidente en el siniestro."))

    # ═══════════════════════════════════════════════════════════
    # CÓDIGO POSTAL - Código SRT: 55
    # Debe ser numérico o CPA válido, no vacío ni todo ceros
    # ═══════════════════════════════════════════════════════════
    cp = _val("codigo_postal")
    if cp and cp != "0" * len(cp):
        # CPA format: L + 4 dígitos + 3 letras (ej: C1425DKA) o numérico puro (ej: 1425)
        cp_limpio = cp.strip()
        es_numerico = cp_limpio.isdigit()
        es_cpa = (len(cp_limpio) == 8 and cp_limpio[0].isalpha()
                  and cp_limpio[1:5].isdigit() and cp_limpio[5:8].isalpha())
        if not es_numerico and not es_cpa:
            errores.append(_error(
                num_fila, "codigo_postal",
                _pos(campos, "codigo_postal"),
                cp,
                f"Código Postal o CPA incorrecto: '{cp}'. "
                f"Debe ser numérico (ej: 1425) o CPA (ej: C1425DKA).",
                norma, "ERROR", "55",
                "Corregir el código postal del lugar de ocurrencia."))

    # ═══════════════════════════════════════════════════════════
    # DIAGNÓSTICO CIE-10 - Código SRT: 59
    # Formato: 1 letra + 2-3 dígitos (ej: S610, M544, T141)
    # ═══════════════════════════════════════════════════════════
    diag1 = _val("diagnostico_1__cie_10")
    if diag1 and diag1.strip():
        diag_limpio = diag1.strip()
        es_cie10 = (len(diag_limpio) >= 3 and len(diag_limpio) <= 4
                    and diag_limpio[0].isalpha()
                    and diag_limpio[1:].isdigit())
        if not es_cie10:
            errores.append(_error(
                num_fila, "diagnostico_1__cie_10",
                _pos(campos, "diagnostico_1__cie_10"),
                diag1,
                f"Diagnóstico CIE-10 inválido: '{diag_limpio}'. "
                f"Formato esperado: 1 letra + 2-3 dígitos (ej: S610, M544).",
                norma, "ERROR", "59",
                "Corregir el diagnóstico CIE-10 en el siniestro."))

    # ═══════════════════════════════════════════════════════════
    # FECHA DE NACIMIENTO - Código SRT: 77
    # Debe ser fecha válida, no futura, razonable (edad 14-120)
    # ═══════════════════════════════════════════════════════════
    fecha_nac = _fecha("fecha_nacimiento")
    fecha_nac_raw = _val("fecha_nacimiento")
    if fecha_nac_raw and fecha_nac_raw != "0" * len(fecha_nac_raw):
        if not fecha_nac:
            errores.append(_error(
                num_fila, "fecha_nacimiento",
                _pos(campos, "fecha_nacimiento"),
                fecha_nac_raw,
                f"Fecha de nacimiento inválida: '{fecha_nac_raw}'. "
                f"No es una fecha válida con formato YYYYMMDD.",
                norma, "ERROR", "77",
                "Corregir la fecha de nacimiento del trabajador."))
        else:
            ahora = datetime.now()
            if fecha_nac > ahora:
                errores.append(_error(
                    num_fila, "fecha_nacimiento",
                    _pos(campos, "fecha_nacimiento"),
                    fecha_nac_raw,
                    "Fecha de nacimiento es posterior a la fecha actual.",
                    norma, "ERROR", "77",
                    "Corregir la fecha de nacimiento del trabajador."))
            elif fecha_ocurrencia:
                edad = (fecha_ocurrencia - fecha_nac).days // 365
                if edad < 14:
                    errores.append(_error(
                        num_fila, "fecha_nacimiento",
                        _pos(campos, "fecha_nacimiento"),
                        fecha_nac_raw,
                        f"La edad del trabajador al momento del siniestro sería {edad} años. "
                        f"Menor a la edad laboral mínima (14).",
                        norma, "WARNING", "77",
                        "Verificar la fecha de nacimiento del trabajador."))

    # ═══════════════════════════════════════════════════════════
    # CÓDIGO DE LOCALIDAD - Código SRT: AM
    # Debe ser alfanumérico válido, no vacío ni todo ceros
    # ═══════════════════════════════════════════════════════════
    cod_loc = _val("codigo_localidad")
    cod_prov = _val("codigo_provincia")
    if cod_loc and cod_loc.replace("0", "").strip() == "":
        # Todo ceros = localidad no informada (ya se valida como obligatorio)
        pass
    elif cod_loc and cod_prov:
        # Validar que provincia es numérica de 2 dígitos y localidad coherente
        if not cod_prov.isdigit() or len(cod_prov) != 2:
            errores.append(_error(
                num_fila, "codigo_provincia",
                _pos(campos, "codigo_provincia"),
                cod_prov,
                f"Código de provincia inválido: '{cod_prov}'. Debe ser numérico de 2 dígitos.",
                norma, "ERROR", "AM",
                "Corregir el código de provincia del lugar de ocurrencia."))
        elif int(cod_prov) < 1 or int(cod_prov) > 24:
            errores.append(_error(
                num_fila, "codigo_provincia",
                _pos(campos, "codigo_provincia"),
                cod_prov,
                f"Código de provincia fuera de rango: '{cod_prov}'. Debe estar entre 01 y 24.",
                norma, "ERROR", "AM",
                "Corregir el código de provincia del lugar de ocurrencia."))

    # ═══════════════════════════════════════════════════════════
    # B6: SECUELAS INCAPACITANTES + EGRESO P o A
    # Si SB/CB con Secuelas=S, el egreso debe ser P (Permanente) o A (Alta con ILP)
    # ═══════════════════════════════════════════════════════════
    if secuelas == "S" and motivo_cese_ilt:
        if categoria in (CATEGORIAS_CON_BAJA | CATEGORIAS_SIN_BAJA):
            if motivo_cese_ilt not in ("P", "A"):
                errores.append(_error(
                    num_fila, "motivo_cese_ilt",
                    _pos(campos, "motivo_cese_ilt"),
                    motivo_cese_ilt,
                    f"Si hay Secuelas Incapacitantes (S), la Forma de Egreso debe ser "
                    f"'P' (Permanente) o 'A' (Alta con ILP). Se informó: '{motivo_cese_ilt}'.",
                    norma, "ERROR", "B6",
                    "Cambiar la forma de egreso a 'P' o 'A' en Detalle de Siniestros."))

    # ═══════════════════════════════════════════════════════════
    # E0: PATOLOGÍA TRAZADORA distinto de S/N
    # ═══════════════════════════════════════════════════════════
    if patologia_trazadora and patologia_trazadora not in ("S", "N"):
        errores.append(_error(
            num_fila, "patologia_trazadora",
            _pos(campos, "patologia_trazadora"),
            patologia_trazadora,
            f"Patología Trazadora inválida: '{patologia_trazadora}'. Debe ser 'S' o 'N'.",
            norma, "ERROR", "E0",
            "Corregir el valor de Patología Trazadora a 'S' o 'N'."))

    # ═══════════════════════════════════════════════════════════
    # FB: OCURRENCIA VÍA PÚBLICA inválido
    # ═══════════════════════════════════════════════════════════
    if ocurrencia_via_publica and ocurrencia_via_publica not in ("S", "N"):
        errores.append(_error(
            num_fila, "ocurrencia_en_via_publica",
            _pos(campos, "ocurrencia_en_via_publica"),
            ocurrencia_via_publica,
            f"Campo Ocurrencia Vía Pública inválido: '{ocurrencia_via_publica}'. "
            f"Debe ser 'S' o 'N'.",
            norma, "ERROR", "FB",
            "Corregir el campo Ocurrencia Vía Pública a 'S' o 'N'."))

    # ═══════════════════════════════════════════════════════════
    # LN: FECHA DE DEFUNCIÓN incorrecta
    # Si está informada, debe ser coherente con la ocurrencia
    # ═══════════════════════════════════════════════════════════
    if fecha_defuncion:
        if fecha_ocurrencia and fecha_defuncion < fecha_ocurrencia:
            errores.append(_error(
                num_fila, "fecha_de_defuncion",
                _pos(campos, "fecha_de_defuncion"),
                _val("fecha_de_defuncion"),
                f"Fecha de defunción ({_val('fecha_de_defuncion')}) es anterior a "
                f"la fecha de ocurrencia ({_val('fecha_de_ocurrencia')}). No es coherente.",
                norma, "ERROR", "LN",
                "Corregir la fecha de defunción en el siniestro."))

    fecha_defuncion_raw = _val("fecha_de_defuncion")
    if fecha_defuncion_raw and fecha_defuncion_raw != "0" * len(fecha_defuncion_raw) and not fecha_defuncion:
        errores.append(_error(
            num_fila, "fecha_de_defuncion",
            _pos(campos, "fecha_de_defuncion"),
            fecha_defuncion_raw,
            f"Fecha de defunción inválida: '{fecha_defuncion_raw}'. "
            f"No es una fecha válida con formato YYYYMMDD.",
            norma, "ERROR", "LN",
            "Corregir la fecha de defunción en el siniestro."))

    # ═══════════════════════════════════════════════════════════
    # LÑ: TIPO PRESTADOR MÉDICO 1RA ATENCIÓN inválido
    # ═══════════════════════════════════════════════════════════
    if tipo_prestador and tipo_prestador not in ("0", "") and tipo_prestador not in ("1", "2", "3", "4"):
        errores.append(_error(
            num_fila, "tipo_prestador_medico_de_la_1ra_atencion",
            _pos(campos, "tipo_prestador_medico_de_la_1ra_atencion"),
            tipo_prestador,
            f"Tipo Prestador Médico 1ra Atención inválido: '{tipo_prestador}'. "
            f"Valores válidos: 1, 2, 3, 4.",
            norma, "ERROR", "LÑ",
            "Corregir el tipo de prestador médico de primera atención."))

    # ═══════════════════════════════════════════════════════════
    # C0: VALORES OBLIGATORIOS FALTANTES (forma accid, zona, naturaleza)
    # Campos que deben estar completos cuando hay diagnóstico
    # ═══════════════════════════════════════════════════════════
    diag_presente = _val("diagnostico_1__cie_10") and _val("diagnostico_1__cie_10").strip()
    campos_c0_faltantes = []
    if not _val("forma_del_accidente") or _val("forma_del_accidente") == "000":
        campos_c0_faltantes.append("Forma del Accidente")
    if not _val("zona_del_cuerpo_1") or _val("zona_del_cuerpo_1") == "000":
        campos_c0_faltantes.append("Zona del Cuerpo")
    if not _val("naturaleza_de_la_lesion_1") or _val("naturaleza_de_la_lesion_1") == "00":
        campos_c0_faltantes.append("Naturaleza de la Lesión")
    if not diag_presente:
        campos_c0_faltantes.append("Diagnóstico CIE-10")

    if campos_c0_faltantes:
        errores.append(_error(
            num_fila, "campos_obligatorios_diagnostico",
            "N/A",
            f"Faltantes: {', '.join(campos_c0_faltantes)}",
            f"Faltan valores obligatorios: {', '.join(campos_c0_faltantes)}. "
            f"Estos campos son requeridos para todo siniestro.",
            norma, "ERROR", "C0",
            "Completar los campos de diagnóstico faltantes en el siniestro."))

    # ═══════════════════════════════════════════════════════════
    # 75: FECHA CESE ILT Y/O CÓDIGO DE EGRESO VACÍO
    # Complementa B8: si categoría con baja y tiene alta médica,
    # deberían tener fecha cese y egreso
    # ═══════════════════════════════════════════════════════════
    if categoria in CATEGORIAS_CON_BAJA and fecha_alta_medica:
        if not fecha_cese_ilt and not motivo_cese_ilt:
            errores.append(_error(
                num_fila, "fecha_cese_ilt / motivo_cese_ilt",
                f"{_pos(campos, 'fecha_cese_ilt')} / {_pos(campos, 'motivo_cese_ilt')}",
                "(ambos vacíos)",
                f"Para categoría {categoria} con alta médica informada, "
                f"se esperan Fecha de Cese ILT y Código de Egreso.",
                norma, "WARNING", "75",
                "Completar la fecha de cese ILT y la forma de egreso."))

    return errores


# ── Funciones auxiliares ──

def _validar_cuit_cuil(cuit: str) -> bool:
    """
    Valida el dígito verificador de una CUIT/CUIL argentina.
    Algoritmo oficial de AFIP: módulo 11 con pesos [5,4,3,2,7,6,5,4,3,2].
    """
    if not cuit or len(cuit) != 11 or not cuit.isdigit():
        return False
    pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = sum(int(cuit[i]) * pesos[i] for i in range(10))
    resto = suma % 11
    if resto == 0:
        verificador = 0
    elif resto == 1:
        verificador = 9  # Caso especial
    else:
        verificador = 11 - resto
    return int(cuit[10]) == verificador


def _error(
    fila: int, campo: str, posicion: str, valor: str,
    error: str, referencia: str, severidad: str,
    codigo_srt: str | None = None,
    resolucion: str | None = None
) -> dict:
    """Construye un dict de error estandarizado."""
    resultado = {
        "fila": fila,
        "campo": campo,
        "posicion": posicion,
        "valor_encontrado": valor,
        "error": error,
        "referencia_norma": referencia,
        "severidad": severidad,
    }
    if codigo_srt:
        resultado["codigo_srt"] = codigo_srt
    if resolucion:
        resultado["resolucion"] = resolucion
    return resultado


def _pos(campos: dict, nombre: str) -> str:
    """Retorna string de posición 'inicio-fin' para un campo."""
    campo = campos.get(nombre)
    if not campo:
        return "N/A"
    return f"{campo['posicion_inicio']}-{campo['posicion_inicio'] + campo['longitud'] - 1}"


def generar_resumen_validacion(errores: list[dict]) -> dict:
    """
    Genera un resumen de validación para el agente.

    Returns:
        Dict con: es_valido, total_errores, errores_por_tipo,
        errores_por_codigo_srt, errores
    """
    if not errores:
        return {
            "es_valido": True,
            "total_errores": 0,
            "errores_por_tipo": {},
            "errores_por_codigo_srt": {},
            "errores": [],
        }

    errores_por_tipo = {}
    errores_por_codigo_srt = {}

    for error in errores:
        tipo = error["campo"]
        errores_por_tipo[tipo] = errores_por_tipo.get(tipo, 0) + 1

        codigo = error.get("codigo_srt")
        if codigo:
            if codigo not in errores_por_codigo_srt:
                errores_por_codigo_srt[codigo] = {
                    "cantidad": 0,
                    "ejemplo": error["error"],
                    "resolucion": error.get("resolucion", ""),
                }
            errores_por_codigo_srt[codigo]["cantidad"] += 1

    return {
        "es_valido": False,
        "total_errores": len(errores),
        "errores_por_tipo": errores_por_tipo,
        "errores_por_codigo_srt": errores_por_codigo_srt,
        "errores": errores[:50],  # Limitar para no saturar el contexto del LLM
    }
