"""
Pipeline de ingesta RAG: PDFs + TXTs → Chunks → Embeddings → FAISS Index.

Se ejecuta UNA VEZ (o cuando cambien las resoluciones).
El index generado se commitea al repo.

Uso:
    python rag/ingest.py --input-dir ./normativa --output-dir ./rag/faiss_index
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import faiss
import numpy as np
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config


def extraer_texto_pdf(pdf_path: Path) -> list[dict]:
    """Extrae texto de un PDF usando pdftotext (poppler-utils).

    Las tablas de campos en los PDFs de la SRT son imágenes; pdftotext
    extrae el texto de las páginas que sí tienen capa de texto (artículos,
    procedimientos, aclaraciones) e ignora las páginas imagen.
    """
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True, text=True, timeout=60,
        )
        texto_completo = result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print(f"  WARN: pdftotext no disponible para {pdf_path.name}, omitiendo")
        return []

    if not texto_completo.strip():
        return []

    # Dividir por páginas (pdftotext usa form-feed \f como separador)
    paginas_raw = texto_completo.split("\f")
    paginas = []
    for i, texto in enumerate(paginas_raw):
        texto = texto.strip()
        # Saltar páginas con menos de 50 caracteres (probablemente imagen)
        if texto and len(texto) > 50:
            paginas.append({
                "texto": texto,
                "fuente": pdf_path.name,
                "pagina": i + 1,
            })
    return paginas


def extraer_texto_txt(txt_path: Path) -> list[dict]:
    """Lee un archivo .txt como un único bloque de texto."""
    try:
        texto = txt_path.read_text(encoding="utf-8").strip()
    except Exception:
        texto = txt_path.read_text(encoding="latin-1").strip()
    if not texto:
        return []
    return [{"texto": texto, "fuente": txt_path.name, "pagina": 1}]


def crear_chunks(paginas: list[dict]) -> list[dict]:
    """Divide las páginas en chunks con overlap."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    
    chunks = []
    for pagina in paginas:
        textos = splitter.split_text(pagina["texto"])
        for texto in textos:
            chunks.append({
                "texto": texto,
                "fuente": pagina["fuente"],
                "pagina": pagina["pagina"],
            })
    return chunks


def _cargar_modelo_neural(nombre_modelo: str):
    """Intenta cargar un modelo sentence-transformers. Retorna None si falla."""
    try:
        from sentence_transformers import SentenceTransformer
        modelo = SentenceTransformer(nombre_modelo)
        # Test rápido para confirmar que funciona
        modelo.encode(["test"], show_progress_bar=False)
        return modelo
    except Exception as e:
        print(f"  WARN: no se pudo cargar modelo neural ({e})")
        return None


def generar_embeddings(chunks: list[dict], modelo_nombre: str) -> np.ndarray:
    """Genera embeddings para todos los chunks.

    Intenta usar sentence-transformers (modelo neural). Si el modelo no está
    disponible localmente (ambiente sin internet), usa TF-IDF + SVD como
    fallback determinístico suficiente para el PoC.
    """
    textos = [chunk["texto"] for chunk in chunks]

    modelo = _cargar_modelo_neural(modelo_nombre)
    if modelo is not None:
        print(f"  Usando modelo neural: {modelo_nombre}")
        embeddings = modelo.encode(textos, show_progress_bar=True, normalize_embeddings=True)
        return np.array(embeddings, dtype="float32")

    # ── Fallback: TF-IDF + SVD (LSA) ──────────────────────────────────────
    print("  Usando fallback TF-IDF + SVD (PoC sin acceso a HuggingFace)")
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import TruncatedSVD
    from sklearn.preprocessing import normalize

    n_components = min(384, len(textos) - 1)  # dimensión del embedding
    vectorizer = TfidfVectorizer(max_features=20000, sublinear_tf=True, min_df=1)
    svd = TruncatedSVD(n_components=n_components, random_state=42)

    tfidf_matrix = vectorizer.fit_transform(textos)
    dense = svd.fit_transform(tfidf_matrix)
    embeddings = normalize(dense, norm="l2").astype("float32")
    return embeddings


def crear_index_faiss(embeddings: np.ndarray) -> faiss.IndexFlatIP:
    """Crea un index FAISS con Inner Product (para embeddings normalizados = cosine sim)."""
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)
    return index


def guardar_index(
    index: faiss.IndexFlatIP, chunks: list[dict], output_dir: Path
):
    """Guarda el index FAISS y los metadatos de chunks."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    faiss.write_index(index, str(output_dir / "index.faiss"))
    
    with open(output_dir / "chunks.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    
    print(f"Index guardado en {output_dir}")
    print(f"  - {index.ntotal} vectores de dimensión {index.d}")
    print(f"  - {len(chunks)} chunks con metadatos")


def main(input_dir: str, output_dir: str):
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    # 1. Encontrar PDFs y TXTs
    pdfs = sorted(input_path.glob("*.pdf"))
    txts = sorted(input_path.glob("*.txt"))

    if not pdfs and not txts:
        print(f"No se encontraron PDFs ni TXTs en {input_path}")
        return

    print(f"PDFs encontrados ({len(pdfs)}): {[p.name for p in pdfs]}")
    print(f"TXTs encontrados ({len(txts)}): {[t.name for t in txts]}")

    # 2. Extraer texto
    todas_las_paginas = []
    for pdf in pdfs:
        paginas = extraer_texto_pdf(pdf)
        print(f"  {pdf.name}: {len(paginas)} páginas con texto")
        todas_las_paginas.extend(paginas)
    for txt in txts:
        paginas = extraer_texto_txt(txt)
        print(f"  {txt.name}: {len(paginas)} bloques")
        todas_las_paginas.extend(paginas)
    
    # 3. Chunking
    chunks = crear_chunks(todas_las_paginas)
    print(f"Total chunks: {len(chunks)}")
    
    # 4. Embeddings
    print(f"Generando embeddings con {config.EMBEDDING_MODEL}...")
    embeddings = generar_embeddings(chunks, config.EMBEDDING_MODEL)
    print(f"Shape embeddings: {embeddings.shape}")
    
    # 5. Index FAISS
    index = crear_index_faiss(embeddings)
    
    # 6. Guardar
    guardar_index(index, chunks, output_path)
    print("¡Ingesta completada!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingesta de PDFs normativos a FAISS")
    parser.add_argument("--input-dir", default="./normativa", help="Directorio con PDFs")
    parser.add_argument("--output-dir", default="./rag/faiss_index", help="Directorio de salida")
    args = parser.parse_args()
    
    main(args.input_dir, args.output_dir)
