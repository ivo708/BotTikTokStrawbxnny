# Imagen del bot de repost de TikTok. Corre scheduler.py, que ejecuta
# `tiktok_bot.py repost` cada REPOST_INTERVAL_HOURS horas (default: 8).
#
# IMPORTANTE: config.json y tokens.json NO se incluyen en la imagen (ver
# .dockerignore). Se montan como volumenes en tiempo de ejecucion, para no
# hornear credenciales en ninguna capa de la imagen. tokens.json se genera
# corriendo tiktok_auth.py *fuera* de Docker (necesita abrir un navegador),
# una sola vez - ver el README principal.

FROM python:3.11-slim

WORKDIR /app

# Dependencias primero, para aprovechar la cache de Docker en rebuilds
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Codigo del bot
COPY tiktok_bot.py .
COPY scheduler.py .
COPY download_helper.py .
COPY zernio_client.py .

# Carpeta donde se guardan los .mp4 descargados (se monta como volumen)
RUN mkdir -p /app/videos

# Defaults - se pueden sobreescribir en docker-compose.yml o `docker run -e`
ENV REPOST_INTERVAL_HOURS=8 \
    REPOST_VIA=zernio \
    REPOST_PRIVACY=PUBLIC_TO_EVERYONE \
    REPOST_ALSO="" \
    RUN_ON_START=true \
    ALWAYS_POST_ON_START=false \
    REPOST_MARKER_CODEPOINT=267B \
    PYTHONUNBUFFERED=1

CMD ["python", "scheduler.py"]
