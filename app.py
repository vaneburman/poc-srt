"""
Interfaz de usuario del Agente SRT.
Streamlit app con chat + upload + generación de archivos.
"""
import streamlit as st
from pathlib import Path
from datetime import date

import config

st.set_page_config(
    page_title="Agente SRT - PoC",
    page_icon="📋",
    layout="wide",
)

st.title("📋 Agente IA - Normativa SRT")
st.caption("PoC: Generación y validación de archivos posicionales (Res. 3326/3327)")


# === Inicialización ===

@st.cache_resource
def cargar_agente():
    from agente import Agente
    return Agente()


if "mensajes" not in st.session_state:
    st.session_state.mensajes = []

if "agente" not in st.session_state:
    try:
        st.session_state.agente = cargar_agente()
    except Exception as e:
        st.error(f"Error inicializando agente: {e}")
        st.stop()


# === Sidebar ===

with st.sidebar:
    st.header("⚡ Acciones Rápidas")
    
    st.subheader("Generar Archivo")
    col1, col2 = st.columns(2)
    with col1:
        tipo = st.selectbox("Tipo", ["AT", "EP"])
    with col2:
        operacion = st.selectbox("Operación", ["A - Alta", "B - Baja"])
    
    fecha_desde = st.date_input("Desde", value=date(2024, 1, 1))
    fecha_hasta = st.date_input("Hasta", value=date(2024, 1, 31))
    
    if st.button("🔨 Generar TXT", use_container_width=True):
        op_code = operacion[0]
        prompt = (
            f"Generame el archivo {tipo} de "
            f"{'altas' if op_code == 'A' else 'bajas'} "
            f"desde {fecha_desde} hasta {fecha_hasta}"
        )
        st.session_state.mensajes.append({"role": "user", "content": prompt})
        st.rerun()
    
    st.divider()
    
    st.subheader("Validar Archivo")
    archivo_subido = st.file_uploader(
        "Subir archivo TXT",
        type=["txt", "at", "ep"],
        help="Subí un archivo TXT posicional para validar",
    )
    
    if archivo_subido:
        # Guardar archivo temporalmente
        temp_path = config.OUTPUT_PATH / archivo_subido.name
        temp_path.write_bytes(archivo_subido.getvalue())
        
        tipo_val = st.selectbox("Tipo archivo", ["AT", "EP"], key="tipo_val")
        op_val = st.selectbox("Operación archivo", ["A - Alta", "B - Baja"], key="op_val")
        
        if st.button("✅ Validar", use_container_width=True):
            op_code = op_val[0]
            prompt = (
                f"Validá el archivo {archivo_subido.name} "
                f"como {tipo_val} {'alta' if op_code == 'A' else 'baja'}. "
                f"Ruta: {temp_path}"
            )
            st.session_state.mensajes.append({"role": "user", "content": prompt})
            st.rerun()
    
    st.divider()
    
    if st.button("🗑️ Limpiar chat", use_container_width=True):
        st.session_state.mensajes = []
        st.session_state.agente.resetear_historial()
        st.rerun()


# === Chat ===

# Mostrar historial
for msg in st.session_state.mensajes:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input del usuario
prompt_usuario = st.chat_input("Preguntá sobre normativa SRT, pedí generar o validar archivos...")

if prompt_usuario:
    st.session_state.mensajes.append({"role": "user", "content": prompt_usuario})
    with st.chat_message("user"):
        st.markdown(prompt_usuario)

# Procesar último mensaje si es del usuario
if st.session_state.mensajes and st.session_state.mensajes[-1]["role"] == "user":
    ultimo_mensaje = st.session_state.mensajes[-1]["content"]
    
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            try:
                respuesta = st.session_state.agente.procesar(ultimo_mensaje)
                st.markdown(respuesta)
                st.session_state.mensajes.append(
                    {"role": "assistant", "content": respuesta}
                )
            except Exception as e:
                error_msg = f"Error: {e}"
                st.error(error_msg)
                st.session_state.mensajes.append(
                    {"role": "assistant", "content": error_msg}
                )
    
    # Verificar si se generó un archivo para ofrecer descarga
    archivos_output = list(config.OUTPUT_PATH.glob("*.txt"))
    if archivos_output:
        ultimo_archivo = max(archivos_output, key=lambda p: p.stat().st_mtime)
        with open(ultimo_archivo, "rb") as f:
            st.download_button(
                label=f"📥 Descargar {ultimo_archivo.name}",
                data=f.read(),
                file_name=ultimo_archivo.name,
                mime="text/plain",
            )
