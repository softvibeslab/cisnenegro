# Agente Cisne · CMS y Hermes / Telegram

Implementación local del asistente de Cisne Negro: conocimiento del negocio, diseño y desarrollo, CRUD editorial y generación de imágenes del menú a partir de etiquetas. El chat se abre en **`/cms/#agente`** con una cuenta del CMS. El perfil Hermes se llama **`cisne-negro`**.

## Estado de esta entrega

- Chat integrado en el CMS, herramientas CRUD, trabajos de imagen y cliente Hermes implementados y probados localmente.
- Perfil Hermes creado en el entorno de trabajo, con proveedor/modelo propios configurados y prueba real de identidad completada. No se copiaron memorias, bots ni datos de otros clientes.
- El chat web y las imágenes requieren `OPENAI_API_KEY` en el servidor. La suscripción/autenticación de Hermes no sustituye esa clave de API.
- Telegram requiere un bot dedicado, sus operadores permitidos y una cuenta CMS editorial. El gateway todavía no está iniciado.
- Esta entrega no está desplegada en producción ni publicada como una actualización de GitHub. Las pruebas de generación usan un proveedor simulado; todavía no se ha generado una imagen real mediante esta nueva API.

## Qué puede hacer

| Desde el agente | Resultado |
|---|---|
| Consultar la carta y el negocio | Lee contenido y versión vigentes del CMS |
| Crear, editar o eliminar cervezas, alimentos, bebidas, eventos y galería | Cambios acotados por ID en el borrador |
| Cambiar textos de portada, contacto y horarios | Actualización parcial de los campos admitidos |
| Ocultar un producto temporalmente | Conserva su ID e historial |
| Recibir una etiqueta | Guarda el original en MediaHub y permite leer la referencia visual |
| Generar una imagen para una cerveza | Trabajo privado, vista previa y selección explícita del resultado |
| Proponer contenido y diseño | Usa la identidad y las fuentes del proyecto |
| Desarrollar funciones desde Hermes | Trabaja en el repositorio con herramientas de desarrollo y pruebas |

El chat del CMS no ejecuta comandos de servidor ni modifica código. La publicación sigue en el control existente del CMS, con rol propietario. El cliente Hermes ofrece publicación explícita separada; una cuenta editorial no puede usarla. El Content Hub y la publicación en redes no forman parte de este CRUD.

```mermaid
flowchart LR
    CMS[Chat privado del CMS] --> Tools[Operaciones editoriales]
    Telegram[Telegram autorizado] --> Hermes[Perfil Hermes: cisne-negro]
    Hermes --> Tools
    Tools --> Draft[Borrador y control de versión]
    Label[Etiqueta original] --> Media[MediaHub privado]
    Media --> Image[Generación de imagen]
    Image --> Review[Vista previa y elección]
    Review --> Draft
    Draft --> Preview[Vista previa del menú]
    Preview --> Publish[Publicar desde CMS]
```

La implementación usa un agente con herramientas, no una cadena de agentes independientes para cada paso. El [flujo de etiqueta](flujo-etiqueta.json) documenta contratos, límites y errores.

## Probar en local

Desde `hosting-independiente/`, ejecutar `./iniciar-local.sh` y abrir `http://127.0.0.1:8088/cms/#agente`. Los accesos locales quedan en la carpeta de datos indicada al iniciar. Sin clave de IA aparece un estado explícito de conexión pendiente; el resto del CMS sigue disponible.

Configurar fuera del repositorio, en el entorno que arranca el servidor:

```dotenv
OPENAI_API_KEY=
CISNE_AGENT_MODEL=gpt-6-astra
CISNE_IMAGE_MODEL=gpt-image-2.5-sunburst
```

La plantilla `.env.example` no se carga automáticamente al iniciar con Python. En Docker Compose se usa el archivo privado de variables definido por el despliegue. Reiniciar la aplicación después de cambiar las variables. Nunca poner claves en JavaScript, mensajes, capturas o Git.

El proveedor web utiliza Responses API con herramientas y la API de edición de imágenes. Modelos configurables; la cuenta debe tener acceso a los modelos seleccionados. Las solicitudes de imagen llevan la etiqueta y una referencia editorial de Colchita, cuando está disponible. No se envían cookies, cuentas del CMS ni datos de socios al modelo.

## Flujo de una cerveza nueva

1. Adjuntar una foto legible de la etiqueta o elegirla en MediaHub.
2. Pedir al agente que cree la cerveza. Resolver los datos que falten: nombre, estilo, ABV, perfil, presentación y precio. No se rellenan con valores inventados.
3. Conservar el original como `etiqueta`; la generación usa el ID de la referencia y la versión del borrador.
4. Solicitar la imagen. Se registra un trabajo y se muestra su avance; se puede recuperar al recargar el CMS.
5. Revisar nombre, identidad, estilo, porcentaje y encuadre. El resultado es una ilustración editorial, no una etiqueta oficial nueva.
6. Elegir **Usar imagen en el borrador**. Solo cambia `img` de la cerveza seleccionada.
7. Revisar la vista previa. El propietario publica cuando corresponda, después de revisar todos los cambios pendientes.

En Telegram, Hermes descarga el resultado de forma autenticada en su directorio privado y puede mostrar el adjunto al operador antes de aplicarlo. Ver [perfil e instalación](hermes/README.md).

## Permisos, versiones y límites

Las rutas del agente reutilizan sesión, CSRF, origen y roles del CMS. No existe un acceso público del agente ni un token administrativo incrustado. Cada escritura valida el documento y compara la versión; un conflicto devuelve 409 y exige releer. La generación no asigna imágenes ni publica automáticamente.

Límites iniciales: 20 consultas por cuenta en diez minutos; tres rondas del modelo y tres cambios por consulta; seis trabajos de imagen por cuenta por hora y dos simultáneos. El chat conserva un historial acotado en memoria del navegador, que se borra al cerrar sesión. Los trabajos y su procedencia persisten en la base del CMS; las imágenes, en MediaHub.

Una petición de imagen repetida con la misma cerveza, etiqueta, versión y modelo reutiliza el trabajo existente. Los trabajos interrumpidos se muestran como fallidos después de diez minutos; no se reenvían automáticamente al proveedor. El reintento es explícito y puede tener coste del proveedor. Se conserva el intento anterior.

## API para Hermes y otros clientes privados

| Ruta | Función |
|---|---|
| `GET /cms/api/agent/config` | Estado de configuración, sin claves |
| `GET /cms/api/agent/content` | Documento, versión y campos permitidos |
| `POST /cms/api/agent/content` | `{version, operation}`: una operación CRUD |
| `POST /cms/api/agent/chat` | Mensaje, historial acotado, versión y etiqueta opcional |
| `POST /cms/api/agent/images` | `{collection, id, reference_media_id, version}` |
| `GET /cms/api/agent/images` | Últimos trabajos visibles para la cuenta |
| `GET /cms/api/agent/images/{id}` | Estado y resultado de un trabajo |

Publicación, vista previa y subidas utilizan las rutas existentes del CMS. El cliente Hermes ofrece comandos acotados y sesiones privadas; no es un proxy HTTP arbitrario. Consulta [su skill](hermes/skills/cisne-cms/SKILL.md).

## Fuentes y mantenimiento

- [Instrucciones del agente](instrucciones.md) y [conocimiento verificable](conocimiento/README.md).
- [Resumen incluido en la imagen del servidor](../hosting-independiente/backend/agent_knowledge.md): actualizar junto con el conocimiento si cambia la marca o el alcance.
- [Verificación de esta entrega](VERIFICACION.md).
- Documentación de implementación consultada: [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling), [edición/generación de imágenes](https://developers.openai.com/api/docs/guides/image-generation), [perfiles Hermes](https://hermes-agent.nousresearch.com/docs/user-guide/profiles) y [Telegram](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram).
