# Plan: estrategia de contenido multiplataforma + Content Hub de Cisne Negro

Fecha: 8 de octubre de 2026. Estado: **plan para aprobación** (no se ha construido nada todavía).

Fuentes:
- El «Método Definitivo para Crear Contenido» (`../metodocontenido/`).
- El informe de análisis (`/analisis/`).
- Una línea base calculada con 200 posts de Instagram y 14 de TikTok (`datos/resumen-linea-base.json`, script `datos/linea_base.py`).
- Una investigación de mejores prácticas, casos, regulación y APIs con fuentes (§12).
- La revisión de `agency-agents` y del CMS ya publicado en `/cms/`.

---

## 1. Resumen

1. **El método se convierte en un workflow de 9 pasos (W0–W8)**, con un responsable (agente, skill o herramienta), un entregable y una compuerta de calidad en cada paso. Se agrega una compuerta que el método no tiene: **cumplimiento COFEPRIS**, porque es obligatoria en publicidad de alcohol en México.
2. **Estrategia: 4 pilares × 4 tópicos, de donde salen 16 secciones candidatas; en el mes piloto se prueban 6 con el protocolo R1–R3 del método.** Se priorizan las que los datos ya respaldan: eventos y colaboraciones rinden ×2.0, comunidad ×1.5 y carruseles 3.4× sobre la foto. Al mismo tiempo se arreglan las debilidades: 0 de 69 reseñas respondidas, TikTok abandonado, Google Business Profile sin publicaciones y frecuencia de 1.2 posts por semana.
3. **Mes piloto: del lunes 2 al domingo 29 de noviembre de 2026.** Tiene dos anclas: Día de Muertos y el **Aniversario Año III**. La preparación va del 12 de octubre al 1 de noviembre.
4. **Content Hub: un módulo nuevo dentro del CMS ya publicado (`/cms/#hub`).** La experiencia toma de Meta Business Suite: Planner con calendario, lista, kanban y matriz; un composer con vistas previas por red; aprobación con enlace para el dueño; un laboratorio de secciones que aplica el método y mide resultados; CRUD de piezas y de catálogos base (canal, formato, pilar, tópico, sección, plantilla, usuario, aliado…), y **atributos personalizados**. Publicación por etapas: primero asistida, después por API de Meta (Instagram, Facebook y Threads), y TikTok mandando el video a su bandeja de borradores.

---

## 2. Diagnóstico: de dónde partimos

### 2.1 Insights que dicen qué contenido hacer

| Insight | Dato | Implicación |
|---|---|---|
| Eventos y colaboraciones son el motor | 9 de los 10 mejores posts. Índice ×2.0, aunque son solo el 13% de lo publicado | Una sección fija de agenda y un aliado distinto cada mes |
| Coautor (collab) | Mediana 104 contra 23 de un post propio (×2.7) | Usar coautoría en Instagram en todo evento con aliado |
| Carruseles | Mediana 70 contra 20.5 de la foto (3.4×), pero son solo 26 de 200 posts | El carrusel es el formato base de producto y maridaje |
| Comunidad, mascotas, «etiqueta a tus compas» | ×1.5 | Pilar «La Parvada», hecho para que la gente lo comparta por DM |
| El cambio de voz funcionó | Captions genéricos: mediana 16 → voz con humor y eventos: 37.5 | Mantener la voz pícara y local; no volver a «Descubre/Sumérgete» |
| Mejor horario | **Martes de 12 a 14 h ×1.33** (se sostiene sin collabs) y jueves de 12 a 18 h ×1.23–1.25 | Los posts más importantes van martes y jueves |
| El peor horario es el más usado | El sábado concentra 88 de 200 posts junto con el viernes y rinde ×0.79 | El sábado queda solo para stories en vivo |
| TikTok tiene potencial | Un viral de 50,900 vistas (×57) sobre el «primer taproom con microcervecería de Pachuca»; después la cuenta dejó de publicar | Reactivar con ese mensaje, corregido: «primer», no «único» |
| Reseñas como prueba social | 4.5★ en 69 reseñas; frases que sirven para contenido («parada obligada en Pachuca») | Sección «Reseña en voz alta» y responder todas las reseñas |
| Material narrativo propio | Historias de los nombres de 8 cervezas, fundadores, sustentabilidad, prensa | Sección «¡Cuéntalo en el Cisne!» y «Lunes de producción» |

### 2.2 Debilidades que el plan corrige

- **Google Business Profile pasivo:** 0 publicaciones, 0 respuestas a reseñas y categoría «Restaurante» sin «Cervecería». Es el canal con más intención de visita.
- **Frecuencia en Instagram:** cayó de 9.8 posts al mes en 2024 a 4–5 en 2025 y 2026, con huecos de hasta 70 días.
- **TikTok:** 774 días sin publicar y sin enlace en la bio.
- **Conversación casi nula:** de 0.2 a 1.6 comentarios por post. #CuéntaloEnElCisne se ha usado en 1 de 200 posts.
- **Hashtags genéricos en inglés:** 74 de 200 posts no llevan ninguno. Hay que pasar a etiquetas locales: #pachuca, #quehacerenpachuca, #cervezaartesanalpachuca.
- **Datos que se contradicen:** el estilo de Henry IX y el ABV de ¿A poco sí pa'? no coinciden entre fuentes, y no se sabe si Guamaica es propia o invitada. **No se publican fichas técnicas hasta que el cliente las valide.**
- **Sin métricas privadas** (alcance, guardados, compartidos): dependen de los pendientes de acceso B1–B4 del backlog.
- **Riesgos fuera de redes:** la landing de Abacus con datos falsos, Tripadvisor marcado como «cerrado» y Facebook bloqueado por edad. Son pendientes del cliente; el plan no los resuelve, solo los recuerda.

### 2.3 Canales: rol y cadencia propuesta

| Canal | Estado hoy | Rol en la estrategia | Cadencia del piloto |
|---|---|---|---|
| **Instagram** @cisnenegro.mx | 3,513 seguidores, 1.2 posts/semana | Canal principal de marca y comunidad | 3–4 posts de feed por semana (carruseles y reels), stories diarias y 1 Trial Reel por semana para probar ganchos con gente que no sigue la cuenta |
| **Google Business Profile** | 4.5★, 69 reseñas, pasivo | Convertir búsquedas en visitas, SEO local | 1 publicación y 5–10 fotos reales por semana; **responder el 100% de las reseñas** (las 69 pendientes y las nuevas) |
| **TikTok** | Inactivo desde 2024 | Descubrimiento local (búsqueda y Local Feed) | 3 por semana, reutilizando los reels propios sin marca de agua |
| **Facebook** | Restringido por edad, sin datos | Cobertura de un público mayor; álbumes de eventos | Publicación cruzada de reels y carruseles, y álbumes de eventos |
| **WhatsApp** | Solo enlace de mensaje | Canal propio para lanzamientos (como Tree House) | Crear un **Canal**: martes «Barril de la semana» y viernes «Agenda del finde». Siempre a mano, porque los Canales no tienen API |
| **Threads** | Sin verificar (backlog B4) | Conversación ligera y encuestas | 3 por semana, derivados de cada pieza |
| **YouTube Shorts** | No existe | Archivo y búsqueda | Opcional: subir los mismos reels si el cliente quiere el canal |
| **Correo y Pasaporte** | Socios con aceptación de avisos por WhatsApp | Retención | Aviso de «barril nuevo» a quienes aceptaron recibirlo (plantilla de WhatsApp con costo por mensaje) |

### 2.4 Interacción ideal (la base del método)

Se calcula con likes + comentarios de los últimos 12 meses. Los datos públicos no traen compartidos ni guardados.

| Formato en Instagram | Interacción ideal inicial | Nota |
|---|---|---|
| Reel | **32** | Vistas: mediana de 1,212 reproducciones |
| Carrusel | **56** (49 sin collab) | — |
| Imagen | **43** | Sin contar el atípico del Oktoberfest (802) |
| Video de TikTok | 25 (incluye compartidos y guardados) | Sin contar el viral |

**Recalibración:** cuando el cliente dé acceso a Business Suite (B2), la interacción ideal se recalcula con la fórmula completa del método (likes + comentarios + compartidos + guardados) y se agrega la tasa por alcance, que es la métrica recomendada para cuentas pequeñas.

---

## 3. El método convertido en workflow (W0–W8)

| Paso | Qué se hace | Responsable (agente, skill o herramienta) | Entregable | Compuerta de calidad |
|---|---|---|---|---|
| **W0 Insumos** | Actualizar la línea base, las reseñas, el benchmark y el inventario de medios | `datos/linea_base.py`; skills `web-scraper-apify`, `google-maps-scraper` y `social-media-analyzer`; agente Trend Researcher; MCP Nimble para monitorear competidores | Línea base del mes y lista de material disponible | Datos con fecha de corte; nada inventado |
| **W1 Pilares y tópicos** | **Taller orgánico con los dueños** (las 5 preguntas del método) y después el *prompt maestro* para completar | Agentes Content Creator y Brand Guardian; skills `content-strategy` y `marketing-context` | 4 pilares × 4 tópicos aprobados | El dueño aprueba; cada pilar se puede medir |
| **W2 Ideas y secciones** | Lluvia de temas por tópico. Una idea se vuelve sección si tiene **varios temas y una periodicidad**; se eligen 4 secciones por pilar | Skills `social-content` y `marketing-ideas`; agente Content Creator | 16 secciones candidatas; las demás quedan en reserva | Cada sección tiene periodicidad y al menos 10 temas |
| **W3 Temas por sección** | 10 títulos con gancho y una explicación por sección | Agente copy-writer; skills `copywriting` y `content-humanizer` | Banco de temas en el Hub | Voz Cisne (pícara y local) y datos verificados |
| **W4 Formato y plantilla** | Elegir formato y plantilla (de las 9 del PDF del método, adaptadas) y diseñarla una vez para reutilizarla | Agentes Carousel Growth Engine, Instagram Curator, TikTok Strategist, Short-Video Editing Coach y format-adapter; **MCP de Canva** (brand kit y plantillas) | Plantillas Canva por sección y guion de grabación | La plantilla ahorra tiempo (regla del método); medidas y zonas seguras correctas |
| **W5 Cumplimiento** | Checklist COFEPRIS y de las plataformas por pieza | Agente Legal Compliance Checker más el nuevo «Alcohol Ad Compliance MX» (§9) | Pieza marcada como «cumple» u «observada» | Bloquea la aprobación si falla un punto obligatorio |
| **W6 Aprobación y programación** | El dueño aprueba desde el enlace; la pieza se programa o publica | **Content Hub** (§7); agente Workflow Architect | Pieza en estado Programado o Publicado | Sin aprobación no se programa |
| **W7 Prueba R1–R3** | Publicar 3 temas por sección; si R1 no llega a la interacción ideal, **cambiar hora, plantilla o formato** antes de R2 | Laboratorio del Hub; agentes Experiment Tracker y Analytics Reporter | Estado de la sección: Vigente o No funcionó | Medición a las 24 h contra la interacción ideal de su formato |
| **W8 Seguimiento** | Las secciones vigentes entran a la planeación semanal; su estado se recalcula: Normal, Buena, Saturada (60–100% en los últimos 5 posts) o Dejó de funcionar (menos del 60%) | Hub; skills `dataviz`, `weekly-review` y `schedule` (reporte semanal automático) | Reporte mensual y siguiente mes | Las secciones saturadas se renuevan o se descansan |

La línea base, los catálogos, el banco de temas, la parrilla y las métricas viven en el Hub. Así, una persona nueva puede retomar el trabajo desde ahí sin depender de esta conversación.

---

## 4. Regulación: la restricción que define el diseño

La guía de COFEPRIS (agosto de 2024; LGS art. 308 y Reglamento de Publicidad art. 34) considera **internet** un medio de difusión. Para publicidad de alcohol establece:

- **Prohibido:**
  - Mostrar a alguien bebiendo o con el recipiente en la mano.
  - Personas menores de 25 años o mensajes dirigidos a menores.
  - **Asociar el consumo con alegría, esparcimiento, éxito o sexualidad, con actividades creativas (música, arte) o deportivas, o con celebraciones cívicas o religiosas.**
  - Frases que inviten a consumir («¡ven por tu chela!») y promociones de barra libre.
- **Permitido:** informar sobre las características del producto, su calidad y su técnica de elaboración, y mostrar el servicio sin personas en cuadro.
- **Obligatorio:** leyenda sanitaria («EVITE EL EXCESO» o «EL ABUSO DE ESTE PRODUCTO ES NOCIVO PARA LA SALUD») y, en publicidad, **permiso de publicidad**.

**Conflicto:** lo que mejor funciona hoy en Cisne Negro es justo lo más expuesto: eventos con música o arte, fechas como el 15 de septiembre, el futbol y gente celebrando.

**Cómo lo resuelve el plan:**
1. **Revisión de un abogado sanitario antes del piloto.** No está claro qué tanto aplica la guía al contenido orgánico de un establecimiento sobre sí mismo (está sin verificar). Es una decisión del cliente.
2. **Producción con el cumplimiento como punto de partida:**
   - En cuadro: barril, vertido sin manos, espuma, etiquetas, ilustración, cocina, fermentadores, staff mayor de 25 años sin beber, mascotas, lugar vacío o antes de abrir.
   - Los eventos se anuncian con datos (qué, cuándo, aliado) y sin asociarlos al consumo.
   - La comida, la cultura de los nombres y el oficio cervecero cargan el contenido.
3. **Leyenda fija** en el pie del texto y en la última lámina de cada pieza sobre cerveza.
4. **Checklist bloqueante en el Hub** (§7.4). En publicidad pagada: permiso COFEPRIS y segmentación de 18+ (idealmente 25+). El contenido de marca pagado en TikTok requiere permiso de la plataforma.

---

## 5. Estrategia: pilares, tópicos y secciones (propuesta para el taller W1)

El método pide construir los pilares de forma orgánica con los dueños. Esta es la **propuesta de partida**, armada con los datos; en el taller se ajusta.

### Pilar 1. «El Barril»: oficio y producto
| Tópico | Secciones candidatas (★ = se prueba en el piloto) | Formato y plantilla |
|---|---|---|
| Barril de la semana | ★ **Barril de la semana**: ficha del barril con estilo, notas y maridaje sugerido, solo con datos validados | Carrusel de 5–7 láminas; martes de 12 a 14 h |
| Historias de nombres | ★ **¡Cuéntalo en el Cisne!**: la historia detrás de ¡Alarma!, ¿A poco sí pa'?, Barrilete Cósmico, Matador… | Reel de «volteo de etiqueta»: se oculta la etiqueta, se cuenta la historia y se revela (adaptado del volteo de libro del PDF) |
| Detrás del tanque | ★ **Lunes de producción**: el lunes cierran porque es día de cocción, así que el detrás de cámaras sale natural | Reel corto: dry hop, molienda, fermentadores |
| Escuela Cisne | **Si te gusta… pide…** (plantilla Si…/Haz): «Si te gustan las cítricas → ¡Alarma!» | Carrusel o slideshow de TikTok |

### Pilar 2. «La Mesa»: cocina y maridaje
| Tópico | Secciones candidatas | Formato y plantilla |
|---|---|---|
| Maridaje | ★ **Maridaje del finde**: las parejas oficiales (Agua Puerca + Tlayuda de picaña, ¿A poco sí pa'? + Palomitas de coliflor…) | Carrusel; jueves de 15 a 18 h |
| Platillo estrella | **El plato que manda**: dona, ceviche, Philly | Reel de proceso en cocina |
| Cocina abierta | **A puerta abierta**: detrás de cámaras de cocina | Reel |
| Para todos | **#CervezaParaTodos**: vegetariano, sin alcohol y «no soy de cerveza» | Carrusel tipo «Yo antes / Yo ahora» |

### Pilar 3. «La Parvada»: comunidad
| Tópico | Secciones candidatas | Formato y plantilla |
|---|---|---|
| Voz del cliente | ★ **Reseña en voz alta**: captura de una reseña real de Google más la respuesta del Cisne | «Pantallazo celular» (PDF); domingo |
| Pasaporte | **Ranking del Pasaporte** (mensual): mostrar el alias solo si el socio lo permite | Captura del ranking y del sello |
| Pet friendly | **Perrhijos del Cisne** | Foto o reel; hecho para compartir por DM |
| La barra | **Quién te sirve**: staff mayor de 25 y fundadores, con su barril favorito | Reel de presentación |

### Pilar 4. «La Agenda»: eventos, aliados y Pachuca
| Tópico | Secciones candidatas | Formato y plantilla |
|---|---|---|
| Eventos y collabs | ★ **Agenda Cisne** con coautoría del aliado (ya rinde ×2.0) | Imagen o carrusel con fecha, más un recap en carrusel |
| Temporada | **Efemérides**: Día de Muertos, Aniversario; evitar las cívicas por COFEPRIS | Carrusel |
| Pachuca | **Pachuca tiene lo suyo**: la ciudad, los pastes, el viento, la cultura pop | Meme o reel (plantilla Meme/Reel) |
| Lanzamientos | **Edición limitada**: «Ejercicio #1», etc. | Reel de teaser más aviso en el Canal de WhatsApp |

**Equilibrio objetivo del mes:** 30% Barril, 25% Mesa, 20% Parvada, 25% Agenda. El Hub mide el equilibrio real contra el objetivo en la matriz.

---

## 6. Parrilla del piloto de temporada (del 24 de octubre al 29 de noviembre de 2026)

> **Reprogramada el 10 de octubre de 2026.** El piloto arranca el sábado 24 de octubre, una semana antes de Halloween, y aprovecha las fechas de temporada. La fuente de verdad son las 42 piezas de [`datos/parrilla-piloto.json`](datos/parrilla-piloto.json) (versión 2). La versión anterior, que empezaba el lunes 19, queda en `datos/historico/parrilla-piloto-v1-19oct.json`.

### 6.1 Semana tipo

| Día | Espacio | Sección | Canales |
|---|---|---|---|
| Lun | A. Reel | Lunes de producción | Reel en IG y FB, TikTok, Shorts (opcional) |
| Mar 12–14 h | B. Carrusel | Barril de la semana | IG, álbum de FB, Threads, publicación en GBP, Canal de WhatsApp |
| Mié | C. Reel o TikTok | ¡Cuéntalo en el Cisne! / Si te gusta… | TikTok y Trial Reel en IG |
| Jue 15–18 h | D. Carrusel | Maridaje del finde | IG, FB, GBP |
| Vie | E. Agenda | Agenda Cisne (stories y Canal) | Stories en IG y FB, Canal de WhatsApp |
| Sáb | — | Solo stories en vivo (sin feed) | Stories |
| Dom | F. Imagen | Reseña en voz alta / Ranking | IG, FB, Threads |

Todos los días: stories con encuesta del barril, cuenta regresiva para eventos o detrás de barra. Cada semana: 5–10 fotos reales en GBP y respuesta a las reseñas.

### 6.2 Fechas de temporada

| Fecha | Festividad | Cómo se aprovecha | Regla |
|---|---|---|---|
| 24 al 31 de oct | **Semana de Halloween** | Cuenta regresiva en stories y en el Canal desde el sábado 24, etiquetas «disfrazadas», ¡Alarma! junto a una calabaza, «Les tengo miedo a las stouts» en ¡Cuéntalo!, los Camarones Piedra «que no necesitan disfraz», evento en GBP y concurso de disfraces el sábado 31 | La palabra Halloween nunca va en la misma frase que la cerveza; premio sin alcohol; nadie bebiendo en cuadro |
| 30 de oct al 1 de nov | **Día de Muertos** | Ofrenda de los perrhijos en la terraza: la comunidad trae la foto de su mascota y el domingo 1 se publica el carrusel (sin cerveza). La ofrenda a las etiquetas que se fueron sale solo con visto bueno legal | El Lunes de producción del 2 de noviembre no se relaciona con la festividad |
| Jueves 5 de nov | **Día Internacional de la Stout** (primer jueves de noviembre) | El Maridaje del finde se dedica a Agua Puerca (Imperial Stout) + Tlayuda de Picaña Adobada, la pareja oficial | La efeméride va en su propia frase; se confirma con la consulta legal |
| 13 al 16 de nov | **Buen Fin y puente** (por confirmar) | Promoción solo de comida o de growler revisado; la reseña de «las garrafitas» cae ese domingo; el martes 17 Agua Puerca destaca la lata para llevar; aviso si el Cisne abre el lunes 16 | Nada de «barra libre»; el 20 de noviembre es cívico y no se asocia a la cerveza |
| 6 al 23 de nov | **Aniversario Año III** (supuesto sábado 21) | Guarda la fecha, programa con aliados, «Quién te sirve», stories del día y recap | Si cambia la fecha se mueven agenda, stories y recap |

### 6.3 Calendario (R1–R3 = las tres pruebas del método)

| Semana | Lun | Mar | Mié | Jue | Vie | Sáb / Dom |
|---|---|---|---|---|---|---|
| **0 · 24–25 oct** (arranque) | — | — | — | — | — | Sáb: stories «Faltan 7 noches» + Canal · Dom: Reseña R1 «Parada obligada en Pachuca» y Agenda R1 «Las etiquetas ya escogieron disfraz» |
| **1 · 26 oct–1 nov** (Halloween) | Producción R1: cerrado para ustedes, abierto para el tanque | Barril R1: ¡Alarma! posa con calabaza | ¡Cuéntalo! R1: ¿A poco sí, pa'? («Les tengo miedo a las stouts») | GBP: evento de Halloween · Maridaje R1: Tropkiller + Camarones Piedra | Agenda R2: datos del sábado 31 + convocatoria a la ofrenda de los perrhijos | Sáb 31: stories de Halloween · Dom 1: ofrenda de los perrhijos y ofrenda a las etiquetas (solo con visto bueno legal) |
| **2 · 2–8 nov** (Muertos y Stout) | Producción R2: todo empieza en un costal | Barril R2: Barrilete Cósmico | ¡Cuéntalo! R2: ¡Alarma! y la denuncia anónima | GBP: hamburguesas · Maridaje R2: Día de la Stout, Agua Puerca + Tlayuda | Agenda R3: Año III, guarda la fecha | Dom: Reseña R2 «el personal se toma el tiempo de explicar» |
| **3 · 9–15 nov** (Buen Fin) | Producción R3: los fermentadores (y grabación de «Quién te sirve») | Barril R3: ¿A poco sí pa'? | ¡Cuéntalo! R3: Barrilete Cósmico y la cita de Sacheri | GBP: para quien no toma alcohol · Maridaje R3: Kiwi Plis + Taco de Pescado | Buen Fin (por confirmar) · Año III: el programa se está armando | Dom: Reseña R3 «te venden las garrafitas» |
| **4 · 16–22 nov** (puente y Año III) | Feriado: Quién te sirve | Barril: Agua Puerca, también en lata para llevar | Si te gusta… R1: por perfil | GBP: Año III · Maridaje: ¿A poco sí pa'? + Palomitas de Coliflor | Año III: ya hay programa | Sáb 21: stories del Año III · Dom: Reseña «de esos lugares a los que da gusto volver» |
| **5 · 23–29 nov** (cierre) | Recap: así quedó el Año III | Barril: Guamaica | Si te gusta… R2: las cinco parejas oficiales | GBP: postres · Maridaje: Boca Negra + Sándwich de Suadero | Agenda del finde y lo que viene en diciembre | Dom: Ranking del Pasaporte de noviembre · reporte mensual |

Notas:
- **Volumen:** 42 piezas y 131 variantes: 31 publicaciones en el feed de Instagram (5 a 7 por semana completa), 14 TikToks, 7 publicaciones en GBP (más 5–10 fotos reales por semana), 12 avisos en el Canal de WhatsApp y stories diarias.
- **Pruebas:** las seis secciones del piloto hacen R1–R3 entre el 25 de octubre y el 15 de noviembre. «Si te gusta…» arranca el 18 de noviembre y su R3 queda para diciembre, igual que el Ranking del Pasaporte.
- **Pasaron al banco de temas** (sin fecha, listas para diciembre): «¿A dónde va el bagazo?», el barril de Henry IX, la reseña «casi cada semana algo nuevo», el GBP del Ceviche de Atún, la pareja propuesta ¡Alarma! + Hamburguesa De Costilla de Res y «Si te gusta… por fruta».
- **Para arrancar el sábado 24 hacen falta:** la confirmación de Halloween y del concurso, la decoración de temporada para las fotos, la tap list de la semana y el permiso de @rick_agridulce para la ilustración del miércoles 28.
- **Datos por validar con el cliente antes de producir:** la ofrenda de mascotas en la terraza, las fichas de Tropkiller y Boca Negra, la fecha del aniversario, los aliados, los permisos de los ilustradores, el Buen Fin y si se abre el lunes 16. La consulta legal revisa la ofrenda de etiquetas y la mención del Día de la Stout.

### 6.4 KPIs del piloto

| Tipo | KPI | Meta del mes | Fuente |
|---|---|---|---|
| ⭐ Estrella | **Visitas atribuidas** | Línea base en noviembre; meta para diciembre | Altas y visitas del Pasaporte con UTM o código por canal, y «¿cómo nos conociste?» |
| Constancia | Posts de feed por semana en IG | ≥ 3.5 | Hub |
| Método | Secciones probadas y vigentes | 6 probadas, ≥ 3 vigentes | Laboratorio del Hub |
| Interacción | Mediana por formato contra la interacción ideal | ≥ 100% en las secciones vigentes | Medición a 24 h |
| Distribución | Compartidos y guardados por alcance | Línea base (requiere B2) | Insights de IG |
| Local | Reseñas respondidas | 100% (69 pendientes + nuevas) | GBP |
| Local | Reseñas nuevas por semana | ≥ 3, de forma constante | Pasaporte → Google |
| Descubrimiento | TikTok reactivado | 12 videos; mediana ≥ 900 vistas | TikTok |
| Conversión | Clics al menú QR y al Pasaporte desde redes | Línea base | UTM |

---

## 7. Content Hub: el tablero de contenido

### 7.1 Dónde vive

Será un módulo del CMS ya publicado en `/cms/` (Flask + SQLite, «Neón y tinta», login con CSRF, MediaHub con 477 medios):
- **Código:** `backend/cms_hub.py` como Blueprint, con datos propios en `hub.sqlite`.
- **Rutas:** `/cms/#hub` y `/cms/api/hub/*`.
- **Lo que se reutiliza:** la sesión, los permisos, la bitácora (`activity`), MediaHub (las piezas guardan `media_id`), el catálogo publicado de cervezas, platillos y eventos (como fuente de temas), y los componentes de diálogo, tabla y formulario.

Las piezas **no** se guardan en el documento único del CMS: cada pieza tiene su propio historial de versiones.

> **Requisito previo:** el código del CMS está en producción pero **no tiene ningún commit en git** y lo construyó otra sesión. Antes de tocarlo hay que respaldarlo y versionarlo de forma coordinada.

### 7.2 Navegación (inspirada en Meta Business Suite)

| Sección | Qué muestra | Patrón de referencia |
|---|---|---|
| **Inicio** | Pendientes de aprobación, lo próximo a publicar, errores, KPIs de la semana, cuota de API | Pantalla de inicio de Business Suite |
| **Planner** | Calendario de mes o semana con fichas por red (ícono y color por pilar). Arrastrar para reprogramar, crear con doble clic, filtros por red, pilar, sección, estado y responsable, y «horarios sugeridos» (al inicio salen de la línea base y luego aprenden de los resultados) | Planner de Meta y Later |
| **Parrilla** | Tabla editable estilo hoja de cálculo con todas las piezas: edición en línea, columnas configurables (incluidos los atributos personalizados), exportar a CSV o PDF para el cliente | Matriz de contenido del método |
| **Matriz** | (a) Pilar × tópico × sección con conteo de piezas y estado; (b) pilar × red × semana con cuotas contra lo real (mapa de calor); (c) equilibrio del mes contra el objetivo del §5 | Matriz del método |
| **Kanban** | Columnas por estado: Idea → Borrador → En revisión → Observada → Aprobada → Programada → Publicada / Error | Planable y Notion |
| **Composer** | Texto base más variantes por red; MediaHub integrado; vista previa real (feed 4:5 o 3:4, reel o story 9:16, TikTok, Threads, GBP, WhatsApp); contador de caracteres y validador de proporción y duración por formato; hashtags guardados; UTM automático; **checklist de cumplimiento**; programar o enviar a revisión | Composer de Business Suite |
| **Aprobación** | Enlace firmado para el dueño **sin login**, optimizado para celular: ver vista previa, aprobar, pedir cambios con comentario. Comentarios internos ocultos al dueño; recordatorio si la pieza vence sin aprobar | Sprout Social |
| **Laboratorio** | Las secciones con su prueba R1–R3 contra la interacción ideal por formato; regla automática «cambiar hora, plantilla o formato» si R1 falla; estado de la prueba (No empezada, Empezada, Vigente, No funcionó) y estado de la sección (Normal, Buena, Saturada, Dejó de funcionar) con la regla del 60% en los últimos 5 posts | Hoja de iteración del método |
| **Resultados** | Captura a 24 h (manual al principio, después por la API de Insights), gráficas por sección, formato, día y hora, y reporte mensual | Analytics Reporter + `dataviz` |
| **Banco de ideas** | Temas por sección (W3), en reserva, con botón para convertirlos en pieza | Tormenta de ideas del método |
| **Catálogos** | CRUD de las entidades base (§7.3) | — |
| **Ajustes** | Conexiones con las redes (OAuth), tokens, cuotas, la leyenda sanitaria por defecto, zona horaria | — |

### 7.3 Modelo de datos (CRUD)

**Catálogos base:**

| Catálogo | Campos clave | Para qué sirve |
|---|---|---|
| **Canal** | Red, cuenta o handle, color, método de publicación (API, bandeja o manual), límites, conexión | Filtros, vistas previas, cuotas y en qué red sale cada pieza |
| **Formato** | Por canal: tipo (reel, carrusel, imagen, story, video, texto, publicación GBP, aviso de Canal), proporción, duración máxima, límite de caracteres, número de láminas | El composer valida automáticamente; cada formato tiene su propia interacción ideal |
| **Pilar** | Nombre, color, % objetivo, descripción | Equilibrio y medición por área |
| **Tópico** | Pilar, nombre | Variedad dentro del pilar |
| **Sección** | Tópico, nombre, periodicidad, formato y plantilla por defecto, **interacción ideal**, tiempo de producción, estado de prueba, estado de sección | El corazón del método |
| **Plantilla** | Tipo de post (las 9 del PDF y las propias): qué es, virtud, qué se necesita, tiempo, enlace al diseño de Canva | Producir rápido, como pide el método |
| **Usuario / rol** | Se reutilizan los usuarios del CMS; roles nuevos: dueño, editor, aprobador, community manager | Permisos y responsables |
| **Aliado** | Cuenta, tipo (chef, artista, cervecería, marca), contacto, historial de collabs | Coautoría (×2.7) y agenda |
| **Campaña / evento** | Nombre, fechas, objetivo, piezas | Anclas como el Aniversario y las efemérides |
| **Hashtags y UTM** | Grupos por pilar o canal, parámetros | Constancia local y atribución |
| **Checklist de cumplimiento** | Reglas (bloqueantes o de aviso) por tipo de pieza | El paso W5 automatizado |

**Datos de operación:**
- **Pieza.**
- **Variante por canal:** copy, medios, fecha programada, estado de publicación, id externo, error.
- **Versión de pieza.**
- **Comentario.**
- **Aprobación:** quién, cuándo, decisión y motivo.
- **Métrica por variante:** likes, comentarios, compartidos, guardados, envíos, alcance, vistas, fuente y momento de medición.
- **Cola de publicación.**
- **Bitácora.**

### 7.4 Atributos personalizados: por qué aportan valor

Son **campos definidos por el usuario** para cualquier entidad (pieza, sección, aliado, campaña) sin tocar código. Pueden ser de texto, número, lista, fecha, sí/no, usuario o enlace a una cerveza o platillo del catálogo. Se pueden marcar como filtrables, como columna de la parrilla o como dimensión de los reportes.

Ejemplos para Cisne Negro y la pregunta que permiten responder:

| Atributo | Tipo | Pregunta que responde |
|---|---|---|
| Cerveza destacada | Enlace al catálogo | ¿Qué barril genera más interacción y visitas? |
| Tipo de gancho (pregunta, dato, humor, revelación) | Lista | ¿Qué gancho retiene más en los reels? |
| Con coautor | Sí/no + aliado | ¿Cuánto suma cada aliado? |
| Personas en cuadro (ninguna / staff 25+ / clientes) | Lista | Control de cumplimiento y su efecto en el rendimiento |
| Objetivo (alcance / comunidad / visita) | Lista | ¿Cada pieza cumple el objetivo para el que se hizo? |
| Requiere grabación / locación | Sí/no + lista | Planear la sesión de grabación del lunes |
| Presupuesto de pauta | Número | ROI cuando se active la publicidad pagada |

Así el tablero crece con el negocio. Por ejemplo, el día que se quiera medir «temporada de futbol» o «colaboración con ilustrador», basta con crear el atributo. Técnicamente es un modelo de definición de atributos más sus valores, validado por tipo e indexado para filtrar.

### 7.5 Publicación: por etapas

| Etapa | Instagram, Facebook, Threads | TikTok | GBP | Canal de WhatsApp / YouTube |
|---|---|---|---|---|
| **H1 Asistida** (MVP) | El Hub avisa a la hora programada; botones de «copiar texto» y «descargar medios»; se marca como publicado y se pega el enlace | Igual | Igual | Igual |
| **H2 API** | Graph API con *Standard Access* (cuentas propias, sin revisión de la app): programación por un timer de systemd fuera de gunicorn, URLs de medios firmadas y temporales, tokens en `/etc/` fuera del repo, reintentos y estado de error, cuota visible (`content_publishing_limit`); Trial Reels vía `trial_params` | **Upload a la bandeja** (`video.upload`): el staff termina la publicación en la app (sin auditoría de TikTok) | `localPosts` si Google aprueba el acceso (≈14 días); si no, manual | Canal: siempre manual (no tiene API). YouTube: privado hasta pasar la auditoría, o manual |
| **H3 Insights** | Métricas por API (alcance, guardados, compartidos, envíos) a las 24 h: completa la fórmula del método | API de TikTok de lectura | Métricas de GBP | — |

**Alternativa a evaluar:** Postiz instalado en el VPS (código abierto) como motor de publicación, con el Hub encima. Ahorra la integración pero agrega un servicio que mantener. Composio también tiene conectores de redes que vale la pena revisar.

### 7.6 UX/UI

- **Patrones de Meta que se copian:** calendario con arrastrar y soltar, pestañas Programado / Publicado / Borradores, vista previa por ubicación y personalización por red, horarios sugeridos y estados visibles con color.
- **Más simple que Meta:** una sola pantalla para crear (el composer en un panel lateral), acciones masivas en la parrilla, atajos de teclado y aprobación móvil con un toque.
- **Accesibilidad:** foco visible, objetivos táctiles de 44 px, contraste AA y sin depender solo del color para el estado (ícono más texto).
- **Estilo:** «Neón y tinta» del CMS para que se sienta parte del mismo producto. Sin librerías externas (la CSP del CMS solo permite archivos propios), así que el calendario se construye en JS propio.

---

## 8. Agentes, skills, MCP y herramientas (qué aporta cada uno)

| Necesidad | Usar | Aporte |
|---|---|---|
| Estrategia y calendario | Agentes Content Creator, Social Media Strategist y Brand Guardian; skills `content-strategy`, `social-content` y `marketing-ideas` | Pilares, secciones y voz |
| Orquestación | Runbook `agency-agents/strategy/runbooks/scenario-marketing-campaign.md` y plantillas de handoff (`strategy/coordination/handoff-templates.md`) | Traspasos con criterios de aceptación entre fases |
| Copy | Agente copy-writer; skills `copywriting` y `content-humanizer` | Textos por red con sus límites, sin sonar a IA |
| Diseño de plantillas | **MCP de Canva** (brand kit, plantillas de marca, exportación) y agente format-adapter | Plantillas reutilizables por sección (W4) |
| Video | Agentes Short-Video Editing Coach y TikTok Strategist; `comfy` solo para maquetas, nunca para piezas finales (riesgo de originalidad y de COFEPRIS) | Guiones y ganchos |
| Investigación y monitoreo | Agente Trend Researcher; skills `web-scraper-apify` y `google-maps-scraper`; MCP Nimble | Competidores de Pachuca y reseñas nuevas |
| Medición | Agentes Experiment Tracker y Analytics Reporter; skills `dataviz` y `statistical-analyst` | Las pruebas R1–R3, reportes y lectura honesta de muestras pequeñas |
| Automatización | Skills `schedule` (reporte semanal en la nube) y `weekly-review` | Constancia sin depender de la memoria del equipo |
| Construcción del Hub | Agentes UX Architect, UI Designer, Workflow Architect, Backend Architect y Frontend Developer; skills `ui-ux-pro-max`, `frontend-design` y `playwright-pro`; agentes Evidence Collector, Accessibility Auditor y API Tester | Diseño, desarrollo y QA con evidencia |

**No conviene usar:** los agentes de plataformas chinas (incluido «multi-platform-publisher», que publica solo en redes chinas) ni los orientados a B2B, LinkedIn o X.

---

## 9. Agentes nuevos que conviene crear

1. **Brewery Content Strategist:** aplica este método (W1–W8) con conocimiento de estilos, temporadas, maridaje y operación de taproom.
2. **Alcohol Ad Compliance MX:** COFEPRIS (LGS 308 y Reglamento art. 34), leyendas, edad 25+ en pantalla y políticas de Meta, TikTok y Google; revisa cada pieza y bloquea la aprobación si falla.
3. **Social Publishing Integrator:** Graph API, TikTok Content Posting, GBP; tokens, cuotas y errores.

También se pueden instalar del repo agentes que faltan: API Platform Engineer, Identity & Access Engineer, Test Automation Engineer, Statistician y Data Privacy Officer (`scripts/install.sh --tool claude-code --agent …`).

---

## 10. Hoja de ruta

| Fase | Fechas propuestas | Entregables | Depende de |
|---|---|---|---|
| **F0 Requisitos** | 9 al 16 de oct | CMS versionado en git (coordinado con la otra sesión); accesos B1–B4 solicitados; consulta legal COFEPRIS; Canal de WhatsApp creado; fecha del aniversario y tap list de noviembre | Cliente y otra sesión |
| **F1 Estrategia** | 12 al 18 de oct | Taller W1, 4×4 pilares y tópicos, 16 secciones, banco de temas (W3), plantillas de Canva de las 6 secciones del piloto | Taller con los dueños |
| **F2 Hub MVP (H1)** | 13 al 31 de oct | Catálogos con CRUD, atributos personalizados, Planner, Parrilla, Matriz, Kanban, Composer, Aprobación por enlace, Laboratorio y publicación asistida; pruebas de backend, E2E y accesibilidad | F0 (CMS en git) |
| **F3 Producción de temporada** | 17 al 23 de oct | Fotos de la decoración de Halloween, grabación del lunes 26 (lote de 2 semanas), parrilla de la primera semana cargada y aprobada, respuestas a las 69 reseñas | F1 (el piloto arranca con la parrilla semilla aunque el Hub siga en construcción) |
| **F4 Piloto** | 24 de oct al 29 de nov | Publicación, pruebas R1–R3 y reporte semanal | — |
| **F5 API e Insights (H2–H3)** | En paralelo, nov | Publicación por API en Meta, bandeja de TikTok, métricas automáticas | Accesos de Meta (B2) |
| **F6 Cierre** | 30 de nov al 4 de dic | Reporte mensual: secciones vigentes, recalibración de la interacción ideal y plan de diciembre | — |

---

## 11. Decisiones para el usuario y riesgos

**Decisiones:**
1. ¿El mes piloto es **noviembre** (con el Aniversario Año III) o se adelanta a otra fecha?
2. ¿El Hub va **dentro del CMS** (recomendado) coordinando con la otra sesión, o como un servicio aparte con login propio?
3. **Publicación:** ¿API directa de Meta (recomendado) o Postiz instalado como motor?
4. **COFEPRIS:** ¿se paga la consulta legal antes del piloto? Mientras tanto, se produce con el cumplimiento como punto de partida.
5. ¿Quién aprueba (uno o los dos hermanos Carrasco) y quién produce las fotos y videos (staff o Softvibes)?
6. **Canales:** ¿YouTube Shorts y Threads entran en el piloto?

**Riesgos:**
- **El CMS sin versionar:** construir encima sin respaldo puede perder producción.
- **La regulación limita el formato más fuerte** (eventos con música y celebración).
- **Sin métricas privadas,** la interacción ideal queda subestimada.
- **Muestras chicas** (3 posts por sección): el método decide con criterio operativo, no estadístico, y así se reporta.
- **Dependencia de aliados** para la coautoría.
- **Datos de producto sin validar.**

---

## 12. Fuentes principales de la investigación

- **COFEPRIS,** Guía de Publicidad de Bebidas Alcohólicas (agosto de 2024): https://www.gob.mx/cms/uploads/attachment/file/936691/Gu_a_Publicidad_de_Bebidas_Alcoh_licas._CAS_y_COS___002_.pdf__4_.pdf
- **Reglamento de la LGS en Materia de Publicidad:** https://www.diputados.gob.mx/LeyesBiblio/regley/Reg_LGS_MP.pdf
- **Meta, publicación de contenido en Instagram (Graph API):** https://developers.facebook.com/docs/instagram-platform/content-publishing
- **TikTok Content Posting API:** https://developers.tiktok.com/doc/content-posting-api-get-started-upload-content
- **Google Business Profile, `localPosts`:** https://developers.google.com/my-business/reference/rest/v4/accounts.locations.localPosts/create
- **Instagram Trial Reels:** https://creators.instagram.com/blog/instagram-trial-reels
- **Instagram limita el alcance de cuentas que repostean contenido ajeno** (30 de abril de 2026): https://techcrunch.com/2026/04/30/instagram-restricts-reach-of-content-aggregators-in-new-crackdown/
- **Benchmarks de Socialinsider 2026:** https://www.socialinsider.io/social-media-benchmarks
- **Benchmarks de Rival IQ 2025:** https://www.rivaliq.com/blog/social-media-industry-benchmark-report/
- **Whitespark, factores de ranking local 2026:** https://whitespark.ca/local-search-ranking-factors/
- **Sprout Social, flujos de aprobación:** https://sproutsocial.com/insights/social-media-approval/
- **Tree House** (Forbes, junio de 2025): https://www.forbes.com/sites/emsauter/2025/06/15/tree-house-brewing-company--the-largest-brewery-youve-never-heard-of/

**Pendiente de verificar:**
- Qué tanto aplica COFEPRIS al contenido orgánico de un establecimiento.
- El límite exacto de publicaciones por API en Instagram (50 o 100 cada 24 h).
- El mínimo de seguidores para usar Trial Reels.
- La política de anuncios de alcohol de Google.
- Las fechas del Buen Fin 2026.
- Los precios de los agregadores, que vienen de fuentes secundarias.
