# CMS de Cisne Negro

Publicado con autorización el 8 de octubre de 2026: https://cisnenegro.softvibes.art/cms/

## Entrar y trabajar

Usa el usuario y la contraseña existentes del panel, guardados en `PRIVADO/credenciales-panel.txt`. No deben copiarse en documentos públicos. El propietario puede crear cuentas individuales desde **Usuarios**, hasta tres cuentas activas.

1. Abre **Menú y cervezas** para ajustar productos, presentaciones, precios, disponibilidad y maridajes. **Editor visual** permite seleccionar bloques de la portada o editar sus campos; incluye vista de celular.
2. Elige fotografías y videos en **MediaHub**. Cambiar la foto de un producto afecta esa selección; archivar un medio conserva los usos ya publicados.
3. Pulsa **Guardar borrador**. El borrador se conserva en el servidor y actualiza la vista previa privada.
4. Revisa los cambios respecto a la publicación actual y pulsa **Publicar**. La web y el menú QR cambian juntos.
5. En **Publicaciones**, recuperar una versión la copia al borrador. Es necesario publicarla para hacerla visible. Esta recuperación no cambia socios, visitas, canjes ni NPS.

Un aviso de conflicto significa que otra persona guardó una versión más reciente. El panel conserva los cambios locales para que puedas revisarlos antes de recargar. Los cambios que todavía no se han guardado no se sincronizan entre dispositivos.

## Módulos y permisos

| Módulo | Uso |
|---|---|
| Inicio | Catálogo, medios, experiencias, almacenamiento y accesos |
| Editor visual | Portada, foto o video, textos, historia, secciones y metadatos |
| Menú y cervezas | Barril, latas, cocina, bebidas, categorías, orden, disponibilidad, precios y Vuelo |
| MediaHub | Subida múltiple, búsqueda, categorías, etiquetas, fichas, miniaturas, videos, usos y archivo recuperable |
| Eventos y galería | Altas, edición, imágenes, enlaces, orden y visibilidad |
| Datos del negocio | Contacto, horarios, dirección, ubicación, redes y enlaces |
| Publicaciones | Comparación de cambios, autor, fecha e historial recuperable |
| Usuarios | Propietarios y editores, activación y revocación de sesiones al cambiar acceso |
| Pasaporte | Panel existente de socios, código del día, visitas, canjes, NPS, estadísticas y ranking |

**Propietario:** puede publicar, restaurar versiones, gestionar usuarios y operar el Pasaporte. **Editor:** puede trabajar con contenido, catálogo y MediaHub; no puede publicar ni acceder a datos privados del club. Los permisos se comprueban en el servidor.

## MediaHub

Se importaron **477 medios únicos** de Cisne Negro. Se detectaron tres duplicados exactos y se conservaron las 480 referencias de origen. La marca de revisión queda pendiente hasta que el equipo revise el material. Las etiquetas permiten agrupar colecciones, campañas o temporadas y buscarlas sin duplicar archivos.

- Fotos: JPG, PNG, WebP y HEIC/HEIF; máximo 20 MB y 40 megapíxeles. Se crean versiones optimizadas y miniaturas, conservando el original privado.
- Videos: MP4; máximo 100 MB y cinco minutos. Se preparan en segundo plano como video silencioso para web y generan miniatura. Un estado de procesamiento o error impide seleccionarlos antes de estar listos.
- Cuota: 10 GB, incluyendo originales y derivados. Los archivados siguen ocupando espacio porque pueden estar referenciados por publicaciones anteriores.
- Portada: permite elegir fotografía, video de escritorio, video de celular y fotografía de respaldo. Se conserva el control de pausa y la consideración de preferencias de movimiento reducido.
- Punto focal: las coordenadas de la ficha controlan el encuadre cuando la imagen o el video se recortan. Guarda la ficha y revisa la vista previa; el encuadre se incorpora al publicar y las versiones anteriores conservan el suyo.
- No hay borrado físico desde el panel. Archivar y recuperar evitan romper publicaciones anteriores.

La biblioteca no conecta automáticamente cuentas sociales. La generación con IA, el montaje de video y la publicación en redes no forman parte de esta entrega.

## Operación técnica

- Código: `backend/cms_server.py`, `cms_content.py`, `cms_media.py` y `sitio/cms/`.
- Dependencias: `backend/requirements-cms.txt`; entorno del servidor en `/opt/cisnenegro-cms/venv`.
- Servicio: `cisnenegro-cms`, usuario `cisnecms`, puerto local `8795`.
- Contenido persistente: `/var/lib/cisnenegro-cms/cms.sqlite`.
- Biblioteca: `/var/lib/cisnenegro-cms/media/`, con índice SQLite, originales y derivados.
- Identidad del equipo: cookie segura `cn_staff`, sesiones de 12 horas, CSRF y límite de intentos de acceso. Los originales nunca se sirven desde una ruta pública. Los derivados nuevos requieren sesión hasta que una publicación los utilice.
- El Pasaporte mantiene su base independiente en `/var/lib/cisnenegro-club/club.db`. El CMS pasa un token interno al consultar su administración. Los secretos permanecen en archivos del servidor fuera de la raíz pública.
- El dominio de Softvibes conserva `noindex`, igual que antes de esta entrega.

`deploy/publicar-cms.sh` actualiza solo el código y los recursos necesarios. `deploy/publicar.sh` ya no elimina rutas remotas. Los archivos locales HTML/JSON son plantillas y semillas: editar esos archivos no reemplaza el contenido que los dueños hayan publicado desde el CMS.

## Respaldos y recuperación

El temporizador `cisnenegro-cms-backup.timer` ejecuta diariamente a las 03:40 de Ciudad de México, con hasta dos minutos de variación. Conserva los últimos 14 snapshots propios; los medios idénticos se comparten entre respaldos para ahorrar espacio. El respaldo independiente del club conserva su configuración anterior.

Comprobación manual en el VPS:

```sh
systemctl start cisnenegro-cms-backup.service
systemctl show cisnenegro-cms-backup.service -p Result -p ExecMainStatus
python3 /opt/cisnenegro-cms/backup-cms.py --verify
```

`--verify` restaura una copia a un directorio temporal y comprueba SQLite, hashes, originales, derivados y referencias publicadas. No reemplaza bases activas. Para una recuperación real del CMS: detener `cisnenegro-cms`, conservar una copia del directorio persistente actual, restaurar juntos `cms.sqlite`, `media/` y `media-map.json` del snapshot validado, asignar propietario `cisnecms:cisnecms` y volver a iniciar el servicio. No mezclar los WAL/SHM de una base anterior con las bases restauradas y no sustituir la base del club.

## Verificación de entrega

Pruebas automatizadas de contenido, cargas, permisos, publicación, conflictos, recuperación, archivos privados y autenticación del proxy; 55 comprobaciones existentes del Pasaporte y 15 del controlador de video. Recorrido visual de acceso, inicio, biblioteca y edición con vista previa, en escritorio y ancho móvil de 375 px.

En producción se comprobaron HTTPS, acceso con credenciales existentes, cookie segura, publicación del contenido inicial sin alterarlo, cierre de sesión, acceso privado a borradores, operación del proxy del Pasaporte y conservación de las rutas públicas. Se ejecutó y verificó un respaldo con los 477 medios.
