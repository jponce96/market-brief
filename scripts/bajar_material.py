"""Trae de Google Drive el material que escribió Claude esta mañana.

Cómo funciona: la carpeta de Drive está compartida como "cualquier persona
con el enlace puede ver". Drive publica de esas carpetas una página de
listado que se puede leer sin cuenta, y de ahí salen los nombres y los
identificadores de los archivos del día.

Se buscan dos archivos con la fecha en el nombre:

    informe-AAAA-MM-DD.html
    guion-AAAA-MM-DD.txt

Si los de hoy no están todavía, el script se detiene en lugar de mandar
material viejo.

    python scripts/bajar_material.py
    python scripts/bajar_material.py --listar     # muestra qué ve en la carpeta
"""

from __future__ import annotations

import html as html_lib
import re
import sys
import urllib.error
import urllib.request
from datetime import date

from comun import ARCHIVO_GUION, DIR_DATOS, asegurar_carpetas, log, morir, secreto

LISTADO = "https://drive.google.com/embeddedfolderview?id={folder_id}#list"
DESCARGA = "https://drive.google.com/uc?export=download&id={file_id}"
ARCHIVO_HTML = DIR_DATOS / "informe.html"

MINIMO_PALABRAS_GUION = 200
MINIMO_BYTES_INFORME = 2000
AGENTE = {"User-Agent": "Mozilla/5.0 (compatible; market-brief-bot/1.0)"}


def _pedir(url: str) -> bytes:
    pedido = urllib.request.Request(url, headers=AGENTE)
    try:
        with urllib.request.urlopen(pedido, timeout=60) as respuesta:
            return respuesta.read()
    except urllib.error.URLError as e:
        morir(f"No pude acceder a {url.split('?')[0]}: {e}")
    return b""


def listar_carpeta(folder_id: str) -> dict[str, str]:
    """Devuelve {nombre de archivo: identificador} de la carpeta compartida."""
    crudo = _pedir(LISTADO.format(folder_id=folder_id)).decode("utf-8", errors="replace")

    # Cada entrada del listado trae el id en el atributo y el nombre en el título.
    patron = re.compile(
        r'id="entry-([A-Za-z0-9_\-]{15,})".*?flip-entry-title"[^>]*>(.*?)</div>',
        re.DOTALL,
    )
    archivos = {html_lib.unescape(nombre.strip()): fid for fid, nombre in patron.findall(crudo)}

    if not archivos:
        morir(
            "La carpeta no devolvió ningún archivo. Casi siempre es que todavía no está "
            "compartida como 'cualquier persona con el enlace puede ver'."
        )
    return archivos


def buscar(archivos: dict[str, str], prefijo: str, extension: str) -> tuple[str, str] | None:
    hoy = f"{prefijo}-{date.today():%Y-%m-%d}{extension}"
    if hoy in archivos:
        return hoy, archivos[hoy]

    candidatos = sorted(n for n in archivos if n.startswith(prefijo) and n.endswith(extension))
    if candidatos:
        log(f"  no encontré {hoy}; el más reciente que hay es {candidatos[-1]}")
    return None


def main() -> None:
    asegurar_carpetas()
    archivos = listar_carpeta(secreto("DRIVE_FOLDER_ID"))
    log(f"La carpeta tiene {len(archivos)} archivos")

    if "--listar" in sys.argv:
        for nombre in sorted(archivos):
            log(f"  {nombre}")
        return

    # ---- guion ----------------------------------------------------------
    encontrado = buscar(archivos, "guion", ".txt")
    if not encontrado:
        morir("No está el guion de hoy. No sigo: prefiero no mandarte el episodio de ayer.")
    nombre, fid = encontrado
    texto = _pedir(DESCARGA.format(file_id=fid)).decode("utf-8-sig", errors="replace")
    palabras = len(texto.split())
    if palabras < MINIMO_PALABRAS_GUION:
        morir(f"El guion {nombre} tiene solo {palabras} palabras. Parece incompleto.")
    ARCHIVO_GUION.write_text(texto, encoding="utf-8")
    log(f"Guion: {nombre}, {palabras} palabras (unos {palabras / 150:.0f} minutos)")

    # ---- informe --------------------------------------------------------
    encontrado = buscar(archivos, "informe", ".html")
    if not encontrado:
        log("No está el informe de hoy. Sigo igual: el mail va con el link y el audio.")
        return
    nombre, fid = encontrado
    contenido = _pedir(DESCARGA.format(file_id=fid))
    if len(contenido) < MINIMO_BYTES_INFORME:
        log(f"El informe {nombre} pesa muy poco, no lo adjunto.")
        return
    ARCHIVO_HTML.write_bytes(contenido)
    log(f"Informe: {nombre}, {len(contenido) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
