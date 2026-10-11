"""
chats.py - Router asíncrono con FastAPI y Motor para consultar 'chat_histories' en MongoDB.

Endpoints:
  GET /api/chats               → Consulta la colección 'chat_histories' y devuelve la lista de sesiones (sessionId)
  GET /api/chats/{session_id}  → Busca el documento por sessionId y devuelve el arreglo History formateado:
                                 [ { "sender": "human" | "ai", "text": "contenido del mensaje" } ]
  GET /api/chats/status/ping   → Verifica la conexión con MongoDB Atlas
"""
from __future__ import annotations

import logging
from typing import List, Union, Dict, Any
from fastapi import APIRouter, HTTPException, status

from app.database import test_mongo_connection
from app.schemas.chat_schema import (
    ChatDetailResponse,
    ChatListResponse,
    ChatMessage,
    ChatSessionSummary,
)
from app.services.chat_service import (
    obtener_mensajes_sesion,
    obtener_todas_las_sesiones,
    obtener_lista_session_ids,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chats", tags=["Chats"])


@router.get(
    "/status/ping",
    summary="Verificar conexión con MongoDB Atlas",
    description="Ejecuta un comando ping asíncrono a MongoDB Atlas utilizando Motor.",
)
async def ping_mongodb() -> dict:
    """Verifica el estado de la conexión a MongoDB Atlas."""
    return await test_mongo_connection()


@router.get(
    "",
    summary="Listar todas las sesiones de chat (sessionId)",
    description=(
        "Consulta la colección 'chat_histories' en MongoDB y devuelve la lista de sesiones "
        "con sus respectivos sessionId y resumen de mensajes."
    ),
)
async def listar_chats() -> Any:
    """Devuelve la lista de clientes/contactos con sesiones de chat registradas en MongoDB."""
    try:
        sesiones = await obtener_todas_las_sesiones()
        return {
            "total": len(sesiones),
            "chats": [s.model_dump() for s in sesiones],
            "sessionIds": [s.sessionId for s in sesiones],
        }
    except ConnectionError as ce:
        logger.error("Error de conexión a MongoDB al listar chats: %s", ce)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Servicio de base de datos MongoDB no disponible: {ce}",
        )
    except Exception as exc:
        logger.error("Error inesperado al obtener sesiones de chat: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener sesiones de chat: {str(exc)}",
        )


@router.get(
    "/{session_id}",
    response_model=List[ChatMessage],
    summary="Obtener mensajes de una sesión formateados",
    description=(
        "Busca el documento que coincida con 'sessionId' en 'chat_histories' y devuelve "
        "el arreglo de mensajes History formateado como: [ { 'sender': 'human' | 'ai', 'text': string } ]"
    ),
)
async def obtener_chat_por_sesion(session_id: str) -> List[ChatMessage]:
    """
    Busca el documento que coincida con sessionId y devuelve el arreglo de mensajes
    History formateado como [ { "sender": "human" | "ai", "text": "contenido" } ].
    """
    if not session_id or not session_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El parámetro session_id es requerido.",
        )

    try:
        mensajes = await obtener_mensajes_sesion(session_id.strip())
        return mensajes
    except ConnectionError as ce:
        logger.error("Error de conexión a MongoDB al obtener chat '%s': %s", session_id, ce)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Servicio de base de datos MongoDB no disponible: {ce}",
        )
    except Exception as exc:
        logger.error("Error inesperado al obtener historial de '%s': %s", session_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener el historial de chat: {str(exc)}",
        )
