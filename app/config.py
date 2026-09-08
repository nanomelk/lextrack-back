"""
config.py - Carga de variables de entorno para el Estudio Jurídico App.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Soportar GOOGLE_SHEETS_SPREADSHEET_ID con strip
GOOGLE_SHEETS_SPREADSHEET_ID: str = (
    os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "").strip()
)

# Soportar credenciales pasadas directamente como JSON string en variable de entorno
GOOGLE_CREDENTIALS_JSON: str = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()

# Soportar CREDENTIALS_FILE o GOOGLE_CREDENTIALS_PATH con fallback y strip
GOOGLE_CREDENTIALS_PATH: str = (
    os.getenv("CREDENTIALS_FILE")
    or os.getenv("GOOGLE_CREDENTIALS_PATH")
    or "credentials.json"
).strip()

_default_origins = "http://localhost:5173,http://localhost:3000,https://lextrack-liard.vercel.app"
CORS_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", _default_origins).split(",")
    if origin.strip()
]


# Nombre de la hoja dentro del Spreadsheet
SHEET_NAME_CASOS: str = os.getenv("SHEET_NAME_CASOS", "Casos").strip()
SHEET_NAME_INGESTA: str = os.getenv("SHEET_NAME_INGESTA", "Ingesta").strip()

# WhatsApp Business Cloud API Configuration
WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip()
WHATSAPP_API_TOKEN: str = os.getenv("WHATSAPP_API_TOKEN", "").strip()
WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()

