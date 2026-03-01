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

# ============================================================
# Verificación de API key antes de todo
# ============================================================

if not config.GEMINI_API_KEY:
    st.error(
        "⚠️ **GEMINI_API_KEY no configurada.**\n\n"
        "Creá un archivo `.env` en la raíz del proyecto con:\n"
        "```\nGEMINI_API_KEY=tu_api_key_aqui\n```\n\n"
        "Obtené una API key gratis en: https://aistudio.google.com/apikey"
    )
    st.stop()


# ============================================================
# Inicialización del agente (por sesión, no cacheado globalmente)
# ============================================================

if "agente" not in st.session_state:
    try:
        from agente import Agente
        st.session_state.agente = Agente()
    except ValueError as e:
        st.error(f"❌ Error de configuración: {e}")
        st.stop()
    except Exception as e:
        st.error(f"❌ Error inicializando el agente: {e}")
        st.stop()

if "mensajes" not in st.session_state:
    st.session_state.mensajes = []


# ============================================================
# Helpers para indicadores de tool calls
# ============================================================

import agente.orquestador as _orq_module
from agente.tools import ejecutar_tool as _ejecutar_tool_original

_TOOL_LABELS = {
    "consultar_normativa": "🔍 Consultando normativa...",
    "generar_txt": "🔨 Generando archivo TXT...",
    "validar_txt": "✅ Validando archivo...",
}


def _procesar_con_indicadores(agente_inst, mensaje: str, status_ctx) -> str:
    """Procesa el mensaje mostrando indicadores de tool calls en el status."""

    def _ejecutar_con_display(tool_name: str, tool_args: dict) -> str:
        label = _TOOL_LABELS.get(tool_name, f"⚙️ Ejecutando {tool_name}...")
        status_ctx.write(label)
        return _ejecutar_tool_original(tool_name, tool_args)

    _orq_module.ejecutar_tool = _ejecutar_con_display
    try:
        return agente_inst.procesar(mensaje)
    finally:
        _orq_module.ejecutar_tool = _ejecutar_tool_original


# ============================================================
# UI: Header
# ============================================================

st.title("📋 Agente IA - Normativa SRT")
st.caption("PoC: Generación y validación de archivos posicionales (Res. 3326/3327)")


# ============================================================
# UI: Sidebar
# ============================================================

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


# ============================================================
# UI: Bienvenida (cuando no hay mensajes)
# ============================================================

if not st.session_state.mensajes:
    st.info(
        "👋 **Bienvenido al Agente SRT**\n\n"
        "Puedo ayudarte con:\n\n"
        "- 📖 **Consultar normativa** — preguntá sobre campos, códigos, formatos "
        "y requisitos de las Resoluciones 3326/2014 y 3327/2014\n"
        "- 🔨 **Generar archivos TXT** — generá el archivo posicional para declarar "
        "AT (Accidentes de Trabajo) o EP (Enfermedades Profesionales)\n"
        "- ✅ **Validar archivos TXT** — subí un archivo existente y te explico "
        "los errores encontrados con referencia a la norma\n\n"
        "**Ejemplos:**\n"
        "- *¿Cuál es el formato del campo CUIL en AT alta?*\n"
        "- *Generame el archivo AT de altas de enero 2024*\n"
        "- *Validá este archivo como EP baja*"
    )


# ============================================================
# UI: Historial del chat
# ============================================================

for msg in st.session_state.mensajes:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# ============================================================
# UI: Input del usuario
# ============================================================

prompt_usuario = st.chat_input(
    "Preguntá sobre normativa SRT, pedí generar o validar archivos..."
)

if prompt_usuario:
    st.session_state.mensajes.append({"role": "user", "content": prompt_usuario})
    with st.chat_message("user"):
        st.markdown(prompt_usuario)


# ============================================================
# UI: Procesamiento del último mensaje de usuario
# ============================================================

if st.session_state.mensajes and st.session_state.mensajes[-1]["role"] == "user":
    ultimo_mensaje = st.session_state.mensajes[-1]["content"]

    with st.chat_message("assistant"):
        with st.status("El agente está pensando...", expanded=True) as status:
            try:
                respuesta = _procesar_con_indicadores(
                    st.session_state.agente, ultimo_mensaje, status
                )
                status.update(label="Listo ✓", state="complete", expanded=False)
            except Exception as e:
                status.update(label="Error", state="error", expanded=False)
                respuesta = f"Error al procesar: {e}"
                st.error(respuesta)

        st.markdown(respuesta)
        st.session_state.mensajes.append({"role": "assistant", "content": respuesta})

    # Ofrecer descarga si se generó un archivo
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
