"""Reserva exclusiva del comprador. El canal de monitoreo continúa separado."""
import asyncio
from contextlib import suppress
import logging
from fastapi import APIRouter, Depends, HTTPException, Path, Response, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.security import HTTPAuthorizationCredentials
from app.session_security import require_session
from app.resource_security import sessions_enabled, resource_context, check_unit_access
from app.services.control_service import control_service
from app.services.websocket_manager import manager

router = APIRouter(tags=['Control exclusivo del comprador 4.3'])
logger = logging.getLogger(__name__)


def enabled():
    if not sessions_enabled():
        raise HTTPException(503,'Las reservas requieren el modo de sesiones.')


@router.get('/vehiculos/{id_vehiculo}/control', dependencies=[Depends(enabled)])
async def status(response: Response, id_vehiculo: int = Path(gt=0), session: dict = Depends(require_session)):
    response.headers['Cache-Control']='no-store'
    unit = await asyncio.to_thread(resource_context,'vehiculo',id_vehiculo)
    check_unit_access(session,unit)
    rows = await control_service.db('sp_control_reservas')
    row = next((r for r in rows if r['id_vehiculo']==id_vehiculo),None)
    own = bool(row and row['id_sesion']==session['id_sesion'])
    return {'reservada':row is not None,'propia':own,
            'id_control':row['id_control'] if own else None,
            'estado':row['estado'] if row else None}


@router.post('/vehiculos/{id_vehiculo}/control/reservar', status_code=201, dependencies=[Depends(enabled)])
async def reserve(response: Response, id_vehiculo: int = Path(gt=0), session: dict = Depends(require_session)):
    response.headers['Cache-Control']='no-store'
    unit = await asyncio.to_thread(resource_context,'vehiculo',id_vehiculo)
    check_unit_access(session,unit)
    return await control_service.reserve(session,id_vehiculo)


@router.post('/control/{id_control}/cerrar', dependencies=[Depends(enabled)])
async def close(id_control: int = Path(gt=0), session: dict = Depends(require_session)):
    await control_service.context(id_control,session,active=False)
    await control_service.close(id_control,'CANCELADA')
    return {'mensaje':'Reserva cerrada después de procesar la solicitud DETENER.', 'parada_solicitada':True}


@router.websocket('/ws/control/{id_control}')
async def control_socket(websocket: WebSocket, id_control: int):
    attached = False
    unit = None
    try:
        enabled()
        await websocket.accept()
        message = await asyncio.wait_for(websocket.receive_json(),timeout=10)
        if not isinstance(message,dict) or message.get('tipo')!='autenticar':
            raise HTTPException(401,'Autenticación requerida.')
        token = message.get('token')
        if not isinstance(token,str) or not 20<=len(token)<=200:
            raise HTTPException(401,'Token inválido.')
        credentials = HTTPAuthorizationCredentials(scheme='Bearer',credentials=token)
        session = await asyncio.to_thread(require_session,credentials)
        row = await control_service.context(id_control,session)
        unit = row['id_vehiculo']
        if id_control in control_service.sockets:
            raise HTTPException(409,'La reserva ya tiene un canal de control.')
        control_service.sockets[id_control]=websocket
        control_service.awaiting.pop(id_control,None)
        attached = True
        websocket.state.session_token=token
        websocket.state.auth_kind='control'
        websocket.state.control_id=id_control
        websocket.state.account_session=session
        await manager.conectar(unit,websocket)
        await websocket.send_json(jsonable_encoder({'tipo':'control_autorizado',**row}))
        while True:
            await asyncio.to_thread(require_session,credentials)
            await control_service.context(id_control,session)
            try:
                message = await asyncio.wait_for(websocket.receive_json(),timeout=1)
            except asyncio.TimeoutError:
                continue
            if isinstance(message,dict) and message.get('tipo')=='renovar':
                result = await control_service.db('sp_control_renovar',(id_control,session['id_sesion'],unit),True)
                await websocket.send_json(jsonable_encoder({'tipo':'control_renovado',**result[0]}))
    except WebSocketDisconnect:
        pass
    except (HTTPException,ValueError,asyncio.TimeoutError):
        with suppress(Exception):
            await websocket.close(code=1008)
    except Exception:
        with suppress(Exception):
            await websocket.close(code=1011)
    finally:
        if attached:
            manager.desconectar(unit,websocket)
            if control_service.sockets.get(id_control) is websocket:
                control_service.sockets.pop(id_control,None)
            try:
                await control_service.close(id_control,'DESCONECTADA')
            except Exception:
                logger.warning('La reserva desconectada queda pendiente de parada y recuperación.')
