"""
Búsqueda semántica sobre el index FAISS de normativa SRT.
"""
import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

import config

# Lazy loading del modelo y el index
_modelo = None
_index = None
_chunks = None


def _cargar_recursos():
    """Carga el modelo de embeddings y el index FAISS (lazy, una sola vez)."""
    global _modelo, _index, _chunks
    
    if _modelo is None:
        _modelo = SentenceTransformer(config.EMBEDDING_MODEL)
    
    if _index is None:
        index_path = config.FAISS_INDEX_PATH / "index.faiss"
        chunks_path = config.FAISS_INDEX_PATH / "chunks.json"
        
        if not index_path.exists():
            raise FileNotFoundError(
                f"Index FAISS no encontrado en {index_path}. "
                f"Ejecutá: python rag/ingest.py"
            )
        
        _index = faiss.read_index(str(index_path))
        
        with open(chunks_path, "r", encoding="utf-8") as f:
            _chunks = json.load(f)


def buscar_normativa(pregunta: str, top_k: int = 5) -> list[dict]:
    """
    Busca chunks relevantes en el index FAISS.
    
    Args:
        pregunta: Consulta en lenguaje natural
        top_k: Número de resultados a retornar
    
    Returns:
        Lista de dicts con: texto, fuente, pagina, score
    """
    _cargar_recursos()
    
    # Generar embedding de la pregunta
    query_embedding = _modelo.encode([pregunta], normalize_embeddings=True)
    query_embedding = np.array(query_embedding, dtype="float32")
    
    # Buscar en FAISS
    scores, indices = _index.search(query_embedding, top_k)
    
    resultados = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(_chunks):
            continue
        chunk = _chunks[idx]
        resultados.append({
            "texto": chunk["texto"],
            "fuente": chunk["fuente"],
            "pagina": chunk["pagina"],
            "score": float(score),
        })
    
    return resultados
