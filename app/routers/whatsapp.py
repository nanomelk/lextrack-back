"""
whatsapp.py - Router FastAPI para la integración con WhatsApp Business Cloud API.
Proporciona verificación de Webhook de Meta e ingesta dinámica por chatbot conversacional.

GET /api/v1/whatsapp/webhook  → Verificación de Webhook por Meta (hub.verify_token)
POST /api/v1/whatsapp/webhook → Ingesta y procesamiento conversacional de mensajes de clientes
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from app.config import WHATSAPP_VERIFY_TOKEN
from app.schemas.caso_schema import CasoDB
from app.services.sheets_service import insertar_caso_por_telefono
from app.services.whatsapp_service import enviar_mensaje_whatsapp

router = APIRouter(prefix="/api/v1/whatsapp", tags=["WhatsApp Integration"])
logger = logging.getLogger(__name__)

# Diccionario en memoria para almacenar las sesiones conversacionales por número de teléfono
# Estructura: { phone_number: { "step": int, "data": dict } }
user_sessions: Dict[str, Dict[str, Any]] = {}


@router.get(
    "/webhook",
    summary="Verificación del Webhook de WhatsApp Cloud API",
    description="Endpoint GET para validar el Webhook solicitado por Meta durante la configuración.",
)
async def verificar_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
) -> Response:
    """
    Responde al apretón de manos (handshake) de la API de Meta.
    Verifica que hub.verify_token coincida con WHATSAPP_VERIFY_TOKEN.
    """
    logger.info("Solicitud de verificación de Webhook de Meta recibida: mode=%s", hub_mode)

    if hub_mode == "subscribe" and hub_verify_token == WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook de WhatsApp verificado exitosamente.")
        return Response(content=hub_challenge or "", media_type="text/plain", status_code=200)

    logger.warning("Fallo en la verificación del token de WhatsApp. Token recibido: %s", hub_verify_token)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Verificación de token inválida. Token no coincide con WHATSAPP_VERIFY_TOKEN.",
    )


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Recepción de mensajes entrantes de WhatsApp",
    description="Endpoint POST para recibir webhooks de Meta y procesar mensajes a través del chatbot conversacional.",
)
async def recibir_mensaje_webhook(request: Request) -> dict[str, Any]:
    """
    Recibe el payload JSON del webhook de Meta WhatsApp API y gestiona el flujo del chatbot.
    """
    try:
        body = await request.json()
    except Exception as exc:
        logger.error("Error al decodificar JSON del webhook: %s", exc)
        return {"status": "error", "message": "Invalid JSON body"}

    # Extraer mensajes del payload de Meta
    entry = body.get("entry", [])
    if not entry:
        return {"status": "ignored", "reason": "No entry found"}

    changes = entry[0].get("changes", [])
    if not changes:
        return {"status": "ignored", "reason": "No changes found"}

    value = changes[0].get("value", {})
    messages = value.get("messages", [])

    if not messages:
        # Puede ser una notificación de estado de mensaje enviado/leído
        return {"status": "ignored", "reason": "No messages in payload"}

    message_data = messages[0]
    from_number = message_data.get("from", "").strip()
    msg_type = message_data.get("type", "")

    # Solo procesamos mensajes de texto por el momento
    if msg_type != "text":
        logger.info("Mensaje no-texto recibido de %s (tipo: %s)", from_number, msg_type)
        await enviar_mensaje_whatsapp(
            from_number,
            "Por favor, envíe su respuesta en texto plano para continuar con la ingesta.",
        )
        return {"status": "handled", "reason": "Non-text message received"}

    text_body = message_data.get("text", {}).get("body", "").strip()
    logger.info("Mensaje recibido de %s: '%s'", from_number, text_body)

    # Formatear el número con el prefijo + si no lo posee para uniformidad en el sistema
    formatted_phone = f"+{from_number}" if not from_number.startswith("+") else from_number

    # Procesar lógica de chatbot conversacional
    await procesar_chatbot_conversacional(formatted_phone, text_body)

    return {"status": "processed"}


async def procesar_chatbot_conversacional(phone_number: str, message_text: str) -> None:
    """
    Máquina de estados conversacional para recopilar secuencialmente los datos requeridos (RD-02).
    """
    # Si el usuario quiere reiniciar o cancelar
    if message_text.lower() in ["reiniciar", "cancelar", "inicio", "reset"]:
        user_sessions.pop(phone_number, None)
        await enviar_mensaje_whatsapp(
            phone_number,
            "🔄 Sesión cancelada. Envíe cualquier mensaje para iniciar un nuevo registro de caso.",
        )
        return

    session = user_sessions.get(phone_number)

    # Paso 0 (Inicial / Usuario nuevo o sin sesión activa)
    if session is None:
        user_sessions[phone_number] = {
            "step": 1,
            "data": {},
        }
        prompt_paso_0 = (
            "¡Hola! Bienvenido al Estudio Jurídico. "
            "Para registrar su caso, por favor envíe su *Nombre Completo*."
        )
        await enviar_mensaje_whatsapp(phone_number, prompt_paso_0)
        return

    step = session.get("step", 1)
    data = session.get("data", {})

    # Paso 1: Recibir Nombre Completo -> Solicitar DNI
    if step == 1:
        data["nombre_cliente"] = message_text
        session["step"] = 2
        prompt_paso_1 = "Gracias. Por favor, ingrese su número de *DNI*."
        await enviar_mensaje_whatsapp(phone_number, prompt_paso_1)
        return

    # Paso 2: Recibir DNI -> Solicitar Domicilio Real
    if step == 2:
        data["dni_cliente"] = message_text
        session["step"] = 3
        prompt_paso_2 = "Ingrese su *Domicilio Real*."
        await enviar_mensaje_whatsapp(phone_number, prompt_paso_2)
        return

    # Paso 3: Recibir Domicilio Real -> Solicitar Resumen del Hecho
    if step == 3:
        data["domicilio_cliente"] = message_text
        session["step"] = 4
        prompt_paso_3 = "Describa brevemente el *Resumen del Hecho* o consulta."
        await enviar_mensaje_whatsapp(phone_number, prompt_paso_3)
        return

    # Paso 4: Recibir Resumen del Hecho -> Solicitar Link Evidencia / 'No'
    if step == 4:
        data["resumen_hecho"] = message_text
        session["step"] = 5
        prompt_paso_4 = "Si posee documentación/evidencia en Google Drive, envíe el *Enlace*, o responda 'No'."
        await enviar_mensaje_whatsapp(phone_number, prompt_paso_4)
        return

    # Paso 5: Recibir Link Evidencia -> Ingestar en Google Sheets y Confirmar
    if step == 5:
        link_input = message_text.strip()
        link_evidencia = (
            ""
            if link_input.lower() in ["no", "n/a", "none", "ninguno", "no tengo"]
            else link_input
        )
        data["link_evidencia"] = link_evidencia

        # Construir objeto CasoDB (RD-01)
        nombre = data.get("nombre_cliente", "")
        dni = data.get("dni_cliente", "")
        domicilio = data.get("domicilio_cliente", "")
        resumen = data.get("resumen_hecho", "")

        nuevo_caso = CasoDB(
            caratula=f"{nombre} s/ Ingesta WhatsApp",
            nro_expediente="PENDIENTE",
            fuero="Sin Asignar",
            fecha_vencimiento=date.today().isoformat(),
            tipo_plazo="Sin Asignar",
            estado_tramite="Ingesta Recibida",
            link_evidencia=link_evidencia,
            nombre_cliente=nombre,
            dni_cliente=dni,
            domicilio_cliente=domicilio,
            resumen_hecho=resumen,
        )

        try:
            caso_guardado = insertar_caso_por_telefono(phone_number, nuevo_caso)
            id_generado = caso_guardado.id_caso

            msg_confirmacion = (
                f"✅ ¡Muchas gracias, *{nombre}*! Su caso ha sido registrado exitosamente.\n\n"
                f"📋 *ID de Caso:* `{id_generado}`\n"
                f"📌 *Estado:* Ingesta Recibida\n\n"
                f"Un profesional del Estudio Jurídico revisará su consulta y se pondrá en contacto a la brevedad."
            )
            await enviar_mensaje_whatsapp(phone_number, msg_confirmacion)

        except Exception as exc:
            logger.error("Error al insertar caso desde WhatsApp para %s: %s", phone_number, exc, exc_info=True)
            await enviar_mensaje_whatsapp(
                phone_number,
                "⚠️ Ocurrió un inconveniente al guardar los datos de su caso. Por favor intente más tarde.",
            )
        finally:
            # Limpiar sesión del usuario tras finalizar la ingesta
            user_sessions.pop(phone_number, None)
