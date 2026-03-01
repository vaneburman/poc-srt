FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el proyecto completo
# - schemas/ y rag/faiss_index/ ya están en el repo (se copian aquí)
# - output/ se crea en runtime vía config.py (OUTPUT_PATH.mkdir(exist_ok=True))
COPY . .

EXPOSE 7860

# HuggingFace Spaces usa 7860; Railway/Render inyectan $PORT automáticamente
CMD uvicorn backend:app --host 0.0.0.0 --port ${PORT:-7860}
