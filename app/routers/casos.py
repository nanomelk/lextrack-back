"""
casos.py - Router CRUD para la gestión de expedientes/casos (RD-01).

GET    /api/v1/casos           → Lista todos los casos
GET    /api/v1/casos/{id_caso} → Obtiene un caso por ID
POST   /api/v1/casos           → Crea un caso manualmente
PATCH  /api/v1/casos/{id_caso}/estado → Actualiza el estado del trámite
"""
from __future__ import annotations

import logging
from typing import Any

import gspread.exceptions
from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError

from app.schemas.caso_schema import CasoListResponse, CasoDB
from app.services.sheets_service import (
    actualizar_estado_caso,
    insertar_caso,
    obtener_casos,
)

router = APIRouter(prefix="/api/v1/casos", tags=["Casos"])
logger = logging.getLogger(__name__)


def _handle_sheets_exception(exc: Exception, operation: str) -> HTTPException:
    """Mapea excepciones de Google Sheets, Pydantic y sistema a HTTPExceptions claras."""
    logger.error("Error en operación '%s': %s", operation, exc, exc_info=True)

    if isinstance(exc, gspread.exceptions.SpreadsheetNotFound):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró la planilla de Google Sheets especificada. Verifica GOOGLE_SHEETS_SPREADSHEET_ID: {exc}",
        )
    if isinstance(exc, gspread.exceptions.WorksheetNotFound):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró la hoja dentro del Spreadsheet: {exc}",
        )
    if isinstance(exc, FileNotFoundError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error de configuración: {exc}",
        )
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Error de validación de datos (Pydantic): {exc.errors()}",
        )
    if isinstance(exc, gspread.exceptions.APIError):
        # Extraer detalle de respuesta de Google si existe
        error_msg = str(exc)
        if hasattr(exc, "response") and exc.response is not None:
            try:
                error_msg = exc.response.text
            except Exception:
                pass
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error de Google Sheets API: {error_msg}",
        )
    if isinstance(exc, PermissionError):
        cause = getattr(exc, "__cause__", None)
        cause_detail = f" Detalle técnico: {cause}" if cause else ""
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Error de permisos o API no habilitada al acceder a Google Sheets. Asegúrate de habilitar 'Google Sheets API' y 'Google Drive API' en Google Cloud Console, y compartir la planilla con la Service Account.{cause_detail}",
        )
    if isinstance(exc, ValueError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Valor inválido de configuración: {exc}",
        )

    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Error interno del servidor durante '{operation}': {str(exc) or type(exc).__name__}",
    )


@router.get(
    "",
    response_model=CasoListResponse,
    summary="Listar todos los casos",
)
async def listar_casos() -> CasoListResponse:
    """Retorna todos los expedientes almacenados en Google Sheets."""
    try:
        casos_raw: list[dict[str, Any]] = obtener_casos()
        casos: list[CasoDB] = []
        for row in casos_raw:
            try:
                casos.append(CasoDB(**row))
            except ValidationError as val_err:
                logger.warning("Fila descartada por fallo de validación: %s | Error: %s", row, val_err)
                continue

        return CasoListResponse(total=len(casos), casos=casos)
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle_sheets_exception(exc, "listar_casos") from exc


@router.get(
    "/{id_caso}",
    response_model=CasoDB,
    summary="Obtener caso por ID",
)
async def obtener_caso(id_caso: str) -> CasoDB:
    """Busca y retorna un caso específico por su ID."""
    try:
        casos_raw = obtener_casos()
        for row in casos_raw:
            if row.get("id_caso") == id_caso:
                return CasoDB(**row)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Caso '{id_caso}' no encontrado.",
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle_sheets_exception(exc, f"obtener_caso({id_caso})") from exc


@router.post(
    "",
    response_model=CasoDB,
    status_code=status.HTTP_201_CREATED,
    summary="Crear caso manualmente (ficha completa)",
)
async def crear_caso(caso: CasoDB) -> CasoDB:
    """Inserta una ficha completa RD-01 directamente en Google Sheets."""
    try:
        return insertar_caso(caso)
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle_sheets_exception(exc, "crear_caso") from exc


@router.patch(
    "/{id_caso}/estado",
    summary="Actualizar estado del trámite",
)
async def actualizar_estado(id_caso: str, nuevo_estado: str) -> dict[str, str]:
    """Actualiza el campo estado_tramite de un caso existente."""
    try:
        actualizado = actualizar_estado_caso(id_caso, nuevo_estado)
        if not actualizado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Caso '{id_caso}' no encontrado.",
            )
        return {
            "id_caso": id_caso,
            "estado_tramite": nuevo_estado,
            "mensaje": "Estado actualizado correctamente",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle_sheets_exception(exc, f"actualizar_estado({id_caso})") from exc
