"""
Tests para el agente y sus tools (sin LLM real).

Todos los tests corren sin GEMINI_API_KEY:
- TestToolsAislamiento: llama ejecutar_tool directamente (motor + RAG, no LLM)
- TestAgenteInstanciacion: inyecta un MockLLM que no llama a ninguna API
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# Mock LLM reutilizable
# ============================================================

from agente.llm_client import LLMClient


class MockLLM(LLMClient):
    """LLM falso que retorna texto fijo, sin ninguna llamada a API."""

    def __init__(self, respuesta: str = "Respuesta mock del agente"):
        self.respuesta = respuesta

    def invoke_with_tools(self, messages, tools, system_prompt):
        return {"type": "text", "content": self.respuesta}


class MockLLMQueRaisea(LLMClient):
    """LLM falso que simula una falla de conectividad."""

    def invoke_with_tools(self, messages, tools, system_prompt):
        raise ConnectionError("LLM no disponible")


# ============================================================
# Tests de tools en aislamiento (sin LLM)
# ============================================================

class TestToolsAislamiento:
    """Tests de tools ejecutadas directamente con ejecutar_tool, sin LLM."""

    def test_tool_desconocida_retorna_error_controlado(self):
        """Una tool inexistente devuelve JSON con 'error', no lanza excepción."""
        from agente.tools import ejecutar_tool

        resultado = json.loads(ejecutar_tool("tool_inexistente", {}))
        assert "error" in resultado

    def test_consultar_normativa_retorna_estructura_correcta(self):
        """consultar_normativa devuelve dict con 'resultados' (lista) o 'error'."""
        from agente.tools import ejecutar_tool

        resultado = json.loads(
            ejecutar_tool("consultar_normativa", {"pregunta": "formato de fecha siniestro"})
        )
        assert "resultados" in resultado or "error" in resultado
        if "resultados" in resultado:
            assert isinstance(resultado["resultados"], list)

    def test_generar_txt_con_mock_data_produce_archivo(self):
        """generar_txt con mock data genera un archivo TXT sin errores."""
        from agente.tools import ejecutar_tool

        resultado = json.loads(
            ejecutar_tool(
                "generar_txt",
                {
                    "tipo": "AT",
                    "operacion": "A",
                    "fecha_desde": "2024-01-01",
                    "fecha_hasta": "2024-01-31",
                },
            )
        )

        assert "error" not in resultado, f"generar_txt falló: {resultado.get('error')}"
        assert "nombre_archivo" in resultado
        assert "total_registros" in resultado
        assert resultado["total_registros"] > 0

    def test_validar_txt_sobre_archivo_generado_retorna_valido(self, monkeypatch, tmp_path):
        """Un archivo generado por el motor con esquema simple pasa la validación via tool."""
        from motor.generador import generar_registro
        from agente.tools import ejecutar_tool

        # Esquema mínimo controlado: un solo campo obligatorio presente en mock data
        esquema_test = {
            "metadata": {
                "norma": "Test",
                "tipo": "AT",
                "operacion": "A",
                "longitud_registro": 11,
                "encoding": "latin-1",
                "line_separator": "\r\n",
            },
            "campos": [
                {
                    "nombre": "cuil_trabajador",
                    "descripcion": "CUIL",
                    "posicion_inicio": 1,
                    "longitud": 11,
                    "tipo": "N",
                    "padding_char": "0",
                    "alineacion": "right",
                    "obligatorio": True,
                    "fuente_dato": "endpoint:cuil_trabajador",
                    "valores_validos": None,
                }
            ],
        }

        # Generar un registro válido con el esquema simple
        datos = {"cuil_trabajador": "20345678901"}
        registro = generar_registro(datos, esquema_test)  # "20345678901" (11 chars)

        # Escribir el archivo al disco
        test_file = tmp_path / "test_at_simple.txt"
        test_file.write_bytes(registro.encode("latin-1"))

        # Parchear el esquema que usa el validador con el esquema simple
        monkeypatch.setattr("motor.validador.cargar_esquema", lambda t, o: esquema_test)

        # Validar via herramienta ejecutar_tool
        resultado = json.loads(
            ejecutar_tool(
                "validar_txt",
                {
                    "archivo_path": str(test_file),
                    "tipo": "AT",
                    "operacion": "A",
                },
            )
        )
        assert "es_valido" in resultado
        assert resultado["es_valido"] is True, f"Validación falló inesperadamente: {resultado}"


# ============================================================
# Tests de instanciación del agente con MockLLM
# ============================================================

class TestAgenteInstanciacion:
    """Tests del Agente con LLM mock (sin API key)."""

    def test_agente_instancia_con_mock_llm(self):
        """Agente se instancia sin errores cuando se le pasa un LLM mock."""
        from agente.orquestador import Agente

        agente = Agente(llm_client=MockLLM())
        assert agente is not None
        assert agente.historial == []

    def test_agente_procesa_mensaje_con_mock_llm(self):
        """agente.procesar() retorna la respuesta del LLM mock."""
        from agente.orquestador import Agente

        agente = Agente(llm_client=MockLLM("Respuesta de prueba"))
        respuesta = agente.procesar("Hola, ¿qué podés hacer?")

        assert respuesta == "Respuesta de prueba"
        assert len(agente.historial) == 2  # user + assistant

    def test_agente_historial_acumula_mensajes(self):
        """El historial crece correctamente con mensajes sucesivos."""
        from agente.orquestador import Agente

        agente = Agente(llm_client=MockLLM())
        agente.procesar("Primer mensaje")
        agente.procesar("Segundo mensaje")

        assert len(agente.historial) == 4  # 2 user + 2 assistant

    def test_agente_resetear_historial(self):
        """resetear_historial limpia el historial correctamente."""
        from agente.orquestador import Agente

        agente = Agente(llm_client=MockLLM())
        agente.procesar("Mensaje de prueba")
        agente.resetear_historial()

        assert agente.historial == []

    def test_agente_llm_no_disponible_propaga_excepcion(self):
        """Si el LLM falla, el orquestador propaga la excepción (no la silencia)."""
        from agente.orquestador import Agente

        agente = Agente(llm_client=MockLLMQueRaisea())

        with pytest.raises(ConnectionError, match="LLM no disponible"):
            agente.procesar("Mensaje que va a fallar")
