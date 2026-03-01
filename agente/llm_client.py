"""
Abstracción del cliente LLM.

Patrón Strategy: permite cambiar de Gemini (PoC) a Bedrock (AWS)
sin modificar el agente ni las tools.

Migración a AWS:
    1. Implementar BedrockClient (misma interfaz)
    2. Cambiar LLM_PROVIDER en config.py
    Fin.
"""
import json
from abc import ABC, abstractmethod

import config


class LLMClient(ABC):
    """Interfaz base para clientes LLM."""
    
    @abstractmethod
    def invoke_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ) -> dict:
        """
        Envía mensajes al LLM con herramientas disponibles.
        
        Args:
            messages: Historial de mensajes [{role, content}, ...]
            tools: Definición de tools para function calling
            system_prompt: System prompt del agente
        
        Returns:
            Dict con:
                - type: 'text' | 'tool_call'
                - content: str (si type='text')
                - tool_name: str (si type='tool_call')
                - tool_args: dict (si type='tool_call')
        """
        pass


class GeminiClient(LLMClient):
    """
    Cliente para Gemini 2.0 Flash (PoC - gratuito).
    
    Free tier: 15 RPM, 1M TPM, 1500 RPD.
    Docs: https://ai.google.dev/gemini-api/docs/function-calling
    """
    
    def __init__(self):
        import google.generativeai as genai
        
        if not config.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY no configurada. "
                "Obtené una gratis en https://aistudio.google.com/apikey"
            )
        
        genai.configure(api_key=config.GEMINI_API_KEY)
        self._genai = genai
    
    def invoke_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ) -> dict:
        # Convertir tools al formato de Gemini
        gemini_tools = self._convertir_tools(tools)
        
        # Crear modelo con system instruction
        model = self._genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=system_prompt,
            tools=gemini_tools,
            generation_config=self._genai.GenerationConfig(
                temperature=config.LLM_TEMPERATURE,
                max_output_tokens=config.LLM_MAX_TOKENS,
            ),
        )
        
        # Convertir mensajes al formato de Gemini
        gemini_messages = self._convertir_mensajes(messages)
        
        # Llamar al modelo
        response = model.generate_content(gemini_messages)
        
        # Parsear respuesta
        return self._parsear_respuesta(response)
    
    def _convertir_tools(self, tools: list[dict]) -> list:
        """Convierte definición de tools al formato Gemini."""
        function_declarations = []
        for tool in tools:
            function_declarations.append({
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            })
        return [{"function_declarations": function_declarations}]
    
    def _convertir_mensajes(self, messages: list[dict]) -> list:
        """Convierte mensajes al formato Gemini Content."""
        gemini_msgs = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            gemini_msgs.append({
                "role": role,
                "parts": [{"text": msg["content"]}] if isinstance(msg["content"], str) else msg["content"],
            })
        return gemini_msgs
    
    def _parsear_respuesta(self, response) -> dict:
        """Parsea la respuesta de Gemini a formato unificado."""
        candidate = response.candidates[0]
        
        for part in candidate.content.parts:
            # Si hay un function call
            if hasattr(part, "function_call") and part.function_call.name:
                return {
                    "type": "tool_call",
                    "tool_name": part.function_call.name,
                    "tool_args": {k: v for k, v in part.function_call.args.items()},
                }
            # Si hay texto
            if hasattr(part, "text") and part.text:
                return {
                    "type": "text",
                    "content": part.text,
                }
        
        return {"type": "text", "content": "No pude generar una respuesta."}


# === Factory ===

def crear_llm_client() -> LLMClient:
    """
    Factory que crea el cliente LLM según la configuración.
    
    Migración a AWS: agregar 'elif provider == "bedrock": return BedrockClient()'
    """
    return GeminiClient()


# === Placeholder para AWS ===
# class BedrockClient(LLMClient):
#     """
#     Cliente para Bedrock Claude Haiku (producción AWS).
#     Implementar al migrar. Misma interfaz que GeminiClient.
#     
#     def __init__(self):
#         import boto3
#         self.client = boto3.client('bedrock-runtime')
#         self.model_id = 'anthropic.claude-3-haiku-20240307-v1:0'
#     """
#     pass
