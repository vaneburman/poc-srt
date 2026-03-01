"""
Backend FastAPI para el Agente SRT.

Expone la API REST que consume el frontend estático y sirve
el archivo HTML desde GET /.

Ejecutar:
    uvicorn backend:app --reload
"""
import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
from agente.orquestador import Agente
import agente.orquestador as _orq_module
from agente.tools import ejecutar_tool as _original_ejecutar_tool


# ============================================================
# App
# ============================================================

app = FastAPI(title="Agente SRT API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Sesiones en memoria (session_id → Agente)
# ============================================================

_sessions: dict[str, Agente] = {}


def _get_agente(session_id: str) -> Agente:
    """Devuelve o crea una instancia de Agente para la sesión dada."""
    if session_id not in _sessions:
        _sessions[session_id] = Agente()
    return _sessions[session_id]


# ============================================================
# Helper: ejecutar agente con tracking de tool calls
# ============================================================

def _procesar_con_tracking(agente: Agente, mensaje: str) -> dict:
    """
    Llama a agente.procesar() registrando tool calls y archivos generados.

    Usa un closure por request para capturar los tool calls sin interferencia
    entre sesiones (PoC de usuario único; para multiusuario usar threading.local).
    """
    tools_used: list[dict] = []
    archivo_generado: Optional[dict] = None

    def _tracked_tool(tool_name: str, tool_args: dict) -> str:
        nonlocal archivo_generado
        tools_used.append({"name": tool_name, "args": tool_args})
        resultado_json = _original_ejecutar_tool(tool_name, tool_args)
        if tool_name == "generar_txt":
            res = json.loads(resultado_json)
            if "nombre_archivo" in res:
                archivo_generado = {
                    "nombre": res["nombre_archivo"],
                    "url": f"/api/download/{res['nombre_archivo']}",
                }
        return resultado_json

    _orq_module.ejecutar_tool = _tracked_tool
    try:
        respuesta = agente.procesar(mensaje)
    finally:
        _orq_module.ejecutar_tool = _original_ejecutar_tool

    return {
        "respuesta": respuesta,
        "tools_used": tools_used,
        "archivo_generado": archivo_generado,
    }


# ============================================================
# Endpoints API
# ============================================================

class ChatRequest(BaseModel):
    mensaje: str
    session_id: str


@app.post("/api/chat")
def chat(req: ChatRequest):
    if not config.GEMINI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail=(
                "GEMINI_API_KEY no configurada. "
                "Editá el .env con tu API key y reiniciá el servidor."
            ),
        )
    agente = _get_agente(req.session_id)
    try:
        return _procesar_con_tracking(agente, req.mensaje)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/validar")
def validar(
    archivo: UploadFile = File(...),
    tipo: str = Form(...),
    operacion: str = Form(...),
    session_id: str = Form(...),
):
    if not config.GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY no configurada.")

    safe_name = Path(archivo.filename).name
    temp_path = config.OUTPUT_PATH / safe_name
    temp_path.write_bytes(archivo.file.read())

    agente = _get_agente(session_id)
    op_label = "alta" if operacion.upper() == "A" else "baja"
    mensaje = (
        f"Validá el archivo {safe_name} como {tipo.upper()} {op_label}. "
        f"Ruta: {temp_path}"
    )
    try:
        return _procesar_con_tracking(agente, mensaje)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download/{filename}")
def download(filename: str):
    safe_name = Path(filename).name
    file_path = config.OUTPUT_PATH / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    return FileResponse(path=str(file_path), filename=safe_name, media_type="text/plain")


@app.get("/api/health")
def health():
    schemas = sorted(f.stem for f in config.SCHEMAS_PATH.glob("*.json"))
    rag_chunks = 0
    try:
        chunks_path = config.FAISS_INDEX_PATH / "chunks.json"
        if chunks_path.exists():
            rag_chunks = len(json.loads(chunks_path.read_text(encoding="utf-8")))
    except Exception:
        pass
    return {"status": "ok", "rag_chunks": rag_chunks, "schemas": schemas}


# ============================================================
# Servir frontend estático
# ============================================================

_frontend = Path("frontend")

if _frontend.exists():
    app.mount("/assets", StaticFiles(directory=str(_frontend)), name="assets")


@app.get("/")
def root():
    index = _frontend / "index.html"
    if not index.exists():
        return {"message": "Frontend no encontrado. Asegurate de correr desde la raíz del proyecto."}
    return FileResponse(str(index))


# ============================================================
# Entry point directo (lee $PORT si está seteado por Railway/Render)
# ============================================================

if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.getenv("PORT", 7860))
    uvicorn.run("backend:app", host="0.0.0.0", port=port, reload=False)
