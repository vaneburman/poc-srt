# PoC Agente IA para Normativa SRT

Agente de IA con arquitectura neuro-simbólica para la generación y validación de archivos TXT posicionales según normativa de la Superintendencia de Riesgos del Trabajo (SRT).

## Quick Start

```bash
# 1. Clonar y entrar al proyecto
git clone <repo-url>
cd poc-agente-srt

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con tu GEMINI_API_KEY

# 5. (Primera vez) Generar index RAG
python rag/ingest.py --input-dir ./normativa --output-dir ./rag/faiss_index

# 6. Iniciar el servidor
uvicorn backend:app --reload

# 7. Abrir en el navegador
# http://localhost:8000
```

## Estructura del Proyecto

```
poc-agente-srt/
├── schemas/          # Esquemas JSON de formatos posicionales SRT
├── normativa/        # PDFs de resoluciones (no versionados)
├── rag/              # Pipeline RAG: ingesta + búsqueda semántica
├── motor/            # Motor determinístico: generación + validación TXT
├── agente/           # Orquestador IA + tools + prompts
├── mock_data/        # Datos de prueba (simulan endpoint Java)
├── tests/            # Tests unitarios y E2E
├── docs/             # Documentación técnica
├── frontend/         # UI (HTML/CSS/JS)
│   └── index.html    # Single-page app
├── backend.py        # FastAPI backend
├── app.py            # Streamlit UI (alternativa local)
└── config.py         # Configuración centralizada
```

## Documentación

- [Plan de Implementación](docs/PLAN_IMPLEMENTACION.md)
- [Guía de Migración a AWS](docs/GUIA_MIGRACION_AWS.md)

## API Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/api/chat` | Enviar mensaje al agente |
| `POST` | `/api/validar` | Validar archivo TXT subido |
| `GET` | `/api/download/{filename}` | Descargar archivo generado |
| `GET` | `/api/health` | Estado del sistema |
| `GET` | `/` | Frontend web |

## Stack

| Capa | Tecnología |
|------|-----------|
| LLM | Gemini 2.0 Flash (free tier) |
| Embeddings | all-MiniLM-L6-v2 (local) |
| Vector DB | FAISS (in-process) |
| Motor | Python puro |
| Backend | FastAPI + Uvicorn |
| Frontend | HTML / CSS / JS |
