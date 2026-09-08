"""
database.py - Conexión con Google Sheets API usando gspread y Service Account.
Expone un cliente singleton thread-safe para ser utilizado en toda la aplicación.
"""
import json
import logging
import os
import gspread
from google.oauth2.service_account import Credentials
from app.config import (
    GOOGLE_CREDENTIALS_PATH,
    GOOGLE_CREDENTIALS_JSON,
    GOOGLE_SHEETS_SPREADSHEET_ID,
)

logger = logging.getLogger(__name__)

# Scopes necesarios para Sheets y Drive
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_client: gspread.Client | None = None
_spreadsheet: gspread.Spreadsheet | None = None


def _buscar_archivo_credenciales() -> str | None:
    """Busca el archivo de credenciales en múltiples rutas estándar (incluyendo Render)."""
    candidatos = [
        GOOGLE_CREDENTIALS_PATH,
        "/etc/secrets/credentials.json",
        "/etc/secrets/credentials",
        os.path.join(os.getcwd(), "credentials.json"),
        os.path.join(os.path.dirname(__file__), "..", "credentials.json"),
        os.path.join(os.path.dirname(__file__), "..", "..", "credentials.json"),
        "credentials.json",
    ]
    for ruta in candidatos:
        if ruta and os.path.isfile(ruta):
            return os.path.abspath(ruta)
    return None


def get_client() -> gspread.Client:
    """Retorna un cliente gspread autenticado (singleton)."""
    global _client
    if _client is None:
        if GOOGLE_CREDENTIALS_JSON:
            try:
                logger.info("🔑 Cargando credenciales desde la variable GOOGLE_CREDENTIALS_JSON...")
                creds_info = json.loads(GOOGLE_CREDENTIALS_JSON)
                creds = Credentials.from_service_account_info(
                    creds_info, scopes=SCOPES
                )
            except Exception as exc:
                raise ValueError(
                    f"Error al procesar la variable GOOGLE_CREDENTIALS_JSON: {exc}"
                ) from exc
        else:
            archivo_encontrado = _buscar_archivo_credenciales()
            if archivo_encontrado:
                logger.info("🔑 Cargando credenciales desde archivo: %s", archivo_encontrado)
                creds = Credentials.from_service_account_file(
                    archivo_encontrado, scopes=SCOPES
                )
            else:
                raise FileNotFoundError(
                    f"Archivo de credenciales no encontrado. Se buscó en: '{GOOGLE_CREDENTIALS_PATH}', "
                    "'/etc/secrets/credentials.json' y 'credentials.json'. "
                    "Configura la variable CREDENTIALS_FILE=/etc/secrets/credentials.json o GOOGLE_CREDENTIALS_JSON en Render."
                )
        _client = gspread.authorize(creds)
        logger.info("✅ Cliente Google Sheets autenticado exitosamente.")
    return _client





def get_spreadsheet() -> gspread.Spreadsheet:
    """Retorna el Spreadsheet principal (singleton)."""
    global _spreadsheet
    if _spreadsheet is None:
        if not GOOGLE_SHEETS_SPREADSHEET_ID:
            raise ValueError(
                "La variable de entorno GOOGLE_SHEETS_SPREADSHEET_ID está vacía o no definida."
            )
        client = get_client()
        _spreadsheet = client.open_by_key(GOOGLE_SHEETS_SPREADSHEET_ID)
    return _spreadsheet


def get_worksheet(sheet_name: str) -> gspread.Worksheet:
    """Retorna una hoja específica por nombre, creándola si no existe."""
    spreadsheet = get_spreadsheet()
    try:
        return spreadsheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
