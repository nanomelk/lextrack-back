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


# ---------------------------------------------------------------------------
# MongoDB Client (Motor AsyncIOMotorClient para n8n chat_histories)
# ---------------------------------------------------------------------------
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from app.config import MONGODB_URL, DATABASE_NAME, MONGODB_CHAT_COLLECTION

_motor_client: AsyncIOMotorClient | None = None


def get_motor_client() -> AsyncIOMotorClient:
    """Retorna una instancia singleton de AsyncIOMotorClient con timeouts configurados."""
    global _motor_client
    if _motor_client is None:
        if not MONGODB_URL:
            raise ValueError("MONGODB_URL no está configurada.")
        logger.info("🔌 Inicializando cliente Motor Async MongoDB: %s (DB: %s)", MONGODB_URL, DATABASE_NAME)
        _motor_client = AsyncIOMotorClient(
            MONGODB_URL,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )
    return _motor_client


def get_database() -> AsyncIOMotorDatabase:
    """Retorna la base de datos asíncrona de MongoDB (DATABASE_NAME)."""
    client = get_motor_client()
    return client[DATABASE_NAME]


def get_chat_collection() -> AsyncIOMotorCollection:
    """Retorna la colección asíncrona 'chat_histories' de n8n."""
    db = get_database()
    return db[MONGODB_CHAT_COLLECTION]


async def test_mongo_connection() -> dict:
    """Verifica y ejecuta un ping a MongoDB Atlas / servidor."""
    try:
        client = get_motor_client()
        # El comando ping valida la autenticación y conectividad
        ping_result = await client.admin.command('ping')
        logger.info("✅ Conexión a MongoDB exitosa: %s", ping_result)
        return {"status": "connected", "database": DATABASE_NAME, "ping": ping_result}
    except Exception as exc:
        logger.error("❌ Error de conexión a MongoDB: %s", exc)
        return {"status": "error", "database": DATABASE_NAME, "detail": str(exc)}


