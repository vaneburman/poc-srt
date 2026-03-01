#!/usr/bin/env python3
"""
Script para probar el agente SRT desde la terminal.

Uso: python test_agente_manual.py
Requiere GEMINI_API_KEY en .env

Permite chatear con el agente por stdin/stdout.
Muestra claramente cuando el agente usa una tool (nombre + args).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import agente.orquestador as _orq_module
from agente.tools import ejecutar_tool as _ejecutar_tool_original


def _ejecutar_tool_con_display(tool_name: str, tool_args: dict) -> str:
    """Wrapper que muestra la tool call antes de ejecutarla."""
    print(f"  [TOOL] {tool_name}({tool_args})")
    resultado = _ejecutar_tool_original(tool_name, tool_args)
    return resultado


def main():
    # Parchear ejecutar_tool en el módulo orquestador para ver los tool calls
    _orq_module.ejecutar_tool = _ejecutar_tool_con_display

    print("=== Agente SRT - Prueba Manual ===")
    print("Escribe tu consulta o 'salir' para terminar\n")

    try:
        from agente.orquestador import Agente
        agente = Agente()
        print("[OK] Agente inicializado correctamente\n")
    except ValueError as e:
        print(f"[ERROR] No se pudo inicializar el agente: {e}")
        sys.exit(1)

    while True:
        try:
            user_input = input("Usuario: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo...")
            break

        if not user_input:
            continue

        if user_input.lower() == "salir":
            print("Hasta luego!")
            break

        print()
        respuesta = agente.procesar(user_input)
        print(f"Agente: {respuesta}\n")
        print("-" * 50)


if __name__ == "__main__":
    main()
