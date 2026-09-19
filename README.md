# Bot de repost aleatorio para TikTok (tu propia cuenta)

Corre en Docker, se activa cada N horas (configurable), consulta tus
videos ORIGINALES (excluye reposts anteriores del propio bot), arma el
ranking de los 100 con más vistas, elige uno al azar, lo descarga sin
marca de agua y lo vuelve a publicar — público, de inmediato.

## Qué hace y qué NO hace

✅ Consulta metadatos de tus videos (vistas, título, fecha) vía la
Display API oficial de TikTok.
✅ Calcula el top 100 por `view_count` entre tus videos **originales**
(ver "Marcador de repost" más abajo) y elige uno al azar.
✅ **Descarga automáticamente** el .mp4 sin marca de agua usando TikWM
(servicio de terceros), a partir del `share_url` que ya da la Display
API. Pide la versión HD (`hd=1`) y reintenta si hay rate limit.
✅ Publica el video elegido — por default vía **Zernio** (tier gratuito
real, público desde el primer post), con alternativa la API directa de
TikTok (`--via tiktok-direct`).
✅ **Marca cada repost** con un carácter Unicode invisible al final del
caption, para nunca volver a elegirlo como fuente de otro repost.
✅ **Corre en Docker** con un scheduler propio: se activa cada N horas
(default 8, configurable por variable de entorno), sin cron externo.

## Setup — resumen rápido

1. **TikTok**: crea una app en developers.tiktok.com, corre
   `python tiktok_auth.py` una vez en tu máquina (no en Docker — abre un
   navegador) para generar `tokens.json`. Detalle completo más abajo.
2. **Zernio** (vía de publicación default, gratis): sigue
   **[`SETUP_ZERNIO.md`](./SETUP_ZERNIO.md)** paso a paso.
3. Copia `config.example.json` → `config.json` y rellena las claves.
4. Copia `.env.example` → `.env` y ajusta el intervalo si quieres otro
   distinto de 8h.
5. `docker compose up -d --build`

## Correr en Docker

```bash
cp config.example.json config.json   # rellena tus claves
cp .env.example .env                 # ajusta REPOST_INTERVAL_HOURS si quieres
touch repost_state.json              # archivo vacio; Docker lo necesita creado de antemano
python tiktok_auth.py                # una sola vez, fuera de Docker (abre navegador)
docker compose up -d --build
docker compose logs -f               # ver los reposts en vivo
```

El contenedor:
- Al arrancar, intenta un repost (`RUN_ON_START=true` por default) — ver
  "Evitar spam al reiniciar (PC de casa vs. VPS)" más abajo para cuándo
  ese repost realmente sale o se omite.
- Persiste `tokens.json`, `repost_state.json` y la carpeta `videos/` como
  volúmenes, así que sobrevive a reinicios sin perder el access token,
  el historial de reposts, ni re-descargar videos.
- `config.json` se monta de solo lectura (`:ro`) — nunca se hornea en la
  imagen ni en ninguna capa de Docker (ver `.dockerignore`).

**Cambiar el intervalo o la vía sin tocar código:**
```bash
# en .env, o directo en la llamada:
REPOST_INTERVAL_HOURS=4 REPOST_VIA=zernio docker compose up -d --build
```

Variables disponibles (todas en `.env.example`):

| Variable | Default | Qué hace |
|---|---|---|
| `REPOST_INTERVAL_HOURS` | `8` | Cada cuántas horas repostea (acepta decimales, ej. `0.5` = 30 min) |
| `REPOST_VIA` | `zernio` | `zernio` \| `tiktok-direct` |
| `REPOST_PRIVACY` | `PUBLIC_TO_EVERYONE` | Nivel de privacidad de TikTok |
| `REPOST_ALSO` | *(vacío)* | Otras plataformas separadas por coma, ej. `instagram,youtube` (solo con `--via zernio`) |
| `RUN_ON_START` | `true` | Si el arranque del contenedor intenta un repost |
| `ALWAYS_POST_ON_START` | `false` | Si `true`, ese repost de arranque sale siempre; si `false`, solo sale si ya pasó `REPOST_INTERVAL_HOURS` desde el último (ver sección de abajo) |
| `REPOST_MARKER_CODEPOINT` | `267B` | Codepoint (hex) del carácter que marca un repost en el caption. `267B` = ♻ (visible), `2063` = INVISIBLE SEPARATOR (no se ve) |

### Evitar spam al reiniciar (PC de casa vs. VPS)

Cada repost exitoso queda registrado en `repost_state.json` (montado como
volumen, sobrevive a reinicios). Con `RUN_ON_START=true`:

- **`ALWAYS_POST_ON_START=false` (default)**: el repost de arranque solo
  sale si ya pasó `REPOST_INTERVAL_HOURS` desde el último repost
  registrado; si no, se omite y se espera el tiempo restante. Pensado
  para correr en una **PC de casa** que se prende y apaga (o Docker
  Desktop se reinicia solo): así apagar/prender varias veces al día no
  suma un repost extra por cada arranque.
- **`ALWAYS_POST_ON_START=true`**: repostea siempre al arrancar, sin
  mirar el historial (el comportamiento original). Tiene sentido en una
  **VPS** siempre encendida, donde el contenedor arranca una sola vez y
  querés ese primer post inmediato garantizado.

Si un repost falla (rate limit, token vencido, etc.), no se actualiza
`repost_state.json`, así que el siguiente intento (arranque o ciclo) no
lo cuenta como si hubiera salido.

**Ver logs / parar / reiniciar:**
```bash
docker compose logs -f          # logs en vivo (cada corrida queda registrada con timestamp UTC)
docker compose restart          # reinicia el scheduler (por ejemplo, tras cambiar .env)
docker compose down             # para y elimina el contenedor (los volúmenes persisten)
```

**Sin Docker Compose, con `docker run` directo:**
```bash
docker build -t tiktok-repost-bot .
touch repost_state.json
docker run -d --name tiktok_repost_bot \
  -e REPOST_INTERVAL_HOURS=8 -e REPOST_VIA=zernio \
  -v $(pwd)/config.json:/app/config.json:ro \
  -v $(pwd)/tokens.json:/app/tokens.json \
  -v $(pwd)/videos:/app/videos \
  -v $(pwd)/repost_state.json:/app/repost_state.json \
  tiktok-repost-bot
```

## Marcador de repost (para no repostear un repost)

Cada vez que el bot publica algo, le agrega al final del caption un
carácter Unicode invisible: `U+2063` (INVISIBLE SEPARATOR). No se ve al
leer la descripción en TikTok ni en ninguna otra plataforma, pero el bot
lo detecta programáticamente.

Al correr `listar` o `repost`, el bot **filtra fuera** cualquier video
cuyo título ya contenga ese carácter antes de armar el top 100 y elegir
al azar — así el pool de selección son siempre tus videos originales, no
reposts anteriores del propio bot.

## Zernio: vía default (gratis)

Zernio ya pasó la auditoría "Direct Post" de TikTok con su propia app —
por eso publica `PUBLIC_TO_EVERYONE` desde el primer post, sin que tú
pases por la revisión de TikTok. Tier gratuito real: primeras 2 cuentas
conectadas, posts ilimitados, sin tarjeta de crédito.

Setup completo, incluyendo una advertencia real sobre una reseña de
seguridad y cómo mitigarla, en **[`SETUP_ZERNIO.md`](./SETUP_ZERNIO.md)**.

## Alternativa sin terceros: tu propia app de TikTok

Si prefieres no depender de ningún tercero para publicar (aceptando que
quede privado si tu app no está auditada):
```
python tiktok_bot.py repost --via tiktok-direct --privacy SELF_ONLY
```
o en Docker: `REPOST_VIA=tiktok-direct REPOST_PRIVACY=SELF_ONLY`.

Nota: las normas de TikTok consideran que una herramienta pensada solo
para republicar contenido de tu propia cuenta no suele calificar para
pasar la auditoría (que exige apps pensadas para un público amplio), así
que con esta vía probablemente te quedes permanentemente en modo no
auditado (privado).

## Sobre la descarga (TikWM)

⚠️ **El paso de descarga NO es una API oficial de TikTok.**
`download_helper.py` usa TikWM, que hace ingeniería inversa de TikTok
para resolver el link directo del video. Esto es cómodo, pero:
- Puede fallar o dejar de funcionar en cualquier momento.
- Está en zona gris respecto a los Términos de Servicio de TikTok, aunque
  sea tu propio contenido público.
- Si falla, descarga el .mp4 tú mismo y guárdalo en
  `videos/<video_id>.mp4` — el bot lo detecta y lo usa en vez de
  intentar la descarga automática.

## Configuración de TikTok (una sola vez, fuera de Docker)

1. Crea una app en https://developers.tiktok.com/apps
2. Añade los productos **Login Kit** y **Content Posting API**.
3. Agrega la Redirect URI: `http://localhost:8080/callback`
4. Copia `config.example.json` a `config.json` y rellena `client_key` y
   `client_secret`.
5. Instala dependencias localmente (solo para este paso):
   ```
   pip install -r requirements.txt
   ```
6. Ejecuta la autenticación (abre el navegador, inicias sesión y
   autorizas tu propia cuenta):
   ```
   python tiktok_auth.py
   ```
   Esto guarda `tokens.json` (el `refresh_token` dura ~1 año). Este
   archivo es el que se monta como volumen en el contenedor de Docker.

## Uso manual (sin Docker, para pruebas)

```
python tiktok_bot.py listar                          # top 100 original por vistas
python tiktok_bot.py repost                           # elige al azar, vía Zernio, público
python tiktok_bot.py repost --id 123 --title "Caption" # repost específico
```

## Límites técnicos a tener en cuenta

- 6 llamadas por minuto por access_token de TikTok (límite oficial,
  aplica al listado vía Display API).
- El access_token expira cada 24h; el bot lo refresca automáticamente
  con el refresh_token en cada ejecución.
- Tope de posts por cuenta cada 24h vía API de terceros (~15, puede
  variar) — separado del límite de la app nativa de TikTok.
- Zernio tiene además sus propios límites de requests — ver
  `SETUP_ZERNIO.md`.
