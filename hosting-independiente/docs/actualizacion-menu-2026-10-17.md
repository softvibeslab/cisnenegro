# Menú actualizado según referencia del 17 de octubre de 2026

Publicado en https://cisnenegro.mx/menu/ mediante CMS, revisión 4 (borrador 3).
El alias https://cisne.softvibes.art/menu/ sirve el mismo catálogo.

Se mantuvieron el diseño y las funciones actuales y se igualó el catálogo al PDF proporcionado por el usuario. Referencia transcrita en `menu-referencia-2026-10-17.json`.

## Cambios

- Agregados: Colchita, Brutal de Border Psycho, Chocobanana de Olla de Santa Sabina y Chamorro Adobado.
- Ocultos, conservando sus identificadores: Guamaica, Different Breakfast y Faro.
- Chamorro: $280 solo; $400 con dos cervezas Henry IX o Colchita. La referencia no define volumen ni combinación de estilos. Se conserva esa descripción sin añadir condiciones.
- Foto original del Chamorro incorporada en MediaHub. Colchita queda sin imagen al no existir una fotografía identificada.
- Presentaciones de latas y botellas visibles; descripciones de comida ajustadas a la referencia.
- Henry IX conserva IPA, 5.0%, 14 oz $110 y 4 oz $35, como el texto del PDF. La fotografía del combo dice Munich Helles: discrepancia de origen pendiente de confirmar por el negocio.
- 49 fichas del PDF corresponden a 50 SKU: Tal Cual mantiene Toronja y Jamaica separados. Distribución: 6 barril, 18 latas/botellas, 21 comida, 5 bebidas.
- Guamaica ya no aparece en el maridaje de portada porque el producto está oculto. Los demás contenidos editoriales se conservaron.

## Verificación

Comparación completa del catálogo y precios contra la referencia; validación de documento y render; 8 pruebas de CMS aprobadas; sintaxis de JavaScript válida. Las pruebas de variantes/pedidos se realizaron en memoria, sin crear pedidos reales. Publicación y lectura pública verificadas con HTTPS y SNI del dominio final al servidor 31.220.63.211. El catálogo final y el alias temporal coinciden.

El cambio de código se limita a mostrar `detalle` en latas y renovar la versión del script en la plantilla y el render del CMS. Se reconstruyó solo el servicio `app` con su configuración existente; estado saludable verificado.

## Recuperación

El CMS conserva la revisión anterior 3. Para deshacer el contenido, recuperar esa revisión en el CMS y publicar una nueva revisión; no sobrescribir cambios posteriores sin revisarlos.

Respaldos privados locales: `../../PRIVADO/menu-actualizacion-20261017/` (estado anterior, payload, estado posterior y verificaciones, sin cookies ni contraseñas). Respaldo de los tres archivos de código en el servidor: `/srv/cisne/backups/menu-20261017/source-before.tar`. Imagen anterior: `cisne-independent:before-menu-20261017`.

La fuente de verdad del contenido es el CMS de producción, no el JSON semilla de una instalación nueva.


## Ajuste final: diseño nuevo, únicamente carta adjunta

Revisión 5 publicada tras la aclaración del usuario. Se mantiene el catálogo de 50 SKU que representa las 49 fichas del PDF, con sus precios y variantes. Se oculta la oferta adicional «Vuelo del Cisne» tanto en el menú como en la portada (`menu.vuelo.visible=false`), conservando diseño, fotos, filtros, Pasaporte y pedidos. El indicador es editable desde el CMS.

La visibilidad también se respeta al revalidar carritos y crear pedidos nuevos; los pedidos históricos conservan sus importes. Se mantienen los nodos de la interfaz para no romper el visor de etiquetas. Se renovó la versión de los tres scripts afectados para que los navegadores carguen el cambio.

Verificación: 20 pruebas Python de CMS/operación aprobadas; prueba JavaScript de disponibilidad y revalidación del carrito aprobada; validación de render, catálogo y scripts; lectura pública con TLS de ambos dominios y revisión visual en Safari. Captura: `capturas-menu-20261017/nueva-version-solo-carta.png`. No se generaron pedidos reales.

Respaldos: imagen `cisne-independent:before-solo-carta-20261017`, archivos en `/srv/cisne/backups/solo-carta-20261017/`, estado CMS anterior y posterior bajo `../../PRIVADO/menu-actualizacion-20261017/` con sufijo `solo-carta`. La revisión 4 permanece disponible para recuperar el estado anterior del contenido.


## Opciones del menú pausadas — revisión 6

Por solicitud del usuario, Wi-Fi y Pasaporte quedan ocultos temporalmente solo en `/menu/`: encabezado, enlace del pie y aperturas de los diálogos. Los atributos `data-wifi="false"` y `data-pasaporte="false"` de la plantilla permiten reactivarlos después. La inicialización de socios y de Wi-Fi queda pausada; las utilidades compartidas de QR y los pedidos se conservan. No se modificaron catálogo, cuentas, configuración de red ni contenido de portada.

Verificación: sintaxis de JS, render, igualdad del documento CMS antes/después, lectura HTTPS en ambos dominios y revisión visual en Safari. Publicación 6; borrador 4 sin cambios. Respaldo de código en `/srv/cisne/backups/opciones-menu-20261017/` e imagen `cisne-independent:before-opciones-menu-20261017`.

## Imagen de Colchita — revisión 7

Ilustración aprobada por el usuario incorporada al MediaHub y asignada a `menu.barril[id=colchita].img`. Medio `5ba627a63a7e482899f8880d696bf6f5`, WebP público de 78,654 bytes; original PNG conservado. La ficha identifica la imagen como ilustración generada, no etiqueta oficial. Referencias y prompt en [colchita/README.md](colchita/README.md).

Publicación 7, borrador 5. Se verificó que el único cambio de contenido es la imagen de Colchita y que el catálogo y archivo público responden correctamente en ambos dominios. Sin despliegue de código. Respaldos privados con sufijo `colchita` en la carpeta de esta actualización.

## Mostrar pedido sin QR — revisión 8

Por solicitud del usuario, la tarjeta «Mostrar al mesero» presenta solo productos, cantidades, presentaciones, notas, mesa y total estimado. El QR y sus controles quedan ocultos temporalmente mediante `data-pedido-qr="false"` en el body del menú. Se conserva «Volver» y «Ya lo pedí»; el resumen ocupa una sola columna también en escritorio. No se precarga la biblioteca QR, ni se crea un pedido remoto ni se inicia sondeo desde esta tarjeta mientras el indicador esté desactivado. Para reactivarlo se puede cambiar el atributo a `true` y volver a publicar la plantilla.

Se actualizaron únicamente HTML, JS, CSS del menú y versión del script impuesta por el render CMS. Nueva versión de caché: `cms-20261017-pedido`. El contenido editorial queda idéntico al de la revisión 7, incluida la imagen de Colchita. Borrador 5, publicación 8.

Verificación: sintaxis JS, 10 pruebas existentes de CMS, render con QR oculto y resumen disponible, igualdad de assets locales y públicos en ambos dominios y comprobación visual del flujo agregar → mostrar → limpiar en Safari. El producto de prueba se retiró del carrito local. Captura: [pedido-sin-qr.png](capturas-menu-20261017/pedido-sin-qr.png).

Respaldo de los cuatro archivos en `/srv/cisne/backups/pedido-sin-qr-20261017/`; imagen anterior `cisne-independent:before-pedido-sin-qr-20261017`. Instantáneas de estado CMS y verificaciones privadas con sufijo `pedido-sin-qr`. Se reconstruyó únicamente `app`; contenedor saludable.
