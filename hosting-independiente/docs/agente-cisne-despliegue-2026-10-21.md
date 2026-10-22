# Agente Cisne · despliegue del 21 de octubre de 2026

El botón flotante y popup del CMS están desplegados y conectados al perfil Hermes **`cisne-negro`**. Acceso verificado: **[https://cisne.softvibes.art/cms/](https://cisne.softvibes.art/cms/)**. Se utilizan las cuentas existentes del CMS de producción; los accesos locales no sustituyen esas cuentas.

Una consulta real utilizó `read_content` y respondió con información del CMS. El borrador **5** y la publicación **8** permanecieron intactos. El agente se encuentra en las secciones autenticadas del CMS; la carta pública `/menu/` conserva su experiencia para clientes.

## Alcance y pendientes

- Chat: `configured=true`, `provider=hermes`, perfil `cisne-negro`, modelo `gpt-6-astra`.
- CRUD editorial implementado y probado; las operaciones guardan borradores con control de versión. La verificación en producción fue de lectura.
- Imágenes: `image_configured=false`; falta configurar la API y verificar una generación real desde etiqueta.
- Telegram: gateway no iniciado; requiere bot exclusivo, operadores permitidos y cuenta editorial.
- GitHub: al realizar este despliegue, la actualización todavía no se había enviado. El código se entregó después en la rama `feat/agente-cisne-cms-hermes`; la preparación posterior del perfil remoto no está desplegada.
- Dominio canónico: incidencia DNS separada, descrita más adelante. No se modificaron DNS en esta entrega.

## Instalación

| Componente | Ruta / identificación |
|---|---|
| Servidor | `31.220.63.211` |
| Código de aplicación | `/srv/cisne/app/` |
| Datos persistentes | `/srv/cisne/data/` |
| Configuración privada | `/etc/cisne/app.env` |
| Compose | `/srv/cisne/app/deploy/compose.yaml` y `compose.override.yaml` |
| Imagen activa | `cisne-independent:local` |
| Imagen anterior | `cisne-independent:before-agent-20261021` |
| Servicio host | `cisne-hermes.service`, activo y habilitado |
| Identidad del proceso | Usuario `cisneagent`, grupo numérico `10001` |
| Código del bridge y worker | `/srv/cisne/hermes/backend/` |
| Perfil Hermes | `/srv/cisne/hermes/profiles/cisne-negro/` |
| Instalación Hermes | `/usr/local/lib/hermes-agent/` |
| Commit Hermes validado | `d62716c7043e57ef7a29e81a02ddbc19334e29df` |
| Socket host → contenedor | `/srv/cisne/hermes/run/bridge.sock` → `/run/cisne-hermes/bridge.sock` |

`compose.override.yaml` es la copia operativa de [`deploy/compose.hermes.yaml`](../deploy/compose.hermes.yaml). Conserva el volumen de datos y monta únicamente el directorio del socket en modo de solo lectura. El perfil, la autenticación y el código Hermes del host no se montan en Docker. La autenticación limitada al proveedor elegido para Cisne permanece dentro de su perfil privado.

El bridge utiliza socket Unix, dos solicitudes simultáneas, procesos sin shell, entorno filtrado y herramientas editoriales permitidas. El CMS ejecuta cada operación con la sesión del usuario; el worker Hermes no publica ni ejecuta herramientas de desarrollo. El servicio no modifica las instalaciones ni perfiles de otros proyectos.

Los cambios de base consisten en tablas aditivas para solicitudes y trabajos de imagen. No se reemplazaron datos operativos, semilla del menú, usuarios, borradores o publicaciones; no se ejecutó una importación editorial.

## Respaldos y validación

- Código y configuración previos: `/srv/cisne/backups/agente-popup-20261021/`.
- Imagen anterior conservada: `cisne-independent:before-agent-20261021`.
- Datos: `/var/backups/cisne/cisne-20261021T234927775687Z.tar.gz`, con restauración de verificación: **1,448 archivos y 479 medios**.
- **108 pruebas Python** de aplicación aprobadas, incluido el bridge Unix y las restricciones del worker.
- Verificaciones previas de esta implementación: **22 comprobaciones de interfaz**, **17 del cliente Hermes** y **11 JavaScript** de seguridad/caché.
- Consulta real del modelo en producción y estado de configuración autenticado verificados. Sin cambios editoriales durante la prueba: borrador 5 y publicación 8.
- Popup revisado visualmente en Chrome sobre producción; respondió con productos del borrador. Evidencia autenticada conservada de forma privada, fuera de Git.
- Alias temporal con TLS válido; dominio canónico con HTTP 200 al conectar directamente a `31.220.63.211` usando SNI y validación del certificado.

Las pruebas automatizadas usan datos temporales y proveedores simulados. No equivalen a una prueba de generación real de imagen ni de Telegram; ambas quedan pendientes.

## Incidencia del dominio canónico

Al cierre, la resolución pública de `cisnenegro.mx` devuelve **`SERVFAIL`**. Las cuatro autoridades `ns-cloud-b*.googledomains.com` rechazan las consultas con **`REFUSED`**, mientras la delegación de `.mx` sigue apuntando a ellas. La consulta del registrador muestra **Registrar.eu / Openprovider**; Hostinger muestra la transferencia en **Error** y el acceso al dominio en su cartera devuelve **404**.

Estos resultados muestran una delegación/zona sin servicio coherente; cambiar únicamente un registro A dentro de una zona inaccesible no resolvería la delegación. Primero se debe reconciliar con Hostinger el estado de transferencia y la gestión de la zona, y después validar o ajustar los servidores de nombres y registros. Conservar los registros de correo y verificaciones existentes. No se hicieron cambios DNS durante el despliegue del agente.

El alias `cisne.softvibes.art` permanece disponible con HTTPS. La aplicación, el vhost canónico y su certificado responden correctamente por conexión directa con SNI. El incidente no se debe al popup ni a la reconstrucción del contenedor.

## Comprobaciones operativas

Comandos sin salida de secretos:

```sh
cd /srv/cisne/app/deploy
sudo docker compose config --quiet
sudo docker compose ps
sudo systemctl is-active cisne-hermes
sudo systemctl is-enabled cisne-hermes
curl --fail https://cisne.softvibes.art/healthz
curl --fail --resolve cisnenegro.mx:443:31.220.63.211 https://cisnenegro.mx/healthz
```

Abrir el CMS temporal, iniciar sesión y pulsar **Agente Cisne**. Pedir una consulta de contenido para comprobar el modelo sin generar una edición. No imprimir `docker compose config` sin `--quiet`, archivos de entorno, autenticación ni cookies.

## Revertir únicamente el código

Si se necesita volver a la aplicación anterior, conservar primero la imagen actual con otra etiqueta y volver a apuntar `local` a la imagen previa. Los comandos recrean únicamente `app`; mantienen el volumen, las cuentas y el contenido actual:

```sh
sudo docker image inspect cisne-independent:before-agent-20261021 --format '{{.Id}}'
sudo docker image tag cisne-independent:local cisne-independent:agent-20261021
sudo docker image tag cisne-independent:before-agent-20261021 cisne-independent:local
cd /srv/cisne/app/deploy
sudo docker compose up -d --no-build --force-recreate app
curl --fail https://cisne.softvibes.art/healthz
```

Comprobar acceso al CMS y carta pública. El código anterior ignora las tablas aditivas del agente; **no restaurar la base para una reversión de código**. El bridge puede detenerse después si ya no se utiliza: `sudo systemctl stop cisne-hermes`. Conservar el respaldo de código/configuración para una investigación o restauración completa y no ejecutar una nueva compilación hasta decidir qué fuentes deben permanecer activas.

Para recuperar la imagen del agente guardada durante esa reversión, volver a etiquetarla como `local`, iniciar el bridge y recrear la aplicación:

```sh
sudo docker image tag cisne-independent:agent-20261021 cisne-independent:local
sudo systemctl start cisne-hermes
cd /srv/cisne/app/deploy
sudo docker compose up -d --no-build --force-recreate app
curl --fail https://cisne.softvibes.art/healthz
```

Una restauración de datos solo corresponde a una pérdida o corrupción confirmada y requiere detener la aplicación, conservar el estado presente y seguir el procedimiento de respaldos existente. No es parte de estos comandos de reversión.
