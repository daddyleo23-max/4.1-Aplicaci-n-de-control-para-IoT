#!/usr/bin/env python3
"""Escucha los eventos WSS de un vehículo y los imprime como JSON legible."""

import argparse
import asyncio
import json

import websockets


DEFAULT_URL = "wss://34.194.45.28/ws/vehiculos/1"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Escucha eventos WebSocket publicados por la API IoT."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"URL WSS del vehículo (predeterminada: {DEFAULT_URL})",
    )
    return parser.parse_args()


async def listen(url):
    print(f"Conectando a {url} …")
    async with websockets.connect(
        url,
        ping_interval=None,
        open_timeout=10,
        close_timeout=5,
    ) as socket:
        print("Conectado. Esperando eventos; Ctrl+C para salir.\n")
        async for message in socket:
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                print(message)
                continue
            print(json.dumps(payload, indent=2, ensure_ascii=False), flush=True)


def main():
    args = parse_args()
    try:
        asyncio.run(listen(args.url))
    except KeyboardInterrupt:
        print("\nEscucha finalizada.")
    except (OSError, websockets.exceptions.WebSocketException) as error:
        raise SystemExit(f"No se pudo mantener la conexión WSS: {error}") from error


if __name__ == "__main__":
    main()
