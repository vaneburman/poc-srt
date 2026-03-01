"""Tests para el motor de generación y validación TXT posicional."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.utils import aplicar_padding, validar_tipo, extraer_valor_campo


# ============================================================
# Tests de utilidades de formateo
# ============================================================

class TestAplicarPadding:
    def test_numerico_right_align(self):
        assert aplicar_padding("123", 11, "0", "right") == "00000000123"

    def test_alfanumerico_left_align(self):
        resultado = aplicar_padding("PEREZ", 30, " ", "left")
        assert resultado == "PEREZ" + " " * 25
        assert len(resultado) == 30

    def test_truncamiento_excede_longitud(self):
        resultado = aplicar_padding("NOMBRE MUY LARGO PARA EL CAMPO", 20, " ", "left")
        assert resultado == "NOMBRE MUY LARGO PAR"
        assert len(resultado) == 20

    def test_valor_vacio(self):
        assert aplicar_padding("", 5, "0", "right") == "00000"
        assert aplicar_padding("", 5, " ", "left") == "     "

    def test_valor_none(self):
        assert aplicar_padding(None, 5, "0", "right") == "00000"

    def test_valor_exacto(self):
        assert aplicar_padding("12345", 5, "0", "right") == "12345"

    def test_fecha_padding(self):
        assert aplicar_padding("20240115", 8, "0", "right") == "20240115"

    def test_cuil_padding(self):
        assert aplicar_padding("20345678901", 11, "0", "right") == "20345678901"

    def test_cuil_corto_padding(self):
        assert aplicar_padding("345678901", 11, "0", "right") == "00345678901"


class TestValidarTipo:
    def test_numerico_valido(self):
        assert validar_tipo("00000012345", "N") is True

    def test_numerico_invalido(self):
        assert validar_tipo("123ABC", "N") is False

    def test_numerico_espacios(self):
        assert validar_tipo("     ", "N") is True  # Campo vacío permitido

    def test_numerico_ceros(self):
        assert validar_tipo("00000", "N") is True

    def test_fecha_valida(self):
        assert validar_tipo("20240115", "F") is True

    def test_fecha_invalida_mes(self):
        assert validar_tipo("20241315", "F") is False

    def test_fecha_invalida_dia(self):
        assert validar_tipo("20240132", "F") is False

    def test_fecha_vacia(self):
        assert validar_tipo("00000000", "F") is True

    def test_alfanumerico_cualquiera(self):
        assert validar_tipo("ABC 123 !@#", "A") is True


class TestExtraerValorCampo:
    def test_primer_campo(self):
        linea = "120345678901GONZALEZ"
        assert extraer_valor_campo(linea, 1, 1) == "1"

    def test_cuil(self):
        linea = "120345678901GONZALEZ"
        assert extraer_valor_campo(linea, 2, 11) == "20345678901"

    def test_apellido(self):
        linea = "120345678901GONZALEZ                      "  # 42 chars: 12 prefix + 30 field
        assert extraer_valor_campo(linea, 13, 30) == "GONZALEZ                      "[:30]


# ============================================================
# Tests del motor de generación
# ============================================================

class TestGeneradorRegistro:
    @pytest.fixture
    def esquema_simple(self):
        return {
            "metadata": {
                "norma": "Test",
                "tipo": "AT",
                "operacion": "A",
                "longitud_registro": 45,
                "encoding": "latin-1",
                "line_separator": "\r\n",
            },
            "campos": [
                {
                    "nombre": "tipo_registro",
                    "posicion_inicio": 1,
                    "longitud": 1,
                    "tipo": "N",
                    "padding_char": "0",
                    "alineacion": "right",
                    "obligatorio": True,
                    "fuente_dato": "constante:1",
                },
                {
                    "nombre": "cuil",
                    "posicion_inicio": 2,
                    "longitud": 11,
                    "tipo": "N",
                    "padding_char": "0",
                    "alineacion": "right",
                    "obligatorio": True,
                    "fuente_dato": "endpoint:cuil_trabajador",
                },
                {
                    "nombre": "apellido",
                    "posicion_inicio": 13,
                    "longitud": 20,
                    "tipo": "A",
                    "padding_char": " ",
                    "alineacion": "left",
                    "obligatorio": True,
                    "fuente_dato": "endpoint:apellido",
                },
                {
                    "nombre": "fecha",
                    "posicion_inicio": 33,
                    "longitud": 8,
                    "tipo": "F",
                    "padding_char": "0",
                    "alineacion": "right",
                    "obligatorio": True,
                    "fuente_dato": "endpoint:fecha_siniestro",
                },
                {
                    "nombre": "filler",
                    "posicion_inicio": 41,
                    "longitud": 5,
                    "tipo": "A",
                    "padding_char": " ",
                    "alineacion": "left",
                    "obligatorio": False,
                    "fuente_dato": "constante: ",
                },
            ],
        }

    @pytest.fixture
    def datos_siniestro(self):
        return {
            "cuil_trabajador": "20345678901",
            "apellido": "GONZALEZ",
            "fecha_siniestro": "20240115",
        }

    def test_generar_registro_longitud_correcta(self, esquema_simple, datos_siniestro):
        from motor.generador import generar_registro
        registro = generar_registro(datos_siniestro, esquema_simple)
        assert len(registro) == 45

    def test_generar_registro_tipo_registro(self, esquema_simple, datos_siniestro):
        from motor.generador import generar_registro
        registro = generar_registro(datos_siniestro, esquema_simple)
        assert registro[0] == "1"

    def test_generar_registro_cuil(self, esquema_simple, datos_siniestro):
        from motor.generador import generar_registro
        registro = generar_registro(datos_siniestro, esquema_simple)
        assert registro[1:12] == "20345678901"

    def test_generar_registro_apellido_padded(self, esquema_simple, datos_siniestro):
        from motor.generador import generar_registro
        registro = generar_registro(datos_siniestro, esquema_simple)
        apellido = registro[12:32]
        assert apellido == "GONZALEZ            "
        assert len(apellido) == 20

    def test_generar_archivo_multiples_registros(self, esquema_simple):
        from motor.generador import generar_registro
        datos_lista = [
            {"cuil_trabajador": "20345678901", "apellido": "GONZALEZ", "fecha_siniestro": "20240115"},
            {"cuil_trabajador": "27298765432", "apellido": "MARTINEZ", "fecha_siniestro": "20240118"},
        ]
        for datos in datos_lista:
            registro = generar_registro(datos, esquema_simple)
            assert len(registro) == 45


# ============================================================
# Tests del motor de validación
# ============================================================

class TestValidador:
    @pytest.fixture
    def esquema_simple(self):
        return {
            "metadata": {
                "norma": "Test",
                "tipo": "AT",
                "operacion": "A",
                "longitud_registro": 15,
                "encoding": "latin-1",
                "line_separator": "\r\n",
            },
            "campos": [
                {
                    "nombre": "tipo_registro",
                    "descripcion": "Tipo registro",
                    "posicion_inicio": 1,
                    "longitud": 1,
                    "tipo": "N",
                    "padding_char": "0",
                    "alineacion": "right",
                    "obligatorio": True,
                    "valores_validos": ["1"],
                },
                {
                    "nombre": "codigo",
                    "descripcion": "Código",
                    "posicion_inicio": 2,
                    "longitud": 4,
                    "tipo": "N",
                    "padding_char": "0",
                    "alineacion": "right",
                    "obligatorio": True,
                    "valores_validos": None,
                },
                {
                    "nombre": "nombre",
                    "descripcion": "Nombre",
                    "posicion_inicio": 6,
                    "longitud": 10,
                    "tipo": "A",
                    "padding_char": " ",
                    "alineacion": "left",
                    "obligatorio": True,
                    "valores_validos": None,
                },
            ],
        }

    def test_archivo_valido_sin_errores(self, esquema_simple, monkeypatch):
        from motor import validador
        monkeypatch.setattr(
            "motor.validador.cargar_esquema",
            lambda t, o: esquema_simple,
        )
        contenido = "10042GONZALEZ  "
        errores = validador.validar_archivo(contenido, "AT", "A")
        assert len(errores) == 0

    def test_longitud_incorrecta(self, esquema_simple, monkeypatch):
        from motor import validador
        monkeypatch.setattr(
            "motor.validador.cargar_esquema",
            lambda t, o: esquema_simple,
        )
        contenido = "10042GONZALEZ"  # 13 chars, esperados 15
        errores = validador.validar_archivo(contenido, "AT", "A")
        assert any(e["campo"] == "registro_completo" for e in errores)

    def test_valor_no_permitido(self, esquema_simple, monkeypatch):
        from motor import validador
        esquema_simple["campos"][0]["valores_validos"] = ["1"]
        monkeypatch.setattr(
            "motor.validador.cargar_esquema",
            lambda t, o: esquema_simple,
        )
        contenido = "90042GONZALEZ  "  # tipo_registro=9, solo acepta 1
        errores = validador.validar_archivo(contenido, "AT", "A")
        assert any(e["campo"] == "tipo_registro" for e in errores)

    def test_archivo_vacio(self, esquema_simple, monkeypatch):
        from motor import validador
        monkeypatch.setattr(
            "motor.validador.cargar_esquema",
            lambda t, o: esquema_simple,
        )
        errores = validador.validar_archivo("", "AT", "A")
        assert len(errores) > 0
        assert errores[0]["severidad"] == "FATAL"

    def test_resumen_validacion_ok(self):
        from motor.validador import generar_resumen_validacion
        resumen = generar_resumen_validacion([])
        assert resumen["es_valido"] is True
        assert resumen["total_errores"] == 0

    def test_resumen_validacion_con_errores(self):
        from motor.validador import generar_resumen_validacion
        errores = [
            {"fila": 1, "campo": "cuil", "posicion": "2-12",
             "valor_encontrado": "ABC", "error": "No numérico",
             "referencia_norma": "Res 3326", "severidad": "ERROR"},
            {"fila": 2, "campo": "cuil", "posicion": "2-12",
             "valor_encontrado": "XYZ", "error": "No numérico",
             "referencia_norma": "Res 3326", "severidad": "ERROR"},
        ]
        resumen = generar_resumen_validacion(errores)
        assert resumen["es_valido"] is False
        assert resumen["total_errores"] == 2
        assert resumen["errores_por_tipo"]["cuil"] == 2
