"""
sheets_service.py - Capa de servicio para lectura/escritura en Google Sheets con manejo defensivo.

Columnas de la hoja "Casos" (RD-01) - 12 campos:
  0: id_caso | 1: caratula | 2: nro_expediente | 3: fuero
  4: fecha_vencimiento | 5: tipo_plazo | 6: estado_tramite
  7: link_evidencia | 8: nombre_cliente | 9: dni_cliente
  10: domicilio_cliente | 11: resumen_hecho
"""
from __future__ import annotations

import logging
from typing import Any

import gspread

from app.config import SHEET_NAME_CASOS
from app.database import get_worksheet
from app.schemas.caso_schema import CasoDB

logger = logging.getLogger(__name__)

# Encabezados esperados en la hoja – orden ESTRICTO de 12 campos (RD-01)
HEADERS_CASOS = [
    "id_caso",
    "caratula",
    "nro_expediente",
    "fuero",
    "fecha_vencimiento",
    "tipo_plazo",
    "estado_tramite",
    "link_evidencia",
    "nombre_cliente",
    "dni_cliente",
    "domicilio_cliente",
    "resumen_hecho",
]


def _ensure_headers(ws: gspread.Worksheet) -> None:
    """Crea la fila de encabezados si la hoja está vacía o no tiene el encabezado esperado."""
    try:
        first_row = ws.row_values(1)
    except Exception as exc:
        logger.warning("No se pudo leer la primera fila de la hoja '%s': %s", ws.title, exc)
        first_row = []

    if not first_row or first_row[0].strip() != "id_caso":
        ws.insert_row(HEADERS_CASOS, index=1)
        logger.info("Encabezados creados en la hoja '%s'.", ws.title)


def _generar_id_caso(ws: gspread.Worksheet) -> str:
    """Genera un id_caso secuencial basado en la cantidad de filas existentes."""
    try:
        all_values = ws.get_all_values()
        total_datos = max(0, len(all_values) - 1)
    except Exception:
        total_datos = 0
    numero = total_datos + 1
    return f"CASO-{numero:03d}"


def insertar_caso(caso: CasoDB) -> CasoDB:
    """
    Inserta una nueva fila en la hoja 'Casos' con los datos del caso (12 columnas).
    Retorna el objeto CasoDB con el id_caso asignado.
    """
    ws = get_worksheet(SHEET_NAME_CASOS)
    _ensure_headers(ws)

    # Si no tiene id, autogeneramos
    if not caso.id_caso:
        caso.id_caso = _generar_id_caso(ws)

    fila = [
        caso.id_caso or "",
        caso.caratula or "Sin Carátula",
        caso.nro_expediente or "PENDIENTE",
        caso.fuero or "Sin Asignar",
        caso.fecha_vencimiento or "",
        caso.tipo_plazo or "Sin Asignar",
        caso.estado_tramite or "Ingesta Recibida",
        caso.link_evidencia or "",
        caso.nombre_cliente or "",
        caso.dni_cliente or "",
        caso.domicilio_cliente or "",
        caso.resumen_hecho or "",
    ]

    ws.append_row(fila, value_input_option="USER_ENTERED")
    logger.info("Caso '%s' insertado correctamente.", caso.id_caso)
    return caso


def obtener_casos() -> list[dict[str, Any]]:
    """
    Lee todas las filas de la hoja 'Casos' de forma defensiva y las retorna
    como lista de diccionarios usando los 12 encabezados estándar.
    Si la hoja está vacía o solo contiene encabezados, retorna una lista vacía [].
    """
    ws = get_worksheet(SHEET_NAME_CASOS)
    _ensure_headers(ws)

    try:
        all_rows = ws.get_all_values()
    except Exception as exc:
        logger.error("Error al leer valores de la hoja '%s': %s", ws.title, exc)
        raise

    if not all_rows or len(all_rows) <= 1:
        logger.info("La hoja '%s' no contiene filas de datos.", ws.title)
        return []

    # Omitimos la fila 0 (encabezados) y procesamos cada fila
    records: list[dict[str, Any]] = []
    for row in all_rows[1:]:
        # Si la fila entera está en blanco, la omitimos
        if not any(str(cell).strip() for cell in row):
            continue

        # Rellenamos con cadenas vacías si la fila tiene menos de 12 columnas
        padded = [str(c).strip() if c is not None else "" for c in row]
        if len(padded) < 12:
            padded += [""] * (12 - len(padded))

        # Si el id_caso está vacío, omitimos la fila
        id_caso = padded[0]
        if not id_caso:
            continue

        record = {
            "id_caso": id_caso,
            "caratula": padded[1] or "Sin Carátula",
            "nro_expediente": padded[2] or "PENDIENTE",
            "fuero": padded[3] or "Sin Asignar",
            "fecha_vencimiento": padded[4] or "",
            "tipo_plazo": padded[5] or "Sin Asignar",
            "estado_tramite": padded[6] or "Ingesta Recibida",
            "link_evidencia": padded[7] or "",
            "nombre_cliente": padded[8] or "",
            "dni_cliente": padded[9] or "",
            "domicilio_cliente": padded[10] or "",
            "resumen_hecho": padded[11] or "",
        }
        records.append(record)

    logger.info("Se obtuvieron y sanitizaron %d casos desde Google Sheets.", len(records))
    return records


def actualizar_estado_caso(id_caso: str, nuevo_estado: str) -> bool:
    """
    Actualiza el campo estado_tramite de un caso existente.
    Retorna True si se actualizó, False si no se encontró.
    """
    ws = get_worksheet(SHEET_NAME_CASOS)
    try:
        cell = ws.find(id_caso, in_column=1)
    except gspread.exceptions.CellNotFound:
        logger.warning("Caso '%s' no encontrado para actualizar.", id_caso)
        return False

    col_estado = HEADERS_CASOS.index("estado_tramite") + 1
    ws.update_cell(cell.row, col_estado, nuevo_estado)
    logger.info("Estado del caso '%s' actualizado a '%s'.", id_caso, nuevo_estado)
    return True


def obtener_o_crear_hoja_por_telefono(phone_number: str) -> gspread.Worksheet:
    """
    Obtiene o crea automáticamente una pestaña (worksheet) nombrada con el número de teléfono.
    Garantiza que la Fila 1 tenga los 12 encabezados estándar.
    """
    sheet_name = str(phone_number).strip()
    ws = get_worksheet(sheet_name)
    _ensure_headers(ws)
    return ws


def insertar_caso_por_telefono(phone_number: str, caso: CasoDB) -> CasoDB:
    """
    Inserta un nuevo caso en la pestaña dinámica correspondiente al número de teléfono emisor
    y opcionalmente también en la pestaña principal de 'Casos'.
    """
    phone_ws = obtener_o_crear_hoja_por_telefono(phone_number)
    main_ws = get_worksheet(SHEET_NAME_CASOS)
    _ensure_headers(main_ws)

    # Si no tiene id, autogeneramos con el consecutivo global del spreadsheet
    if not caso.id_caso:
        caso.id_caso = _generar_id_caso(main_ws)

    fila = [
        caso.id_caso or "",
        caso.caratula or "Sin Carátula",
        caso.nro_expediente or "PENDIENTE",
        caso.fuero or "Sin Asignar",
        caso.fecha_vencimiento or "",
        caso.tipo_plazo or "Sin Asignar",
        caso.estado_tramite or "Ingesta Recibida",
        caso.link_evidencia or "",
        caso.nombre_cliente or "",
        caso.dni_cliente or "",
        caso.domicilio_cliente or "",
        caso.resumen_hecho or "",
    ]

    # Insertar en la pestaña del teléfono
    phone_ws.append_row(fila, value_input_option="USER_ENTERED")
    logger.info("Caso '%s' insertado en pestaña de teléfono '%s'.", caso.id_caso, phone_number)

    # Insertar también en la hoja general 'Casos' para consolidación
    try:
        main_ws.append_row(fila, value_input_option="USER_ENTERED")
        logger.info("Caso '%s' insertado en la hoja principal 'Casos'.", caso.id_caso)
    except Exception as exc:
        logger.warning("No se pudo replicar el caso '%s' en la hoja principal: %s", caso.id_caso, exc)

    return caso

