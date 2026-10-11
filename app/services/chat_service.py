"""
chat_service.py - Servicio asíncrono con Motor (AsyncIOMotorClient) para MongoDB.
Interactúa con la colección 'chat_histories' alimentada por n8n / LangChain.
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

from app.database import get_chat_collection
from app.schemas.chat_schema import ChatMessage, ChatSessionSummary

logger = logging.getLogger(__name__)


def _normalize_sender(raw_val: Any) -> str:
    """
    Normaliza el tipo o rol de emisor a 'human' o 'ai'.
    Soporta formatos estándar de n8n, LangChain, OpenAI y bots de mensajería.
    """
    if not raw_val:
        return "human"
    
    val_str = str(raw_val).strip().lower()
    if val_str in ("human", "user", "client", "cliente", "usuario", "humanmessage"):
        return "human"
    if val_str in ("ai", "bot", "assistant", "asistente", "system", "aimessage", "modelo"):
        return "ai"
    
    # Fallbacks por contenido de texto
    if "human" in val_str or "user" in val_str:
        return "human"
    if "ai" in val_str or "bot" in val_str or "assist" in val_str:
        return "ai"
    
    return "human"


def _extract_text_from_item(item: Any) -> str:
    """Extrae el contenido de texto de un mensaje proveniente de n8n/LangChain."""
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return str(item)

    # 1. Si viene con 'text'
    if "text" in item and item["text"] is not None:
        return str(item["text"])

    # 2. Formato LangChain n8n: { "data": { "content": "..." } }
    if "data" in item and isinstance(item["data"], dict):
        data_obj = item["data"]
        if "content" in data_obj and data_obj["content"] is not None:
            return str(data_obj["content"])
        if "text" in data_obj and data_obj["text"] is not None:
            return str(data_obj["text"])

    # 3. Formato OpenAI / Chat standard: { "content": "..." }
    if "content" in item and item["content"] is not None:
        return str(item["content"])

    # 4. Formato { "message": "..." }
    if "message" in item and item["message"] is not None:
        return str(item["message"])

    # 5. Formato { "body": "..." }
    if "body" in item and item["body"] is not None:
        return str(item["body"])

    return str(item)


def _extract_timestamp(item: Any) -> Optional[str]:
    """Extrae timestamp o fecha del mensaje si existe."""
    if not isinstance(item, dict):
        return None
    for key in ("timestamp", "created_at", "createdAt", "date", "fecha", "time"):
        if key in item and item[key]:
            return str(item[key])
    if "data" in item and isinstance(item["data"], dict):
        for key in ("timestamp", "created_at", "createdAt", "date", "fecha", "time"):
            if key in item["data"] and item["data"][key]:
                return str(item["data"][key])
    return None


def parse_chat_message(item: Any) -> ChatMessage:
    """Parsea y convierte cualquier estructura de mensaje n8n a ChatMessage estándar."""
    sender_raw = "human"
    if isinstance(item, dict):
        # Buscar sender en type, sender, role, id, o data.type
        sender_raw = (
            item.get("sender")
            or item.get("type")
            or item.get("role")
            or item.get("id")
            or (item.get("data", {}).get("type") if isinstance(item.get("data"), dict) else None)
            or (item.get("data", {}).get("role") if isinstance(item.get("data"), dict) else None)
            or "human"
        )
    
    sender_normalized = _normalize_sender(sender_raw)
    text_content = _extract_text_from_item(item)
    timestamp = _extract_timestamp(item)

    return ChatMessage(
        sender=sender_normalized,
        text=text_content,
        timestamp=timestamp,
    )


async def obtener_todas_las_sesiones() -> List[ChatSessionSummary]:
    """
    Busca todas las sesiones únicas en la colección 'chat_histories' de MongoDB
    usando Motor de forma asíncrona.
    """
    try:
        col = get_chat_collection()
    except Exception as exc:
        logger.error("Error al obtener colección de chats: %s", exc)
        raise exc

    try:
        cursor = col.find(
            {},
            {
                "sessionId": 1,
                "session_id": 1,
                "History": 1,
                "history": 1,
                "messages": 1,
                "updatedAt": 1,
                "createdAt": 1,
            },
        )
        docs = await cursor.to_list(length=1000)
    except ServerSelectionTimeoutError as sste:
        logger.error("Timeout de conexión a MongoDB: %s", sste)
        raise ConnectionError(f"No se pudo conectar a MongoDB. Verifica MONGODB_URL: {sste}") from sste
    except PyMongoError as pme:
        logger.error("Error de Motor/PyMongo al listar chats: %s", pme)
        raise pme

    sesiones_map: dict[str, dict[str, Any]] = {}

    for doc in docs:
        session_id = doc.get("sessionId") or doc.get("session_id")
        if not session_id:
            continue
        
        session_id_str = str(session_id).strip()
        if not session_id_str:
            continue

        raw_history = doc.get("History") or doc.get("history") or doc.get("messages") or []
        if isinstance(raw_history, dict):
            raw_history = [raw_history]
        elif not isinstance(raw_history, list):
            raw_history = []

        parsed_msgs = [parse_chat_message(m) for m in raw_history if m is not None]

        if session_id_str in sesiones_map:
            sesiones_map[session_id_str]["messages"].extend(parsed_msgs)
            if doc.get("updatedAt") or doc.get("createdAt"):
                sesiones_map[session_id_str]["updated_at"] = str(doc.get("updatedAt") or doc.get("createdAt"))
        else:
            sesiones_map[session_id_str] = {
                "sessionId": session_id_str,
                "messages": parsed_msgs,
                "updated_at": str(doc.get("updatedAt") or doc.get("createdAt") or "") if (doc.get("updatedAt") or doc.get("createdAt")) else None,
            }

    if not sesiones_map and docs:
        for doc in docs:
            session_id = doc.get("sessionId") or doc.get("session_id")
            if not session_id:
                continue
            session_id_str = str(session_id).strip()
            msg = parse_chat_message(doc)
            if session_id_str not in sesiones_map:
                sesiones_map[session_id_str] = {
                    "sessionId": session_id_str,
                    "messages": [msg],
                    "updated_at": str(doc.get("updatedAt") or doc.get("createdAt") or "") if (doc.get("updatedAt") or doc.get("createdAt")) else None,
                }
            else:
                sesiones_map[session_id_str]["messages"].append(msg)

    resultados: List[ChatSessionSummary] = []
    for s_id, data in sesiones_map.items():
        msgs = data["messages"]
        last_msg = msgs[-1] if msgs else None
        
        resultados.append(
            ChatSessionSummary(
                sessionId=s_id,
                last_message=last_msg.text if last_msg else None,
                last_sender=last_msg.sender if last_msg else None,
                total_messages=len(msgs),
                updated_at=data["updated_at"] or (last_msg.timestamp if last_msg else None),
            )
        )

    resultados.sort(key=lambda s: s.total_messages > 0, reverse=True)
    return resultados


async def obtener_lista_session_ids() -> List[str]:
    """Retorna directamente la lista de sessionIds únicos existentes."""
    try:
        col = get_chat_collection()
        distinct_ids = await col.distinct("sessionId")
        if not distinct_ids:
            distinct_ids = await col.distinct("session_id")
        return [str(s) for s in distinct_ids if s]
    except Exception as exc:
        logger.error("Error al obtener distinct sessionId: %s", exc)
        # Fallback a obtener todas las sesiones
        sesiones = await obtener_todas_las_sesiones()
        return [s.sessionId for s in sesiones]


async def obtener_mensajes_sesion(session_id: str) -> List[ChatMessage]:
    """
    Obtiene y formatea los mensajes del array 'History' para una sesión específica en MongoDB.
    Retorna lista de ChatMessage formateados como:
    [
      { "sender": "human" | "ai", "text": "contenido" }
    ]
    """
    try:
        col = get_chat_collection()
    except Exception as exc:
        logger.error("Error al conectar a MongoDB para session_id '%s': %s", session_id, exc)
        raise exc

    clean_id = str(session_id).strip()

    try:
        cursor = col.find(
            {
                "$or": [
                    {"sessionId": clean_id},
                    {"session_id": clean_id},
                    {"sessionId": {"$regex": f"^{clean_id}$", "$options": "i"}},
                ]
            }
        )
        docs = await cursor.to_list(length=500)
    except ServerSelectionTimeoutError as sste:
        logger.error("Timeout de conexión al buscar mensajes de '%s': %s", clean_id, sste)
        raise ConnectionError(f"No se pudo conectar a MongoDB: {sste}") from sste
    except PyMongoError as pme:
        logger.error("Error de Motor al consultar session '%s': %s", clean_id, pme)
        raise pme

    mensajes: List[ChatMessage] = []

    for doc in docs:
        raw_history = doc.get("History") or doc.get("history") or doc.get("messages")
        if raw_history is not None:
            if isinstance(raw_history, list):
                for item in raw_history:
                    if item is not None:
                        mensajes.append(parse_chat_message(item))
            elif isinstance(raw_history, dict):
                mensajes.append(parse_chat_message(raw_history))
        else:
            mensajes.append(parse_chat_message(doc))

    return mensajes
