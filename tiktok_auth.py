"""
tiktok_auth.py
--------------
Flujo de autenticación OAuth2 (una sola vez) para obtener el access_token
y refresh_token de tu propia cuenta de TikTok.

Requisitos previos:
1. Crear una app en https://developers.tiktok.com/ (TikTok for Developers).
2. Añadir los productos "Login Kit" y "Content Posting API" a tu app.
3. Configurar una Redirect URI, por ejemplo: http://localhost:8080/callback
4. Solicitar los scopes: user.info.basic, video.list, video.publish
5. Copiar tu CLIENT_KEY y CLIENT_SECRET en config.json (ver config.example.json)

Uso:
    python tiktok_auth.py
Esto abrirá un enlace para que autorices tu propia cuenta, levantará un
servidor local para capturar el "code" de redirección, y guardará los
tokens en tokens.json.
"""

import json
import http.server
import urllib.parse
import webbrowser
import requests
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
TOKENS_PATH = os.path.join(os.path.dirname(__file__), "tokens.json")

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"

SCOPES = "user.info.basic,video.list,video.publish"


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


received_code = {}


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            received_code["code"] = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(
                "Autorizacion recibida. Ya puedes cerrar esta ventana.".encode()
            )
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # silencia el log del servidor


def get_authorization_code(client_key, redirect_uri):
    params = {
        "client_key": client_key,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": "tiktok_repost_bot",
    }
    url = AUTH_URL + "?" + urllib.parse.urlencode(params)
    print("Abriendo el navegador para autorizar tu cuenta de TikTok...")
    print("Si no se abre solo, entra manualmente a este enlace:\n", url)
    webbrowser.open(url)

    # Levanta un servidor local temporal para capturar el redirect
    port = int(redirect_uri.split(":")[-1].split("/")[0])
    server = http.server.HTTPServer(("localhost", port), CallbackHandler)
    while "code" not in received_code:
        server.handle_request()
    server.server_close()
    return received_code["code"]


def exchange_code_for_tokens(client_key, client_secret, code, redirect_uri):
    data = {
        "client_key": client_key,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    resp = requests.post(TOKEN_URL, data=data, headers={
        "Content-Type": "application/x-www-form-urlencoded",
    })
    resp.raise_for_status()
    return resp.json()


def main():
    config = load_config()
    code = get_authorization_code(config["client_key"], config["redirect_uri"])
    tokens = exchange_code_for_tokens(
        config["client_key"], config["client_secret"], code, config["redirect_uri"]
    )
    if "access_token" not in tokens:
        print("Error obteniendo tokens:", tokens)
        return
    with open(TOKENS_PATH, "w") as f:
        json.dump(tokens, f, indent=2)
    print("Tokens guardados en", TOKENS_PATH)
    print("access_token expira en", tokens.get("expires_in"), "segundos")
    print("refresh_token expira en", tokens.get("refresh_expires_in"), "segundos (~1 año)")


if __name__ == "__main__":
    main()
