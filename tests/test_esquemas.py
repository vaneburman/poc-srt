"""Tests de validación estructural para esquemas JSON y mock data SRT."""
import json
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"
MOCK_DATA_DIR = Path(__file__).parent.parent / "mock_data"

SCHEMA_FILES = [
    "at_3326_alta.json",
    "at_3326_baja.json",
    "ep_3327_alta.json",
    "ep_3327_baja.json",
]

CAMPOS_REQUERIDOS = {
    "nombre", "longitud", "tipo", "padding_char", "alineacion", "posicion_inicio"
}

# Mapa de mock data → esquema correspondiente
MOCK_SCHEMA_MAP = [
    ("siniestros_at_alta.json", "at_3326_alta.json"),
    ("siniestros_at_baja.json", "at_3326_baja.json"),
    ("siniestros_ep_alta.json", "ep_3327_alta.json"),
    ("siniestros_ep_baja.json", "ep_3327_baja.json"),
]


# ============================================================
# Helpers
# ============================================================

def _cargar_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _endpoint_keys(esquema: dict) -> set:
    """Extrae las claves endpoint:X referenciadas por el esquema."""
    keys = set()
    for campo in esquema["campos"]:
        fuente = campo.get("fuente_dato", "")
        if fuente.startswith("endpoint:"):
            keys.add(fuente.split(":", 1)[1])
    return keys


# ============================================================
# Tests de esquemas JSON
# ============================================================

class TestEsquemasJSON:
    @pytest.mark.parametrize("schema_file", SCHEMA_FILES)
    def test_esquema_parseable(self, schema_file):
        """El archivo existe y es un JSON válido con secciones metadata y campos."""
        ruta = SCHEMAS_DIR / schema_file
        assert ruta.exists(), f"Esquema no encontrado: {schema_file}"
        esquema = _cargar_json(ruta)
        assert "metadata" in esquema, f"{schema_file}: falta sección 'metadata'"
        assert "campos" in esquema, f"{schema_file}: falta sección 'campos'"
        assert isinstance(esquema["campos"], list), f"{schema_file}: 'campos' debe ser una lista"
        assert len(esquema["campos"]) > 0, f"{schema_file}: 'campos' no puede estar vacío"

    @pytest.mark.parametrize("schema_file", SCHEMA_FILES)
    def test_suma_longitudes_igual_longitud_registro(self, schema_file):
        """La suma de longitudes de todos los campos == longitud_registro en metadata."""
        esquema = _cargar_json(SCHEMAS_DIR / schema_file)
        longitud_total = esquema["metadata"]["longitud_registro"]
        suma = sum(c["longitud"] for c in esquema["campos"])
        assert suma == longitud_total, (
            f"{schema_file}: suma de longitudes de campos ({suma}) "
            f"!= longitud_registro ({longitud_total})"
        )

    @pytest.mark.parametrize("schema_file", SCHEMA_FILES)
    def test_campos_tienen_atributos_requeridos(self, schema_file):
        """Cada campo tiene todos los atributos requeridos por el motor."""
        esquema = _cargar_json(SCHEMAS_DIR / schema_file)
        for i, campo in enumerate(esquema["campos"]):
            faltantes = CAMPOS_REQUERIDOS - set(campo.keys())
            assert not faltantes, (
                f"{schema_file}, campo #{i} ({campo.get('nombre', '?')}): "
                f"faltan atributos requeridos: {faltantes}"
            )

    @pytest.mark.parametrize("schema_file", SCHEMA_FILES)
    def test_posiciones_consecutivas_sin_solapamiento(self, schema_file):
        """Los campos son contiguos: posicion_inicio de cada campo == fin del anterior + 1."""
        esquema = _cargar_json(SCHEMAS_DIR / schema_file)
        pos_esperada = 1
        for campo in esquema["campos"]:
            assert campo["posicion_inicio"] == pos_esperada, (
                f"{schema_file}, campo '{campo['nombre']}': "
                f"posicion_inicio esperada {pos_esperada}, "
                f"encontrada {campo['posicion_inicio']}"
            )
            pos_esperada += campo["longitud"]


# ============================================================
# Tests de consistencia mock data ↔ esquema
# ============================================================

class TestMockDataConsistencia:
    @pytest.mark.parametrize("mock_file,schema_file", MOCK_SCHEMA_MAP)
    def test_mock_data_parseable(self, mock_file, schema_file):
        """El archivo existe, es JSON válido y tiene al menos 1 registro en 'resultado'."""
        ruta = MOCK_DATA_DIR / mock_file
        assert ruta.exists(), f"Mock data no encontrado: {mock_file}"
        data = _cargar_json(ruta)
        assert "resultado" in data, f"{mock_file}: falta sección 'resultado'"
        assert len(data["resultado"]) >= 1, f"{mock_file}: 'resultado' está vacío"

    @pytest.mark.parametrize("mock_file,schema_file", MOCK_SCHEMA_MAP)
    def test_mock_data_tiene_campos_referenciados_por_esquema(self, mock_file, schema_file):
        """Cada registro del mock data tiene las claves que el esquema requiere (fuente_dato endpoint:X)."""
        esquema = _cargar_json(SCHEMAS_DIR / schema_file)
        endpoint_keys = _endpoint_keys(esquema)

        data = _cargar_json(MOCK_DATA_DIR / mock_file)
        for i, registro in enumerate(data["resultado"]):
            faltantes = endpoint_keys - set(registro.keys())
            assert not faltantes, (
                f"{mock_file}, registro #{i}: "
                f"faltan campos referenciados por {schema_file}: {faltantes}"
            )
