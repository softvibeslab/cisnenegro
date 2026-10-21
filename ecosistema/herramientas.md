# Herramientas y funcionamiento del ecosistema

Este mapa describe los archivos observados en Cisne Negro. Las versiones son las fijadas por el proyecto, no una afirmación de que sean las últimas disponibles.

## Aplicación

| Capa | Implementación | Fuente de verdad |
|---|---|---|
| Interfaz pública | HTML, CSS y JavaScript; assets locales y PWA | `hosting-independiente/sitio/` |
| CMS y publicación | Python, Flask, BeautifulSoup; borrador, vista previa, publicación y versiones | `hosting-independiente/backend/cms_*.py` |
| Operación | Python y SQLite; pedidos, cuentas, equipo, permisos y administración | `hosting-independiente/backend/` |
| MediaHub | Pillow/pillow-heif y FFmpeg/ffprobe; originales, derivados y privacidad | `hosting-independiente/backend/cms_media.py` |
| Proceso web | Gunicorn detrás del proxy; una instancia sobre el volumen SQLite | `hosting-independiente/scripts/start.py` |
| Despliegue actual | Docker Compose y Nginx; HTTPS y respaldo programado | `hosting-independiente/deploy/` |
| Alternativa de servidor limpio | Compose con perfil Caddy | `hosting-independiente/deploy/README.md` |

Python mínimo documentado: 3.11. El entorno validado y la imagen del proyecto usan Python 3.14; la imagen base está fijada por digest en `hosting-independiente/Dockerfile`. El script de respaldo del host requiere Python 3.12 o posterior. Se requiere almacenamiento persistente y una sola instancia escritora sobre las bases SQLite.

Versiones principales fijadas en [`requirements.lock`](../hosting-independiente/requirements.lock): Flask 3.1.3, Gunicorn 23.0.0, BeautifulSoup 4.15.0, Pillow 12.3.0, pillow-heif 1.8.0 y bcrypt 5.0.0. Instalar el archivo completo; esta lista breve no sustituye sus dependencias transitivas.

## Desarrollo local y verificación

```sh
# Desde la raíz del repositorio:
cd hosting-independiente
./iniciar-local.sh
```

Abrir `http://127.0.0.1:8088/`, `/menu/`, `/cms/#editor`, `/admin/` y `/equipo/`. El script crea `.venv` e instala el lock. Las cuentas locales se generan en una carpeta de datos separada, indicada al iniciar; nunca usar ni copiar una base de producción para una prueba rápida.

Pruebas existentes, en otra terminal y desde `hosting-independiente/`:

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
.venv/bin/python -m unittest discover -s deploy -p 'test_*.py' -v
node tests/frontend-security.cjs
node tests/menu-availability.cjs
```

Las pruebas específicas deben elegirse según el cambio. Revisar visualmente el flujo modificado en móvil y escritorio; no presentar la ejecución de una prueba de datos como una revisión de diseño. Los scripts históricos de Playwright requieren su paquete y navegadores en un entorno de desarrollo independiente; no forman parte de las dependencias del servidor.

## Contenido, medios y documentos

| Trabajo | Herramientas observadas | Archivos reproducibles |
|---|---|---|
| Ilustración Colchita | Herramienta integrada imagegen | `hosting-independiente/docs/colchita/README.md`, imagen y referencias |
| Ilustraciones de cervezas anteriores | Render de HTML mediante Playwright | `herramientas/ilustrar-cervezas.cjs` |
| Video hero | Python estándar, FFmpeg y ffprobe | `video-hero/render.py`, `video-hero/fuentes-y-montaje-v2.json` |
| Propuesta PDF | ReportLab y PyMuPDF | `propuesta-economica/generar_pdf.py` |
| Manual PDF | ReportLab, Pillow; revisión con pypdf y Poppler | `manual-usuario/generar_pdf.py` y README |
| Investigación social | Apify, yt-dlp y curl; normalización con Python | `scraping/README.md`, `scraping/scripts/` |

Los generadores de PDF existentes pueden depender de fuentes o rutas locales del entorno original. Antes de ejecutarlos en otra máquina, adaptar esas entradas a archivos disponibles y con permiso de uso; no incluir fuentes comerciales del sistema dentro del repositorio. Para ejecutar el video se necesitan sus originales, cuya disponibilidad se explica en `video-hero/README.md`.

## Qué depende del asistente o de una cuenta externa

- **Codex:** interpreta los `SKILL.md`; sus herramientas integradas de imagen, búsqueda, navegador/computer use y delegación de agentes pertenecen al entorno del asistente. No son ejecutables que este paquete pueda instalar o transferir.
- **imagegen integrada:** es la ruta utilizada para Colchita. La skill incluye una alternativa CLI que necesita dependencias y una API key propia; solo se utiliza si el usuario elige expresamente esa alternativa. No hay claves ni gasto automático al instalar la skill.
- **Navegador:** los accesos y conectores dependen del entorno actual. Usar la interfaz de automatización autorizada; no copiar perfiles, cookies ni sesiones. Si una plataforma restringe la consulta, registrar ese límite y usar fuentes públicas o exportaciones autorizadas.
- **Apify y otras fuentes:** necesitan cuenta, permisos y presupuesto de quien ejecuta. Consultar los scripts y entradas antes de lanzar un actor; no asumir que una herramienta citada en un plan está instalada.
- **Hostinger y DNS:** necesitan acceso autorizado a la cuenta y al servidor del usuario. Los archivos de `deploy/` son configuraciones del proyecto; no conceden acceso a esa infraestructura.
- **GitHub:** requiere autenticación propia para push, releases y administración. Un clon del repositorio no incluye tokens ni la configuración global de Git del autor.

## Entrega y publicación

Conservar el código y las plantillas de ejemplo en Git. Bases de datos, secretos, sesiones, respaldos operativos y datos personales se trasladan por un canal privado independiente, cuando esté autorizado. Antes de publicar: revisar el diff y el destino, ejecutar las verificaciones pertinentes y comprobar que el paquete no contiene material privado. Una solicitud explícita de publicación autoriza esa acción dentro de su alcance; las skills no añaden autorizaciones nuevas.

Para producción seguir la [guía de despliegue](../hosting-independiente/deploy/README.md) y el [estado actual](../hosting-independiente/DESPLIEGUE.md). No repetir una instalación inicial sobre un servidor ya operativo ni sustituir sus datos por los de una demostración local.
