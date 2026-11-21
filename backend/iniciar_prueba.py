"""Arrancar el backend 4.3 en loopback y contra la copia aislada."""

import argparse
import os
from pathlib import Path
import re

from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--copia", required=True)
    parser.add_argument("--env", default="C:/practica_2_6_iot/.env")
    args = parser.parse_args()
    if not re.fullmatch(r"iot_prueba_\d{8}_\d{6}_\d{6}", args.copia):
        raise SystemExit("Indica la copia de prueba.")
    environment = Path(args.env).resolve(strict=True)
    load_dotenv(environment, override=False)
    os.environ["DB_NAME"] = args.copia
    os.environ["IOT_AUTH_MODE"] = "sesiones"
    import uvicorn

    print(f"FastAPI 4.3 de prueba. Base: {args.copia}")
    print("Swagger: http://127.0.0.1:8001/docs")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8001)


if __name__ == "__main__":
    main()
