FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el proyecto completo
# - schemas/ y rag/faiss_index/ ya están en el repo (se copian aquí)
# - output/ se crea en runtime vía config.py (OUTPUT_PATH.mkdir(exist_ok=True))
COPY . .

EXPOSE 8000

# Railway y Render inyectan $PORT; el default 8000 sirve para correr localmente
CMD uvicorn backend:app --host 0.0.0.0 --port ${PORT:-8000}
