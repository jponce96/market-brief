"""Convierte el informe HTML en un PDF para adjuntar al mail.

Usa el Chrome que ya viene instalado en las máquinas de GitHub, así que no
hay nada que instalar. Si no encuentra ningún navegador, avisa y sigue sin
PDF: el mail igual sale con el HTML adjunto.

    python scripts/armar_pdf.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

from comun import DIR_DATOS, asegurar_carpetas, log

ARCHIVO_HTML = DIR_DATOS / "informe.html"
CANDIDATOS = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]


def buscar_navegador() -> str | None:
    for nombre in CANDIDATOS:
        ruta = shutil.which(nombre)
        if ruta:
            return ruta
    return None


def envolver(html: str) -> str:
    """El informe viene sin cabecera porque así lo publica la plataforma.

    Para imprimirlo hace falta un documento completo, con los fondos de color
    forzados: si no, Chrome imprime las tablas y los recuadros en blanco.
    """
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<style>
  :root {{ color-scheme: light; }}
  body {{ margin: 0; font: 14px system-ui, sans-serif; background: #f6f6f2; }}
  img {{ max-width: 100%; }}
  * {{ -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
  @page {{ size: A4; margin: 14mm 12mm; }}
  section, figure, .step {{ break-inside: avoid; }}
  h2 {{ break-after: avoid; }}
</style>
</head><body>{html}</body></html>"""


def main() -> None:
    asegurar_carpetas()

    if not ARCHIVO_HTML.exists():
        log("No hay informe para convertir. Salteo el PDF.")
        return

    navegador = buscar_navegador()
    if not navegador:
        log("No encontré Chrome ni Chromium. El mail va a ir solo con el HTML adjunto.")
        return

    destino = DIR_DATOS / f"market-brief-{date.today():%Y-%m-%d}.pdf"

    with tempfile.TemporaryDirectory() as tmp:
        fuente = Path(tmp) / "informe.html"
        fuente.write_text(envolver(ARCHIVO_HTML.read_text(encoding="utf-8")), encoding="utf-8")

        comando = [
            navegador,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--virtual-time-budget=10000",
            "--no-pdf-header-footer",
            f"--print-to-pdf={destino}",
            fuente.as_uri(),
        ]
        log("Generando el PDF")
        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=180)

    if not destino.exists() or destino.stat().st_size < 10_000:
        log(f"El PDF no salió bien, sigo sin él. Salida del navegador: {resultado.stderr[-400:]}")
        destino.unlink(missing_ok=True)
        return

    log(f"PDF listo: {destino.name} ({destino.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    try:
        main()
    except subprocess.TimeoutExpired:
        log("El navegador tardó demasiado. Sigo sin PDF.")
    sys.exit(0)
