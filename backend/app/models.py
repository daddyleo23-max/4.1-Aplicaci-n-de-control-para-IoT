from pydantic import BaseModel, Field


class MovimientoRequest(BaseModel):
    id_comando: int = Field(
        gt=0,
        description="Identificador del comando que se desea ejecutar.",
        examples=[2],
    )
    id_comando_giro: int | None = Field(
        default=None, gt=0,
        description="Opcional: giro izquierdo/derecho simultáneo con ADELANTE o ATRAS. Requiere reserva y canal de control; no se admite en Invitado.",
    )

# Modelos CRUD para la API IoT
from pydantic import BaseModel, Field

class VehiculoCrearRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    modelo: str = Field(min_length=1, max_length=100)
    descripcion: str = Field(default="", max_length=500)
    microcontrolador: str = Field(min_length=1, max_length=100)

class VehiculoActualizarRequest(VehiculoCrearRequest):
    activo: bool = True

class ComandoCrearRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    codigo: int
    descripcion: str = Field(default="", max_length=500)

class ComandoActualizarRequest(ComandoCrearRequest):
    activo: bool = True

class DemoCrearRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    descripcion: str = Field(default="", max_length=500)

class DemoActualizarRequest(DemoCrearRequest):
    activo: bool = True

class MovimientoDemoCrearRequest(BaseModel):
    id_comando: int = Field(gt=0)
    orden: int = Field(gt=0)
    duracion_ms: int = Field(gt=0)
    pausa_ms: int = Field(ge=0, default=0)

class MovimientoDemoActualizarRequest(MovimientoDemoCrearRequest):
    pass
