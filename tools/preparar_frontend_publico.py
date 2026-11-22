"""Genera ZIP público revisable; no publica ni modifica js/config.js original."""
import argparse
from pathlib import Path
from urllib.parse import urlsplit
import zipfile


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--api',required=True);args=parser.parse_args()
    url=urlsplit(args.api)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
        raise SystemExit('Indica sólo el origen HTTPS público de FastAPI, sin credenciales ni rutas.')
    if url.hostname in ('localhost','127.0.0.1','::1'):raise SystemExit('No uses loopback para la publicación.')
    origin=args.api.rstrip('/')
    root=Path(__file__).resolve().parents[1];target=root.parent/'frontend_4_3_publico.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        z.write(root/'index.html','index.html')
        for directory in ('assets','css','js'):
            for path in sorted((root/directory).rglob('*')):
                if not path.is_file() or path.name.endswith('.local.js'):continue
                name=path.relative_to(root).as_posix()
                if name=='js/config.js':
                    text=path.read_text().replace('sessionAuth: false','sessionAuth: true').replace('https://34.194.45.28',origin)
                    z.writestr(name,text)
                else:z.write(path,name)
    print('Paquete público preparado:',target)
    print('Pendiente: verificar API desplegada, publicar y validar HTTPS/WSS desde el sitio público.')

if __name__=='__main__':main()
