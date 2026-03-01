"""
Configuración centralizada del proyecto.
Lee variables de .env y provee defaults seguros.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# === Paths ===
PROJECT_ROOT = Path(__file__).parent
SCHEMAS_PATH = Path(os.getenv("SCHEMAS_PATH", PROJECT_ROOT / "schemas"))
MOCK_DATA_PATH = Path(os.getenv("MOCK_DATA_PATH", PROJECT_ROOT / "mock_data"))
FAISS_INDEX_PATH = Path(os.getenv("FAISS_INDEX_PATH", PROJECT_ROOT / "rag" / "faiss_index"))
OUTPUT_PATH = PROJECT_ROOT / "output"
OUTPUT_PATH.mkdir(exist_ok=True)

# === Backend ===
JAVA_ENDPOINT_URL = os.getenv("JAVA_ENDPOINT_URL", "http://localhost:8080/api/siniestros/srt")
USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "true").lower() == "true"

# === LLM ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))

# === RAG ===
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
RAG_TOP_K = 5
