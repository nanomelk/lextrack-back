"""
whatsapp_service.py - Servicio para interactuar con WhatsApp Business Cloud API.
Permite el envío de mensajes de texto salientes a los usuarios utilizando la Graph API de Meta.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import WHATSAPP_API_TOKEN, WHATSAPP_PHONE_NUMBER_ID

logger = logging.getLogger(__name__)

META_GRAPH_URL_TEMPLATE = "https://graph.facebook.com/v18.0/{phone_number_id}/messages"


async def enviar_mensaje_whatsapp(to_phone: str, message_text: str) -> dict[str, Any]:
    """
    Envía un mensaje de texto saliente al número especificado a través de la WhatsApp Business Cloud API.
    
    :param to_phone: Número de teléfono receptor (ej. '+5493513110238' o '5493513110238').
    :param message_text: Contenido del mensaje de texto.
    :return: Diccionario con la respuesta de la API de Meta.
    """
    if not WHATSAPP_API_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        logger.warning(
            "WhatsApp API Token o Phone Number ID no configurados. Omitiendo envío a %s",
            to_phone,
        )
        return {"status": "skipped", "reason": "Missing WhatsApp API credentials"}

    url = META_GRAPH_URL_TEMPLATE.format(phone_number_id=WHATSAPP_PHONE_NUMBER_ID)

    # Limpiar el formato del número enviándolo como dígitos (Meta prefiere dígitos sin '+')
    recipient_phone = to_phone.replace("+", "").strip()

    headers = {
        "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_phone,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": message_text,
        },
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response_data = response.json()

            if response.status_code in (200, 201):
                logger.info("Mensaje enviado exitosamente a WhatsApp %s", recipient_phone)
                return response_data
            else:
                logger.error(
                    "Error al enviar mensaje a WhatsApp %s (HTTP %d): %s",
                    recipient_phone,
                    response.status_code,
                    response_data,
                )
                return response_data

        except httpx.HTTPError as exc:
            logger.error("Error de red/HTTP al contactar Meta Graph API: %s", exc)
            return {"status": "error", "message": str(exc)}
