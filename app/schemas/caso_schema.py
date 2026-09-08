"""
caso_schema.py - Modelos Pydantic para el Estudio Jurídico App.

RD-02: IngestaCreate  → Datos mínimos recibidos por WhatsApp/Formulario
RD-01: CasoDB         → Ficha completa del expediente procesal
"""
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# RD-02 – Datos Mínimos de Ingesta
# ---------------------------------------------------------------------------
class IngestaCreate(BaseModel):
    """Payload de ingesta recibido desde formulario web o WhatsApp."""
    nombre_completo: str = Field(..., description="Nombre y apellido del cliente")
    dni: str = Field(..., description="DNI / documento de identidad")
    domicilio_real: str = Field(..., description="Domicilio real del cliente")
    resumen_hecho: str = Field(..., description="Descripción breve del hecho/caso")
    link_evidencia_drive: Optional[str] = Field(
        default="", description="URL de Google Drive con evidencias adjuntas"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "nombre_completo": "Juan Carlos Pérez",
                "dni": "28456789",
                "domicilio_real": "Av. Corrientes 1234, CABA",
                "resumen_hecho": "Accidente de tránsito el 15/08/2026 en Av. 9 de Julio.",
                "link_evidencia_drive": "https://drive.google.com/drive/folders/XXXXX"
            }
        }


# ---------------------------------------------------------------------------
# RD-01 – Ficha Completa del Caso (lectura/escritura en Sheets)
# ---------------------------------------------------------------------------
class CasoDB(BaseModel):
    """Ficha completa del expediente procesal almacenada en Google Sheets (12 columnas)."""
    id_caso: str = Field(default="", description="Identificador único (Ej: CASO-001)")
    caratula: str = Field(default="Sin Carátula", description="Carátula del expediente")
    nro_expediente: str = Field(default="PENDIENTE", description="Número de expediente judicial")
    fuero: str = Field(default="Sin Asignar", description="Fuero: Civil, Laboral, Familia, Penal...")
    fecha_vencimiento: Optional[str] = Field(default="", description="Fecha de vencimiento ISO (YYYY-MM-DD)")
    tipo_plazo: str = Field(default="Sin Asignar", description="Tipo de plazo: Perentorio, Ordinal")
    estado_tramite: str = Field(
        default="Ingesta Recibida",
        description="Estado: Ingesta Recibida, Pendiente Documentación, En Revisión, Ficha Completada"
    )
    link_evidencia: Optional[str] = Field(default="", description="URL de evidencia en Google Drive")
    nombre_cliente: Optional[str] = Field(default="", description="Nombre del cliente")
    dni_cliente: Optional[str] = Field(default="", description="DNI del cliente")
    domicilio_cliente: Optional[str] = Field(default="", description="Domicilio del cliente")
    resumen_hecho: Optional[str] = Field(default="", description="Resumen del hecho")

    class Config:
        json_schema_extra = {
            "example": {
                "id_caso": "CASO-001",
                "caratula": "Pérez Juan c/ Transportes Rápidos S.A.",
                "nro_expediente": "12345/2026",
                "fuero": "Civil",
                "fecha_vencimiento": "2026-09-05",
                "tipo_plazo": "Perentorio",
                "estado_tramite": "Ingesta Recibida",
                "link_evidencia": "https://drive.google.com/drive/folders/XXXXX",
                "nombre_cliente": "Juan Carlos Pérez",
                "dni_cliente": "28456789",
                "domicilio_cliente": "Av. Corrientes 1234, CABA",
                "resumen_hecho": "Accidente de tránsito el 15/08/2026."
            }
        }


# ---------------------------------------------------------------------------
# Respuesta paginada / listado
# ---------------------------------------------------------------------------
class CasoListResponse(BaseModel):
    total: int = 0
    casos: list[CasoDB] = Field(default_factory=list)
