# Pendientes — Campos reales de las Resoluciones SRT

Este documento rastrea el gap entre los esquemas simplificados de la PoC
y los esquemas completos requeridos para producción.

Los esquemas actuales en `schemas/` son funcionales end-to-end pero usan
un subconjunto de campos. Antes de pasar a producción, deben completarse
con todos los campos de cada resolución.

---

## Resolución 3326/2014 — Accidentes de Trabajo (AT)

### Campos pendientes en AT Alta (`at_3326_alta.json`)

| Campo | Descripción | Pos estimada | Long | Tipo |
|-------|-------------|-------------|------|------|
| cuil_empleador | CUIL del empleador (ART) | — | 11 | N |
| cuit_art | CUIT de la ART | — | 11 | N |
| codigo_actividad | Código de actividad económica (CIIU) | — | 6 | N |
| siniestralidad_ant | Indicador de siniestralidad anterior | — | 1 | N |
| lugar_siniestro | Descripción del lugar del siniestro | — | 60 | A |
| descripcion_siniestro | Descripción breve del siniestro | — | 100 | A |
| parte_cuerpo | Código de parte del cuerpo afectada | — | 3 | N |
| naturaleza_lesion | Código de naturaleza de la lesión | — | 3 | N |
| agente_material | Agente material del siniestro | — | 3 | N |
| forma_siniestro | Forma en que ocurrió el siniestro | — | 3 | N |
| testigos | Indicador de presencia de testigos (S/N) | — | 1 | A |
| requirio_internacion | Indicador de internación (S/N) | — | 1 | A |
| dias_internacion | Cantidad de días de internación | — | 3 | N |
| codigo_medico_tratante | Matrícula del médico tratante | — | 10 | N |

### Campos pendientes en AT Baja (`at_3326_baja.json`)

| Campo | Descripción | Long | Tipo |
|-------|-------------|------|------|
| codigo_resultado | Resultado de la prestación médica | 2 | N |
| porcentaje_incapacidad | Porcentaje de incapacidad determinado | 5 | N |
| tipo_incapacidad | Tipo de incapacidad (temporal/permanente) | 2 | N |
| fecha_alta_medica | Fecha efectiva de alta médica | 8 | F |
| nro_expediente | Número de expediente SRT | 15 | A |

---

## Resolución 3327/2014 — Enfermedades Profesionales (EP)

### Campos pendientes en EP Alta (`ep_3327_alta.json`)

| Campo | Descripción | Long | Tipo |
|-------|-------------|------|------|
| cuil_empleador | CUIL del empleador | 11 | N |
| cuit_art | CUIT de la ART | 11 | N |
| tiempo_exposicion_anios | Años de exposición al agente | 3 | N |
| tiempo_exposicion_meses | Meses adicionales de exposición | 2 | N |
| descripcion_tarea | Descripción de la tarea realizada | 80 | A |
| ambiente_trabajo | Descripción del ambiente de trabajo | 80 | A |
| medidas_prevencion | Indicador de medidas de prevención (S/N) | 1 | A |
| epp_utilizado | Indicador de EPP utilizado (S/N) | 1 | A |
| nro_comision_medica | Número de comisión médica interviniente | 5 | N |
| requirio_junta_medica | Indicador de junta médica (S/N) | 1 | A |

### Campos pendientes en EP Baja (`ep_3327_baja.json`)

| Campo | Descripción | Long | Tipo |
|-------|-------------|------|------|
| porcentaje_incapacidad | Porcentaje de incapacidad determinado | 5 | N |
| tipo_incapacidad | Tipo de incapacidad | 2 | N |
| fecha_dictamen | Fecha de dictamen de la comisión médica | 8 | F |
| nro_expediente | Número de expediente SRT | 15 | A |
| resolucion_srt | Número de resolución SRT asociada | 10 | A |

---

## valores_validos pendientes de completar

Los siguientes campos tienen `valores_validos: null` pero deberían tener
listas completas según los anexos de las resoluciones:

| Esquema | Campo | Fuente de los valores |
|---------|-------|-----------------------|
| AT Alta | `codigo_diagnostico` | CIE-10 (lista completa ~14.000 códigos) |
| AT Alta | `tipo_accidente` | Resolución 463/2009 Anexo I |
| EP Alta | `codigo_enfermedad` | Decreto 658/96 + actualizaciones |
| EP Alta | `agente_causante` | Decreto 658/96 Anexo I |
| Todos | `codigo_provincia` | Completo (ya implementado: 01-24) |

---

## Longitudes de registro a confirmar

Los esquemas actuales usan longitud_registro=200 para todos los formatos.
Verificar contra los archivos de especificación técnica oficiales de la SRT:

- [ ] AT Alta: confirmar longitud exacta con SRT
- [ ] AT Baja: confirmar longitud exacta con SRT
- [ ] EP Alta: confirmar longitud exacta con SRT
- [ ] EP Baja: confirmar longitud exacta con SRT

---

## Prioridad de completado

1. **Alta prioridad** (afectan validación en producción):
   - Completar `valores_validos` para `codigo_enfermedad` y `agente_causante`
   - Confirmar longitudes de registro con documentación oficial SRT
   - Agregar `cuil_empleador` y `cuit_art` (campos frecuentemente usados)

2. **Media prioridad** (mejoran calidad de datos):
   - Agregar campos de descripción textual (lugar, naturaleza, forma)
   - Agregar `parte_cuerpo` y `naturaleza_lesion`

3. **Baja prioridad** (para fases posteriores):
   - Campos de expediente y resolución SRT
   - Indicadores de internación y médico tratante
