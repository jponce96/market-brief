"""Configuración y utilidades compartidas.

Todo lo que es secreto (claves, IDs, URLs privadas) sale de variables de
entorno, nunca de config.json. Así el repositorio puede ser público sin
exponer nada: en GitHub esas variables vienen de los Secrets, y en tu PC
del archivo .env, que no se sube.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CONFIG_PATH = RAIZ / "config.json"
DIR_DATOS = RAIZ / "data"
DIR_AUDIO = RAIZ / "audio"

ARCHIVO_DATOS = DIR_DATOS / "market_data.json"
ARCHIVO_GUION = DIR_DATOS / "guion.txt"


def log(mensaje: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {mensaje}", flush=True)


def morir(mensaje: str) -> None:
    log(f"ERROR: {mensaje}")
    sys.exit(1)


def cargar_env() -> None:
    """Carga .env si existe. En GitHub Actions no hace falta: están los Secrets."""
    env_path = RAIZ / ".env"
    if not env_path.exists():
        return
    for linea in env_path.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def cargar_config() -> dict:
    if not CONFIG_PATH.exists():
        morir("No encontré config.json en la raíz del repositorio.")
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def secreto(nombre: str, obligatorio: bool = True) -> str | None:
    """Lee un valor sensible del entorno."""
    cargar_env()
    valor = os.environ.get(nombre, "").strip()
    if not valor and obligatorio:
        morir(
            f"Falta la variable {nombre}. "
            "En GitHub va en Settings > Secrets and variables > Actions; en tu PC, en el archivo .env."
        )
    return valor or None


def asegurar_carpetas() -> None:
    DIR_DATOS.mkdir(parents=True, exist_ok=True)
    DIR_AUDIO.mkdir(parents=True, exist_ok=True)
