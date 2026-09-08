"""
database.py - Conexión con Google Sheets API usando gspread y Service Account.
Expone un cliente singleton thread-safe para ser utilizado en toda la aplicación.
"""
import json
import os
import gspread
from google.oauth2.service_account import Credentials
from app.config import (
    GOOGLE_CREDENTIALS_PATH,
    GOOGLE_CREDENTIALS_JSON,
    GOOGLE_SHEETS_SPREADSHEET_ID,
)

# Scopes necesarios para Sheets y Drive
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_client: gspread.Client | None = None
_spreadsheet: gspread.Spreadsheet | None = None


def get_client() -> gspread.Client:
    """Retorna un cliente gspread autenticado (singleton)."""
    global _client
    if _client is None:
        if GOOGLE_CREDENTIALS_JSON:
            try:
                creds_info = json.loads(GOOGLE_CREDENTIALS_JSON)
                creds = Credentials.from_service_account_info(
                    creds_info, scopes=SCOPES
                )
            except Exception as exc:
                raise ValueError(
                    f"Error al procesar la variable GOOGLE_CREDENTIALS_JSON: {exc}"
                ) from exc
        elif os.path.exists(GOOGLE_CREDENTIALS_PATH):
            creds = Credentials.from_service_account_file(
                GOOGLE_CREDENTIALS_PATH, scopes=SCOPES
            )
        else:
            raise FileNotFoundError(
                f"Archivo de credenciales no encontrado en la ruta: '{GOOGLE_CREDENTIALS_PATH}' "
                "y no se definió la variable GOOGLE_CREDENTIALS_JSON."
            )
        _client = gspread.authorize(creds)
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
