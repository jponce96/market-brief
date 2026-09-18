"""Convierte el guion en un MP3: una sola voz, lectura literal.

Usa las voces neuronales de Microsoft (edge-tts). Ese servicio a veces
rechaza los pedidos que vienen de servidores en la nube, así que si falla
cae automáticamente a Piper, que corre offline con un modelo descargado y
no depende de ningún servicio externo.

    python scripts/generar_audio.py
    python scripts/generar_audio.py --motor piper
    python scripts/generar_audio.py --voces
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
import urllib.request
from datetime import date
from pathlib import Path

from comun import ARCHIVO_GUION, DIR_AUDIO, asegurar_carpetas, cargar_config, log, morir

LIMITE_CHUNK = 3000
BASE_PIPER = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
MODELO_PIPER = "en_US-lessac-medium.onnx"


# --------------------------------------------------------------------------
# preparación del texto
# --------------------------------------------------------------------------
def partir_en_chunks(texto: str, limite: int = LIMITE_CHUNK) -> list[str]:
    """Parte por párrafos, sin cortar oraciones al medio."""
    chunks: list[str] = []
    actual = ""
    for parrafo in texto.split("\n\n"):
        parrafo = parrafo.strip()
        if not parrafo:
            continue
        if len(actual) + len(parrafo) + 2 > limite and actual:
            chunks.append(actual)
            actual = parrafo
        else:
            actual = f"{actual}\n\n{parrafo}" if actual else parrafo
    if actual:
        chunks.append(actual)
    return chunks


# --------------------------------------------------------------------------
# motor 1: edge-tts
# --------------------------------------------------------------------------
async def _listar_voces() -> None:
    import edge_tts

    for v in sorted(await edge_tts.list_voices(), key=lambda x: x["ShortName"]):
        if v["Locale"].startswith("en-"):
            print(f'{v["ShortName"]:38} {v["Gender"]:8} {v["Locale"]}')


async def _sintetizar_edge(texto: str, destino: Path, voz: str, velocidad: str, volumen: str) -> None:
    import edge_tts

    chunks = partir_en_chunks(texto)
    log(f"edge-tts: {len(chunks)} bloques con la voz {voz}")
    with destino.open("wb") as salida:
        for i, chunk in enumerate(chunks, start=1):
            comunicador = edge_tts.Communicate(chunk, voz, rate=velocidad, volume=volumen)
            async for evento in comunicador.stream():
                if evento["type"] == "audio":
                    salida.write(evento["data"])
            log(f"  bloque {i}/{len(chunks)}")


# --------------------------------------------------------------------------
# motor 2: piper (offline, plan B)
# --------------------------------------------------------------------------
def _bajar_modelo_piper(carpeta: Path) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    modelo = carpeta / MODELO_PIPER
    config = carpeta / f"{MODELO_PIPER}.json"
    for destino, url in ((modelo, f"{BASE_PIPER}/{MODELO_PIPER}"), (config, f"{BASE_PIPER}/{MODELO_PIPER}.json")):
        if destino.exists():
            continue
        log(f"  bajando {destino.name}")
        urllib.request.urlretrieve(url, destino)
    return modelo


def _sintetizar_piper(texto: str, destino: Path) -> None:
    if shutil.which("piper") is None:
        morir("Piper no está instalado. Agregá piper-tts a requirements.txt.")
    if shutil.which("ffmpeg") is None:
        morir("Falta ffmpeg para pasar de wav a mp3.")

    modelo = _bajar_modelo_piper(DIR_AUDIO / "modelos")
    wav = destino.with_suffix(".wav")

    log("piper: sintetizando")
    subprocess.run(
        ["piper", "--model", str(modelo), "--output_file", str(wav)],
        input=texto.encode("utf-8"),
        check=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "96k", str(destino)],
        check=True,
    )
    wav.unlink(missing_ok=True)


# --------------------------------------------------------------------------
def main() -> None:
    if "--voces" in sys.argv:
        asyncio.run(_listar_voces())
        return

    asegurar_carpetas()
    config = cargar_config()
    audio_cfg = config["audio"]

    motor = "auto"
    if "--motor" in sys.argv:
        motor = sys.argv[sys.argv.index("--motor") + 1]

    origen = ARCHIVO_GUION
    for arg in sys.argv[1:]:
        if not arg.startswith("--") and arg not in ("edge", "piper", "auto"):
            origen = Path(arg).expanduser()
            break

    if not origen.exists():
        morir(f"No encontré el guion en {origen}")

    texto = origen.read_text(encoding="utf-8").strip()
    if not texto:
        morir("El guion está vacío")

    palabras = len(texto.split())
    log(f"Guion: {palabras} palabras (unos {palabras / 150:.1f} minutos)")

    destino = DIR_AUDIO / f"market-brief-{date.today():%Y-%m-%d}.mp3"

    if motor in ("auto", "edge"):
        try:
            asyncio.run(
                _sintetizar_edge(
                    texto,
                    destino,
                    voz=audio_cfg["voz"],
                    velocidad=audio_cfg["velocidad"],
                    volumen=audio_cfg.get("volumen", "+0%"),
                )
            )
        except Exception as e:  # noqa: BLE001
            if motor == "edge":
                morir(f"edge-tts falló: {e}")
            log(f"edge-tts falló ({e}). Paso a Piper.")
            destino.unlink(missing_ok=True)
            _sintetizar_piper(texto, destino)
    else:
        _sintetizar_piper(texto, destino)

    if not destino.exists() or destino.stat().st_size < 10_000:
        morir("El audio salió vacío o demasiado chico.")

    log(f"Audio listo: {destino} ({destino.stat().st_size / (1024 * 1024):.1f} MB)")


if __name__ == "__main__":
    main()
