# 🐍 Backend — Documentación Técnica

Documentación interna del backend FastAPI del sistema LexTrack.

---

## Módulos y Responsabilidades

### `app/main.py` — Entrypoint de la API

Punto de entrada de la aplicación FastAPI. Define la configuración global.

**Responsabilidades:**
- Instanciar la aplicación FastAPI con título, descripción y versión
- Registrar el middleware de CORS con los orígenes permitidos
- Registrar el middleware de logging de latencia HTTP
- Manejar el ciclo de vida (startup/shutdown) con `lifespan`
- Registrar los routers de `casos` e `ingesta`
- Exponer el endpoint `/health`

**Middlewares registrados:**

| Middleware | Propósito |
|---|---|
| `CORSMiddleware` | Permite solicitudes cross-origin desde el frontend |
| `log_requests` | Loguea método, ruta, código de respuesta y latencia en ms |

---

### `app/config.py` — Variables de Entorno

Carga el archivo `.env` al inicio y expone las configuraciones como constantes Python.

```python
GOOGLE_SHEETS_SPREADSHEET_ID  # ID del Spreadsheet destino
GOOGLE_CREDENTIALS_PATH       # Ruta al credentials.json
CORS_ORIGINS                  # Lista de orígenes CORS permitidos
SHEET_NAME_CASOS              # Nombre de la hoja (default: "Casos")
SHEET_NAME_INGESTA            # Nombre de hoja de ingesta (futuro)
```

---

### `app/database.py` — Conexión con Google Sheets

Implementa el patrón **Singleton** para reutilizar la conexión autenticada.

**Flujo de autenticación:**
```
credentials.json (Service Account)
        ↓
google.oauth2.service_account.Credentials
        ↓ (con scopes: Sheets + Drive)
gspread.authorize(creds)
        ↓
gspread.Client (singleton _client)
        ↓
spreadsheet.worksheet(nombre)  → gspread.Worksheet
```

**Funciones expuestas:**

```python
get_client() → gspread.Client
    # Retorna cliente autenticado (crea uno si no existe)

get_spreadsheet() → gspread.Spreadsheet
    # Retorna el spreadsheet principal (singleton)

get_worksheet(sheet_name: str) → gspread.Worksheet
    # Retorna hoja por nombre; la crea si no existe
```

**Scopes OAuth2 utilizados:**
- `https://www.googleapis.com/auth/spreadsheets` — Lectura/escritura en Sheets
- `https://www.googleapis.com/auth/drive` — Acceso a archivos de Drive

---

### `app/schemas/caso_schema.py` — Modelos de Datos

Define los modelos Pydantic v2 que validan los datos de entrada y salida.

#### `IngestaCreate` (RD-02)

```python
class IngestaCreate(BaseModel):
    nombre_completo: str          # Requerido
    dni: str                      # Requerido
    domicilio_real: str           # Requerido
    resumen_hecho: str            # Requerido
    link_evidencia_drive: Optional[str] = ""  # Opcional
```

#### `CasoDB` (RD-01)

```python
class CasoDB(BaseModel):
    id_caso: str                  # "CASO-001"
    caratula: str                 # Nombre del expediente
    nro_expediente: str           # Número judicial
    fuero: str                    # Civil, Laboral, etc.
    fecha_vencimiento: str        # "YYYY-MM-DD"
    tipo_plazo: str               # Perentorio, Ordinal
    estado_tramite: str           # Ver estados
    link_evidencia: str           # URL Drive
    nombre_cliente: Optional[str]
    dni_cliente: Optional[str]
    domicilio_cliente: Optional[str]
    resumen_hecho: Optional[str]
```

#### `CasoListResponse`

```python
class CasoListResponse(BaseModel):
    total: int
    casos: list[CasoDB]
```

---

### `app/services/sheets_service.py` — Lógica de Negocio Google Sheets

Capa de servicio que encapsula toda la lógica de acceso a Google Sheets.

#### Estructura de columnas (orden estricto)

```
A: id_caso         E: fecha_vencimiento    I: nombre_cliente
B: caratula        F: tipo_plazo           J: dni_cliente
C: nro_expediente  G: estado_tramite       K: domicilio_cliente
D: fuero           H: link_evidencia       L: resumen_hecho
```

#### Funciones

```python
_ensure_headers(ws: Worksheet) -> None
    """
    Verifica que la primera fila tenga los encabezados correctos.
    Si la hoja está vacía, los inserta automáticamente.
    Llamada internamente antes de cada operación de escritura/lectura.
    """

_generar_id_caso(ws: Worksheet) -> str
    """
    Genera un ID secuencial basado en el número de filas existentes.
    Formato: CASO-NNN (con padding de 3 dígitos).
    Ejemplo: CASO-001, CASO-042, CASO-100.
    """

insertar_caso(caso: CasoDB) -> CasoDB
    """
    Escribe una nueva fila al final de la hoja con los datos del caso.
    Usa value_input_option='USER_ENTERED' para respetar formatos.
    Retorna el objeto CasoDB con el id_caso final.
    """

obtener_casos() -> list[dict[str, Any]]
    """
    Lee todas las filas usando get_all_records() con expected_headers.
    Retorna lista de diccionarios [{columna: valor}, ...].
    Las filas vacías son excluidas automáticamente por gspread.
    """

actualizar_estado_caso(id_caso: str, nuevo_estado: str) -> bool
    """
    Busca la celda con el id_caso en la columna A.
    Actualiza la columna G (estado_tramite) de esa fila.
    Retorna True si encontró y actualizó, False si no encontró.
    """
```

---

### `app/routers/ingesta.py` — Router de Ingesta

#### `POST /api/v1/ingesta`

**Flujo interno:**
```python
1. Recibe IngestaCreate (RD-02) validado por Pydantic
2. Obtiene la worksheet actual para calcular el próximo ID
3. Llama a _generar_id_caso() → "CASO-NNN"
4. Construye CasoDB con valores predeterminados:
   - caratula = "{nombre_completo} s/ Sin Carátula Asignada"
   - nro_expediente = "PENDIENTE"
   - fuero = "Sin Asignar"
   - fecha_vencimiento = fecha de hoy (placeholder)
   - estado_tramite = "Ingesta Recibida"
5. Llama a insertar_caso(nuevo_caso)
6. Retorna el CasoDB creado con HTTP 201
```

---

### `app/routers/casos.py` — Router de Casos

#### `GET /api/v1/casos`
Llama a `obtener_casos()` y mapea los diccionarios a objetos `CasoDB`.
Filtra filas donde `id_caso` esté vacío (encabezado o fila vacía).

#### `GET /api/v1/casos/{id_caso}`
Itera sobre `obtener_casos()` y busca por `id_caso`. Lanza 404 si no encuentra.

#### `POST /api/v1/casos`
Llama directamente a `insertar_caso()` con el `CasoDB` recibido.

#### `PATCH /api/v1/casos/{id_caso}/estado`
Llama a `actualizar_estado_caso()`. Lanza 404 si retorna False.

---

## Manejo de Errores

Todos los routers usan el patrón:

```python
try:
    # lógica principal
except HTTPException:
    raise  # re-lanzar 404 etc.
except Exception as exc:
    logger.error("Error: %s", exc)
    raise HTTPException(
        status_code=500,
        detail=f"Error descriptivo: {str(exc)}"
    )
```

## Logging

El sistema usa `logging.basicConfig` con formato estructurado:

```
2026-08-30 10:15:23 | INFO     | app.main    | GET /api/v1/casos → 200 (45.3 ms)
2026-08-30 10:15:24 | INFO     | sheets_svc  | Se obtuvieron 12 casos desde Google Sheets.
```

---

## Dependencias Python

```
fastapi==0.111.0          # Framework web asíncrono
uvicorn[standard]==0.30.1 # Servidor ASGI con soporte WebSocket
gspread==6.1.2            # Cliente Google Sheets
google-auth==2.30.0       # Autenticación OAuth2 Google
google-auth-oauthlib==1.2.0 # OAuth2 flow helper
pydantic==2.7.4           # Validación de datos y modelos
python-dotenv==1.0.1      # Carga de archivos .env
python-multipart==0.0.9   # Soporte form-data (futuros uploads)
```

---

## Comandos Útiles

```bash
# Levantar en desarrollo con hot-reload
uvicorn app.main:app --reload --port 8000

# Levantar en producción (4 workers)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Verificar dependencias
pip list | findstr -i "fastapi gspread pydantic"

# Generar requirements actualizado
pip freeze > requirements.txt
```
