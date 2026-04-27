import asyncio
import logging
from typing import Optional

import anthropic
import openai

from app.services.extraction import ExtractedDoc

logger = logging.getLogger(__name__)

# Maps internal codes to human-readable Spanish labels used inside the AI prompt
PROVIDER_TYPE_DISPLAY = {
    "correduria_seguros": "correduría de seguros",
    "agencia_seguros": "agencia de seguros",
    "colaborador_externo": "colaborador externo",
    "generador_leads": "generador de leads",
}

ENTITY_TYPE_DISPLAY = {
    "PF": "Persona Física",
    "PJ": "Persona Jurídica",
}

# This is the full KYC/KYB system prompt. It tells the AI how to behave as a
# compliance analyst. We pass it with "prompt caching" so Anthropic doesn't
# charge us to re-process this large text on every call.
KYC_SYSTEM_PROMPT = """Actúa como un analista senior de KYC/KYB y compliance documental para la contratación y alta de colaboradores o proveedores vinculados a distribución de seguros.

Tu tarea es analizar la documentación aportada por una entidad o persona candidata a colaborar con nosotros, identificar qué documentos se han aportado, a qué requisito equivalen, qué se ha podido validar documentalmente, qué queda pendiente, y qué riesgos o dudas relevantes existen desde un punto de vista KYC/KYB, regulatorio y operativo.

## 1. Contexto del análisis

Debes analizar la documentación recibida y compararla con la documentación requerida según:

- si el sujeto analizado es una PERSONA FÍSICA o una PERSONA JURÍDICA;
- el tipo de contacto o proveedor, que será uno de estos:
  - correduría de seguros
  - agencia de seguros
  - colaborador externo
  - generador de leads
- si se trata de una entidad/persona española o extranjera.

Debes determinar de forma expresa, al inicio del análisis:
1. si el sujeto analizado es persona física o persona jurídica;
2. cuál es el tipo de contacto indicado;
3. cuál es el país de domicilio;
4. si la documentación recibida parece española o extranjera;
5. si, en caso de proveedor extranjero, los documentos aportados son equivalentes funcionales a los exigidos en España.

## 2. Instrucciones clave de análisis

### 2.1. Regla general
No te limites a comprobar si el nombre del documento coincide literalmente con el requerido. Debes hacer un análisis sustantivo y funcional:

- identificar qué es cada documento recibido;
- explicar para qué sirve;
- indicar a qué requisito español equivale, si aplica;
- decir si permite validar el requisito por completo, parcialmente o no;
- señalar si existe alguna limitación, ambigüedad o riesgo.

### 2.2. Para proveedores extranjeros
Si el proveedor no es español, no exijas necesariamente documentos con la misma denominación española. Debes buscar equivalentes razonables del país de origen.

Tu criterio debe ser:
- si existe equivalencia clara -> marcar como validado;
- si el documento cubre solo parcialmente el requisito -> marcar como validado parcialmente;
- si no hay documento suficiente -> marcar como pendiente;
- si el requisito no existe con ese mismo formato en ese país, pero existe un equivalente funcional -> explicarlo expresamente;
- si hay incertidumbre relevante, debes decirlo de forma clara y prudente, sin inventar.

### 2.3. Sobre las "Declaraciones"
Las "Declaraciones" son un documento separado, firmado por el proveedor.
No debes analizar su contenido material salvo instrucción en contrario.
Solo debes validar:
- si existe ese documento;
- si está firmado;
- y, si es posible verlo, si parece corresponder al tipo de proveedor analizado.

Si no está firmado, debes marcarlo como no válido.

### 2.4. Enfoque de prudencia
No des por válido algo crítico por inferencia débil.

Debes distinguir siempre entre:
- validado;
- validado parcialmente / con reservas;
- pendiente / no acreditado.

## 3. Documentación exigida

### 3.1. Requisitos base para PERSONA JURÍDICA

1. Escrituras de constitución
2. Escrituras de apoderamiento de representantes legales
3. DNI del representante legal
4. Certificado de titularidad de cuenta bancaria propia (cuenta de gastos generales)
5. Acta de titularidad real con antigüedad menor de 12 meses o último Modelo 200 presentado
6. Certificado de estar al corriente con la Seguridad Social
7. Certificado de estar al corriente con Hacienda

### 3.2. Requisitos base para PERSONA FÍSICA

1. Documento de identidad
2. Documento acreditativo de alta / situación censal / actividad económica, cuando aplique
3. Certificado de titularidad de cuenta bancaria propia
4. Documentación fiscal o equivalente que permita comprobar situación tributaria, cuando aplique
5. Certificados de estar al corriente con Hacienda y Seguridad Social, cuando proceda
6. Si actúa mediante representante, documento de apoderamiento o autorización

Si un requisito de persona jurídica no aplica a persona física, debes indicarlo expresamente como "No aplica".

## 4. Requisitos adicionales según tipo de proveedor

### 4.1. Solo para distribuidores (correduría de seguros o agencia de seguros)

1. Resolución de la DGSFP de otorgamiento de clave
2. Certificado de titularidad de la cuenta dedicada a cobros de clientes (solo si van a cobrar ellos directamente)
3. Póliza de RC profesional en vigor + justificante de pago
4. Certificado de formación del responsable de la distribución
5. Declaraciones firmadas del proveedor (independencia, distribución y formación, blanqueo de capitales, no sancionados por DGSFP)

### 4.2. Solo para colaboradores externos

Revisar que no haya indicios de distribución no autorizada. Debe existir documento de Declaraciones firmado (funciones, cumplimiento normativo, no sancionado, PBC/FT, reclamaciones).

### 4.3. Generador de leads

Criterio similar a colaborador externo. Confirmar que la actividad es solo captación. Alertar si parece exceder la mera generación de leads.

## 5. Qué debes revisar en los documentos

### 5.1-5.7: Identificación, representación, titularidad real, cuenta bancaria, situación fiscal, aspectos regulatorios, riesgos e incoherencias.

## 6. Método de clasificación semáforo

- 🟢 VERDE: validado suficientemente.
- 🟡 AMARILLO: validado parcialmente, con reservas.
- 🔴 ROJO: no validado, no aportado, insuficiente, no firmado o con incidencia crítica.

Dividir en: Bloque A (Crítico), Bloque B (Importante), Bloque C (Formal/complementario).

## 7. Formato de salida obligatorio

Informe interno en español. Estructura:
1. Asunto
2. Resumen ejecutivo (3-6 líneas)
3. Documentación recibida identificada
4. Análisis semáforo por bloques (A, B, C) con formato: 🟢/🟡/🔴 Nombre del requisito + Documento revisado + Qué se ha podido validar + Equivalencia + Observaciones + Acción recomendada
5. Pendientes documentales
6. Conclusión operativa (apto / apto con reservas / no apto)

## 8. Reglas de estilo

No inventes datos. Si algo no puede confirmarse, dilo. Sé prudente. Escribe de forma clara y orientada a negocio/compliance.

El informe completo no debe superar los 4.000 caracteres en total. Sé muy conciso: resume cada punto en 1-2 líneas, evita repeticiones y usa frases cortas. Nunca omitas ningún requisito del análisis semáforo ni la conclusión operativa, pero prioriza la brevedad sobre el detalle.

## 10. Proceso interno antes de redactar

1. Clasifica PF o PJ
2. Identifica país y si la documentación es nacional o extranjera
3. Construye la checklist aplicable
4. Mapea documentos contra la checklist
5. Detecta equivalencias y carencias
6. Evalúa riesgos críticos
7. Redacta el email final con formato semáforo

Ahora analiza la documentación que te aporte siguiendo exactamente estas instrucciones."""


def _build_anthropic_content(
    provider_name: str,
    provider_type: str,
    entity_type: str,
    country: str,
    extracted_docs: list[ExtractedDoc],
) -> list[dict]:
    """
    Build the list of content blocks to send to Anthropic's API.
    Each document becomes either a text block or an image block.
    """
    provider_display = PROVIDER_TYPE_DISPLAY.get(provider_type, provider_type)
    entity_display = ENTITY_TYPE_DISPLAY.get(entity_type, entity_type)

    content: list[dict] = [
        {
            "type": "text",
            "text": (
                f"Analiza la siguiente documentación KYC/KYB:\n\n"
                f"- Nombre del proveedor: {provider_name}\n"
                f"- Tipo de proveedor: {provider_display}\n"
                f"- Tipo de entidad: {entity_display}\n"
                f"- País: {country}\n\n"
                f"A continuación se adjuntan los documentos aportados:"
            ),
        }
    ]

    for doc in extracted_docs:
        if doc.image_b64 is not None:
            # Image document — pass pixels directly to Claude Vision
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": doc.mime_type,
                        "data": doc.image_b64,
                    },
                }
            )
            # Add a text label after the image so Claude knows what it was
            content.append(
                {
                    "type": "text",
                    "text": f"[Documento anterior: {doc.label} — {doc.filename}]",
                }
            )
        elif doc.text:
            content.append(
                {
                    "type": "text",
                    "text": f"[{doc.label} — {doc.filename}]\n{doc.text}",
                }
            )
        else:
            # Document that could not be extracted — tell the AI it's missing
            content.append(
                {
                    "type": "text",
                    "text": (
                        f"[{doc.label} — {doc.filename}]\n"
                        f"(No se pudo extraer el contenido de este documento.)"
                    ),
                }
            )

    return content


def _convert_to_openai_content(anthropic_content: list[dict]) -> list[dict]:
    """
    Convert Anthropic-format content blocks to the format OpenAI expects.
    The structure is slightly different for image blocks.
    """
    openai_content: list[dict] = []

    for block in anthropic_content:
        if block["type"] == "text":
            openai_content.append({"type": "text", "text": block["text"]})
        elif block["type"] == "image":
            source = block["source"]
            mime_type = source["media_type"]
            data = source["data"]
            openai_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{data}"},
                }
            )

    return openai_content


DEFAULT_MODEL = "claude-sonnet-4-6"

_anthropic_client: anthropic.AsyncAnthropic | None = None


def _get_anthropic_client(api_key: str) -> anthropic.AsyncAnthropic:
    """Return a module-level cached AsyncAnthropic client."""
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.AsyncAnthropic(api_key=api_key)
    return _anthropic_client


async def _call_anthropic(
    content_list: list[dict],
    anthropic_api_key: str,
    model: str = DEFAULT_MODEL,
) -> tuple[str, str]:
    """
    Call Anthropic's Claude API with the KYC system prompt and document content.
    Uses prompt caching on the system prompt to reduce costs on repeated calls.
    """
    client = _get_anthropic_client(anthropic_api_key)
    response = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": KYC_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": content_list}],
    )
    return response.content[0].text, model


_openai_client: openai.AsyncOpenAI | None = None


def _get_openai_client(api_key: str) -> openai.AsyncOpenAI:
    """Return a module-level cached AsyncOpenAI client."""
    global _openai_client
    if _openai_client is None:
        _openai_client = openai.AsyncOpenAI(api_key=api_key)
    return _openai_client


async def _call_openai(
    content_list: list[dict],
    openai_api_key: str,
) -> tuple[str, str]:
    """
    Call OpenAI's GPT-4o as a fallback if Anthropic is unavailable.
    Converts the content format before sending.
    """
    openai_client = _get_openai_client(openai_api_key)
    openai_content = _convert_to_openai_content(content_list)

    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        max_tokens=4096,
        messages=[
            {"role": "system", "content": KYC_SYSTEM_PROMPT},
            {"role": "user", "content": openai_content},
        ],
    )
    return response.choices[0].message.content, "gpt-4o"


async def run_analysis(
    provider_name: str,
    provider_type: str,
    entity_type: str,
    country: str,
    extracted_docs: list[ExtractedDoc],
    anthropic_api_key: str,
    openai_api_key: str,
    model: str = DEFAULT_MODEL,
) -> tuple[str, str]:
    """
    Run KYC/KYB AI analysis on the provided documents.

    Strategy:
    1. Try Anthropic (Claude) first — up to 2 attempts
    2. If Anthropic fails (rate limit or server error), fall back to OpenAI (GPT-4o)

    Returns:
        Tuple of (ai_response_text, model_name_used)
    """
    content_list = _build_anthropic_content(
        provider_name, provider_type, entity_type, country, extracted_docs
    )

    # If an OpenAI model was explicitly requested, skip Anthropic entirely.
    # Sending a GPT model name to the Anthropic API would cause a 4xx error
    # and waste ~4 seconds on retries before the OpenAI fallback triggered.
    if model.startswith("gpt-"):
        logger.info("GPT model requested — routing directly to OpenAI for provider %s", provider_name)
        try:
            result = await _call_openai(content_list, openai_api_key)
            logger.info("OpenAI API call succeeded")
            return result
        except Exception as exc:
            logger.error("OpenAI API call failed: %s", exc)
            raise RuntimeError(f"OpenAI analysis failed: {exc}") from exc

    # Attempt Anthropic up to 2 times before falling back
    last_exception: Optional[Exception] = None
    for attempt in range(2):
        try:
            logger.info(
                "Calling Anthropic API (attempt %d) for provider %s", attempt + 1, provider_name
            )
            result = await _call_anthropic(content_list, anthropic_api_key, model=model)
            logger.info("Anthropic API call succeeded on attempt %d", attempt + 1)
            return result
        except anthropic.RateLimitError as exc:
            logger.warning("Anthropic rate limit hit (attempt %d): %s", attempt + 1, exc)
            last_exception = exc
            if attempt == 0:
                # Brief pause before retry
                await asyncio.sleep(2)
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                logger.warning(
                    "Anthropic server error %d (attempt %d): %s",
                    exc.status_code,
                    attempt + 1,
                    exc,
                )
                last_exception = exc
                if attempt == 0:
                    await asyncio.sleep(2)
            else:
                # 4xx errors (e.g. invalid request) — no point retrying
                raise
        except Exception as exc:
            logger.warning("Anthropic API call failed (attempt %d): %s", attempt + 1, exc)
            last_exception = exc
            if attempt == 0:
                await asyncio.sleep(2)

    # Anthropic failed twice — fall back to OpenAI
    logger.warning(
        "Anthropic failed after 2 attempts (%s) — falling back to OpenAI", last_exception
    )
    try:
        logger.info("Calling OpenAI API for provider %s", provider_name)
        result = await _call_openai(content_list, openai_api_key)
        logger.info("OpenAI API call succeeded")
        return result
    except Exception as exc:
        logger.error("Both Anthropic and OpenAI failed: %s", exc)
        raise RuntimeError(
            f"AI analysis failed on all providers. Last Anthropic error: {last_exception}. "
            f"OpenAI error: {exc}"
        ) from exc
