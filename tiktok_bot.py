import argparse
import json
import os
import random
import sys
import time

import requests

from download_helper import download_video
from zernio_client import ZernioClient, ZernioError

BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
TOKENS_PATH = os.path.join(BASE_DIR, "tokens.json")
VIDEOS_DIR = os.path.join(BASE_DIR, "videos")  # aqui van tus .mp4, nombrados <video_id>.mp4

API_BASE = "https://open.tiktokapis.com"
TOKEN_URL = f"{API_BASE}/v2/oauth/token/"
VIDEO_LIST_URL = f"{API_BASE}/v2/video/list/"
CREATOR_INFO_URL = f"{API_BASE}/v2/post/publish/creator_info/query/"
POST_INIT_URL = f"{API_BASE}/v2/post/publish/video/init/"
POST_STATUS_URL = f"{API_BASE}/v2/post/publish/status/fetch/"

# Codepoint (hex, sin "U+") del caracter que se agrega al final del caption
# de cada repost, configurable por variable de entorno para no tener que
# tocar el codigo. Default: 267B (\u267b, visible en el caption). Alternativa:
# 2063 (INVISIBLE SEPARATOR, no se ve al leer la descripcion en TikTok).
REPOST_MARKER_CODEPOINT = os.environ.get("REPOST_MARKER_CODEPOINT", "267B")
REPOST_MARKER = chr(int(REPOST_MARKER_CODEPOINT, 16))


def es_repost(titulo: str) -> bool:
    return REPOST_MARKER in (titulo or "")


def con_marca_de_repost(titulo: str) -> str:
    """Agrega el marcador de repost al caption, sin duplicarlo si ya estuviera."""
    titulo = titulo or ""
    return titulo if es_repost(titulo) else titulo + REPOST_MARKER


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_valid_access_token():
    """Devuelve un access_token valido, refrescandolo si hace falta."""
    config = load_json(CONFIG_PATH)
    tokens = load_json(TOKENS_PATH)

    # Refrescamos siempre por simplicidad (barato y evita 401 a mitad de ejecucion)
    data = {
        "client_key": config["client_key"],
        "client_secret": config["client_secret"],
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
    }
    resp = requests.post(TOKEN_URL, data=data, headers={
        "Content-Type": "application/x-www-form-urlencoded",
    })
    resp.raise_for_status()
    new_tokens = resp.json()
    if "access_token" in new_tokens:
        save_json(TOKENS_PATH, new_tokens)
        return new_tokens["access_token"]

    # si el refresh falla, probamos con el token que ya teniamos
    return tokens["access_token"]


def fetch_all_videos(access_token):
    """Pagina /v2/video/list/ hasta traer todos los videos con su view_count."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    fields = "id,title,view_count,share_url,create_time"
    videos = []
    cursor = None
    has_more = True

    while has_more:
        body = {"max_count": 20}
        if cursor:
            body["cursor"] = cursor
        resp = requests.post(
            f"{VIDEO_LIST_URL}?fields={fields}",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("error", {}).get("code") != "ok":
            raise RuntimeError(f"Error de la API: {payload['error']}")
        data = payload["data"]
        videos.extend(data["videos"])
        has_more = data.get("has_more", False)
        cursor = data.get("cursor")
        time.sleep(0.5)  # respeta el limite de rate

    return videos


def top_n_by_views(videos, n=100):
    return sorted(videos, key=lambda v: v.get("view_count", 0), reverse=True)[:n]


def local_file_for(video_id):
    path = os.path.join(VIDEOS_DIR, f"{video_id}.mp4")
    return path if os.path.exists(path) else None


def query_creator_info(access_token):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }
    resp = requests.post(CREATOR_INFO_URL, headers=headers)
    resp.raise_for_status()
    return resp.json()["data"]


def repost_video(access_token, video_path, title, privacy_level):
    file_size = os.path.getsize(video_path)
    chunk_size = min(file_size, 10 * 1024 * 1024)  # 10MB por chunk, ajustable
    total_chunks = (file_size + chunk_size - 1) // chunk_size

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }
    init_body = {
        "post_info": {
            "title": title,
            "privacy_level": privacy_level,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunks,
        },
    }
    resp = requests.post(POST_INIT_URL, headers=headers, json=init_body)
    resp.raise_for_status()
    init_data = resp.json()["data"]
    upload_url = init_data["upload_url"]
    publish_id = init_data["publish_id"]

    # Sube el archivo (si es un solo chunk, un solo PUT)
    with open(video_path, "rb") as f:
        content = f.read()

    put_headers = {
        "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
        "Content-Type": "video/mp4",
    }
    put_resp = requests.put(upload_url, headers=put_headers, data=content)
    put_resp.raise_for_status()

    return publish_id


def poll_status(access_token, publish_id, timeout=120):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }
    start = time.time()
    while time.time() - start < timeout:
        resp = requests.post(POST_STATUS_URL, headers=headers, json={"publish_id": publish_id})
        resp.raise_for_status()
        status = resp.json()["data"]["status"]
        print("Estado de publicacion:", status)
        if status in ("PUBLISH_COMPLETE", "FAILED"):
            return status
        time.sleep(5)
    return "TIMEOUT"


def cmd_listar(args):
    access_token = get_valid_access_token()
    videos = fetch_all_videos(access_token)
    originales = [v for v in videos if not es_repost(v.get("title", ""))]
    top = top_n_by_views(originales, 100)
    print(f"\nTop {len(top)} videos ORIGINALES por vistas (los reposts ya hechos por el bot se excluyen):\n")
    for v in top:
        local = "✅ local" if local_file_for(v["id"]) else "❌ sin archivo local"
        print(f"{v.get('view_count', 0):>10} vistas | {v['id']} | {v.get('title','(sin titulo)')[:50]} | {local}")

    reposts = [v for v in videos if es_repost(v.get("title", ""))]
    print(f"\n({len(reposts)} reposts ya hechos por el bot, excluidos del top de arriba)")


def elegir_y_descargar_video(access_token, args):
    """Selecciona el video (por --id o al azar del top 100) y devuelve (path_local, video_id, title)."""
    if args.id:
        video_id = args.id
        path = local_file_for(video_id)
        if not path:
            print(f"No tengo el .mp4 local para {video_id}. Descargalo tu mismo en videos/{video_id}.mp4")
            sys.exit(1)
        title = args.title or ""
        return path, video_id, title

    videos = fetch_all_videos(access_token)
    originales = [v for v in videos if not es_repost(v.get("title", ""))]
    top = top_n_by_views(originales, 100)
    if not top:
        print("No encontre videos ORIGINALES en tu cuenta (o todos ya son reposts marcados).")
        sys.exit(1)
    elegido = random.choice(top)
    video_id = elegido["id"]
    title = args.title or elegido.get("title", "")
    print(f"Video elegido al azar: {video_id} ({elegido.get('view_count',0)} vistas) - {title}")

    path = local_file_for(video_id)
    if not path:
        print("No lo tengo descargado localmente, lo descargo automaticamente (via TikWM)...")
        try:
            path = download_video(elegido["share_url"], video_id)
            print("Descargado en:", path)
        except Exception as e:
            print(f"No se pudo descargar automaticamente ({e}).")
            print(f"Descargalo tu mismo y guardalo en videos/{video_id}.mp4, luego corre:")
            print(f"  python tiktok_bot.py repost --id {video_id} --title \"{title}\"")
            sys.exit(1)

    return path, video_id, title


def publicar_via_tiktok_direct(access_token, path, title, privacy_arg):
    """Publica usando la Content Posting API oficial de TikTok directamente (tu propia app)."""
    creator_info = query_creator_info(access_token)
    privacy_options = creator_info.get("privacy_level_options", ["SELF_ONLY"])
    privacy_level = privacy_arg if privacy_arg in privacy_options else privacy_options[0]
    print("Nivel de privacidad a usar:", privacy_level, "(opciones disponibles:", privacy_options, ")")

    publish_id = repost_video(access_token, path, title, privacy_level)
    print("Subido. publish_id:", publish_id)
    final_status = poll_status(access_token, publish_id)
    print("Resultado final:", final_status)
    if privacy_level == "SELF_ONLY":
        print("\nNota: quedo publicado como privado (SELF_ONLY) porque tu app no esta auditada.")
        print("Entra a la app de TikTok si quieres cambiarlo a publico manualmente.")


def publicar_via_zernio(path, title, privacy_arg, extra_platforms):
    """Publica via Zernio: tier gratuito real (2 cuentas, posts ilimitados)."""
    config = load_json(CONFIG_PATH)
    zernio_key = config.get("zernio_api_key")
    if not zernio_key:
        print("Falta 'zernio_api_key' en config.json. Genera una gratis en https://zernio.com (Settings > API Keys).")
        sys.exit(1)

    client = ZernioClient(zernio_key)

    try:
        profile_id = load_json(CONFIG_PATH).get("zernio_profile_id") or client.get_default_profile_id()
        accounts = client.list_accounts(profile_id)
    except ZernioError as e:
        print(f"Error consultando cuentas de Zernio: {e}")
        sys.exit(1)

    tiktok_accounts = [a for a in accounts if a.get("platform") == "tiktok"]
    if not tiktok_accounts:
        print("No hay ninguna cuenta de TikTok conectada en tu dashboard de Zernio.")
        print("Conectala primero en https://zernio.com (Connect Account).")
        sys.exit(1)
    tiktok_account_id = tiktok_accounts[0].get("id") or tiktok_accounts[0].get("accountId") or tiktok_accounts[0].get("_id")

    platforms = [{
        "platform": "tiktok",
        "accountId": tiktok_account_id,
        "platformSpecificData": {
            "tiktokSettings": {
                "privacy_level": privacy_arg,
                "allow_comment": True,
                "allow_duet": True,
                "allow_stitch": True,
                # Requeridos por Zernio para que el post no falle: representan
                # que tu (el dueño de la cuenta) ya viste el preview y diste
                # tu consentimiento antes de publicar.
                "content_preview_confirmed": True,
                "express_consent_given": True,
            }
        }
    }]

    for plat in extra_platforms:
        candidatos = [a for a in accounts if a.get("platform") == plat]
        if not candidatos:
            print(f"Aviso: pediste incluir '{plat}' pero no hay ninguna cuenta activa de esa plataforma conectada en Zernio. Se omite.")
            continue
        acc_id = candidatos[0].get("id") or candidatos[0].get("accountId") or candidatos[0].get("_id")
        platforms.append({"platform": plat, "accountId": acc_id})

    print(f"Publicando en {len(platforms)} cuenta(s): " + ", ".join(p["platform"] for p in platforms))

    print("Subiendo el video a Zernio...")
    try:
        media_url = client.upload_media(path)
    except ZernioError as e:
        print(f"Error subiendo el video: {e}")
        sys.exit(1)

    try:
        result = client.create_post(
            content=title,
            platforms=platforms,
            media_url=media_url,
            media_type="video",
            publish_now=True,
            profile_id=profile_id,
        )
    except ZernioError as e:
        print(f"Error creando el post: {e}")
        sys.exit(1)

    post = result.get("post", result)
    print("Post creado. id:", post.get("_id") or post.get("id"))
    print(f"\nListo. Nivel de privacidad de TikTok usado: {privacy_arg} (publicado de una vez, sin quedar en SELF_ONLY).")


def cmd_repost(args):
    access_token = get_valid_access_token()
    path, video_id, title = elegir_y_descargar_video(access_token, args)
    caption = con_marca_de_repost(title)

    if args.via == "zernio":
        extra_platforms = [p.strip() for p in args.also.split(",") if p.strip()] if args.also else []
        publicar_via_zernio(path, caption, args.privacy, extra_platforms)
    else:
        publicar_via_tiktok_direct(access_token, path, caption, args.privacy)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bot de repost aleatorio para tu cuenta de TikTok")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_listar = sub.add_parser("listar", help="Muestra el top 100 de tus videos por vistas")
    p_listar.set_defaults(func=cmd_listar)

    p_repost = sub.add_parser("repost", help="Elige uno al azar del top 100 (o uno especifico) y lo publica")
    p_repost.add_argument("--id", help="Video ID especifico a republicar (opcional)")
    p_repost.add_argument("--title", help="Titulo/caption a usar (opcional)")
    p_repost.add_argument("--privacy", default="PUBLIC_TO_EVERYONE",
                           help="SELF_ONLY, PUBLIC_TO_EVERYONE, MUTUAL_FOLLOW_FRIENDS, etc.")
    p_repost.add_argument("--via", choices=["zernio", "tiktok-direct"], default="zernio",
                           help="zernio (default, tier gratuito real) "
                                "o tiktok-direct (tu propia app, queda en SELF_ONLY si no esta auditada)")
    p_repost.add_argument("--also", default="",
                           help="Solo con --via zernio: otras plataformas donde publicar tambien, "
                                "separadas por coma, ej. --also instagram,youtube")
    p_repost.set_defaults(func=cmd_repost)

    args = parser.parse_args()
    args.func(args)
