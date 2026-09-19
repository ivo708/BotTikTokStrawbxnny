"""
zernio_client.py
-----------------
Cliente minimo para la API de Zernio (https://zernio.com), un servicio de
terceros con tier GRATUITO real (primeras 2 cuentas conectadas, posts
ilimitados, sin tarjeta de credito) que ya paso la auditoria "Direct Post"
de TikTok, ademas de Instagram, YouTube, LinkedIn, X, Facebook, y otras.

IMPORTANTE:
- Esto NO es de TikTok ni de ninguna red social. Es un proveedor externo
  al que le das permiso (via OAuth, desde su dashboard) para publicar en
  tus cuentas conectadas.
- Hay una reseña real en Trustpilot (empresa antes llamada "Late") que
  alega que el acceso a las cuentas persistio incluso despues de
  desconectarlas y borrar los datos desde el dashboard de Zernio. Por
  eso, si en algun momento quieres cortar el acceso de verdad, hazlo
  tambien desde el lado de TikTok: Perfil > Settings and privacy >
  Security and login > Manage app permissions > Remove access. Eso
  invalida el token de raiz sin importar lo que haga Zernio.
- Requiere una cuenta gratuita en zernio.com, con tu cuenta de TikTok
  conectada desde su dashboard, y un API key (empieza con "sk_").

Arquitectura de Zernio (basada en su arquitectura de perfiles):
- Un "profile" agrupa cuentas conectadas (ej. "Mi marca personal").
- Cada cuenta conectada tiene un accountId, usado en cada post.
- POST /v1/media sube un archivo directo (multipart), devuelve una URL.
- POST /v1/posts crea (y publica de inmediato si publishNow=true) un
  post multi-plataforma, con platformSpecificData.tiktokSettings para
  configurar privacidad/comentarios/duet/stitch de TikTok.

Uso:
    from zernio_client import ZernioClient
    client = ZernioClient(api_key="sk_...")
    profile_id = client.get_default_profile_id()
    accounts = client.list_accounts(profile_id)
    media_url = client.upload_media("videos/123.mp4")
    result = client.create_post(
        content="Mi caption",
        platforms=[{"platform": "tiktok", "accountId": "acc_xyz",
                    "platformSpecificData": {"tiktokSettings": {"privacy_level": "PUBLIC_TO_EVERYONE"}}}],
        media_url=media_url,
        media_type="video",
    )
"""

import os
import requests

BASE_URL = "https://zernio.com/api/v1"


class ZernioError(RuntimeError):
    pass


class ZernioClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_key}"})

    def _handle(self, resp: requests.Response) -> dict:
        try:
            payload = resp.json()
        except ValueError:
            resp.raise_for_status()
            raise ZernioError(f"Respuesta no-JSON inesperada: {resp.text[:200]}")

        if resp.status_code >= 400:
            msg = payload.get("error") or payload.get("message") or payload
            raise ZernioError(f"Error de Zernio ({resp.status_code}): {msg}")
        return payload

    # ---------- Perfiles ----------

    def list_profiles(self) -> list:
        resp = self.session.get(f"{BASE_URL}/profiles")
        data = self._handle(resp)
        return data.get("profiles", [])

    def create_profile(self, name: str) -> str:
        resp = self.session.post(f"{BASE_URL}/profiles", json={"name": name})
        data = self._handle(resp)
        return data["id"]

    def get_default_profile_id(self) -> str:
        """Devuelve el primer perfil existente, o crea uno llamado 'TikTok Bot' si no hay ninguno."""
        profiles = self.list_profiles()
        if profiles:
            return profiles[0]["id"]
        return self.create_profile("TikTok Bot")

    # ---------- Cuentas ----------

    def list_accounts(self, profile_id: str) -> list:
        resp = self.session.get(f"{BASE_URL}/accounts", params={"profileId": profile_id})
        data = self._handle(resp)
        return data.get("accounts", data if isinstance(data, list) else [])

    def find_account_id(self, platform: str, profile_id: str) -> str:
        for acc in self.list_accounts(profile_id):
            if acc.get("platform") == platform:
                return acc.get("id") or acc.get("accountId") or acc.get("_id")
        raise ZernioError(f"No encontre una cuenta conectada de {platform} en el perfil {profile_id}. "
                           f"Conectala desde el dashboard de zernio.com")

    # ---------- Media ----------

    def upload_media(self, file_path: str) -> str:
        """Sube un archivo (imagen o video) y devuelve la URL publica para usar en mediaItems."""
        filename = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            resp = self.session.post(f"{BASE_URL}/media", files={"file": (filename, f)})
        data = self._handle(resp)
        # La API puede devolver la url en distintas claves segun la version; cubrimos las mas comunes
        url = data.get("url") or data.get("publicUrl") or data.get("mediaUrl")
        if not url:
            raise ZernioError(f"No encontre la URL del archivo subido en la respuesta: {data}")
        return url

    # ---------- Posts ----------

    def create_post(self, content: str, platforms: list, media_url: str = None,
                     media_type: str = "video", publish_now: bool = True,
                     scheduled_for: str = None, timezone: str = "UTC",
                     profile_id: str = None) -> dict:
        body = {
            "content": content,
            "platforms": platforms,
            "publishNow": publish_now,
        }
        if media_url:
            body["mediaItems"] = [{"type": media_type, "url": media_url}]
        if scheduled_for:
            body["scheduledFor"] = scheduled_for
            body["timezone"] = timezone
            body["publishNow"] = False
        if profile_id:
            body["profileId"] = profile_id

        resp = self.session.post(f"{BASE_URL}/posts", json=body)
        return self._handle(resp)
