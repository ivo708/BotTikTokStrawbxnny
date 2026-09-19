# Instalación desde cero (Windows sin nada instalado)

Guía pensada para una PC con Windows recién formateada, sin Python, sin
Git, sin Docker y sin nada del proyecto. Sigue los pasos en orden.

## 1. Instalar Python

1. Ve a https://www.python.org/downloads/ y descarga la última versión
   de Python 3 (3.11 o superior).
2. Ejecuta el instalador. **Muy importante:** marca la casilla
   **"Add python.exe to PATH"** antes de darle a "Install Now".
3. Verifica la instalación abriendo PowerShell y ejecutando:
   ```powershell
   python --version
   pip --version
   ```
   Si ambos comandos muestran una versión, quedó bien instalado.

## 2. Instalar Git (para descargar/clonar el proyecto)

1. Descarga Git desde https://git-scm.com/download/win
2. Instala con las opciones por defecto.
3. Verifica en PowerShell:
   ```powershell
   git --version
   ```

> Si ya tienes la carpeta del proyecto copiada (por ejemplo por USB o
> ZIP) en vez de clonarla con Git, puedes saltarte este paso.

## 3. Instalar Docker Desktop

El bot corre en Docker, así que necesitas Docker Desktop para Windows.

1. Descarga desde https://www.docker.com/products/docker-desktop/
2. Ejecuta el instalador. Si te pide activar **WSL 2**, acepta — Docker
   Desktop te guiará para instalarlo (puede pedir reiniciar el PC).
   - Si el instalador de Docker no lo hace automáticamente, instala WSL2
     manualmente desde PowerShell **como administrador**:
     ```powershell
     wsl --install
     ```
     y reinicia el PC.
3. Abre Docker Desktop y espera a que el ícono de la ballena (en la
   bandeja del sistema) indique que está corriendo.
4. Verifica en PowerShell:
   ```powershell
   docker --version
   docker compose version
   ```

## 4. Instalar ngrok (solo se usa para autenticar con TikTok)

TikTok exige que la Redirect URI de OAuth sea `https://`, pero el script
de autenticación de este proyecto corre un servidor local sin
certificado. ngrok crea un túnel https hacia ese servidor local. **No
corre todo el tiempo** — solo lo usas los minutos en que autorizas tu
cuenta (paso 10).

1. Crea una cuenta gratis en https://dashboard.ngrok.com/signup
2. Descarga ngrok desde https://ngrok.com/download e instálalo.
3. Copia tu authtoken desde https://dashboard.ngrok.com/get-started/your-authtoken
   y configúralo en PowerShell:
   ```powershell
   ngrok config add-authtoken TU_AUTHTOKEN_AQUI
   ```
4. Reserva tu **dominio estático gratuito** (1 incluido en el plan free,
   no cambia nunca — así solo tienes que configurar la Redirect URI una
   sola vez, incluso si reautenticas dentro de varios meses):
   - Ve a https://dashboard.ngrok.com/domains → "New Domain" → cópialo
     (algo como `tu-nombre-fijo.ngrok-free.app`).

No lo levantes todavía — eso se hace en el paso 10.

## 5. Obtener el proyecto

Si aún no tienes la carpeta `BotTikTok` en el equipo:

```powershell
git clone <url-del-repositorio> BotTikTok
cd BotTikTok
```

Si ya la copiaste manualmente, solo entra a la carpeta:

```powershell
cd "C:\ruta\donde\pusiste\BotTikTok"
```

## 6. Instalar las dependencias de Python (solo para el paso de autenticación)

Docker instala sus propias dependencias dentro del contenedor, pero
necesitas Python localmente **una sola vez** para generar `tokens.json`
(ese paso abre un navegador y no puede correr dentro de Docker).

```powershell
pip install -r requirements.txt
```

## 7. Crear una app de TikTok

1. Entra a https://developers.tiktok.com/apps y crea una app (necesitas
   una cuenta de desarrollador de TikTok).
2. Añade los productos **Login Kit** y **Content Posting API**.
3. Anota el `client_key` y el `client_secret` que te da TikTok.

### 7.1. Alojar el ToS y la Privacy Policy (obligatorios, incluso en Sandbox)

TikTok pide una URL de **Terms of Service**, una de **Privacy Policy** y
una **Web/Desktop URL** para guardar la app, aunque sea de uso personal.
Estas URLs quedan **públicas en internet** (cualquiera con el link puede
verlas, aunque no aparezcan en buscadores) — es un requisito de TikTok,
no se puede evitar. En la carpeta `legal/` de este proyecto ya hay tres
páginas HTML listas (`index.html`, `terms-of-service.html`,
`privacy-policy.html`) con textos adaptados a lo que hace este bot.

1. Abre esos tres archivos y reemplaza `tu-email@ejemplo.com` por un
   correo de contacto real (quedará público) — el proyecto ya trae el
   tuyo puesto (`ivanrojmer@gmail.com`); cámbialo si prefieres otro.
2. Súbelos gratis con **GitHub Pages**, sin usar comandos de git (todo
   por la web):
   - Si no tienes cuenta de GitHub, créala gratis en
     https://github.com/join
   - Ve a https://github.com/new y crea un repositorio **público**
     (por ejemplo `bottiktok-legal`). No hace falta que sea el mismo
     repo del bot — puede ser uno aparte solo para estas 3 páginas.
   - Dentro del repo, click en **"Add file" → "Upload files"** y
     arrastra los 3 archivos de la carpeta `legal/`
     (`index.html`, `terms-of-service.html`, `privacy-policy.html`).
     Click "Commit changes".
   - Ve a **Settings → Pages**. En "Build and deployment → Source"
     elige **"Deploy from a branch"**, rama `main`, carpeta `/ (root)`,
     y dale **Save**.
   - Espera ~1 minuto y recarga la página: te dará la URL pública, algo
     como `https://tu-usuario.github.io/bottiktok-legal/`.
3. Usa esa URL en el formulario de TikTok:
   - **Web/Desktop URL**: `https://tu-usuario.github.io/bottiktok-legal/`
   - **Terms of Service URL**: `https://tu-usuario.github.io/bottiktok-legal/terms-of-service.html`
   - **Privacy Policy URL**: `https://tu-usuario.github.io/bottiktok-legal/privacy-policy.html`
4. También necesitarás un **App icon** (1024x1024, JPG/PNG, hasta 5MB) —
   cualquier imagen simple sirve, ya que es de uso personal.

> Si al abrir la URL de GitHub Pages te pide iniciar sesión o una
> contraseña, revisa que el repositorio sea **público** (no privado) en
> Settings → General → "Danger Zone" → visibilidad. Un repo privado
> requiere GitHub Pro para publicar Pages accesibles sin login.

### 7.2. Configurar la Redirect URI

En el campo Redirect URI del Developer Portal, pon tu dominio fijo de
ngrok (del paso 4) más `/callback`:

```
https://tu-nombre-fijo.ngrok-free.app/callback
```

Esto **se guarda igual aunque ngrok no esté corriendo en este momento**
— TikTok solo valida que el texto tenga formato `https://` al guardar el
formulario. Solo necesitas que ngrok esté realmente levantado cuando
ejecutes `tiktok_auth.py` en el paso 10.

Usa esa misma URL completa en el campo `redirect_uri` de tu
`config.json` (paso 9).

## 8. Configurar Zernio (vía de publicación gratuita recomendada)

Sigue la guía completa del proyecto: **[`SETUP_ZERNIO.md`](./SETUP_ZERNIO.md)**.
De ahí obtendrás `zernio_api_key` y `zernio_profile_id`.

## 9. Crear los archivos de configuración

Copia las plantillas y rellena tus datos:

```powershell
copy config.example.json config.json
copy .env.example .env
```

Edita `config.json` con un editor de texto (Notepad, VS Code, etc.) y
completa:
- `client_key` y `client_secret` (de TikTok, paso 7)
- `redirect_uri`: tu URL de ngrok + `/callback` (paso 7.2)
- `zernio_api_key` y `zernio_profile_id` (de Zernio, paso 8)

Edita `.env` si quieres cambiar el intervalo de reposts u otras
opciones (todas están documentadas dentro del archivo).

## 10. Generar el token de acceso de TikTok

Este es el único momento en que necesitas ngrok realmente levantado.
Abre **dos** ventanas de PowerShell:

**Ventana A** — deja el túnel corriendo:
```powershell
ngrok http --url=tu-nombre-fijo.ngrok-free.app 8080
```

**Ventana B** — corre la autenticación (abre el navegador para que
inicies sesión y autorices tu propia cuenta):
```powershell
python tiktok_auth.py
```

Esto crea `tokens.json`, válido por ~1 año (se refresca solo). Una vez
que veas el mensaje "Tokens guardados en tokens.json", puedes cerrar
ambas ventanas — **de aquí en adelante no vuelves a necesitar ngrok**
para nada del funcionamiento normal del bot (el contenedor de Docker
solo usa el `refresh_token`, ya guardado en `tokens.json`).

Solo tendrás que repetir este paso 10 (con ngrok otra vez) si dentro de
~1 año el `refresh_token` expira y necesitas reautenticar — como
reservaste un dominio fijo en el paso 4, la Redirect URI seguirá siendo
la misma y no hay que tocar nada en el Developer Portal.

## 11. Crear el archivo de estado vacío

Docker necesita que este archivo exista de antemano para poder montarlo
como volumen:

```powershell
New-Item -ItemType File -Name repost_state.json -Force
```

(o si usas la terminal de Git Bash / WSL: `touch repost_state.json`)

## 12. Levantar el bot con Docker

```powershell
docker compose up -d --build
```

Verifica que está corriendo y sigue los logs en vivo:

```powershell
docker compose logs -f
```

Esto ya corre 24/7 sin ngrok ni Python locales — solo Docker Desktop
necesita estar abierto.

## Comandos útiles después de instalado

```powershell
docker compose restart          # reiniciar (por ejemplo tras editar .env)
docker compose down             # parar y eliminar el contenedor (los volúmenes se conservan)
docker compose up -d --build    # volver a levantar
```

## Resumen de todo lo que se instaló

| Herramienta | Para qué sirve | ¿Corre 24/7? |
|---|---|---|
| Python 3.11+ | Correr `tiktok_auth.py` (autenticación única) y las dependencias en `requirements.txt` | No, solo durante el paso 10 |
| Git | Descargar/actualizar el código del proyecto | No |
| Docker Desktop (con WSL2) | Correr el bot de forma continua con el scheduler | Sí, mientras quieras que el bot funcione |
| ngrok | Exponer `tiktok_auth.py` con https para el login de TikTok | No, solo durante el paso 10 (o al reautenticar) |

Si algo falla, revisa primero `README.md` (setup general) y
`SETUP_ZERNIO.md` (configuración de Zernio), que tienen el detalle de
cada paso de configuración específico del bot.
