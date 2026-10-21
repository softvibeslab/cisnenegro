# Despliegue independiente de Cisne Negro

Aplicación y datos separados del sitio anterior. Un servidor nuevo proporciona independencia del VPS anterior; ejecutar este paquete en el mismo VPS proporciona aislamiento de aplicación, pero comparte servidor y disponibilidad. Estas instrucciones no ejecutan cambios ni contienen credenciales.

**Instalación vigente:** publicada en https://cisnenegro.mx/ (temporal https://cisne.softvibes.art/) sobre `31.220.63.211`, con Docker y Nginx. Los temporizadores de respaldo y activación final ya están instalados. Ver [registro del despliegue](../DESPLIEGUE.md) antes de ejecutar instrucciones de instalación inicial.

El modo recomendado para un VPS limpio es **Compose + Caddy**: deja preparados `cisne.softvibes.art`, `www.cisnenegro.mx` y la redirección de `www.cisnenegro.mx` a `cisnenegro.mx`. El modo nginx sirve para convivir con otros sitios en un servidor que ya ocupa los puertos 80/443.

Comprobado el 10 de octubre: imagen Linux ARM64 local y AMD64 en el VPS, acceso y persistencia en producción, HTTPS público temporal, configuración real de Caddy y su autorización por dominio. Las imágenes base están fijadas por digest; actualizarlas de forma deliberada junto con una nueva validación. El 17 de octubre se guardaron los DNS finales y se emitió el certificado para ambos nombres; rutas, accesos y redirecciones quedaron verificados. Algunas cachés conservan temporalmente el destino anterior.

## Preparación común

Requiere Docker Engine con Compose en Linux. Subir el código completo de `hosting-independiente/` a `/srv/cisne/app/`, conservar `deploy/` dentro y ejecutar los comandos en `/srv/cisne/app/deploy/`. No subir `.venv`, bases locales de prueba ni cuentas de demostración.

```sh
sudo install -d -m 700 /etc/cisne
sudo install -d -o 10001 -g 10001 -m 700 /srv/cisne/data
sudo install -m 600 ../.env.example /etc/cisne/app.env
sudoedit /etc/cisne/app.env
```

El último archivo es privado, fuera del código. Configurar:

```dotenv
CMS_ORIGIN=https://cisnenegro.mx
CMS_ALLOWED_ORIGINS=https://cisne.softvibes.art,https://www.cisnenegro.mx,https://cisnenegro.mx
PUBLIC_INDEX_HOST=cisnenegro.mx
APP_DATA_DIR=/var/data
PORT=8080
```

Además, completar `CLUB_SECRET` y `CLUB_ADMIN_TOKEN` con valores aleatorios privados de al menos 32 caracteres. Para conservar sesiones/códigos existentes, seguir la migración de claves de la base operativa. Nunca incluir las claves en Git, comandos compartidos o capturas de pantalla.

Importar las bases consistentes del CMS y de la operación v2, y los medios, dentro de `/srv/cisne/data/`; propietario UID/GID `10001:10001`. Para instalación vacía usar temporalmente las variables `CMS_BOOTSTRAP_USER/PASSWORD` del README principal y crear Equipo con `scripts/create_team.py`; retirarlas al terminar. No sustituir datos reales con la carpeta de validación local.

```sh
sudo docker compose config --quiet
sudo docker compose build app
```

Si se importó un CMS existente, con la aplicación de destino todavía detenida adaptar sus publicaciones a las plantillas v2. Esta operación guarda una copia SQLite privada y conserva la revisión publicada y el borrador:

```sh
sudo docker compose run --rm --no-deps app python scripts/prepare_import.py --data-dir /var/data
```

Después:

```sh
sudo docker compose up -d app
curl --fail http://127.0.0.1:8888/healthz
sudo docker compose ps
```

No ejecutar `docker compose config` sin `--quiet` sobre el archivo real: mostraría las variables privadas. Una sola instancia de `app` usa SQLite y el volumen; no escalar réplicas. La aplicación escucha únicamente en `127.0.0.1:8888` del host y en la red privada de Compose. Los registros de cada servicio rotan a 3 archivos de 10 MB.

## VPS limpio: HTTPS con Caddy

Los puertos TCP 80/443 deben estar libres y permitidos; UDP 443 es opcional para HTTP/3. Configurar inicialmente solo el registro DNS de `cisne.softvibes.art` hacia la IP del servidor elegido. No modificar los registros del dominio en transferencia todavía.

```sh
sudo docker compose --profile standalone run --rm --no-deps caddy caddy validate --config /etc/caddy/Caddyfile
sudo docker compose --profile standalone up -d
curl --fail https://cisne.softvibes.art/healthz
```

Caddy solicita el certificado al llegar la primera conexión HTTPS de cada dominio. Su autorización interna acepta únicamente los tres nombres configurados. Así no intenta emitir certificados finales al arrancar antes de que el DNS apunte al servidor. Una visita manual anticipada usando SNI o `--resolve` sí puede desencadenar ese intento: esperar a la propagación para verificar TLS final. La primera conexión puede tardar unos segundos mientras se emite el certificado; Caddy gestiona después su renovación. Los certificados persisten en `/srv/cisne/caddy-data/` y `/srv/cisne/caddy-config/`.

Una vez aprobada la transferencia y validado el sitio temporal, apuntar `cisnenegro.mx` y `www.cisnenegro.mx` al servidor. Mantener MX y los TXT del correo. Revisar A/AAAA/CNAME anteriores y las políticas CAA; no dejar un AAAA apuntando a otro servidor. Con DNS correcto y ACME permitido, esta configuración activa HTTPS final y la redirección de `www` al dominio sin prefijo sin reconstruir ni cambiar el contenedor. Las URLs SEO propias de publicaciones guardadas se adaptan al dominio público al servir HTML, sin modificar borradores ni historial. El CMS admite ambos orígenes desde el comienzo; el dominio temporal permanece sin indexación.

Verificar `/`, `/menu/`, `/cms/#editor`, `/admin/`, `/equipo/` y `/healthz` en el dominio final, incluyendo acceso, publicación, un medio y operación. Las sesiones pertenecen a cada dominio: el usuario vuelve a iniciar sesión al cambiar de nombre. Mantener `cisne.softvibes.art` disponible durante la transición; configurar su redirección definitiva después de comprobar el corte.

## Alternativa: nginx ya existente

Arrancar únicamente `app`; **no** activar el perfil `standalone`. Mantener intactos los demás virtual hosts. Preparar `/var/lib/cisne-acme/`, habilitar primero `nginx-cisne-http.conf` como un virtual host separado y comprobar `nginx -t` antes de recargar. Tras apuntar el DNS temporal, obtener el certificado con el Certbot ya disponible en el servidor:

```sh
sudo certbot certonly --webroot -w /var/lib/cisne-acme -d cisne.softvibes.art
```

Reemplazar ese virtual host por `nginx-cisne.conf`, verificar `nginx -t` y recargar nginx. Configurar la renovación automática existente y su recarga posterior de nginx; verificar con `certbot renew --dry-run`. El proxy conserva las rutas, permite cargas de hasta 105 MiB y espera hasta 240 segundos; sobrescribe las cabeceras de origen y elimina el token interno que pudiera enviar un cliente.

La emisión y activación del dominio final quedan automatizadas con `activate_final.py` y `cisne-final-domain.timer`. Para una instalación nueva, habilitar `nginx-cisne-final-pending.conf` como `/etc/nginx/sites-available/cisne-final`, enlazarlo desde `sites-enabled`, validar Nginx e instalar las dos unidades `cisne-final-domain.*`. El script exige el marcador del archivo, consulta dos resolvers y modifica solo este vhost cuando ambos dominios apuntan a la IP prevista; restaura el archivo anterior si la configuración no es válida. **En el servidor publicado ya completó la activación y el certificado final está instalado.** No copiar rutas de certificados inexistentes ni habilitar ambos archivos temporales nginx simultáneamente.

## Operación y reversión

```sh
sudo docker compose ps
sudo docker compose logs --tail 80 app
sudo docker compose restart app
```

El script `backup.py` requiere Python 3.12 o posterior en el host. Detiene solo `app` mientras copia los medios y crea las tres copias SQLite; la reinicia incluso si falla la copia y espera su estado saludable. Comprime después de reanudar el servicio, restaura en una carpeta temporal, verifica las bases, compara SHA-256 y comprueba los originales/derivados de los medios listos. Solo entonces conserva el nuevo respaldo y retira los que exceden los 14 más recientes. Los archivos quedan privados en `/var/backups/cisne/`, fuera del contenedor.

```sh
sudo python3 /srv/cisne/app/deploy/backup.py
```

Cada ejecución produce una interrupción breve. Las unidades `cisne-independent-backup.service/.timer` incluidas programan la copia a las 03:55 de Ciudad de México. En el servidor publicado ya están instaladas y activas; no duplicar la tarea en cron. Se comprobó la primera restauración.

Guardar además copias cifradas fuera de este servidor y respaldar `/etc/cisne/app.env` por un canal privado: el script no incluye el archivo de entorno ni certificados y no configura almacenamiento externo. Las bases sí contienen información privada de cuentas, socios y operación. La restauración verificada comprueba archivos y bases; no sustituye una prueba funcional completa. Para restaurar realmente, detener `app`, extraer `data/` en una carpeta privada vacía, comprobar las bases y asignar UID/GID `10001:10001` antes de sustituir el volumen. Conservar la carpeta anterior hasta terminar la prueba funcional. Un snapshot del código no respalda socios, pedidos ni medios.

Para revertir un cambio de código, arrancar la imagen anterior con los mismos datos solo si su esquema sigue siendo compatible. Para revertir la migración, conservar el servidor anterior y los valores DNS antes del corte; evitar que ambos sistemas reciban operaciones a la vez.

Documentación: [TLS a demanda en Caddy](https://caddyserver.com/docs/caddyfile/options#on-demand-tls), [perfiles de Compose](https://docs.docker.com/compose/how-tos/profiles/).
