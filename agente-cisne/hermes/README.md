# Perfil privado Hermes · Cisne Negro

Incluye identidad (`SOUL.md`), skill editorial y cliente Python sin dependencias externas. El instalador crea el perfil `cisne-negro` con `--no-skills`, sin clonar otras cuentas, memorias, sesiones o conectores. No arranca el gateway ni envía mensajes.

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
