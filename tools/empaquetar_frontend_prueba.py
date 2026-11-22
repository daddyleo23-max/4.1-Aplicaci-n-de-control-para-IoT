"""Empaqueta el frontend aislado sin credenciales ni archivos del backend."""
from pathlib import Path
import zipfile


def main():
    source = Path(__file__).resolve().parents[1]
    target = source.parent / "frontend_4_3_prueba.zip"
    launcher = '''from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from pathlib import Path

if __name__ == "__main__":
    handler = partial(SimpleHTTPRequestHandler, directory=str(Path(__file__).resolve().parent))
    print("Frontend de prueba: http://127.0.0.1:8080/#cuenta", flush=True)
    print("Mantén el backend de prueba activo en el puerto 8001.", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8080), handler).serve_forever()
'''
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(source / "index.html", "index.html")
        for directory in ("assets", "css", "js"):
            for path in sorted((source / directory).rglob("*")):
                if not path.is_file() or path.name.endswith(".local.js"):
                    continue
                name = path.relative_to(source).as_posix()
                if name == "js/config.js":
                    config = path.read_text().replace("sessionAuth: false", "sessionAuth: true")
                    config = config.replace("https://34.194.45.28", "http://127.0.0.1:8001")
                    archive.writestr(name, config)
                else:
                    archive.write(path, name)
        archive.writestr("iniciar_frontend.py", launcher)
    print(target)


if __name__ == "__main__":
    main()
