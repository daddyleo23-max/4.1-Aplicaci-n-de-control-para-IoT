from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import pymysql

from app.database import get_connection
from app.routers.vehiculos import router as vehiculos_router
from app.routers.comandos import router as comandos_router
from app.routers.demos import router as demos_router
from app.routers import movimientos
from app.routers import websocket
from app.routers.autenticacion import router as autenticacion_router
from app.routers.administracion import router as administracion_router
from app.routers.cuenta import router as cuenta_router
from app.routers.editor_demos import router as editor_demos_router
from app.resource_security import authorize_resources


app = FastAPI(
    title="API para Vehículo IoT",
    description="API REST y WebSocket para controlar un vehículo IoT.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8080",
        "http://localhost:8080",
        "http://192.168.100.116:8081",
	"https://daddyleo23-max.github.io",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Content-Type", "X-API-Key", "Authorization"],
)


@app.get("/")
def inicio():
    return {
        "mensaje": "API para Vehículo IoT",
        "estado": "funcionando",
    }


app.include_router(vehiculos_router, dependencies=[Depends(authorize_resources)])
app.include_router(comandos_router, dependencies=[Depends(authorize_resources)])
app.include_router(demos_router, dependencies=[Depends(authorize_resources)])
app.include_router(movimientos.router, dependencies=[Depends(authorize_resources)])
app.include_router(websocket.router)
app.include_router(autenticacion_router)
app.include_router(administracion_router)
app.include_router(cuenta_router)
app.include_router(editor_demos_router)


@app.get("/health/db")
def comprobar_base_datos():
    try:
        connection = get_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT DATABASE() AS base_datos, "
                    "VERSION() AS version_mysql"
                )
                resultado = cursor.fetchone()

            return {
                "conectado": True,
                "base_datos": resultado["base_datos"],
                "version_mysql": resultado["version_mysql"],
            }
        finally:
            connection.close()

    except pymysql.MySQLError as error:
        print(f"Error de conexión MySQL: {error}")
        raise HTTPException(
            status_code=503,
            detail="No fue posible conectar con MySQL.",
        ) from error
