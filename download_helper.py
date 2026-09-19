"""
download_helper.py
-------------------
Descarga automatica del archivo .mp4 sin marca de agua de UNO DE TUS
PROPIOS videos, usando TikWM (https://tikwm.com), un servicio de
terceros NO OFICIAL de TikTok que resuelve un share_url publico a un
link de descarga directo.

IMPORTANTE:
- Esto NO es una API oficial de TikTok. Es un servicio externo que hace
  scraping/ingenieria inversa de TikTok. Puede fallar, tener rate limit,
  o dejar de funcionar sin aviso, y tecnicamente esta en una zona gris
  respecto a los Terminos de Servicio de TikTok.
- Se usa aqui solo para automatizar la descarga de TUS PROPIOS videos
  publicos (no de contenido ajeno).
- Si en algun momento deja de funcionar, la alternativa siempre
  disponible es guardar tu .mp4 manualmente en videos/<video_id>.mp4
  (ver tiktok_bot.py), que no depende de ningun tercero.

Formato real de la API de TikWM (documentado por la comunidad, no es
un contrato oficial y puede cambiar):

    GET https://tikwm.com/api/?url=<share_url>&hd=1

    Respuesta (200 OK):
    {
      "code": 0,
      "msg": "success",
      "data": {
        "id": "...",
        "title": "...",
        "play":   "https://.../sin_marca_sd.mp4",
        "hdplay": "https://.../sin_marca_hd.mp4",
        "wmplay": "https://.../con_marca.mp4",
        "size": 1234567,
        "hd_size": 2345678,
        "wm_size": 1234567,
        ...
      }
    }

    code != 0 => error (video privado, url invalida, o rate limit).
    TikWM limita a ~1 request/segundo por IP; si responde con
    "frequently" o code == -1, hay que esperar y reintentar.

Uso desde otro script:
    from download_helper import download_video
    path = download_video(share_url, video_id)
"""

import os
import time
import requests

VIDEOS_DIR = os.path.join(os.path.dirname(__file__), "videos")

TIKWM_ENDPOINT = "https://tikwm.com/api/"

MAX_RETRIES = 4
RETRY_BACKOFF_SECONDS = 3  # se multiplica por el numero de intento


def _request_with_retries(share_url: str) -> dict:
    """Llama a TikWM con reintentos si hay rate limit o error transitorio."""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                TIKWM_ENDPOINT,
                params={"url": share_url, "hd": 1},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=20,
            )
            resp.raise_for_status()
            payload = resp.json()
        except (requests.RequestException, ValueError) as e:
            last_error = e
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)
            continue

        if payload.get("code") == 0 and payload.get("data"):
            return payload["data"]

        # code != 0: puede ser rate limit ("Free Api Limit" / "frequently")
        # o un error real (video privado, url invalida). Reintentamos igual
        # unas pocas veces por si es transitorio.
        last_error = RuntimeError(f"TikWM respondio con error: {payload.get('msg')}")
        time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    raise RuntimeError(f"TikWM no pudo resolver el video tras {MAX_RETRIES} intentos: {last_error}")


def resolve_no_watermark_url(share_url: str, prefer_hd: bool = True) -> str:
    """Devuelve el link directo del mp4 sin marca de agua (HD si esta disponible)."""
    data = _request_with_retries(share_url)
    if prefer_hd and data.get("hdplay"):
        return data["hdplay"]
    if data.get("play"):
        return data["play"]
    raise RuntimeError(f"TikWM no devolvio ningun link sin marca de agua: {data}")


def download_video(share_url: str, video_id: str, prefer_hd: bool = True) -> str:
    """Descarga el video a videos/<video_id>.mp4 y devuelve la ruta local."""
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    dest_path = os.path.join(VIDEOS_DIR, f"{video_id}.mp4")

    if os.path.exists(dest_path):
        return dest_path  # ya lo teniamos descargado

    direct_url = resolve_no_watermark_url(share_url, prefer_hd=prefer_hd)

    tmp_path = dest_path + ".part"
    with requests.get(direct_url, stream=True, headers={"User-Agent": "Mozilla/5.0"}, timeout=60) as r:
        r.raise_for_status()
        with open(tmp_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

    os.replace(tmp_path, dest_path)  # evita dejar archivos a medio descargar si algo falla
    return dest_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Uso: python download_helper.py <share_url> <video_id>")
        sys.exit(1)
    path = download_video(sys.argv[1], sys.argv[2])
    print("Descargado en:", path)
