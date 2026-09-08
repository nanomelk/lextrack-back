"""
ingesta.py - Router para recepción de payloads estructurados (RD-02).
Soporta ingestas desde formularios web o integraciones externas (WhatsApp).

POST /api/v1/ingesta  → Registra un nuevo caso a partir de datos mínimos.
"""
from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, status

from app.schemas.caso_schema import CasoDB, IngestaCreate
from app.services.sheets_service import insertar_caso, _generar_id_caso, get_worksheet
from app.config import SHEET_NAME_CASOS

router = APIRouter(prefix="/api/v1/ingesta", tags=["Ingesta"])
logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=CasoDB,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nueva ingesta de caso",
    description=(
        "Recibe un payload RD-02 con los datos mínimos del cliente "
        "y genera automáticamente una ficha de caso en Google Sheets."
    ),
)
async def crear_ingesta(payload: IngestaCreate) -> CasoDB:
    """
    Convierte una IngestaCreate (RD-02) en un CasoDB (RD-01) con valores
    predeterminados y lo persiste en Google Sheets.
    """
    try:
        # Generamos el id_caso usando la hoja actual
        ws = get_worksheet(SHEET_NAME_CASOS)
        id_caso = _generar_id_caso(ws)

        # Construimos la ficha del caso con valores iniciales
        nuevo_caso = CasoDB(
            id_caso=id_caso,
            caratula=f"{payload.nombre_completo} s/ Sin Carátula Asignada",
            nro_expediente="PENDIENTE",
            fuero="Sin Asignar",
            fecha_vencimiento=date.today().isoformat(),   # Placeholder – debe completarse
            tipo_plazo="Sin Asignar",
            estado_tramite="Ingesta Recibida",
            link_evidencia=payload.link_evidencia_drive or "",
            nombre_cliente=payload.nombre_completo,
            dni_cliente=payload.dni,
            domicilio_cliente=payload.domicilio_real,
            resumen_hecho=payload.resumen_hecho,
        )

        caso_guardado = insertar_caso(nuevo_caso)
        logger.info("Ingesta procesada: %s → %s", payload.nombre_completo, id_caso)
        return caso_guardado

    except Exception as exc:
        logger.error("Error al procesar ingesta: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al registrar la ingesta: {str(exc) or type(exc).__name__}",
        ) from exc
