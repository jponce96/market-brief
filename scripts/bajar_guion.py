"""Descarga el guion del día desde el documento de Google Drive.

El documento tiene que estar compartido como "cualquier persona con el
enlace puede ver". Su ID va en la variable GUION_DOC_ID, que en GitHub es
un Secret: así el enlace no queda escrito en el repositorio.

    python scripts/bajar_guion.py
"""

from __future__ import annotations

import sys
import urllib.request

from comun import ARCHIVO_GUION, asegurar_carpetas, log, morir, secreto

PLANTILLA_EXPORT = "https://docs.google.com/document/d/{doc_id}/export?format=txt"
MINIMO_PALABRAS = 200


def descargar(url: str) -> str:
    pedido = urllib.request.Request(url, headers={"User-Agent": "market-brief-bot/1.0"})
    with urllib.request.urlopen(pedido, timeout=60) as respuesta:
        if respuesta.status != 200:
            morir(f"El documento respondió {respuesta.status}. ¿Está compartido con enlace?")
        return respuesta.read().decode("utf-8", errors="replace")


def limpiar(texto: str) -> str:
    """Google mete un BOM y líneas en blanco de más al exportar."""
    texto = texto.replace("﻿", "").replace("\r\n", "\n")
    parrafos = [p.strip() for p in texto.split("\n") if p.strip()]
    return "\n\n".join(parrafos)


def main() -> None:
    asegurar_carpetas()
    doc_id = secreto("GUION_DOC_ID")
    url = PLANTILLA_EXPORT.format(doc_id=doc_id)

    log("Descargando el guion del día")
    texto = limpiar(descargar(url))

    palabras = len(texto.split())
    if palabras < MINIMO_PALABRAS:
        morir(
            f"El guion tiene solo {palabras} palabras. "
            "Probablemente todavía no se escribió la edición de hoy; no sigo."
        )

    ARCHIVO_GUION.write_text(texto, encoding="utf-8")
    log(f"Guion listo: {palabras} palabras (unos {palabras / 150:.0f} minutos de audio)")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as e:
        morir(f"No pude descargar el documento: {e}")
    except Exception as e:  # noqa: BLE001
        morir(str(e))
    sys.exit(0)
