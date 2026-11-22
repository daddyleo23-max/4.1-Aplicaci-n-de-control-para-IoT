"""Prueba HTTP/WSS pública en unidades nuevas de software, sin operar unidad1."""
import argparse
from urllib.parse import urlsplit
from gestionar_proxy_4_3 import api_check


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='https://34.194.45.28');args=parser.parse_args()
    origin=args.url.rstrip('/');url=urlsplit(origin)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.path or url.query or url.fragment:
        raise SystemExit('Indica el origen HTTPS público, sin rutas ni credenciales.')
    api_check(origin)
    import probar_admin_http
    probar_admin_http.BASE=origin
    import probar_cierre_4_3_http
    print('La prueba verificará REST/WS seguro a través de Caddy. No confirma movimiento físico.')
    probar_cierre_4_3_http.main()

if __name__=='__main__':main()
