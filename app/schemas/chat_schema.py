"""
chat_schema.py - Esquemas Pydantic para el módulo de Visualización de Chats.
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Representa un mensaje individual en una sesión de chat."""
    sender: Literal["human", "ai"] = Field(
        ...,
        description="Emisor del mensaje: 'human' (cliente) o 'ai' (asistente virtual)",
        examples=["human", "ai"],
    )
    text: str = Field(
        ...,
        description="Contenido textual del mensaje",
        examples=["Hola, quisiera consultar sobre un expediente.", "¡Hola! Con gusto te asesoro."],
    )
    timestamp: Optional[str] = Field(
        default=None,
        description="Marca temporal del mensaje si está disponible en el historial",
    )


class ChatSessionSummary(BaseModel):
    """Resumen de una sesión / contacto para el panel lateral."""
    sessionId: str = Field(
        ...,
        description="Identificador único de la sesión (número de teléfono o ID de cliente)",
    )
    last_message: Optional[str] = Field(
        default=None,
        description="Último mensaje intercambiado en la conversación",
    )
    last_sender: Optional[Literal["human", "ai"]] = Field(
        default=None,
        description="Emisor del último mensaje",
    )
    total_messages: int = Field(
        default=0,
        description="Cantidad total de mensajes en el historial",
    )
    updated_at: Optional[str] = Field(
        default=None,
        description="Fecha o timestamp del último mensaje registrado",
    )


class ChatListResponse(BaseModel):
    """Respuesta para el endpoint GET /api/chats."""
    total: int = Field(..., description="Cantidad total de sesiones/contactos encontrados")
    chats: list[ChatSessionSummary] = Field(
        ...,
        description="Listado de contactos/sesiones con su respectivo resumen",
    )


class ChatDetailResponse(BaseModel):
    """Respuesta para el endpoint GET /api/chats/{session_id}."""
    sessionId: str = Field(..., description="Identificador único de la sesión")
    total: int = Field(..., description="Cantidad total de mensajes en la sesión")
    messages: list[ChatMessage] = Field(
        ...,
        description="Lista ordenada de mensajes en el array History formateados como sender y text",
    )
