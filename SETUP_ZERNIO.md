# Setup de Zernio para el bot de TikTok

Guía separada solo para dejar Zernio listo. Para el resto del bot (descarga,
selección de video, marcador de repost), ver el `README.md` principal.

## Qué es y por qué esta opción

Zernio es un servicio de terceros (no de TikTok) que ya pasó la auditoría
"Direct Post" de TikTok con su propia app — por eso puede publicar
`PUBLIC_TO_EVERYONE` en tu cuenta desde el primer post, sin que tú tengas
que pasar por la revisión de TikTok. Su tier gratuito es real: primeras 2
cuentas conectadas, posts ilimitados, sin tarjeta de crédito.

## ⚠️ Antes de empezar: una advertencia real

Encontré una reseña en Trustpilot (la empresa se llamaba "Late" antes de
rebrandearse a Zernio) que alega que el acceso a las cuentas conectadas
persistió incluso después de desconectarlas y borrar los datos desde su
dashboard: https://www.trustpilot.com/review/zernio.com

No pude verificar esto de forma independiente — es una sola reseña — pero
es información real que deberías considerar. La mitigación que sí está
bajo tu control:

**Revoca el acceso también desde el lado de TikTok**, no solo desde el
dashboard de Zernio. Eso invalida el token de raíz sin importar lo que
haga el tercero:

> Perfil → ☰ → Settings and privacy → Security and login → Manage app
> permissions → busca "Zernio" (o "Late") → Remove access

Revisa esa pantalla cada tanto mientras uses el bot.

## Paso 1: Crear cuenta y conectar TikTok

1. Ve a https://zernio.com y crea una cuenta (no pide tarjeta para el
   tier gratuito).
2. En el dashboard, crea un "profile" (o usa el que viene por default) —
   es solo un grupo organizador de cuentas, por ejemplo "Mi TikTok".
3. Conecta tu cuenta de TikTok desde el dashboard (botón "Connect
   account" → TikTok). Esto hace el OAuth por ti; no necesitas registrar
   ninguna app en TikTok for Developers.
4. (Opcional) Si además quieres que el bot publique en otras redes con
   `--also`, conecta esas cuentas también aquí (Instagram, YouTube, etc.
   — cuentan contra tu límite de 2 cuentas gratis).

## Paso 2: Generar el API key

1. En el dashboard de Zernio, ve a **Settings > API Keys** (o
   "Developers", según la versión de la UI).
2. Genera un API key. Empieza con `sk_` seguido de 64 caracteres
   hexadecimales.
3. Guárdalo en un lugar seguro — no se puede volver a ver completo
   después de generado en la mayoría de estos paneles.

## Paso 3: Configurar el bot

1. Copia `config.example.json` a `config.json` si no lo has hecho.
2. Pega tu API key:
   ```json
   {
     "zernio_api_key": "sk_tu_key_aqui",
     "zernio_profile_id": ""
   }
   ```
3. Deja `zernio_profile_id` vacío la primera vez — el bot detecta
   automáticamente tu primer perfil existente (o crea uno llamado
   "TikTok Bot" si no tienes ninguno). Si más adelante quieres fijar un
   perfil específico (por ejemplo si manejas varios), pon aquí su `id`.

## Paso 4: Probar

```
python tiktok_bot.py listar
python tiktok_bot.py repost --via zernio
```

Si todo está bien conectado, el segundo comando: elige un video al azar
de tu top 100 **original** (excluyendo reposts anteriores del bot), lo
descarga, lo sube a Zernio, y lo publica en TikTok como público de
inmediato — marcado internamente con el carácter invisible para que no
se vuelva a elegir como fuente de otro repost.

## Límites del tier gratuito a tener en cuenta

- Primeras 2 cuentas conectadas: gratis, posts ilimitados.
- Cuenta adicional (3ra en adelante): $6/mes cada una.
- Rate limit publicado: 60 req/min en el tier gratis (sube a 1200 req/min
  en tiers pagos, no es relevante para uso personal).
- TikTok tiene además su propio límite diario de posts vía API de
  terceros, separado del límite de la app nativa — si lo alcanzas, solo
  puedes esperar o publicar manualmente desde la app ese día.

## Si algo falla

- **"No hay ninguna cuenta de TikTok conectada"**: revisa que la
  conexión en el paso 1 siga activa (Zernio dashboard → Accounts →
  estado "healthy").
- **Error 401 / invalid_api_key**: regenera el API key en el dashboard y
  actualiza `config.json`.
- **Error de privacidad rechazada**: el nivel de privacidad que pediste
  (`--privacy`) no está entre las opciones que tu cuenta de TikTok
  permite actualmente. Prueba con `PUBLIC_TO_EVERYONE` o revisa tu
  configuración de privacidad en la app de TikTok.
