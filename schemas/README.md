# Esquemas JSON de Formatos Posicionales

Cada archivo JSON define campo por campo el formato posicional de un tipo de declaración SRT.

## Archivos

| Archivo | Norma | Tipo | Operación |
|---------|-------|------|-----------|
| `at_3326_alta.json` | Res. 3326/2014 | AT (Accidente de Trabajo) | Alta |
| `at_3326_baja.json` | Res. 3326/2014 | AT | Baja |
| `ep_3327_alta.json` | Res. 3327/2014 | EP (Enfermedad Profesional) | Alta |
| `ep_3327_baja.json` | Res. 3327/2014 | EP | Baja |

## Cómo agregar un nuevo esquema

1. Copiar un esquema existente como template
2. Actualizar `metadata` (norma, tipo, operación, longitud_registro)
3. Definir cada campo con sus atributos
4. Verificar que la suma de `longitud` de todos los campos == `longitud_registro`
5. Ejecutar los tests: `pytest tests/test_motor.py`

## Estructura de un campo

```json
{
  "nombre": "cuil_trabajador",
  "descripcion": "CUIL del trabajador sin guiones",
  "posicion_inicio": 2,
  "longitud": 11,
  "tipo": "N",
  "padding_char": "0",
  "alineacion": "right",
  "obligatorio": true,
  "valores_validos": null,
  "fuente_dato": "endpoint:cuil_trabajador"
}
```

### Tipos de dato
- `N` — Numérico (padding con `0`, alineado a la derecha)
- `A` — Alfanumérico (padding con espacio, alineado a la izquierda)
- `F` — Fecha formato YYYYMMDD

### Fuentes de dato
- `constante:X` — Valor fijo (ej: `constante:1`)
- `endpoint:campo` — Viene del JSON del endpoint Java
- `calculado:formula` — Campo derivado (futuro)
