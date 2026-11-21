
import asyncio
from fastapi import WebSocket
from starlette.websockets import WebSocketState


class WebSocketManager:

    def __init__(self):
        self.conexiones: dict[int, list[WebSocket]] = {}

    async def conectar(self, id_vehiculo: int, websocket: WebSocket):
        if websocket.application_state != WebSocketState.CONNECTED:
            await websocket.accept()

        if id_vehiculo not in self.conexiones:
            self.conexiones[id_vehiculo] = []

        self.conexiones[id_vehiculo].append(websocket)

    def desconectar(self, id_vehiculo: int, websocket: WebSocket):
        if id_vehiculo in self.conexiones:
            if websocket in self.conexiones[id_vehiculo]:
                self.conexiones[id_vehiculo].remove(websocket)

            if not self.conexiones[id_vehiculo]:
                del self.conexiones[id_vehiculo]

    async def enviar_a_vehiculo(self, id_vehiculo: int, mensaje: dict):
        conexiones = self.conexiones.get(id_vehiculo, []).copy()

        for websocket in conexiones:
            try:
                from app.resource_security import sessions_enabled, check_socket_access
                if sessions_enabled():
                    await asyncio.to_thread(
                        check_socket_access, websocket.state.session_token, id_vehiculo,
                    )
                await websocket.send_json(mensaje)
            except Exception:
                self.desconectar(id_vehiculo, websocket)
                try:
                    await websocket.close(code=1008)
                except Exception:
                    pass


manager = WebSocketManager()
