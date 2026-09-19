"""
scheduler.py
------------
Punto de entrada para correr el bot dentro de Docker: ejecuta
`tiktok_bot.py repost` cada N horas (configurable), en loop infinito.

No usa cron para mantener el contenedor simple (una sola imagen, un solo
proceso, sin instalar/configurar un daemon de cron aparte). Si prefieres
cron real, ver la nota al final de este archivo.

Variables de entorno (todas opcionales, con default razonable):
    REPOST_INTERVAL_HOURS  -> cada cuantas horas repostear (default: 8)
    REPOST_VIA             -> zernio | tiktok-direct (default: zernio)
    REPOST_PRIVACY         -> PUBLIC_TO_EVERYONE | SELF_ONLY | ... (default: PUBLIC_TO_EVERYONE)
    REPOST_ALSO            -> plataformas extra separadas por coma, ej "instagram,youtube" (default: "")
    RUN_ON_START           -> "true"/"false", si el arranque del contenedor
                              intenta un repost (default: true)
    ALWAYS_POST_ON_START   -> "true"/"false" (default: false). Solo aplica si
                              RUN_ON_START=true:
                              - false (default): repostea al arrancar SOLO si ya paso
                                REPOST_INTERVAL_HOURS desde el ultimo repost exitoso
                                (registrado en repost_state.json). Pensado para correr
                                en una PC de casa que se prende/apaga: evita que cada
                                reinicio del contenedor dispare un repost extra.
                              - true: repostea siempre al arrancar, sin mirar el
                                historial (comportamiento viejo; sirve si el bot corre
                                en una VPS siempre encendida y arranca una sola vez).
"""

import datetime
import json
import os
import subprocess
import sys
import time

INTERVAL_HOURS = float(os.environ.get("REPOST_INTERVAL_HOURS", "8"))
VIA = os.environ.get("REPOST_VIA", "zernio")
PRIVACY = os.environ.get("REPOST_PRIVACY", "PUBLIC_TO_EVERYONE")
ALSO = os.environ.get("REPOST_ALSO", "")
RUN_ON_START = os.environ.get("RUN_ON_START", "true").lower() in ("1", "true", "yes")
ALWAYS_POST_ON_START = os.environ.get("ALWAYS_POST_ON_START", "false").lower() in ("1", "true", "yes")

BASE_DIR = os.path.dirname(__file__)
STATE_PATH = os.path.join(BASE_DIR, "repost_state.json")


def log(msg: str):
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {msg}", flush=True)


def load_last_repost():
    """Devuelve el datetime (UTC) del ultimo repost exitoso, o None si no hay registro."""
    try:
        with open(STATE_PATH, "r") as f:
            data = json.load(f)
        return datetime.datetime.fromisoformat(data["last_repost"])
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
        return None


def save_last_repost(ts: datetime.datetime):
    with open(STATE_PATH, "w") as f:
        json.dump({"last_repost": ts.isoformat()}, f)


def run_once():
    cmd = [sys.executable, os.path.join(BASE_DIR, "tiktok_bot.py"), "repost",
           "--via", VIA, "--privacy", PRIVACY]
    if ALSO:
        cmd += ["--also", ALSO]

    log(f"Ejecutando repost: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        save_last_repost(datetime.datetime.now(datetime.timezone.utc))
        log("Repost terminado OK.")
    except subprocess.CalledProcessError as e:
        # No tumbamos el contenedor por un fallo puntual (rate limit, token
        # expirado, servicio de terceros caido, etc). Se reintenta en el
        # siguiente ciclo, según REPOST_INTERVAL_HOURS. No se actualiza
        # repost_state.json, para no dar por hecho un repost que no salio.
        log(f"El repost fallo (codigo {e.returncode}). Se reintentara en el proximo ciclo.")
    except Exception as e:
        log(f"Error inesperado corriendo el repost: {e}. Se reintentara en el proximo ciclo.")


def main():
    log(f"Scheduler iniciado. Intervalo: cada {INTERVAL_HOURS}h. Via: {VIA}. Privacidad: {PRIVACY}."
        + (f" Tambien en: {ALSO}." if ALSO else ""))

    if not RUN_ON_START:
        log("RUN_ON_START=false, se espera al primer intervalo antes del primer repost.")
    elif ALWAYS_POST_ON_START:
        log("ALWAYS_POST_ON_START=true, se repostea al arrancar sin mirar el historial.")
        run_once()
    else:
        last = load_last_repost()
        if last is None:
            log("No hay repost_state.json (primer arranque o borrado). Reposteando ahora.")
            run_once()
        else:
            elapsed_h = (datetime.datetime.now(datetime.timezone.utc) - last).total_seconds() / 3600
            if elapsed_h >= INTERVAL_HOURS:
                log(f"Pasaron {elapsed_h:.1f}h desde el ultimo repost (>= {INTERVAL_HOURS}h). Reposteando ahora.")
                run_once()
            else:
                restante = INTERVAL_HOURS - elapsed_h
                log(f"Ultimo repost hace {elapsed_h:.1f}h, todavia no toca (faltan {restante:.1f}h). "
                    f"Se omite el repost de arranque para no spammear.")

    while True:
        log(f"Durmiendo {INTERVAL_HOURS}h hasta el proximo repost...")
        time.sleep(INTERVAL_HOURS * 3600)
        run_once()


if __name__ == "__main__":
    main()

# Nota: si prefieres cron real en vez de este loop con sleep (por ejemplo
# para tener horarios fijos como "todos los dias a las 9am y 5pm" en vez
# de "cada N horas desde que arranco el contenedor"), reemplaza el CMD del
# Dockerfile por una imagen con cron instalado y un crontab que llame a
# `python tiktok_bot.py repost ...` directamente. El enfoque de este
# archivo es mas simple de operar (un solo proceso, logs en stdout,
# reinicia limpio con `docker compose restart`).
