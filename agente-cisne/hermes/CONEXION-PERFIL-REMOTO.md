# Conectar el perfil del usuario al CMS

## Dos perfiles distintos

| Función | Perfil | Servidor | Ubicación |
|---|---|---|---|
| Conexión actual del CMS, verificada | `cisne-negro` | `31.220.63.211` | `/srv/cisne/hermes/profiles/cisne-negro` |
| Perfil que el usuario quiere conectar | `cisnenegro` | `169.58.107.205` | `/root/.hermes/profiles/cisnenegro` |

El repositorio del segundo servidor está en `/root/cisnenegro`. Su existencia, falta de autenticación de modelo y gateway detenido fueron comunicados por el usuario. La inspección desde esta computadora quedó bloqueada por `Permission denied` de SSH. No se ha verificado ni modificado ese servidor.

El CMS todavía usa el primer perfil. Crear el segundo perfil o clonar el repositorio no cambia la conexión del CMS. El código preparado permite seleccionar `cisnenegro`, pero esa selección no está desplegada.

## Preparación de código

La integración está en la rama `feat/agente-cisne-cms-hermes`. Contiene `agente-cisne/` y estos componentes de `hosting-independiente/backend/`:

- `agent_hermes.py`: cliente del CMS, por proceso local o socket privado.
- `hermes_worker.py`: una inferencia usando identidad, modelo y autenticación del perfil.
- `hermes_socket_bridge.py`: servicio privado por socket Unix.

`CISNE_HERMES_PROFILE_NAME=cisnenegro` selecciona el perfil esperado desde la configuración del servidor. Solo se admiten los dos nombres de esta tabla. El worker comprueba el nombre, la ruta del perfil y `HERMES_HOME`; el cliente comprueba la identidad devuelta. Una discrepancia debe bloquear la inferencia, en lugar de mostrar un perfil distinto como conectado.

No ejecutar `preparar_perfil.py --install` sobre el perfil existente: ese instalador crea el perfil original `cisne-negro`. Tampoco sustituir el `SOUL.md` del usuario por la plantilla del repositorio.

## Secuencia de conexión

1. **Comprobar el servidor de Hermes.** Inspeccionar en lectura la instalación y versión de Hermes, el perfil `cisnenegro`, su modelo/proveedor y el estado del repositorio. Registrar rutas y nombres sin imprimir secretos. Preservar cambios locales del clon.
2. **Obtener el código.** Hacer `git fetch origin` y revisar `origin/feat/agente-cisne-cms-hermes`. Si el clon tiene trabajo propio, usar un worktree separado para la integración. No utilizar `reset --hard`, no sobrescribir el clon ni desplegar desde una rama sin revisar.
3. **Configurar el modelo en ese perfil.** El operador debe completar su autenticación en el propio servidor. Verificar una consulta real con `cisnenegro` antes de conectarlo al CMS. No copiar credenciales, memorias ni conversaciones del perfil actualmente usado por el CMS. El adaptador actual admite únicamente el transporte Hermes `codex_responses`; otro proveedor requiere adaptación y prueba previa.
4. **Preparar el servicio privado.** Ejecutar bridge y worker junto al perfil real, con `CISNE_HERMES_PROFILE_NAME=cisnenegro`, su ruta existente y la instalación Hermes comprobada. Resolver los permisos del servicio después de inspeccionar el host: el ejemplo `cisne-hermes.service` usa otro usuario y `ProtectHome=true`, por lo que no puede aplicarse directamente a un perfil bajo `/root`. No abrir permisos globales de `/root` para resolverlo.
5. **Preparar la comunicación entre servidores.** Usar un túnel SSH supervisado entre sockets Unix, con host verificado y cuenta/llave restringida al canal necesario. La aplicación solo recibe el socket; las credenciales del modelo permanecen en el servidor Hermes. Definir dirección del túnel y permisos según los accesos disponibles. No abrir una API pública ni dar acceso SSH de administración al navegador o al CMS.
6. **Ensayar antes de cambiar el CMS.** Usar un socket independiente, por ejemplo `/srv/cisne/hermes-remote/run/bridge.sock`, y una instancia de prueba sin la base de producción. Verificar `status.profile=cisnenegro`, una consulta real, rechazo de perfil incorrecto y errores de conexión. Comprobar compatibilidad con las APIs internas de la versión instalada de Hermes.
7. **Cambiar la configuración del CMS después del ensayo.** Respaldar configuración e imagen; apuntar el montaje al nuevo socket y fijar `CISNE_HERMES_PROFILE_NAME=cisnenegro` en el contenedor. Reiniciar únicamente la aplicación, verificar login/chat y comprobar que borrador y publicación conservan sus versiones y contenido. Mantener disponible la configuración anterior para revertir.

El gateway Telegram no es requisito para atender el chat web. Su activación, bot y operadores se configuran aparte. El canal CMS usa SOUL/modelo/autenticación del perfil, con herramientas editoriales limitadas; no carga memoria, sesiones de Telegram, skills generales ni herramientas de desarrollo del repositorio.

## Datos pendientes para cerrar la conexión

- Acceso autorizado al servidor `169.58.107.205`, o ejecución de estos pasos por el operador de Hermes en ese servidor.
- Modelo autenticado y consulta real correcta en el perfil `cisnenegro`.
- Versión/ruta de Hermes y permisos reales para definir el servicio y túnel.

Hasta completar estas comprobaciones no se puede afirmar que el CMS usa el perfil del usuario. La conexión actual en `31.220.63.211` permanece operativa.
