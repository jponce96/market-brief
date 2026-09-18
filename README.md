# Market Brief — automatización

Todo corre en los servidores de GitHub, gratis y sin depender de que tu computadora esté prendida. Tu máquina queda solamente como lugar para editar el código si querés cambiar algo.

## Cómo funciona

```
06:15 ART   GitHub Actions   baja cierres con yfinance y los guarda en data/market_data.json
07:00 ART   Claude           lee esos datos, investiga, publica el informe y escribe el guion en Drive
07:20 ART   GitHub Actions   baja el guion, genera el MP3 y manda los mails
```

Las tres piezas se comunican por archivos, no por conexiones directas. Si una falla, las otras siguen funcionando y se nota enseguida cuál fue.

## Puesta en marcha

### 1. El repositorio

Creá un repositorio **público** en GitHub y subí esta carpeta. Tiene que ser público: en las cuentas gratuitas, las tareas programadas en repositorios privados no corren, y en los públicos los minutos son ilimitados.

### Qué queda visible y qué no

En un repositorio público, además del código, cualquiera puede leer los **registros de ejecución** y descargar los **archivos que una corrida deje guardados**. Por eso el proyecto está armado para que tu contenido nunca toque GitHub:

| Queda visible | No queda visible |
|---|---|
| El código de los scripts | El informe, que vive en su propia página privada |
| La lista de tickers de `config.json` | El guion, que se descarga en la corrida y se borra cuando termina |
| Precios de cierre en `data/market_data.json`, que son públicos de todas formas | El MP3, que se manda por mail y no se guarda |
| Que el proceso existe y a qué hora corre | Las direcciones de los suscriptores, enmascaradas en el log |
| | Las claves, encriptadas en Secrets |

Dos reglas que sostienen eso y conviene no romper: el guion nunca se commitea (está en el `.gitignore`) y el MP3 solo se guarda como archivo descargable si lo pedís a mano con la opción `guardar_audio`, pensada para rescatarlo un día que el mail falle.

### 2. La planilla de suscriptores

Ya está creada en tu Drive, en la carpeta *Informe de mercados*, con las columnas `nombre`, `mail`, `activo`, `notas`. Cargás ahí a quien quieras y el próximo envío la levanta sola. Con `activo` en `no` la persona deja de recibirlo sin que tengas que borrar la fila.

Para que GitHub pueda leerla: **Archivo → Compartir → Publicar en la web → pestaña de suscriptores → formato CSV → Publicar**. Copiá esa URL.

### 3. El documento del guion

El documento *Guion del día* de la misma carpeta tiene que quedar como **cualquier persona con el enlace puede ver**. De ahí sale el texto que se convierte en audio.

### 4. Los Secrets

En el repositorio, **Settings → Secrets and variables → Actions → New repository secret**, cargá estos cinco:

| Secret | Qué va |
|---|---|
| `SMTP_USER` | tu dirección de Gmail |
| `SMTP_PASSWORD` | la contraseña de aplicación de Google, 16 letras |
| `SUSCRIPTORES_CSV_URL` | la URL de la planilla publicada como CSV |
| `GUION_DOC_ID` | el ID del documento del guion (lo que va entre `/d/` y `/edit` en su URL) |
| `INFORME_URL` | el link fijo del informe |

La contraseña de aplicación no es la de tu cuenta: se genera en la configuración de seguridad de Google con la verificación en dos pasos activada. Gmail no acepta la contraseña normal por SMTP. Esa clave la cargás vos directamente en GitHub; no hace falta que me la pases ni que quede escrita en ningún archivo.

### 5. Probar

En la pestaña **Actions** del repositorio, cada workflow tiene un botón *Run workflow* para correrlo a mano. El orden para probar es:

1. *Datos de mercado* → tiene que aparecer `data/market_data.json` con los precios.
2. *Audio y mail* con la opción **sin audio** tildada → llegan los mails solo con el link.
3. *Audio y mail* completo → llega el mail con el MP3 adjunto.

Si algo falla, el log de cada paso dice exactamente qué pasó.

## Detalles que conviene saber

**Los horarios no son exactos.** GitHub atrasa las tareas programadas entre cinco y quince minutos cuando hay mucha demanda. Por eso los dos workflows corren con margen: los datos a las 6:15 para el informe de las 7, y la entrega a las 7:20.

**Las tareas se apagan solas si el repositorio queda quieto.** GitHub deshabilita los schedules después de sesenta días sin actividad. Como el workflow de datos hace un commit todos los días, eso no debería pasar nunca; si algún día ves que dejó de correr, es lo primero a mirar.

**El servicio de voces puede rechazar pedidos desde la nube.** Las voces de Microsoft a veces devuelven error cuando el pedido viene de un servidor y no de una computadora personal. Por eso el script cae automáticamente a Piper, que corre offline con un modelo descargado y no depende de nadie. La voz es algo menos natural pero el episodio sale igual. En el log se ve cuál de los dos motores se usó.

**El MP3 queda guardado siete días** como artefacto de la corrida, así que si el mail falla podés bajarlo a mano desde la pestaña Actions.

**La planilla publicada es accesible para quien tenga la URL.** Por eso la URL va como Secret y no escrita en el código. Es razonable para una lista personal; si en algún momento la lista crece o incluye direcciones de terceros que prefieras no exponer, se cambia por una cuenta de servicio de Google y la planilla vuelve a ser privada. Son unos pasos más de configuración y el código cambia poco.

## Correr las piezas a mano

```bash
pip install -r requirements.txt
python scripts/bajar_datos.py
python scripts/bajar_guion.py
python scripts/generar_audio.py            # edge-tts, con Piper de respaldo
python scripts/generar_audio.py --voces    # lista las voces en inglés
python scripts/enviar_mail.py --prueba     # muestra a quién le mandaría, sin enviar
```

En tu PC los secretos salen de un archivo `.env` en la raíz, con una línea por variable. Ese archivo está en el `.gitignore`, así que nunca se sube.
