"""Manda el mail del día, con la lista de destinatarios leída desde tu planilla.

La planilla vive en Drive y tiene cuatro columnas: nombre, mail, activo, notas.
Editás ahí y el próximo envío ya sale con la lista nueva, sin tocar código.
Cada mail sale personalizado con el nombre de la persona.

    python scripts/enviar_mail.py
    python scripts/enviar_mail.py --sin-audio
    python scripts/enviar_mail.py --prueba      # muestra a quién le mandaría, sin enviar
"""

from __future__ import annotations

import csv
import io
import smtplib
import ssl
import sys
import urllib.request
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from comun import DIR_AUDIO, cargar_config, log, morir, secreto

AFIRMATIVOS = {"si", "sí", "yes", "true", "1", "x"}


def enmascarar(mail: str) -> str:
    """Oculta la dirección en el log.

    Los registros de ejecución de un repositorio público los puede leer
    cualquiera, así que las direcciones nunca se imprimen enteras.
    """
    usuario, _, dominio = mail.partition("@")
    visible = usuario[:2] if len(usuario) > 3 else usuario[:1]
    return f"{visible}{'*' * 4}@{dominio}"


# --------------------------------------------------------------------------
def leer_suscriptores(url: str) -> list[dict]:
    """Lee la planilla publicada como CSV y devuelve solo los activos."""
    pedido = urllib.request.Request(url, headers={"User-Agent": "market-brief-bot/1.0"})
    with urllib.request.urlopen(pedido, timeout=60) as respuesta:
        crudo = respuesta.read().decode("utf-8-sig", errors="replace")

    lector = csv.DictReader(io.StringIO(crudo))
    if not lector.fieldnames:
        morir("La planilla vino vacía. Revisá que esté publicada como CSV.")

    columnas = {c.strip().lower(): c for c in lector.fieldnames}
    for requerida in ("nombre", "mail", "activo"):
        if requerida not in columnas:
            morir(f"A la planilla le falta la columna '{requerida}'. Tiene: {lector.fieldnames}")

    suscriptores: list[dict] = []
    for fila in lector:
        mail = (fila.get(columnas["mail"]) or "").strip()
        activo = (fila.get(columnas["activo"]) or "").strip().lower()
        nombre = (fila.get(columnas["nombre"]) or "").strip() or "there"
        if not mail or "@" not in mail:
            continue
        if activo not in AFIRMATIVOS:
            continue
        suscriptores.append({"nombre": nombre, "mail": mail})

    if not suscriptores:
        morir("No hay ningún suscriptor activo en la planilla.")
    return suscriptores


def ultimo_audio() -> Path | None:
    archivos = sorted(DIR_AUDIO.glob("*.mp3"), key=lambda p: p.stat().st_mtime)
    return archivos[-1] if archivos else None


def cuerpo_html(nombre: str, titulo: str, url: str, fecha: str, hay_audio: bool) -> str:
    linea_audio = (
        "<p style='margin:0 0 16px'>The audio version is attached to this email.</p>" if hay_audio else ""
    )
    return f"""\
<div style="font-family:system-ui,-apple-system,'Segoe UI',sans-serif;font-size:15px;line-height:1.6;color:#12120f;max-width:560px">
  <p style="margin:0 0 4px;font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:#86857e">{fecha}</p>
  <h1 style="margin:0 0 16px;font-size:22px;font-weight:600">{titulo}</h1>
  <p style="margin:0 0 16px">Hi {nombre},</p>
  <p style="margin:0 0 20px">Today's brief is ready. Tap below to open the full report with the board and the charts.</p>
  <p style="margin:0 0 20px">
    <a href="{url}" style="display:inline-block;background:#1c5cab;color:#ffffff;text-decoration:none;padding:11px 20px;border-radius:4px;font-weight:600">Open the report</a>
  </p>
  {linea_audio}
  <p style="margin:24px 0 0;font-size:12.5px;color:#86857e">Generated automatically. Analysis material, not investment advice.</p>
</div>"""


# --------------------------------------------------------------------------
def main() -> None:
    config = cargar_config()
    cfg_mail = config["mail"]

    prueba = "--prueba" in sys.argv
    suscriptores = leer_suscriptores(secreto("SUSCRIPTORES_CSV_URL"))
    log(f"Suscriptores activos: {len(suscriptores)}")
    for s in suscriptores:
        log(f"  {enmascarar(s['mail'])}")

    if prueba:
        log("Modo prueba: no mando nada.")
        return

    usuario = secreto("SMTP_USER")
    password = secreto("SMTP_PASSWORD")
    url_informe = secreto("INFORME_URL")

    adjunto = None
    if "--sin-audio" not in sys.argv and cfg_mail.get("adjuntar_audio", True):
        adjunto = ultimo_audio()
        if adjunto:
            limite = cfg_mail.get("tamano_max_adjunto_mb", 20)
            tamano = adjunto.stat().st_size / (1024 * 1024)
            if tamano > limite:
                log(f"El audio pesa {tamano:.1f} MB y supera el límite de {limite}. Va sin adjunto.")
                adjunto = None
        else:
            log("No hay MP3. El mail va solo con el link.")

    datos_audio = adjunto.read_bytes() if adjunto else None
    fecha = date.today().strftime("%Y-%m-%d")
    titulo = config["informe"]["titulo"]
    contexto = ssl.create_default_context()

    with smtplib.SMTP_SSL(cfg_mail["servidor_smtp"], cfg_mail["puerto_smtp"], context=contexto) as servidor:
        servidor.login(usuario, password)

        for s in suscriptores:
            mensaje = EmailMessage()
            mensaje["Subject"] = cfg_mail["asunto"].format(fecha=fecha)
            mensaje["From"] = usuario
            mensaje["To"] = s["mail"]
            mensaje.set_content(
                f"Hi {s['nombre']},\n\n{titulo} — {fecha}\n\nOpen the report: {url_informe}\n\n"
                "Generated automatically. Analysis material, not investment advice."
            )
            mensaje.add_alternative(
                cuerpo_html(s["nombre"], titulo, url_informe, fecha, datos_audio is not None),
                subtype="html",
            )
            if datos_audio:
                mensaje.add_attachment(datos_audio, maintype="audio", subtype="mpeg", filename=adjunto.name)

            servidor.send_message(mensaje)
            log(f"Enviado a {enmascarar(s['mail'])}")

    log(f"Listo: {len(suscriptores)} mails enviados")


if __name__ == "__main__":
    main()
