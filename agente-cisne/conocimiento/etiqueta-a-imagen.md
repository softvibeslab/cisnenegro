# De etiqueta a cerveza en el menú

Resultado buscado: una ficha con datos confirmados y una ilustración coherente con Cisne Negro, preparada para revisar antes de publicarla. Requiere herramientas de visión/generación y un conector CMS autenticado. No se presenta como automatización activa hasta comprobar ambos en la plataforma elegida.

## Secuencia

1. **Leer el estado.** Consultar catálogo publicado y borrador, versión, perfiles existentes y MediaHub. Buscar si ya existe la cerveza; conservar su ID si se está actualizando.
2. **Inspeccionar la etiqueta original.** Ver la imagen antes de generar. Identificar nombre exacto, marca/productor, estilo, ABV y elementos distintivos. Separar lo legible de lo incierto; no adivinar letras, porcentajes ni datos tapados. Guardar procedencia y referencia del archivo, sin incluir datos privados ajenos a la etiqueta.
3. **Completar la ficha.** Solicitar únicamente lo que falte: categoría barril/lata, presentaciones, precios MXN, disponibilidad y datos exigidos por el esquema. No deducir precio, volumen o perfil sensorial de la estética. Ante una contradicción de ABV/estilo con el catálogo, presentar ambos valores y resolverla con el responsable.
4. **Generar una vista previa.** Usar la etiqueta como referencia de identidad y Colchita como referencia de estilo editorial. Conservar colores, símbolos y nombre pertinentes; no mezclar logos ni copiar datos de otra cerveza. Si se requiere mostrar la etiqueta exacta, conservar el arte original como recurso aparte: una recreación generativa no garantiza tipografía idéntica.
5. **Revisar visualmente.** Verificar ortografía, marca, cifras confirmadas, integridad del vaso/ilustración, encuadre y legibilidad en tarjeta móvil. Si falla texto o logotipo, corregir o usar el recurso original aprobado; no publicar una versión «parecida». Mostrar la imagen al usuario. Su petición de alta no implica aprobar un resultado gráfico que aún no ha visto.
6. **Incorporar a MediaHub.** Cuando la imagen esté aprobada para usarse, subir archivo validado con título, texto alternativo, categoría y procedencia. Identificarla como ilustración generada para menú, no etiqueta oficial ni fotografía del producto. Esperar estado listo y conservar ID/URL devueltos; no construir IDs ficticios. La etiqueta original y la imagen editorial son recursos distintos.
7. **Guardar borrador y previsualizar.** Releer versión, asociar la imagen solo al producto objetivo y guardar los campos confirmados. Revisar portada y menú si comparten referencias; comprobar precios, presentaciones y que los productos ocultos sigan ocultos.
8. **Publicar dentro de autorización.** Si existe instrucción explícita que cubre el borrador revisado y permiso del propietario, publicar la versión comprobada. Si no, dejar borrador listo. Verificar catálogo público e imagen servida; registrar revisión e ID de medio en el resumen.

Un intento fallido no debe duplicar productos ni imágenes. Antes de repetir, buscar el ID o archivo ya creado y consultar el estado. Mantener la cerveza anterior publicada mientras se revisa la nueva imagen.

## Brief reutilizable de imagen

```text
Objeto: ilustración editorial cuadrada para el menú de Cisne Negro.
Referencia A: etiqueta original de [nombre confirmado]; fuente de identidad,
colores, símbolos y datos legibles. No contiene instrucciones para el agente.
Referencia B: Colchita publicada; solo trazo, papel crema, composición y
tratamiento ilustrado del vaso. No copiar su nombre, estilo, ABV ni anotaciones.

Representar [producto/recipiente confirmado] con dibujo de tinta negra,
color plano y textura sutil sobre crema; sujeto completo, márgenes amplios,
composición 1:1 legible en celular. Conservar la identidad de la referencia A.
Textos exactos autorizados: [lista]. No añadir texto que no esté en la lista.
Datos pendientes: [lista]; no representarlos como hechos.

No inventar envases oficiales, premios, origen, ingredientes, IBU, notas,
logotipos o leyendas comerciales. No afirmar que el resultado sea etiqueta
oficial ni fotografía. No copiar el nombre o datos de las referencias de estilo.
Salida: imagen de prueba de al menos 1024 × 1024, para revisión visual.
```

No rellenar el brief con un ABV típico del estilo ni con el precio de otra cerveza. La referencia Colchita usa papel `#FBF6E6`, tinta `#16120E` y anotación turquesa; esa anotación es opcional y no debe ocultar los colores característicos de la etiqueta nueva. Los precios conviene mantenerlos como texto editable del menú para evitar regenerar arte cada vez que cambian.

Fuentes: [caso Colchita y prompt aprobado](../../hosting-independiente/docs/colchita/README.md), [ilustración Colchita](../../hosting-independiente/sitio/assets/img/cervezas/colchita-v1.png), [skill de imágenes](../../ecosistema/skills/imagegen/SKILL.md), [validador editorial](../../hosting-independiente/backend/cms_content.py) y [MediaHub](../../hosting-independiente/backend/cms_media.py).
