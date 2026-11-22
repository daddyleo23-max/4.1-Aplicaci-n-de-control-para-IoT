"""Consentimiento del comprador para diagnóstico o soporte operativo temporal."""
from fastapi import APIRouter, Depends, HTTPException, Path, Response
from pydantic import BaseModel, ConfigDict, Field
import pymysql
from app.session_security import require_session, require_admin
from app.resource_security import resource_context
from app.services.procedimiento_service import ProcedimientoService

router = APIRouter(tags=['Soporte autorizado 4.3'])
service = ProcedimientoService()


class Consent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id_administrador: int = Field(gt=0)
    minutos: int = Field(ge=1, le=30)
    operativo: bool = False


def owner(session, unit_id):
    unit = resource_context('vehiculo', unit_id)
    if session['rol'] != 'USUARIO' or not unit['activo'] or unit['id_propietario'] != session['id_usuario']:
        raise HTTPException(403, 'Sólo el comprador propietario puede autorizar o revocar soporte.')


def write(procedure, args):
    try:
        return service.ejecutar_consulta_transaccional(procedure, args)
    except pymysql.MySQLError as error:
        if error.args[0] == 1644:
            raise HTTPException(409, 'La asignación, el permiso o el administrador no son compatibles.') from error
        raise


@router.post('/vehiculos/{id_vehiculo}/soporte', status_code=201)
def grant(data: Consent, id_vehiculo: int = Path(gt=0), session: dict = Depends(require_session)):
    owner(session, id_vehiculo)
    rows = write('sp_soporte_conceder_operativo' if data.operativo else 'sp_soporte_conceder', (session['id_usuario'], id_vehiculo, data.id_administrador, data.minutos))
    return {**rows[0], 'alcance': 'OPERATIVO' if data.operativo else 'MONITOREO',
            'mensaje': 'Movimientos manuales mediante reserva exclusiva; sin acceso a demos privadas.' if data.operativo
                       else 'Diagnóstico autorizado; no permite enviar movimientos ni ejecutar demos.'}


@router.get('/vehiculos/{id_vehiculo}/soporte')
def list_permissions(id_vehiculo: int = Path(gt=0), session: dict = Depends(require_session)):
    owner(session, id_vehiculo)
    return {'permisos': service.ejecutar_consulta('sp_soporte_listar', (session['id_usuario'], id_vehiculo))}


@router.post('/vehiculos/{id_vehiculo}/soporte/{id_permiso}/revocar')
def revoke(id_vehiculo: int = Path(gt=0), id_permiso: int = Path(gt=0), session: dict = Depends(require_session)):
    owner(session, id_vehiculo)
    write('sp_soporte_revocar', (session['id_usuario'], id_vehiculo, id_permiso))
    return {'mensaje': 'Permiso revocado. REST y WSS vuelven a comprobar el consentimiento.'}


@router.get('/soporte/administradores')
def administrators(response: Response, session: dict = Depends(require_session)):
    if session['rol'] != 'USUARIO':
        raise HTTPException(403, 'Esta consulta corresponde al comprador que autoriza soporte.')
    response.headers['Cache-Control'] = 'no-store'
    return {'administradores': service.ejecutar_consulta('sp_soporte_destinatarios')}


@router.get('/admin/soporte')
def my_support(response: Response, session: dict = Depends(require_admin)):
    response.headers['Cache-Control'] = 'no-store'
    return {'permisos': service.ejecutar_consulta('sp_soporte_mis_permisos', (session['id_usuario'],))}
