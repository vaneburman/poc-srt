"""
Pipeline de ingesta RAG: PDFs → Chunks → Embeddings → FAISS Index.

Se ejecuta UNA VEZ (o cuando cambien las resoluciones).
El index generado se commitea al repo.

Uso:
    python rag/ingest.py --input-dir ./normativa --output-dir ./rag/faiss_index
"""
import argparse
import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config


def extraer_texto_pdf(pdf_path: Path) -> list[dict]:
    """Extrae texto de un PDF, página por página."""
    reader = PdfReader(str(pdf_path))
    paginas = []
    for i, page in enumerate(reader.pages):
        texto = page.extract_text()
        if texto and texto.strip():
            paginas.append({
                "texto": texto.strip(),
                "fuente": pdf_path.name,
                "pagina": i + 1,
            })
    return paginas


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


def generar_embeddings(chunks: list[dict], modelo: SentenceTransformer) -> np.ndarray:
    """Genera embeddings para todos los chunks."""
    textos = [chunk["texto"] for chunk in chunks]
    embeddings = modelo.encode(textos, show_progress_bar=True, normalize_embeddings=True)
    return np.array(embeddings, dtype="float32")


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
    
    # 1. Encontrar PDFs
    pdfs = list(input_path.glob("*.pdf"))
    if not pdfs:
        print(f"No se encontraron PDFs en {input_path}")
        print("Colocá los PDFs de las resoluciones en la carpeta normativa/")
        return
    
    print(f"Encontrados {len(pdfs)} PDFs: {[p.name for p in pdfs]}")
    
    # 2. Extraer texto
    todas_las_paginas = []
    for pdf in pdfs:
        paginas = extraer_texto_pdf(pdf)
        print(f"  {pdf.name}: {len(paginas)} páginas")
        todas_las_paginas.extend(paginas)
    
    # 3. Chunking
    chunks = crear_chunks(todas_las_paginas)
    print(f"Total chunks: {len(chunks)}")
    
    # 4. Embeddings
    print(f"Generando embeddings con {config.EMBEDDING_MODEL}...")
    modelo = SentenceTransformer(config.EMBEDDING_MODEL)
    embeddings = generar_embeddings(chunks, modelo)
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
