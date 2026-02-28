# Plan de Implementación Técnica: PoC Agente IA para Normativa SRT

## Versión: 2.0 — Estrategia "Validar Primero, Migrar Después"

---

## 1. Resumen Ejecutivo y Definición del Problema

### El Problema

La Superintendencia de Riesgos del Trabajo (SRT) exige la declaración de Accidentes de Trabajo (AT) y Enfermedades Profesionales (EP) mediante archivos de texto plano (.TXT) con formato posicional estricto (longitud fija, codificación específica, padding exacto) regulados por las Resoluciones 3326/2014, 3327/2014 y sus modificatorias.

Mantener actualizados los mapeos ante cambios normativos y validar archivos masivos es propenso a errores humanos. Además, los LLMs son inherentemente malos contando caracteres y formateando posiciones exactas.

### La Solución (PoC)

Desarrollar un **Agente de IA con arquitectura híbrida (Neuro-Simbólica)**:

1. **El Cerebro (LLM):** Entiende la intención del usuario, consulta la normativa mediante RAG y extrae parámetros estructurados.
2. **El Músculo (Python):** Motor determinístico guiado por esquemas JSON que garantiza precisión matemática en la generación y validación de los archivos TXT.

### Cambio de Estrategia vs. Plan Original

El plan original proponía desarrollar directamente sobre AWS (Bedrock, Lambda, Pinecone). Este plan revisado adopta una estrategia de **"Validar Primero, Migrar Después"**:

| Aspecto | Plan v1.0 (AWS directo) | Plan v2.0 (Local → AWS) |
|---------|------------------------|------------------------|
| Costo | ~$1.50 USD/mes (Bedrock no tiene free tier) | **$0.00 absoluto** |
| Dependencia de DevOps | Alta (IAM, VPC, habilitación de modelos) | **Ninguna para la PoC** |
| Tiempo hasta primera demo | ~3 semanas | **5-7 días** |
| Dependencias externas | Pinecone (SaaS tercero) | **Ninguna** |
| Riesgo organizacional | Si la PoC falla, se gastó presupuesto AWS | **Riesgo cero** |
| Esfuerzo de migración | N/A | Mecánico, 1:1 documentado |

**Principio rector:** Todo componente local tiene un mapping directo a su equivalente AWS. No se escribe código descartable.

---

## 2. Arquitectura de la Solución

### 2.1 Diagrama Conceptual

```
┌─────────────────────────────────────────────────────────┐
│                    USUARIO                               │
│              (Streamlit / Gradio UI)                     │
└────────────────────┬────────────────────────────────────┘
                     │ Prompt / Archivo TXT
                     ▼
┌─────────────────────────────────────────────────────────┐
│              AGENTE ORQUESTADOR                          │
│         (Python + Gemini 2.0 Flash API)                  │
│                                                          │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Clasifica │→│ Selecciona   │→│  Ejecuta Tool &   │   │
│  │  Intent   │  │    Tool      │  │  Formatea Resp.  │   │
│  └──────────┘  └──────────────┘  └──────────────────┘   │
└────────┬──────────────┬──────────────────┬──────────────┘
         │              │                  │
         ▼              ▼                  ▼
┌────────────┐  ┌──────────────┐  ┌──────────────────┐
│   Tool 1   │  │   Tool 2     │  │     Tool 3       │
│  CONSULTAR │  │  GENERAR     │  │    VALIDAR       │
│  NORMATIVA │  │  TXT         │  │    TXT           │
│            │  │              │  │                   │
│ FAISS +    │  │ Motor Det.   │  │  Motor Det.      │
│ Embeddings │  │ + Esquemas   │  │  + Esquemas      │
│ Locales    │  │ JSON         │  │  JSON             │
└────────────┘  └──────┬───────┘  └──────────────────┘
                       │
                       ▼
              ┌──────────────┐
              │ Endpoint Java│
              │  (Dev) o     │
              │  Mock JSON   │
              └──────────────┘
```

### 2.2 Stack Tecnológico

| Capa | Tecnología | Justificación | Equivalente AWS |
|------|-----------|---------------|-----------------|
| **LLM** | Gemini 2.0 Flash (API gratuita) | 15 RPM, 1M TPM gratis. Excelente function calling nativo. | Bedrock: Claude 3 Haiku |
| **Embeddings** | `all-MiniLM-L6-v2` (sentence-transformers) | Open source, corre local, 384 dims, rápido | Bedrock: Titan Embed Text v2 |
| **Base Vectorial** | FAISS (in-process) | Sin servidor, sin red, sin costo. Para ~500 chunks es instantáneo | S3 + FAISS en Lambda (carga en `/tmp`) |
| **Motor Determinístico** | Python puro | Lógica de negocio crítica, zero dependencies externas | AWS Lambda (copy-paste + handler) |
| **Esquemas** | Archivos JSON locales | Versionados en Git, fáciles de actualizar | S3 con versionado |
| **Backend Datos** | Endpoint Java existente (Dev) o mock JSONs | Reutiliza infraestructura existente | Mismo endpoint via API Gateway + VPC Link |
| **Frontend** | Streamlit | Rápido de prototipar, ideal para PoC interna | S3 static + API Gateway o AppRunner |
| **Hosting demo** | Streamlit Community Cloud o local | Gratis, shareable con stakeholders | N/A |

### 2.3 Desglose de Costos

| Componente | Servicio | Costo (USD/mes) |
|-----------|---------|-----------------|
| LLM (Tokens) | Gemini 2.0 Flash (Free Tier) | $0.00 |
| Embeddings | all-MiniLM-L6-v2 (local) | $0.00 |
| Base Vectorial | FAISS (librería local) | $0.00 |
| Computación | Python local / Streamlit Cloud | $0.00 |
| Backend Datos | Endpoint Java existente / Mocks | $0.00 |
| Almacenamiento | Filesystem local / Git repo | $0.00 |
| **TOTAL** | | **$0.00** |

---

## 3. Estructura del Proyecto

```
poc-agente-srt/
│
├── docs/
│   ├── PLAN_IMPLEMENTACION.md      # Este documento
│   └── GUIA_MIGRACION_AWS.md       # Mapping 1:1 local → AWS
│
├── schemas/                         # Esquemas JSON de formatos posicionales
│   ├── at_3326_alta.json            # AT Alta (Res. 3326)
│   ├── at_3326_baja.json            # AT Baja (Res. 3326)
│   ├── ep_3327_alta.json            # EP Alta (Res. 3327)
│   ├── ep_3327_baja.json            # EP Baja (Res. 3327)
│   └── README.md                    # Documentación de cómo agregar nuevos esquemas
│
├── normativa/                       # PDFs de las resoluciones (no se commitean al repo)
│   ├── .gitkeep
│   └── README.md                    # Instrucciones de dónde obtener los PDFs
│
├── rag/
│   ├── ingest.py                    # Script one-shot: PDFs → chunks → FAISS index
│   ├── search.py                    # Función de búsqueda semántica reutilizable
│   ├── faiss_index/                 # Index pre-computado (se commitea al repo)
│   │   ├── index.faiss
│   │   └── chunks.json              # Metadatos de cada chunk (texto, fuente, página)
│   └── README.md
│
├── motor/
│   ├── __init__.py
│   ├── generador.py                 # Genera TXT posicional desde JSON + esquema
│   ├── validador.py                 # Valida TXT contra esquema, devuelve errores
│   ├── esquema_loader.py            # Carga y cachea esquemas JSON
│   └── utils.py                     # Funciones de padding, alineación, formateo
│
├── agente/
│   ├── __init__.py
│   ├── orquestador.py               # Lógica de agente: intent → tool routing
│   ├── tools.py                     # Definición e implementación de tools
│   ├── prompts.py                   # System prompt y templates
│   └── llm_client.py               # Abstracción del LLM (Gemini hoy, Bedrock mañana)
│
├── mock_data/                       # JSONs de ejemplo (simulan endpoint Java)
│   ├── siniestros_at_alta.json
│   ├── siniestros_at_baja.json
│   ├── siniestros_ep_alta.json
│   └── README.md
│
├── tests/
│   ├── test_motor_generador.py      # Tests del generador TXT
│   ├── test_motor_validador.py      # Tests del validador TXT
│   ├── test_esquemas.py             # Validación de esquemas JSON
│   ├── test_rag.py                  # Tests de búsqueda RAG
│   ├── test_agente.py               # Tests end-to-end del agente
│   └── fixtures/                    # Archivos TXT de ejemplo (válidos e inválidos)
│       ├── at_alta_valido.txt
│       ├── at_alta_errores.txt
│       └── README.md
│
├── app.py                           # Streamlit UI - punto de entrada
├── config.py                        # Configuración centralizada (API keys, paths, flags)
├── requirements.txt                 # Dependencias Python
├── .env.example                     # Template de variables de entorno
├── .gitignore
└── README.md                        # Quick start y overview del proyecto
```

---

## 4. Fases de Implementación y Tareas

### Fase 0: Setup del Entorno (Día 0 — 2 horas)

**Objetivo:** Tener el entorno de desarrollo listo para empezar a producir.

**Tareas:**

1. **Crear repositorio Git** con la estructura de directorios.
2. **Configurar entorno Python:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Obtener API key de Gemini** (gratuita): https://aistudio.google.com/apikey
4. **Configurar `.env`:**
   ```env
   GEMINI_API_KEY=tu_api_key_aqui
   JAVA_ENDPOINT_URL=http://localhost:8080/api/siniestros/srt
   USE_MOCK_DATA=true
   FAISS_INDEX_PATH=./rag/faiss_index
   SCHEMAS_PATH=./schemas
   ```
5. **Recopilar PDFs** de las Resoluciones 3326/2014, 3327/2014, 475/17, 81/19 y colocarlos en `normativa/`.

**Entregable:** Repo con estructura, entorno virtual funcional, API key configurada.

**Responsable:** Ingeniero IA / Tech Lead.

---

### Fase 1: Esquemas JSON y Mock Data (Día 1)

**Objetivo:** Tener la fuente de verdad de formatos posicionales en formato machine-readable y datos de prueba.

#### 1.1 Definición de Esquemas JSON

Traducir el Excel de mapeo actual a esquemas JSON estructurados. Cada esquema es un array de objetos que describe campo por campo el formato posicional.

**Estructura de un esquema:**

```json
{
  "metadata": {
    "norma": "Resolución 3326/2014",
    "tipo": "AT",
    "operacion": "A",
    "version": "2024.1",
    "longitud_registro": 1200,
    "encoding": "latin-1",
    "line_separator": "\r\n"
  },
  "campos": [
    {
      "nombre": "tipo_registro",
      "descripcion": "Tipo de registro (siempre '1' para detalle)",
      "posicion_inicio": 1,
      "longitud": 1,
      "tipo": "N",
      "padding_char": "0",
      "alineacion": "right",
      "obligatorio": true,
      "valores_validos": ["1"],
      "fuente_dato": "constante:1"
    },
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
    },
    {
      "nombre": "apellido_trabajador",
      "descripcion": "Apellido del trabajador",
      "posicion_inicio": 13,
      "longitud": 30,
      "tipo": "A",
      "padding_char": " ",
      "alineacion": "left",
      "obligatorio": true,
      "valores_validos": null,
      "fuente_dato": "endpoint:apellido"
    }
  ]
}
```

**Campos del esquema:**

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| `nombre` | string | Identificador interno del campo |
| `descripcion` | string | Descripción humana para el RAG y mensajes de error |
| `posicion_inicio` | int | Posición 1-indexed en la línea |
| `longitud` | int | Longitud exacta en caracteres |
| `tipo` | enum | `N` (numérico), `A` (alfanumérico), `F` (fecha YYYYMMDD) |
| `padding_char` | string | Carácter de relleno (`"0"` para numéricos, `" "` para alfanuméricos) |
| `alineacion` | enum | `left` o `right` |
| `obligatorio` | bool | Si el campo es requerido |
| `valores_validos` | array/null | Lista de valores permitidos (ej: códigos de provincia) |
| `fuente_dato` | string | De dónde viene el dato: `constante:X`, `endpoint:campo`, `calculado:formula` |

#### 1.2 Creación de Mock Data

Generar JSONs que simulen la respuesta del endpoint Java `GET /api/siniestros/srt`:

```json
{
  "resultado": [
    {
      "cuil_trabajador": "20345678901",
      "apellido": "GONZALEZ",
      "nombres": "JUAN CARLOS",
      "fecha_nacimiento": "19850315",
      "sexo": "M",
      "codigo_provincia": "01",
      "fecha_siniestro": "20240115",
      "hora_siniestro": "0930",
      "codigo_diagnostico_cie10": "S62.0",
      "dias_baja": "15",
      "tipo_accidente": "01"
    }
  ],
  "total": 1,
  "filtros_aplicados": {
    "tipo": "AT",
    "operacion": "A",
    "fecha_desde": "2024-01-01",
    "fecha_hasta": "2024-01-31"
  }
}
```

**Entregable:** Archivos JSON en `schemas/` y `mock_data/` completos y validados.

**Responsable:** Ingeniero de Datos / Backend, con input del equipo que conoce el Excel de mapeo.

**Criterio de aceptación:** Los esquemas cubren AT Alta, AT Baja, EP Alta y EP Baja. Cada esquema tiene al menos los 20 campos más críticos mapeados. Los mock data son consistentes con los esquemas.

---

### Fase 2: Motor Determinístico (Días 2-3)

**Objetivo:** El core del sistema — generación y validación de archivos TXT posicionales con precisión matemática.

#### 2.1 Motor de Generación (`motor/generador.py`)

**Lógica:**

```
Input: datos JSON (del endpoint o mock) + esquema JSON
  ↓
Para cada registro en datos:
  ↓
  Para cada campo en esquema.campos:
    1. Extraer valor del JSON según fuente_dato
    2. Aplicar padding según tipo, alineación y longitud
    3. Truncar si excede longitud
    4. Concatenar al registro
  ↓
  Validar que len(registro) == esquema.longitud_registro
  ↓
  Unir registros con line_separator
  ↓
Output: String del archivo TXT completo (encoding latin-1)
```

**Funciones clave:**

```python
def aplicar_formato(valor: str, campo: dict) -> str:
    """Aplica padding, alineación y truncamiento a un valor según su esquema."""

def generar_registro(datos: dict, esquema: dict) -> str:
    """Genera una línea TXT posicional a partir de un dict de datos y un esquema."""

def generar_archivo(lista_datos: list[dict], esquema: dict) -> bytes:
    """Genera el archivo TXT completo con encoding y line separators correctos."""
```

**Reglas de padding:**

| Tipo | Padding | Alineación | Ejemplo (longitud=11) |
|------|---------|------------|----------------------|
| `N` (numérico) | `0` | right | `"12345"` → `"00000012345"` |
| `A` (alfanumérico) | `" "` (espacio) | left | `"PEREZ"` → `"PEREZ      "` |
| `F` (fecha) | `0` | right | `"20240115"` → `"20240115"` |

#### 2.2 Motor de Validación (`motor/validador.py`)

**Lógica:**

```
Input: contenido TXT (bytes o string) + esquema JSON
  ↓
Decodificar con encoding del esquema
Separar en líneas por line_separator
  ↓
Para cada línea:
  Validar longitud total == esquema.longitud_registro
  ↓
  Para cada campo en esquema.campos:
    1. Extraer substring por posicion_inicio y longitud
    2. Validar tipo (¿es numérico si tipo=N?)
    3. Validar valores_validos (si aplica)
    4. Validar obligatoriedad (¿está vacío?)
  ↓
  Acumular errores con contexto: {fila, campo, valor_encontrado, error, referencia_norma}
  ↓
Output: Lista de errores estructurados (vacía si el archivo es válido)
```

**Estructura de un error:**

```json
{
  "fila": 3,
  "campo": "codigo_provincia",
  "posicion": "45-47",
  "valor_encontrado": "99",
  "error": "Valor no permitido. Códigos válidos: 01-24",
  "referencia_norma": "Res. 3326/2014, Anexo I, Campo 12",
  "severidad": "ERROR"
}
```

#### 2.3 Tests Unitarios

**Casos de prueba mínimos:**

| Test | Input | Expected |
|------|-------|----------|
| Padding numérico | `"123"`, longitud=11, tipo=N | `"00000000123"` |
| Padding alfanumérico | `"PEREZ"`, longitud=30, tipo=A | `"PEREZ" + 25 espacios` |
| Truncamiento | `"NOMBRE MUY LARGO PARA EL CAMPO"`, longitud=20 | `"NOMBRE MUY LARGO PAR"` |
| Registro completo | Mock data + esquema AT Alta | String de longitud exacta |
| Validación OK | Archivo generado por el motor | Lista de errores vacía |
| Validación con errores | Archivo con provincia "99" | Error en código_provincia |
| Longitud incorrecta | Línea con 1 carácter de más | Error de longitud de registro |
| Campo obligatorio vacío | Registro sin CUIL | Error de campo obligatorio |

**Entregable:** `motor/` completo con tests unitarios pasando al 100%.

**Responsable:** Backend / Python.

**Criterio de aceptación:** Generar un archivo TXT y validarlo con el mismo motor produce 0 errores. Archivos con errores intencionales son detectados correctamente.

---

### Fase 3: Pipeline RAG (Día 3-4)

**Objetivo:** Dar al agente acceso semántico a la normativa para responder preguntas sobre campos, códigos y formatos.

#### 3.1 Ingesta de Documentos (`rag/ingest.py`)

**Pipeline:**

```
PDFs en normativa/
  ↓ PyPDFLoader o pdfplumber
Texto crudo por página
  ↓ Chunking (1000 tokens, overlap 200)
Chunks con metadatos (fuente, página, sección)
  ↓ all-MiniLM-L6-v2
Embeddings (384 dims)
  ↓ FAISS IndexFlatL2
faiss_index/index.faiss + faiss_index/chunks.json
```

**Decisiones técnicas:**

- **Modelo de embeddings:** `all-MiniLM-L6-v2` de sentence-transformers. Es gratuito, corre local, genera vectores de 384 dimensiones, y tiene excelente performance para español técnico/legal.
- **FAISS vs Pinecone:** Para el volumen de la normativa SRT (~4-5 PDFs, estimado ~300-500 chunks), FAISS en memoria es instantáneo (<1ms por query). No justifica un servicio managed externo.
- **Metadatos del chunk:** Se guardan en un JSON separado porque FAISS no soporta metadatos nativos. Cada chunk tiene: `texto`, `fuente` (nombre del PDF), `pagina`, `seccion` (si es parseable).

**Ejecución:**

```bash
python rag/ingest.py --input-dir ./normativa --output-dir ./rag/faiss_index
```

Se ejecuta **una sola vez** (o cuando cambien las resoluciones). El index generado se commitea al repo para que todos los desarrolladores lo tengan sin correr el pipeline.

#### 3.2 Búsqueda Semántica (`rag/search.py`)

```python
def buscar_normativa(pregunta: str, top_k: int = 5) -> list[dict]:
    """
    Busca chunks relevantes en el index FAISS.
    
    Returns:
        Lista de dicts con: texto, fuente, pagina, score
    """
```

**Entregable:** Index FAISS generado, función de búsqueda testeada con preguntas de ejemplo.

**Responsable:** Ingeniero IA.

**Criterio de aceptación:** La búsqueda "¿Cuál es la longitud del campo CUIL?" devuelve chunks relevantes de la Res. 3326 en el top 3.

---

### Fase 4: Agente Orquestador con Function Calling (Días 4-5)

**Objetivo:** Conectar el LLM con las herramientas de forma inteligente usando lenguaje natural.

#### 4.1 Abstracción del LLM (`agente/llm_client.py`)

**Patrón Strategy** para facilitar la migración futura:

```python
class LLMClient(ABC):
    @abstractmethod
    def invoke_with_tools(self, messages, tools, system_prompt) -> dict:
        """Envía mensajes al LLM con tools disponibles y retorna la respuesta."""

class GeminiClient(LLMClient):
    """Implementación con Gemini 2.0 Flash (PoC)."""

class BedrockClient(LLMClient):
    """Implementación con Bedrock Claude Haiku (producción AWS)."""
    # Se implementa al migrar, misma interfaz
```

Esto significa que al migrar a AWS, solo se crea la clase `BedrockClient` y se cambia una línea en `config.py`. Cero refactor del agente.

#### 4.2 System Prompt (`agente/prompts.py`)

```python
SYSTEM_PROMPT = """
Eres un asistente experto en normativa de la Superintendencia de Riesgos del Trabajo (SRT) 
de Argentina, especializado en las Resoluciones 3326/2014, 3327/2014 y sus modificatorias.

## Tu Rol
Ayudas a los usuarios a:
1. Consultar dudas sobre la normativa SRT (campos, códigos, formatos posicionales).
2. Generar archivos TXT posicionales para declarar AT (Accidentes de Trabajo) y EP 
   (Enfermedades Profesionales).
3. Validar archivos TXT existentes y explicar los errores encontrados.

## Reglas Estrictas
- NUNCA generes ni intentes formatear el contenido posicional del TXT directamente.
- SIEMPRE delega la generación y validación de archivos TXT a las herramientas disponibles.
- Cuando consultes la normativa, cita la fuente exacta (resolución, artículo, campo).
- Si no encontrás información en la normativa, decilo explícitamente. NO inventes.
- Usá temperatura 0 en tus razonamientos sobre códigos y formatos.
- Respondé siempre en español argentino.

## Herramientas Disponibles
Tenés acceso a tres herramientas. Usá la que corresponda según la intención del usuario:
- `consultar_normativa`: Para preguntas sobre la norma, campos, códigos, formatos.
- `generar_txt`: Para crear archivos TXT posicionales. Necesitás: tipo (AT/EP), 
  operación (A=alta, B=baja), y rango de fechas.
- `validar_txt`: Para validar un archivo TXT existente contra el formato oficial.

## Formato de Respuesta
- Para consultas normativas: Respuesta en texto natural con citas a la norma.
- Para generación: Confirmá qué se generó, cuántos registros, y ofrecé el link de descarga.
- Para validación: Listá los errores de forma clara, con el campo afectado, 
  el valor encontrado, y qué dice la norma.
"""
```

#### 4.3 Definición de Tools (`agente/tools.py`)

```python
TOOLS_DEFINITION = [
    {
        "name": "consultar_normativa",
        "description": "Busca información en la normativa SRT (Resoluciones 3326/2014, "
                       "3327/2014 y modificatorias) para responder preguntas sobre campos, "
                       "códigos, formatos posicionales, plazos y requisitos.",
        "parameters": {
            "type": "object",
            "properties": {
                "pregunta": {
                    "type": "string",
                    "description": "La pregunta a buscar en la normativa. Debe ser "
                                   "específica. Ej: 'longitud del campo CUIL en AT alta'"
                }
            },
            "required": ["pregunta"]
        }
    },
    {
        "name": "generar_txt",
        "description": "Genera un archivo TXT con formato posicional de longitud fija "
                       "para declarar ante la SRT. Los datos se obtienen del sistema interno.",
        "parameters": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": ["AT", "EP"],
                    "description": "AT = Accidente de Trabajo, EP = Enfermedad Profesional"
                },
                "operacion": {
                    "type": "string",
                    "enum": ["A", "B"],
                    "description": "A = Alta (nuevo), B = Baja (cierre)"
                },
                "fecha_desde": {
                    "type": "string",
                    "description": "Fecha inicio del período, formato YYYY-MM-DD"
                },
                "fecha_hasta": {
                    "type": "string",
                    "description": "Fecha fin del período, formato YYYY-MM-DD"
                }
            },
            "required": ["tipo", "operacion", "fecha_desde", "fecha_hasta"]
        }
    },
    {
        "name": "validar_txt",
        "description": "Valida un archivo TXT posicional contra el formato oficial de "
                       "la SRT y reporta errores encontrados con referencia a la norma.",
        "parameters": {
            "type": "object",
            "properties": {
                "archivo_path": {
                    "type": "string",
                    "description": "Ruta al archivo TXT a validar"
                },
                "tipo": {
                    "type": "string",
                    "enum": ["AT", "EP"],
                    "description": "Tipo de declaración del archivo"
                },
                "operacion": {
                    "type": "string",
                    "enum": ["A", "B"],
                    "description": "Operación del archivo"
                }
            },
            "required": ["archivo_path", "tipo", "operacion"]
        }
    }
]
```

#### 4.4 Lógica de Orquestación (`agente/orquestador.py`)

El orquestador sigue el patrón **ReAct (Reason + Act)**:

```
1. Recibir mensaje del usuario
2. Enviar al LLM con system prompt + tools + historial
3. Si el LLM pide ejecutar un tool:
   a. Ejecutar la función Python correspondiente
   b. Devolver el resultado al LLM
   c. Volver al paso 2 (el LLM puede pedir otro tool o responder)
4. Si el LLM responde texto: devolver al usuario
```

**Diagrama del loop:**

```
Usuario: "Generame el AT de altas de enero 2024"
  ↓
LLM: tool_call(generar_txt, {tipo: "AT", operacion: "A", 
      fecha_desde: "2024-01-01", fecha_hasta: "2024-01-31"})
  ↓
Orquestador: ejecuta generar_txt() → retorna {archivo: "at_alta_202401.txt", registros: 47}
  ↓
LLM: "Listo, generé el archivo AT de altas de enero 2024 con 47 registros. 
      ¿Querés que lo valide antes de descargarlo?"
```

**Entregable:** Agente funcionando end-to-end en terminal (sin UI aún).

**Responsable:** Ingeniero IA.

**Criterio de aceptación:**
- Pregunta "¿Qué longitud tiene el campo CUIL?" → Responde citando la norma.
- "Generame el AT de altas de enero" → Genera archivo TXT válido.
- "Validá este archivo" → Detecta errores y los explica.
- Si le piden algo que no puede hacer, lo dice sin inventar.

---

### Fase 5: Interfaz de Usuario e Integración (Día 5-6)

**Objetivo:** Interfaz visual de chat para presentar a stakeholders.

#### 5.1 Desarrollo Streamlit (`app.py`)

**Componentes:**

1. **Chat interface** con `st.chat_message` y `st.chat_input`.
2. **File uploader** con `st.file_uploader` para archivos `.txt`, `.at`, `.ep`.
3. **Sidebar** con:
   - Selector de tipo (AT/EP) y operación (Alta/Baja) para generación rápida.
   - Rango de fechas con `st.date_input`.
   - Botón "Generar archivo".
4. **Área de descarga** con `st.download_button` para los TXT generados.
5. **Estado de sesión** con `st.session_state` para historial del chat.

**Flujo de uso esperado:**

```
1. Usuario abre la app
2. Puede escribir en el chat: "Generame el AT de altas de febrero"
   → El agente procesa, genera el TXT, y ofrece descarga
3. O puede subir un archivo TXT
   → El agente lo valida y muestra los errores con explicación
4. O puede preguntar: "¿Qué códigos de provincia acepta el campo 12?"
   → El agente consulta la normativa y responde
```

#### 5.2 Opciones de Despliegue para Demo

| Opción | Pros | Contras | Ideal para |
|--------|------|---------|-----------|
| **Local** (`streamlit run app.py`) | Inmediato, sin setup | Stakeholders necesitan acceso a tu máquina | Demo en vivo presencial |
| **Streamlit Community Cloud** | Gratis, URL shareable, deploy desde GitHub | Público (o requiere login) | Stakeholders prueban solos |
| **HuggingFace Spaces** | Gratis, más control | Setup inicial un poco más largo | Demo pública o showcase |

**Entregable:** App funcional desplegada y accesible para stakeholders.

**Responsable:** Fullstack / Python.

---

### Fase 6: Testing End-to-End y Documentación (Día 6-7)

**Objetivo:** Validar el sistema completo y documentar la guía de migración.

#### 6.1 Plan de Testing

**Escenarios de prueba:**

| # | Escenario | Input | Output Esperado |
|---|-----------|-------|-----------------|
| 1 | Generar AT Alta | "Generame AT altas enero 2024" | Archivo TXT válido, longitud correcta |
| 2 | Generar EP Baja | "Necesito las EP baja de marzo" | Archivo TXT válido |
| 3 | Validar archivo correcto | Upload de TXT generado por el motor | "Sin errores" |
| 4 | Validar con error de provincia | TXT con código provincia "99" | Error detectado, cita la norma |
| 5 | Validar con longitud incorrecta | TXT con línea de longitud errónea | Error de longitud detectado |
| 6 | Consulta normativa simple | "¿Cuántos campos tiene el AT?" | Respuesta con cita a Res. 3326 |
| 7 | Consulta normativa compleja | "¿Cuál es la diferencia entre AT y EP para el campo de diagnóstico?" | Respuesta comparativa con citas |
| 8 | Pregunta fuera de alcance | "¿Cuánto cuesta una ART?" | "No tengo esa información..." |
| 9 | Generación con fechas inválidas | "AT de altas del 30 de febrero" | Manejo graceful del error |
| 10 | Archivo vacío | Upload de TXT vacío | Error informativo |

#### 6.2 Guía de Migración a AWS

Documentar en `docs/GUIA_MIGRACION_AWS.md` el mapping 1:1:

| Componente Local | Servicio AWS | Pasos de Migración |
|-----------------|-------------|-------------------|
| `motor/generador.py` | Lambda `fn_motor_srt` | Agregar handler Lambda, empaquetar como .zip |
| `motor/validador.py` | Misma Lambda (modo validación) | Ídem |
| `agente/orquestador.py` | Lambda `fn_agente` | Implementar `BedrockClient`, misma lógica |
| `agente/llm_client.py` → `GeminiClient` | `BedrockClient` con boto3 | Solo nueva clase, misma interfaz |
| `rag/faiss_index/` | S3 bucket + Lambda carga en `/tmp` | Upload a S3, Lambda descarga al cold start |
| `schemas/*.json` | S3 bucket con versionado | Upload directo |
| `mock_data/` → endpoint real | API Gateway + VPC Link al endpoint Java | Cambiar `JAVA_ENDPOINT_URL` en config |
| Streamlit local | S3 static + API Gateway + Lambda / AppRunner | Reescribir frontend o usar AppRunner |
| `.env` con `GEMINI_API_KEY` | Secrets Manager o Parameter Store | Cambiar `config.py` para leer de SSM |

**Entregable:** Suite de tests E2E pasando, guía de migración completa.

**Responsable:** QA + Tech Lead.

---

## 5. Cronograma Consolidado

| Día | Fase | Tareas Principales | Entregable | Responsable |
|-----|------|-------------------|-----------|-------------|
| **0** | Setup | Repo, venv, API key, PDFs | Entorno listo | Tech Lead |
| **1** | Fase 1 | Esquemas JSON + Mock Data | `schemas/` y `mock_data/` completos | Ing. Datos / Backend |
| **2** | Fase 2a | Motor de generación + utils | `generador.py` con tests | Backend Python |
| **3** | Fase 2b + 3 | Motor de validación + Pipeline RAG | `validador.py` + FAISS index | Backend + Ing. IA |
| **4** | Fase 4a | LLM client + System Prompt + Tools definition | Agente en terminal | Ing. IA |
| **5** | Fase 4b + 5 | Orquestador completo + UI Streamlit | App funcional | Ing. IA + Fullstack |
| **6-7** | Fase 6 | Testing E2E + Ajustes + Doc migración | PoC validada, lista para demo | QA + Tech Lead |

**Total: 7 días calendario (5 días efectivos de desarrollo)**

---

## 6. Riesgos y Mitigaciones

### Riesgo 1: El LLM genera contenido posicional directamente

**Probabilidad:** Media.
**Impacto:** Alto (archivos inválidos para la SRT).
**Mitigación:** El LLM **nunca** ve ni genera el string TXT. El system prompt lo prohíbe explícitamente. El LLM solo pasa parámetros JSON al motor determinístico que aplica slicing matemático de strings. Incluso si el LLM "intenta" generar un TXT en su respuesta de texto, el archivo real siempre viene del motor.

### Riesgo 2: El modelo alucina códigos CIE-10 o de provincia

**Probabilidad:** Media.
**Impacto:** Medio (respuestas incorrectas a consultas normativas).
**Mitigación:** El RAG con FAISS contiene las tablas exactas de la norma. El system prompt incluye la directiva de citar fuente y no inventar. Las tablas de códigos válidos están en los esquemas JSON (campo `valores_validos`), no dependen del LLM.

### Riesgo 3: El endpoint Java en Dev no es alcanzable desde fuera de la red

**Probabilidad:** Alta.
**Impacto:** Bajo (para la PoC).
**Mitigación:** El flag `USE_MOCK_DATA=true` en config permite funcionar completamente con datos de prueba. La PoC se valida con mocks. La integración real con el endpoint se prueba al migrar a AWS (donde Lambda estará en la misma red).

### Riesgo 4: Free tier de Gemini insuficiente para la demo

**Probabilidad:** Baja.
**Impacto:** Medio.
**Mitigación:** El free tier de Gemini 2.0 Flash es de 15 requests por minuto y 1 millón de tokens por minuto. Para una demo con stakeholders (estimado ~50-100 interacciones), sobra. Si se necesita más volumen para testing intensivo, se puede usar un modelo local como Llama 3.1 8B con Ollama como fallback.

### Riesgo 5: Calidad de embeddings para español técnico/legal

**Probabilidad:** Media.
**Impacto:** Bajo (afecta calidad del RAG, no la generación).
**Mitigación:** `all-MiniLM-L6-v2` tiene buen performance multilingüe. Si la calidad de retrieval no es suficiente, se puede cambiar a `paraphrase-multilingual-MiniLM-L12-v2` (también gratuito, 384 dims, optimizado para español). El cambio es una línea en `ingest.py`.

### Riesgo 6: Stakeholders piden cambios al formato durante la demo

**Probabilidad:** Alta.
**Impacto:** Bajo.
**Mitigación:** Los esquemas JSON son el único punto de cambio. Agregar/modificar un campo es editar un JSON, no código. Esto es un argumento de venta ("miren, cambió la resolución, solo actualizo el JSON").

---

## 7. Criterios de Éxito de la PoC

La PoC se considera exitosa si demuestra:

1. **Generación correcta:** Archivos TXT posicionales generados son válidos contra el formato de la SRT (verificado por el motor de validación).
2. **Detección de errores:** El validador detecta al menos 5 tipos diferentes de error en archivos corruptos intencionalmente.
3. **Consulta normativa:** El agente responde correctamente al menos 8/10 preguntas sobre la normativa citando la fuente.
4. **Interacción natural:** Un usuario no técnico puede interactuar con el chat y obtener resultados sin necesitar documentación.
5. **Costo:** $0.00 durante todo el desarrollo y demostración.
6. **Migración viable:** La guía de migración documenta cada componente con su equivalente AWS y pasos concretos.

---

## 8. Próximos Pasos Post-PoC (Roadmap AWS)

Si la PoC es aprobada:

| Prioridad | Tarea | Estimación |
|-----------|-------|-----------|
| P0 | Migrar motor a Lambda + S3 para esquemas | 2 días |
| P0 | Implementar `BedrockClient` para Claude Haiku | 1 día |
| P0 | Conectar endpoint Java real via API Gateway + VPC Link | 2 días |
| P1 | Subir FAISS index a S3 + Lambda con carga en `/tmp` | 1 día |
| P1 | Frontend: S3 static site + API Gateway | 3 días |
| P2 | Step Functions para orquestación visual | 2 días |
| P2 | CloudWatch dashboards y alertas | 1 día |
| P3 | Autenticación con Keycloak existente | 2 días |
| P3 | Pipeline CI/CD con Jenkins existente | 2 días |

**Estimación total de migración: 2-3 semanas con un desarrollador.**
