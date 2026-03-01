"""
Orquestador del Agente IA.

Implementa el loop ReAct (Reason + Act):
1. Recibe mensaje del usuario
2. LLM decide si necesita usar una herramienta o responder directo
3. Si usa herramienta: ejecuta → devuelve resultado al LLM → repite
4. Si responde texto: devuelve al usuario
"""
from agente.llm_client import crear_llm_client, LLMClient
from agente.tools import TOOLS_DEFINITION, ejecutar_tool
from agente.prompts import SYSTEM_PROMPT


class Agente:
    """
    Agente IA para normativa SRT.
    
    Uso:
        agente = Agente()
        respuesta = agente.procesar("Generame el AT de altas de enero 2024")
    """
    
    MAX_TOOL_ITERATIONS = 5  # Prevenir loops infinitos
    
    def __init__(self, llm_client: LLMClient | None = None):
        self.llm = llm_client or crear_llm_client()
        self.historial: list[dict] = []
    
    def procesar(self, mensaje_usuario: str) -> str:
        """
        Procesa un mensaje del usuario y retorna la respuesta del agente.
        
        Args:
            mensaje_usuario: Texto del usuario
        
        Returns:
            Respuesta del agente en texto natural
        """
        # Agregar mensaje del usuario al historial
        self.historial.append({"role": "user", "content": mensaje_usuario})
        
        # Loop ReAct
        for _ in range(self.MAX_TOOL_ITERATIONS):
            respuesta_llm = self.llm.invoke_with_tools(
                messages=self.historial,
                tools=TOOLS_DEFINITION,
                system_prompt=SYSTEM_PROMPT,
            )
            
            if respuesta_llm["type"] == "text":
                # El LLM respondió con texto → fin del loop
                texto = respuesta_llm["content"]
                self.historial.append({"role": "assistant", "content": texto})
                return texto
            
            elif respuesta_llm["type"] == "tool_call":
                # El LLM quiere usar una herramienta
                tool_name = respuesta_llm["tool_name"]
                tool_args = respuesta_llm["tool_args"]
                
                # Ejecutar la herramienta
                resultado = ejecutar_tool(tool_name, tool_args)
                
                # Agregar al historial para que el LLM lo vea
                self.historial.append({
                    "role": "assistant",
                    "content": f"[Ejecutando herramienta: {tool_name}({tool_args})]",
                })
                self.historial.append({
                    "role": "user",
                    "content": f"Resultado de {tool_name}: {resultado}",
                })
        
        # Si se alcanzó el máximo de iteraciones
        return (
            "Lo siento, no pude completar la tarea después de varios intentos. "
            "¿Podés reformular tu consulta?"
        )
    
    def resetear_historial(self):
        """Limpia el historial de conversación."""
        self.historial = []
    
    def obtener_historial(self) -> list[dict]:
        """Retorna una copia del historial actual."""
        return list(self.historial)
