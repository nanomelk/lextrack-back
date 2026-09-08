# LexTrack Backend

API REST construida con FastAPI para el Sistema de Gestión de Casos Jurídicos.

## Requisitos
- Python 3.11+
- Google Cloud Service Account (`credentials.json`)
- Google Sheets configurado

## Instalación local
```bash
python -m venv venv
# En Windows:
.\venv\Scripts\activate
# En Linux/Mac:
# source venv/bin/activate

pip install -r requirements.txt
```

## Configuración
Copia `.env.example` a `.env` y completa tus variables de entorno:
```bash
cp .env.example .env
```
Coloca tu archivo `credentials.json` en la raíz de este directorio.

## Ejecución
```bash
uvicorn app.main:app --reload --port 8000
```
Documentación interactiva disponible en: `http://localhost:8000/docs`
