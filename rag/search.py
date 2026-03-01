"""
Búsqueda en normativa SRT.

Usa FAISS + sentence-transformers si están disponibles.
Si no (cloud free tier sin esas dependencias), cae automáticamente a TF-IDF con sklearn.
"""
import json
from pathlib import Path

import config

# Detectar backend disponible
try:
    import faiss
    from sentence_transformers import SentenceTransformer
    _BACKEND = "faiss"
except ImportError:
    _BACKEND = "tfidf"

import numpy as np  # siempre disponible vía scikit-learn


# Estado global (lazy loading)
_modelo = None
_index = None
_chunks = None
_tfidf_vec = None
_tfidf_matrix = None


def _cargar_recursos():
    """Carga el modelo/index según el backend disponible (lazy, una sola vez)."""
    global _modelo, _index, _chunks, _tfidf_vec, _tfidf_matrix

    # Chunks son siempre necesarios
    if _chunks is None:
        chunks_path = config.FAISS_INDEX_PATH / "chunks.json"
        if not chunks_path.exists():
            raise FileNotFoundError(
                f"chunks.json no encontrado en {chunks_path}. "
                "Ejecutá: python rag/ingest.py"
            )
        with open(chunks_path, "r", encoding="utf-8") as f:
            _chunks = json.load(f)

    if _BACKEND == "faiss":
        if _modelo is None:
            _modelo = SentenceTransformer(config.EMBEDDING_MODEL)
        if _index is None:
            index_path = config.FAISS_INDEX_PATH / "index.faiss"
            if not index_path.exists():
                raise FileNotFoundError(
                    f"Index FAISS no encontrado en {index_path}. "
                    "Ejecutá: python rag/ingest.py"
                )
            _index = faiss.read_index(str(index_path))
    else:
        # TF-IDF: construir vectorizer sobre los chunks la primera vez
        if _tfidf_vec is None:
            from sklearn.feature_extraction.text import TfidfVectorizer
            textos = [c["texto"] for c in _chunks]
            _tfidf_vec = TfidfVectorizer(
                strip_accents="unicode",
                ngram_range=(1, 2),
                max_features=20_000,
            ).fit(textos)
            _tfidf_matrix = _tfidf_vec.transform(textos)


def buscar_normativa(pregunta: str, top_k: int = 5) -> list[dict]:
    """
    Busca chunks relevantes en la normativa SRT.

    Backend FAISS: usa embeddings semánticos (más preciso, requiere torch).
    Backend TF-IDF: usa frecuencia de términos (liviano, funciona en free tier).

    Returns:
        Lista de dicts con: texto, fuente, pagina, score
    """
    _cargar_recursos()

    if _BACKEND == "faiss":
        query_vec = np.array(
            _modelo.encode([pregunta], normalize_embeddings=True), dtype="float32"
        )
        scores, indices = _index.search(query_vec, top_k)
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
    else:
        from sklearn.metrics.pairwise import cosine_similarity
        query_vec = _tfidf_vec.transform([pregunta])
        sims = cosine_similarity(query_vec, _tfidf_matrix)[0]
        top_idx = np.argsort(sims)[::-1][:top_k]
        resultados = []
        for idx in top_idx:
            if sims[idx] < 0.01:
                continue
            chunk = _chunks[int(idx)]
            resultados.append({
                "texto": chunk["texto"],
                "fuente": chunk["fuente"],
                "pagina": chunk["pagina"],
                "score": float(sims[idx]),
            })

    return resultados
