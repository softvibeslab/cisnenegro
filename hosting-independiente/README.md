# Cisne Negro · hosting independiente

Copia de la versión v2 para el dominio `cisnenegro.mx`. **Publicada en https://cisnenegro.mx/ desde el 17 de octubre de 2026** (temporal disponible desde el 10 de octubre en https://cisne.softvibes.art/), dentro del servidor autorizado `31.220.63.211`, con aplicación y datos separados. Ver [estado del despliegue, accesos y cambio DNS](DESPLIEGUE.md).

## Despliegue vigente

El [despliegue](DESPLIEGUE.md) usa Docker Compose detrás del Nginx existente, HTTPS, datos persistentes y respaldo diario verificable. El dominio definitivo tiene DNS y HTTPS activos; el temporal sigue disponible durante la propagación de cachés. El dominio canónico es `https://cisnenegro.mx/`; `www` redirige al dominio sin prefijo. La aplicación comparte el VPS con otros servicios. El modo alternativo Compose + Caddy permanece disponible para trasladarla a un servidor nuevo.

El CMS admite una lista explícita de orígenes para la transición. `PUBLIC_INDEX_HOST=cisnenegro.mx` habilita indexación solamente de las páginas públicas cuando se sirven en ese dominio HTTPS; el temporal, CMS, admin, equipo y APIs permanecen sin indexar. Al cambiar de dominio se vuelve a iniciar sesión.

La importación `scripts/prepare_import.py --data-dir /ruta/privada` regenera las publicaciones con las plantillas v2, adapta URLs e identificadores y conserva el puntero de publicación y el borrador sin publicarlo. Crea un respaldo privado y exige que el destino esté detenido. Se ejecutó sobre las tres publicaciones importadas; la nueva instancia contiene la base operativa v2 y el MediaHub completo.

## Abrir la copia local

Desde esta carpeta:

```sh
./iniciar-local.sh
```

Requisitos: Python 3.11 o posterior y FFmpeg/ffprobe disponibles en PATH. Probado aquí con Python 3.14.7. El script crea su entorno Python aislado e instala las versiones de `requirements.lock`.

| Pantalla | URL local |
|---|---|
| Portada v2 | http://127.0.0.1:8088/ |
| Menú y Pasaporte | http://127.0.0.1:8088/menu/ |
| Editor CMS | http://127.0.0.1:8088/cms/#editor |
| Administración | http://127.0.0.1:8088/admin/ |
| Equipo | http://127.0.0.1:8088/equipo/ |

Usar `127.0.0.1`, como aparece arriba: el CMS comprueba el origen. Para elegir otro puerto: `./iniciar-local.sh --port 8098`.

Los datos persisten fuera del paquete, en `../.hosting-independiente-local/`. Las cuentas se generan en el primer arranque y se conservan; ver `../.hosting-independiente-local/ACCESOS-LOCALES.txt`. CMS y Administración comparten el propietario local. Equipo tiene su administrador y mesero con PIN propio. Las cuentas reales y los socios del servidor **no se copiaron**.

Para detenerlo: Ctrl+C en la terminal que lo inició. No ejecutar dos instancias sobre la misma carpeta de datos. Para una instalación de prueba vacía e independiente, usar `--data-dir /ruta/privada/fuera-del-paquete`.

## Qué incluye

- Portada, menú, panel administrativo, app de equipo, privacidad, assets y PWA de v2, con rutas en la raíz.
- CMS y MediaHub conectados a las plantillas v2, con borradores privados, vista previa, publicación y restauración.
- Un catálogo publicado para la presentación y el cálculo de pedidos. Cambiar precios en borrador no altera pedidos; los importes históricos se conservan.
- Backend operativo real de v2: Pasaporte, pedidos QR, cuentas, registro de cobros, historial y cortes.
- Autenticación de propietario y CSRF en Administración; roles de Equipo independientes; APIs internas no expuestas por el servidor público.
- Procesamiento local de imágenes y video, rutas para medios con acceso controlado y caché limitada al contenido público.
- Arranque local, Dockerfile, plantilla de configuración, versiones de dependencias y pruebas.

La biblioteca copiada para validar localmente contiene **477 medios: 420 imágenes y 57 videos**, con originales, derivados y miniaturas completos. Está en la carpeta privada de datos, no dentro del código ni del ZIP. El CMS local empieza con el contenido de las plantillas v2; no importa los borradores, historial ni usuarios de producción. El Content Hub en desarrollo no se añadió a este entregable.

## Validación

Resultado de esta revisión: **64 pruebas Python y 11 JavaScript aprobadas**, imagen AMD64 desplegada, HTTPS y accesos reales comprobados, respaldo restaurado y reinicio con persistencia. Detalle y límites en [VALIDACION.md](VALIDACION.md) y [DESPLIEGUE.md](DESPLIEGUE.md).

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
.venv/bin/python -m unittest discover -s deploy -p 'test_*.py' -v
node tests/frontend-security.cjs
```

Las pruebas usan bases y archivos temporales. Verifican publicación y precios, roles y CSRF, privacidad de medios, procesamiento real de un MP4, pedido→cuenta→cobro→corte, importación QR sin conexión, cookies, rutas, estado de salud y caché. No escriben en las bases de la copia que estás revisando ni en el VPS.

Revisión manual sugerida: cambiar un título en CMS, revisar el borrador y publicar; cambiar un precio y comprobar menú/pedido; crear un pedido desde el menú y atenderlo con Equipo; subir una fotografía y un video. Todo ocurre en local. El escaneo con cámara requiere un dispositivo/cámara disponible y permiso del usuario; las pruebas automáticas comprueban los datos del QR y su importación.

## Crear el paquete de código

```sh
.venv/bin/python scripts/build_package.py
```

Genera `dist/cisne-negro-hosting.zip` y `dist/SHA256SUMS`. Incluye únicamente código, archivos públicos, configuración de ejemplo y pruebas. Excluye entorno Python, datos, cuentas locales, registros y credenciales. No es un ZIP para `public_html`: necesita un hosting que ejecute la aplicación.

La carpeta privada de prueba no debe subirse como si fueran datos finales del negocio. Antes del corte se necesita una exportación consistente de las bases **activas de v2**, del CMS publicado y de los medios; resolver las revisiones guardadas del CMS anterior para que rendericen v2 sin publicar borradores por accidente. No sustituir usuarios/socios/pedidos reales con las cuentas u operaciones de prueba.

## Arranque en hosting compatible

El contenedor sirve un puerto web detrás del proxy, inicia internamente el CMS y el backend operativo y usa un solo volumen persistente. No requiere el VPS anterior. La imagen se construyó y ejecutó en Linux ARM64 local, incluyendo acceso, rutas y persistencia después de reiniciar. El proveedor de destino requiere su propia comprobación.

1. Elegir hosting con Python/contenedores, FFmpeg, volumen persistente y procesos permanentes. Los requisitos completos están en `../plan-hosting-independiente-v2.md`.
2. Configurar los valores de `.env.example` en el gestor privado del hosting. El archivo es una plantilla; el launcher no carga archivos `.env` automáticamente.
3. Montar el volumen en `/var/data`, escribible por el usuario UID 10001. Colocar allí `cms/` y `club.db` de la migración final, fuera de `/app`.
4. Definir `CMS_ORIGIN=https://cisnenegro.mx`, `CLUB_SECRET` y `CLUB_ADMIN_TOKEN` aleatorios de al menos 32 caracteres. Se conservan las claves operativas necesarias de la migración por un canal privado; nunca se incluyen en la imagen.
5. Construir la imagen con `docker build -t cisne-negro-hosting .` y ejecutar con variables/volumen. El comando del contenedor ya utiliza `--production`; exige HTTPS configurado y secretos sin valores por defecto. No crea cuentas locales en ese modo.
6. Para una base nueva sin cuentas: definir temporalmente `CMS_BOOTSTRAP_USER` y `CMS_BOOTSTRAP_PASSWORD` (mínimo 12 caracteres) para crear el primer propietario y retirarlos después. Si se importan usuarios existentes, se conservan.
7. Para una base de Equipo nueva: ejecutar `python scripts/create_team.py --data-dir /var/data --usuario propietario --nombre 'Responsable de Cisne Negro' --rol admin` en una terminal privada del contenedor e introducir el PIN. Con una base operativa importada, conservar sus usuarios.
8. El proxy HTTPS del hosting debe sobrescribir `X-Forwarded-For` y `X-Forwarded-Proto`; publicar solo el puerto web. El backend operativo escucha en loopback. Verificar `/healthz`, roles, subidas de 100 MB y tiempo de procesamiento antes del corte.
9. Usar una única instancia con SQLite y el volumen. Una arquitectura con réplicas exige cambiar almacenamiento y concurrencia. Configurar copias consistentes, externas al hosting y con restauración ensayada.

## Pendientes operativos

Probar cámara/QR y PWA en teléfonos, confirmar contenidos/aviso de privacidad y completar la réplica externa periódica de respaldos. El contenedor, la copia de datos, los accesos y las redirecciones están verificados en el servidor autorizado. La plantilla de despliegue habilita indexación solo en `cisnenegro.mx` HTTPS; el dominio temporal y los paneles mantienen `noindex`. El origen canónico, TLS y DNS ya están verificados; los registros del correo se conservaron. Algunas cachés aún pueden mostrar el sitio anterior.

Las fuentes y bases originales se conservaron. El despliegue creó su propia copia; el 17 de octubre se conectó el dominio definitivo mediante los dos registros web de Squarespace. Usar la nueva instancia para los próximos cambios; no sincroniza automáticamente sus datos con la anterior.
