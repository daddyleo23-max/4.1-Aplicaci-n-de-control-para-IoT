"""Backend 4.3 dedicado: loopback8002, esquema definitivo y un solo worker."""
import argparse
import os
from pathlib import Path
from dotenv import load_dotenv


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env',default='C:/practica_2_6_iot/.env');args=parser.parse_args()
    root=Path(__file__).resolve().parent
    load_dotenv(Path(args.env).resolve(strict=True),override=True)
    os.environ['DB_NAME']='vehiculo_iot_43';os.environ['IOT_AUTH_MODE']='sesiones'
    import app
    if Path(app.__file__).resolve().parent!=root/'app':raise SystemExit('Se importó otra carpeta app; no se inicia el servidor.')
    from app.database import get_connection
    with get_connection() as db:
        with db.cursor() as c:
            c.execute('SELECT DATABASE() AS base_datos');name=c.fetchone()['base_datos']
            if name!='vehiculo_iot_43':raise SystemExit('El esquema configurado no es el destino definitivo.')
            c.callproc('sp_admin_resumen');summary=c.fetchall()
            while c.nextset():pass
            if not summary or 'unidades_prueba_libres' not in summary[0]:raise SystemExit('El esquema no tiene el resumen020 esperado.')
    print('Backend 4.3 · esquema vehiculo_iot_43 ·',root,flush=True)
    print('Swagger local: http://127.0.0.1:8002/docs · mantener esta terminal abierta.',flush=True)
    import uvicorn
    uvicorn.run('app.main:app',host='127.0.0.1',port=8002,workers=1,proxy_headers=True,forwarded_allow_ips='127.0.0.1')

if __name__=='__main__':main()
