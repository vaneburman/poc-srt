# Guía de Migración a AWS

## Objetivo

Este documento describe paso a paso cómo migrar la PoC local a infraestructura AWS.
Cada componente local tiene un equivalente directo en AWS — no hay código descartable.

---

## Mapping de Componentes

| # | Componente Local | Servicio AWS | Esfuerzo |
|---|-----------------|-------------|----------|
| 1 | `motor/generador.py` + `validador.py` | Lambda `fn_motor_srt` | Bajo |
| 2 | `agente/orquestador.py` | Lambda `fn_agente` | Bajo |
| 3 | `agente/llm_client.py` → `GeminiClient` | `BedrockClient` con boto3 | Bajo |
| 4 | `rag/faiss_index/` | S3 + Lambda carga en `/tmp` | Bajo |
| 5 | `schemas/*.json` | S3 bucket con versionado | Trivial |
| 6 | `mock_data/` → endpoint real | API Gateway + VPC Link | Medio |
| 7 | Streamlit local | S3 static + API Gateway | Medio |
| 8 | `.env` | Secrets Manager / SSM Parameter Store | Bajo |

---

## Paso 1: Motor Determinístico → Lambda

**Archivo:** `motor/generador.py`, `motor/validador.py`, `motor/utils.py`

El motor es Python puro sin dependencias externas. La migración consiste en agregar un handler Lambda.

```python
# lambda_handler.py (nuevo archivo)
import json
from motor.generador import generar_archivo_con_resumen
from motor.validador import validar_archivo, generar_resumen_validacion

def handler(event, context):
    modo = event.get("modo")  # "generar" o "validar"
    
    if modo == "generar":
        resultado = generar_archivo_con_resumen(
            lista_datos=event["datos"],
            tipo=event["tipo"],
            operacion=event["operacion"],
        )
        # Guardar en S3 en vez de filesystem local
        import boto3
        s3 = boto3.client("s3")
        s3.put_object(
            Bucket="poc-srt-archivos",
            Key=resultado["nombre_archivo"],
            Body=resultado["contenido_bytes"],
        )
        # Generar presigned URL
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": "poc-srt-archivos", "Key": resultado["nombre_archivo"]},
            ExpiresIn=3600,
        )
        resultado.pop("contenido_bytes")
        resultado["url_descarga"] = url
        return resultado
    
    elif modo == "validar":
        # Leer de S3 en vez de filesystem
        import boto3
        s3 = boto3.client("s3")
        obj = s3.get_object(Bucket="poc-srt-archivos", Key=event["s3_key"])
        contenido = obj["Body"].read()
        errores = validar_archivo(contenido, event["tipo"], event["operacion"])
        return generar_resumen_validacion(errores)
```

**Empaquetado:**
```bash
cd poc-agente-srt
zip -r lambda_motor.zip motor/ schemas/ lambda_handler.py
# Subir a Lambda con runtime Python 3.12
```

**Schemas en S3:**
```bash
aws s3 sync schemas/ s3://poc-srt-config/schemas/ 
```
Modificar `esquema_loader.py` para leer de S3 en vez de filesystem local.

---

## Paso 2: LLM Client → Bedrock

**Archivo:** `agente/llm_client.py`

Implementar la clase `BedrockClient` que ya está preparada como placeholder:

```python
class BedrockClient(LLMClient):
    def __init__(self):
        import boto3
        self.client = boto3.client("bedrock-runtime", region_name="us-east-1")
        self.model_id = "anthropic.claude-3-haiku-20240307-v1:0"
    
    def invoke_with_tools(self, messages, tools, system_prompt):
        # Convertir tools al formato Anthropic
        anthropic_tools = [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["parameters"],
            }
            for t in tools
        ]
        
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "temperature": 0.0,
            "system": system_prompt,
            "messages": messages,
            "tools": anthropic_tools,
        }
        
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(body),
        )
        
        result = json.loads(response["body"].read())
        
        # Parsear respuesta Anthropic
        for block in result.get("content", []):
            if block["type"] == "tool_use":
                return {
                    "type": "tool_call",
                    "tool_name": block["name"],
                    "tool_args": block["input"],
                }
            elif block["type"] == "text":
                return {"type": "text", "content": block["text"]}
        
        return {"type": "text", "content": "Sin respuesta."}
```

**Cambio en factory:**
```python
def crear_llm_client():
    provider = os.getenv("LLM_PROVIDER", "gemini")
    if provider == "bedrock":
        return BedrockClient()
    return GeminiClient()
```

---

## Paso 3: FAISS Index → S3

**Archivo:** `rag/search.py`

El index FAISS se sube a S3 y la Lambda lo descarga a `/tmp` en el cold start:

```python
import boto3
import os

def _cargar_recursos_aws():
    global _index, _chunks
    s3 = boto3.client("s3")
    
    # Descargar a /tmp (512MB disponibles en Lambda)
    s3.download_file("poc-srt-config", "faiss/index.faiss", "/tmp/index.faiss")
    s3.download_file("poc-srt-config", "faiss/chunks.json", "/tmp/chunks.json")
    
    _index = faiss.read_index("/tmp/index.faiss")
    with open("/tmp/chunks.json") as f:
        _chunks = json.load(f)
```

**Subir index:**
```bash
aws s3 cp rag/faiss_index/index.faiss s3://poc-srt-config/faiss/
aws s3 cp rag/faiss_index/chunks.json s3://poc-srt-config/faiss/
```

**Nota sobre Lambda layers:** `sentence-transformers` y `faiss-cpu` son pesados. Crear un Lambda Layer o usar container image.

---

## Paso 4: Endpoint Java → API Gateway + VPC Link

**Problema:** Las Lambdas de IA deben alcanzar el endpoint Java en la VPC privada sin usar NAT Gateway ($32/mes).

**Solución:**

1. Crear API Gateway (REST API) con VPC Link al endpoint Java
2. Las Lambdas quedan FUERA de la VPC
3. Llaman al endpoint Java via el API Gateway (que sí tiene acceso a la VPC)

```
Lambda (fuera VPC) → API Gateway → VPC Link → Endpoint Java (en VPC)
```

API Gateway free tier: 1M requests/mes → $0.00

---

## Paso 5: Frontend → S3 + API Gateway

**Opción A (rápida):** AppRunner con Streamlit
```bash
# Dockerfile
FROM python:3.12-slim
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501"]
```

**Opción B (costo cero):** Reescribir UI como HTML/JS estático
- Hostear en S3 como static website
- API Gateway como backend → Lambda orquestadora
- Más trabajo pero $0.00

---

## Paso 6: Secrets

Migrar variables de `.env` a AWS Systems Manager Parameter Store:

```bash
aws ssm put-parameter --name "/poc-srt/bedrock-model-id" \
    --value "anthropic.claude-3-haiku-20240307-v1:0" --type String

# En config.py
import boto3
ssm = boto3.client("ssm")
MODEL_ID = ssm.get_parameter(Name="/poc-srt/bedrock-model-id")["Parameter"]["Value"]
```

---

## Checklist de Migración

- [ ] Crear bucket S3 `poc-srt-archivos` y `poc-srt-config`
- [ ] Subir schemas JSON a S3
- [ ] Subir FAISS index a S3
- [ ] Habilitar modelo Claude 3 Haiku en Bedrock (region us-east-1)
- [ ] Crear IAM Role para Lambdas (S3, Bedrock, CloudWatch)
- [ ] Deploy Lambda `fn_motor_srt` con handler
- [ ] Deploy Lambda `fn_agente` con BedrockClient
- [ ] Crear API Gateway + VPC Link para endpoint Java
- [ ] Crear API Gateway para frontend (si se usa S3 static)
- [ ] Configurar parámetros en SSM
- [ ] Test end-to-end en AWS
- [ ] Configurar CloudWatch alarms

**Estimación total: 2-3 semanas con 1 desarrollador.**
