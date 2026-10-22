# Cisne Negro · despliegue publicado

Publicado el 10 de octubre de 2026 en el servidor autorizado `31.220.63.211`.

**Estado actual — 21 de octubre de 2026:** Agente Cisne desplegado y conectado al perfil Hermes `cisne-negro`, con consulta real de contenido verificada y sin cambios editoriales. Acceso disponible: **https://cisne.softvibes.art/cms/**. El dominio canónico `cisnenegro.mx` devuelve `SERVFAIL` por una incidencia de delegación/zona DNS; la aplicación y su TLS responden al conectar directamente al servidor con SNI. Se necesita reconciliar dominio y zona con Hostinger antes de ajustar DNS. Este despliegue no modificó registros DNS. Ver [instalación del agente, respaldos, pruebas y reversión](docs/agente-cisne-despliegue-2026-10-21.md). Las notas del 10 y 17 de octubre que siguen son el historial previo.

**Actualización del 17 de octubre:** publicado en `https://cisnenegro.mx/`, con `www` redirigiendo al dominio principal. El usuario completó la verificación de Squarespace; se sustituyeron los dos registros web por A hacia `31.220.63.211`, TTL 300. Los cuatro servidores autoritativos confirman el cambio. El certificado HTTPS está emitido y las rutas y accesos fueron verificados. Algunas cachés recursivas y el navegador local todavía muestran el sitio anterior mientras caduca su TTL previo de cuatro horas.

| Pantalla | Dirección |
|---|---|
| Portada v2 | https://cisnenegro.mx/ |
| Menú y Pasaporte | https://cisnenegro.mx/menu/ |
| CMS y MediaHub | https://cisnenegro.mx/cms/#editor |
| Administración | https://cisnenegro.mx/admin/ |
| Equipo | https://cisnenegro.mx/equipo/ |

Es una instalación separada de aplicación, datos, configuración y respaldos dentro del mismo VPS. Conserva las cuentas del CMS anterior y del equipo v2. Los accesos existentes están en `../PRIVADO/credenciales-panel.txt` y `../PRIVADO/demo-equipo-v2.txt`; los usuarios de Equipo provienen del entorno de demostración v2. No se crearon ni publicaron contraseñas nuevas.

Usar el CMS y Equipo de **cisnenegro.mx** para los próximos cambios. `cisne.softvibes.art` sigue siendo un acceso temporal a esta misma instalación y sus mismos datos. Las instalaciones anteriores de `cisnenegro.softvibes.art` tienen bases distintas; no sincronizan automáticamente sus cambios y sus servicios siguen disponibles.

## Instalación

- Código: `/srv/cisne/app/`.
- Datos persistentes: `/srv/cisne/data/` (UID/GID 10001, fuera del código).
- Configuración privada: `/etc/cisne/app.env`.
- Compose: `/srv/cisne/app/deploy/compose.yaml`, proyecto `cisne-independent`.
- Aplicación: contenedor `cisne-independent-app-1`, reinicio `unless-stopped`, puerto del host `127.0.0.1:8888`.
- Entrada HTTPS: Nginx del host, vhost propio `/etc/nginx/sites-available/cisne.softvibes.art`.
- Certificado Let's Encrypt válido hasta el 8 de enero de 2027, con renovación automática de Certbot y hook de recarga de Nginx para estos dominios.

El 10 de octubre Hostinger recibió únicamente el registro `A cisne → 31.220.63.211`, TTL 300; el resto de `softvibes.art` permaneció igual. El 17 de octubre se cambiaron en Squarespace únicamente los registros web de `cisnenegro.mx`. Se compararon los cinco MX, los dos TXT, `mytaps` y `_domainconnect` contra la instantánea previa: permanecen iguales en las cuatro autoridades.

## Importación y comprobación

Se creó una instantánea consistente mediante una pausa breve del CMS y del backend v2 originales, que después volvieron a estar activos. Se copiaron 2 socios, 3 cuentas de equipo y 4 pedidos de la base v2; 2 usuarios, 3 publicaciones y el borrador del CMS; y los 477 medios completos. No se fusionó la base operativa del sitio raíz anterior con v2.

Las publicaciones se regeneraron sobre las plantillas v2 conservando la revisión publicada 3 y el borrador. Se adaptaron los identificadores de productos al menú v2 y se conservaron las variantes de agua mineral y chips de camote, sin sustituir precios editoriales ni importes de pedidos. Existe respaldo de la base previa a la adaptación en la carpeta privada de datos.

Comprobado por HTTPS: portada, menú, CMS, equipo, privacidad, video, estado de salud, inicio de sesión del propietario, administración, inicio de sesión del equipo, 49 productos y 477 medios. Safari mostró correctamente portada, menú y pantalla de acceso del CMS. El dominio temporal sigue sin indexación.

Pruebas automatizadas locales: 46 de aplicación/importación, 15 de despliegue/respaldo y 11 de JavaScript. La imagen se construyó en Linux AMD64 en el VPS y el contenedor pasó su comprobación de salud y el reinicio del respaldo.

## Respaldos

`cisne-independent-backup.timer` ejecuta el respaldo diario a las **03:55 de Ciudad de México**, con retención de 14 archivos. Copia SQLite y medios con la aplicación brevemente detenida; la reinicia antes de comprimir y ensaya una restauración temporal comprobando SHA-256, integridad de las tres bases y medios.

Primera copia verificada: `/var/backups/cisne/cisne-20261010T134858435313Z.tar.gz`, 1,442 archivos y 477 medios listos. La configuración privada tiene una copia separada en `/var/backups/cisne-config/app.env`.

La copia externa inicial se conserva en `../PRIVADO/hosting-independiente/`, junto con la configuración necesaria para restaurar. Los respaldos diarios posteriores permanecen en el VPS: todavía no hay una réplica externa periódica configurada.

## Cambio al dominio definitivo

Registros web guardados y comprobados en Squarespace:

| Tipo | Nombre | Destino | TTL sugerido |
|---|---|---|---|
| A | @ | 31.220.63.211 | 300 |
| A | www | 31.220.63.211 | 300 |

Sustituir los registros web anteriores, incluido el CNAME `www` de Squarespace, y quitar cualquier AAAA web que apunte a otra máquina. Mantener los registros del correo y sus verificaciones.

El vhost final está activo. `activate_final.py` completó la emisión y activación tras comprobar ambos dominios. El certificado de `/etc/letsencrypt/live/cisne-final/` cubre apex y `www`, vence el 16 de enero de 2027 y utiliza la renovación automática de Certbot con recarga de Nginx. El temporizador de activación permanece idempotente.

`https://cisnenegro.mx/` sirve esta instalación; `https://www.cisnenegro.mx/` y HTTP redirigen al dominio principal conservando ruta y parámetros, comprobado con `/menu/?mesa=1`. Las páginas públicas del dominio definitivo pueden indexarse; CMS, admin, equipo y APIs permanecen excluidos. Hay que volver a iniciar sesión al cambiar de dominio.

La adaptación configura `CMS_ORIGIN=https://cisnenegro.mx` y `PUBLIC_INDEX_HOST=cisnenegro.mx`, manteniendo los tres orígenes permitidos. Normaliza canonical, metadatos sociales y URLs propias de datos estructurados al servir páginas públicas sin modificar borradores ni bases editoriales. Pasaron 75 pruebas. Por HTTPS público desde el VPS se comprobaron portada, menú, CMS, equipo, privacidad, video, salud, robots y sitemap. Desde el equipo local, conectando a la IP nueva con SNI y certificado validado de `cisnenegro.mx`, se verificaron inicio de sesión CMS, Administración y MediaHub; el acceso administrativo anónimo devolvió 401 y se cerró la sesión de ensayo. El temporal conserva HTTPS y `noindex`.

Reversión del cambio de dominio: configuración y fuentes previas en `/var/backups/cisne-domain-20261017/`, e imagen `cisne-independent:before-apex-20261017`. Instantánea de los DNS originales en `../PRIVADO/hosting-independiente/dns-before-20261017.json`. Se deben conservar Google Workspace, sus verificaciones, `mytaps` y `_domainconnect` al sustituir únicamente los dos registros web.

Estado al cierre del **17 de octubre**: dominio definitivo y HTTPS activos; propagación de cachés todavía parcial. En ese momento no hacía falta volver a modificar DNS. La instantánea posterior de verificación está en `../PRIVADO/hosting-independiente/dns-after-20261017.json`. La incidencia y el despliegue posteriores del 21 de octubre se documentan al inicio de este archivo.
