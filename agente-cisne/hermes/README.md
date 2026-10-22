# Perfil privado Hermes · Cisne Negro

**Perfil del usuario:** `cisnenegro` en `169.58.107.205`, con SOUL en `/root/.hermes/profiles/cisnenegro/SOUL.md`. Todavía no está conectado al CMS. Los apartados de producción siguientes describen el perfil distinto `cisne-negro` en `31.220.63.211`. Consulta la [preparación para conectar el perfil existente](CONEXION-PERFIL-REMOTO.md) antes de usar el instalador o el ejemplo de servicio.

Incluye identidad (`SOUL.md`), skill editorial y cliente Python sin dependencias externas. El instalador crea el perfil `cisne-negro` con `--no-skills`, sin clonar otras cuentas, memorias, sesiones o conectores. No arranca el gateway ni envía mensajes.

## Chat emergente del CMS

El botón flotante **Agente Cisne** conecta con este perfil mediante `hosting-independiente/backend/agent_hermes.py` y `hermes_worker.py`. Arranque local: `./iniciar-local.sh --hermes` desde `hosting-independiente/`. En un servidor usa `CISNE_AGENT_PROVIDER=hermes` y configura las rutas `CISNE_HERMES_ROOT` / `CISNE_HERMES_PROFILE_DIR` si difieren de las predeterminadas. No es una conexión del navegador a la API pública de Hermes: la petición pasa por la sesión, origen, CSRF y permisos del CMS.

El proceso usa el modelo y SOUL del perfil, con las herramientas generales desactivadas. Propone lectura, edición del borrador o generación de imagen, y el CMS valida/ejecuta cada operación con el usuario autenticado. La conversación vive en la ventana del CMS; no se carga ni escribe la memoria compartida de Hermes. Esto permite usar la misma identidad sin exponer sesiones de Telegram a los editores. El chat CMS no necesita `CISNE_CMS_USER/PASSWORD`; esas variables son para el cliente CLI/Telegram.

El adaptador de esta entrega soporta el transporte `codex_responses` del proveedor `openai-codex` que usa el perfil actual. Si se cambia a otro transporte, la conexión queda desactivada hasta implementar y probar su adaptación de mensajes. El perfil debe residir en una carpeta `profiles/cisne-negro`. El estado comprueba instalación/configuración/autenticación y se guarda en caché 30 segundos; la disponibilidad efectiva del proveedor se confirma al enviar una consulta.

Desde el 21 de octubre también está desplegado en [el CMS de producción temporal](https://cisne.softvibes.art/cms/). El contenedor usa `CISNE_HERMES_SOCKET=/run/cisne-hermes/bridge.sock`; el servicio host `cisne-hermes` ejecuta el worker con el perfil dedicado. Una consulta real con `read_content` quedó verificada sin modificar el borrador. La API de generación conserva su clave independiente y sigue pendiente; el gateway Telegram no está iniciado.

## Servicio privado de producción

| Componente | Ubicación / estado |
|---|---|
| Instalación Hermes existente | `/usr/local/lib/hermes-agent`, commit `d62716c7043e57ef7a29e81a02ddbc19334e29df` |
| Perfil | `/srv/cisne/hermes/profiles/cisne-negro`, modelo `gpt-6-astra` |
| Proceso host | `cisne-hermes.service`, usuario `cisneagent`, grupo `10001`; activo y habilitado |
| Socket host | `/srv/cisne/hermes/run/bridge.sock` |
| Socket en Docker | `/run/cisne-hermes/bridge.sock`; directorio montado en solo lectura |
| Compose operativo | `/srv/cisne/app/deploy/compose.override.yaml`, basado en `compose.hermes.yaml` |

La autenticación del proveedor seleccionado reside en el perfil privado de Cisne. El contenedor no recibe credenciales, otras cuentas ni el almacén global del host. El perfil usa permisos `0700`, los archivos de autenticación `0600`; el directorio del socket `0750` y el socket `0660` permiten acceso al grupo del CMS. El servicio escucha únicamente por socket Unix; no abre un puerto HTTP.

El protocolo intercambia una solicitud JSON por conexión, limita entrada a 16 MiB y salida a 2 MiB y admite dos procesos simultáneos. Valida las herramientas antes de iniciar el worker; usa un ejecutable fijo, entorno filtrado, errores sanitizados y ningún reintento automático. El CMS conserva permisos, CSRF y ejecución editorial. Los [archivos de despliegue](../../hosting-independiente/deploy/compose.hermes.yaml) son ejemplos; el [registro operativo](../../hosting-independiente/docs/agente-cisne-despliegue-2026-10-21.md) documenta la instalación y reversión realizadas.

El dominio canónico `cisnenegro.mx` tiene una incidencia de delegación/zona DNS al cierre de esta revisión. Usar el temporal mientras Hostinger reconcilia dominio y zona; no desactivar TLS ni cambiar el origen del CMS para eludir la incidencia.

## Preparar el perfil

Requiere Hermes instalado. `CISNE_REPO_PATH` es opcional y se usa para configurar el directorio de trabajo solo al crear un perfil nuevo; debe ser la ruta absoluta del repositorio independiente. No es una credencial.

```sh
python3 agente-cisne/hermes/preparar_perfil.py
python3 agente-cisne/hermes/preparar_perfil.py --install
```

La primera orden muestra el plan. La segunda crea el perfil y copia únicamente archivos ausentes. Si Hermes crea un SOUL genérico durante esa misma ejecución, se conserva como `SOUL.hermes-default.md`. No reemplaza un perfil existente, no cambia el perfil activo global y no modifica la configuración de otros clientes. Un SOUL o skill preexistente se conserva; cualquier actualización posterior debe revisarse como un cambio separado.

Configura proveedor/modelo con `hermes --profile cisne-negro setup model`. El preparador no copia secretos de otros perfiles. La versión instalada de Hermes admite un fallback de **solo lectura** al almacén global `auth.json` para proveedores que no tengan autenticación propia en el perfil (implementado en `hermes_cli/auth.py`, `_global_auth_file_path` / `_load_global_auth_store`). Eso no copia credenciales a este paquete ni hereda la configuración de Telegram o los accesos CMS: estos deben configurarse por separado. Conserva las claves que configures en el gestor privado o `.env` del perfil, fuera de Git y con permisos `600`:

| Variable | Uso |
|---|---|
| `CISNE_CMS_URL` | Origen canónico, por ejemplo `https://cisnenegro.mx` o loopback local |
| `CISNE_CMS_USER` / `CISNE_CMS_PASSWORD` | Cuenta CMS dedicada; editor para borradores y medios |
| `CISNE_REPO_PATH` | Repositorio para conocimiento y desarrollo |
| `HERMES_HOME` | Hermes lo establece al ejecutar con `--profile cisne-negro`; para el cliente directo debe apuntar al perfil |

El cliente no carga `.env` por su cuenta: recibe variables del proceso. No se pasan secretos por argumentos ni se imprimen para comprobarlos. Su caché usa un subdirectorio `700` y archivo de sesión `600`; verifica sesión y CSRF antes de cada operación. No sigue redirecciones, incluso al mismo dominio. No desactives la validación TLS.

Prueba primero `state`, una edición en un CMS local y una vista previa. La API de agente del CMS, el proveedor de imágenes y sus claves deben estar configurados en el servidor para completar generación. La CLI no instala ni despliega esos componentes.

## Telegram privado

1. Crear un bot dedicado con [BotFather](https://t.me/BotFather) y conservar su token fuera de conversaciones y repositorios.
2. Configurar `TELEGRAM_BOT_TOKEN` en el entorno privado del perfil. Definir `TELEGRAM_ALLOWED_USERS` con los IDs numéricos concretos de operadores autorizados, separados por comas. No usar `*` ni habilitar `TELEGRAM_ALLOW_ALL_USERS` o `GATEWAY_ALLOW_ALL_USERS`.
3. Mantener uso por mensajes directos. No habilitar grupos o canales mediante listas globales de chats. El bot no debe representar un chat público de clientes.
4. Verificar proveedor/modelo, usuario CMS, permiso real y lista de Telegram antes de iniciar manualmente `hermes --profile cisne-negro gateway run`. Ese comando mantiene un servicio activo; este paquete no lo ejecuta.
5. Enviar la etiqueta al bot como archivo/documento para conservar calidad. Hermes debe entregar la ruta local del adjunto; la skill sube ese archivo a MediaHub y solicita generación en el CMS.
6. Cuando la generación termine, `image-download ID_DEL_TRABAJO` guarda el PNG/WebP privado en `$HERMES_HOME/.cisne-generated/` y devuelve su ruta. Hermes puede inspeccionar y adjuntar ese archivo al operador en la conversación actual antes de asociarlo al borrador. La descarga no publica el recurso ni envía mensajes por sí misma.

Cada operador admitido en un mismo perfil comparte la identidad CMS configurada. Una lista de Telegram restringe quién accede, pero **no implementa roles CMS diferentes por persona**. Para editores y publicadores con permisos distintos, usar perfiles/cuentas separados o implementar identidad delegada antes de ampliar acceso. Empezar con cuenta editorial; la publicación queda en el CMS con un propietario o en un perfil privado separado autorizado.

No activar credenciales de propietario en un bot público. El perfil de desarrollo con terminal local debe usarse solo por el responsable técnico, con herramientas limitadas a su trabajo; las instrucciones del agente no son un aislamiento de sistema operativo.

## Comandos y pruebas

La [skill](skills/cisne-cms/SKILL.md) documenta lectura, mutaciones, imágenes, publicación separada y recuperación ante conflictos. El cliente devuelve JSON y no ofrece HTTP arbitrario, shell remoto ni administración de usuarios.

```sh
python3 -m unittest discover -s agente-cisne/hermes/tests -p 'test_*.py' -v
```

Las pruebas levantan un CMS simulado en loopback y usan carpetas temporales; no conectan al negocio ni a Telegram, no generan imágenes pagadas y no crean perfiles reales. El instalador se contrasta con el CLI Hermes disponible (`profile create --no-skills`, `config set terminal.cwd`); no requiere copiar el repositorio de Hermes.
