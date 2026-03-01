# Normativa SRT

Colocá aquí los PDFs de las resoluciones para el pipeline RAG.

## Archivos necesarios

- `res_3326_2014.pdf` — Resolución 3326/2014 (Accidentes de Trabajo)
- `res_3327_2014.pdf` — Resolución 3327/2014 (Enfermedades Profesionales)
- `res_475_2017.pdf` — Resolución 475/2017 (modificatoria)
- `res_81_2019.pdf` — Resolución 81/2019 (modificatoria)

## Dónde obtenerlos

Los PDFs se encuentran en el sitio oficial de la SRT:
https://www.argentina.gob.ar/srt/normativa

**Nota:** Estos archivos NO se versionan en el repositorio (están en `.gitignore`).

## Después de colocar los PDFs

Ejecutar la ingesta RAG:

```bash
python rag/ingest.py --input-dir ./normativa --output-dir ./rag/faiss_index
```
