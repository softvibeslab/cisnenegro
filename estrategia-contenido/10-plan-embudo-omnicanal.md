# Plan: embudo de ventas omnicanal y automatizado de Cisne Negro

Fecha: 8 de octubre de 2026. Estado: **plan para aprobación**. Complementa la estrategia de contenido ([08](08-plan-estrategia-contenido-y-content-hub.md)) y el Content Hub ([09](09-spec-content-hub.md)).

Insumos:
- **Mapa de puntos de contacto y datos del proyecto:** sitio, menú QR, Pasaporte, `/v2` (pedido, mesero), CMS y Hub.
- **Audiencia de `@oktoberfestjabonera`:** 700 de 1,550 seguidores, 225 de 258 seguidos, 50 posts y 97 comentarios, sin login. Costo: 1.96 USD. Los datos agregados están en `datos/audiencia-jabonera.json`; los crudos, fuera de git.
- **Línea base de Instagram y TikTok y 69 reseñas de Google:** `datos/resumen-linea-base.json`.
- **Investigación de embudos, automatización y regulación**, con fuentes (§12).

---

## 1. Resumen

1. **El embudo tiene 6 etapas más un carril B2B de aliados:** Descubrir → Considerar → 1ª visita → **2ª visita** → Lealtad → Embajador. El punto crítico es la **2ª visita**: alrededor del 78% de los clientes de un restaurante viene una sola vez, y quien llega a 4 visitas casi siempre se queda. Hoy la primera cortesía del Pasaporte llega en la visita 5, demasiado tarde.
2. **La página propia es el centro de todo:** cada canal lleva a `cisnenegro…/ir` y a páginas de destino con UTM. De ahí salen 5 llamadas a la acción (CTA): **Ver agenda / Apartar lugar**, **Ver menú y maridaje**, **Cómo llegar**, **Abrir mi Pasaporte** y **Escribir por WhatsApp (con referencia)**. Hoy no se mide nada: no hay analítica, UTM ni origen del registro.
3. **6 buyer personas**, basadas en la audiencia del festival, las reseñas y los datos propios. Se aplican a la parrilla como **atributos del Hub** (`persona`, `etapa`, `cta`) y a la base de socios como **segmentos** (frecuencia y antigüedad de visita, más preferencias).
4. **12 automatizaciones**, priorizadas por impacto medido. El «gracias» después de la visita logra ~30% de regreso, el aviso de visitas acumuladas ~20%, la bienvenida ~7% y el envío masivo solo ~0.3%. Se orquestan con **n8n en el VPS**, salen por la **API oficial de WhatsApp** y por **email (Brevo)**, y usan la API oficial de Instagram para responder comentarios por DM y la de Google para responder reseñas, siempre con aprobación humana.
5. **Restricciones que definen el diseño:**
   - La política de WhatsApp (23 de septiembre de 2026) **prohíbe mensajes sobre alcohol desde la app WhatsApp Business** y la venta de alcohol por catálogo. Solo se permiten por la API oficial, a mayores de 18 y con consentimiento por categoría.
   - COFEPRIS: leyenda obligatoria, sin imperativos de consumo y sin asociar el alcohol con fiesta, arte, música o deporte.
   - La ley de datos personales (LFPDPPP 2025) exige que cada finalidad de marketing tenga su propia casilla de consentimiento y la opción de negarse.

---

## 2. Patrones que definen el embudo

| Patrón | Evidencia | Qué implica |
|---|---|---|
| **Las colaboraciones disparan el alcance** | En el festival, un post con coautor tiene **×13.6** la interacción mediana; en Cisne, ×2.7. El post de 802 tuvo 5 coautores | La etapa Descubrir se apoya en coautorías y en un aliado por mes |
| **El alcance del festival no es local** | El 38% de los comentarios del festival está en posts del músico invitado, y el 7% son fans que preguntan por fechas en otras ciudades | Medir por **visita**, no por likes; filtrar por audiencia local |
| **La gente pregunta datos, no invita** | 25% de los comentarios son preguntas de logística (hora, qué incluye, mochila); solo el 2% etiqueta a amigos | La página de evento debe responder antes de que pregunten (fecha, hora, qué incluye, estacionamiento) |
| **El público es creativo y de escena** | Arte, diseño y foto (15%) y música o DJ (10%) son los intereses más comunes en bios; arte y música suman el 40% de los negocios y creadores seguidores | La persona P2 es grande, pero COFEPRIS prohíbe asociar el consumo con arte o música: el evento se anuncia con datos |
| **La comida convierte a quien no toma cerveza** | La comida aparece en el 69% de las reseñas (4.48★); el maridaje obtiene 5★ | La Mesa y el menú QR sirven de puerta de entrada para P3 |
| **El servicio es la fuga del embudo** | Servicio 4.30★ (lo más bajo); precio 3.75★; críticas a la frescura | El NPS con alerta al dueño en tiempo real y la respuesta a reseñas son parte del embudo |
| **La 2ª visita decide** | 78% de los clientes viene una sola vez; con 4 visitas, ~95% regresa (Bloom y Paytronix) | Micro-recompensa sin alcohol en la visita 2 y recordatorio a los 21 días |
| **Responder reseñas suma** | 0 de 69 respondidas; responder trae +12% de reseñas y +0.12★ (HBR); 42% evita negocios que no responden (BrightLocal 2026) | Es la primera acción, la más barata |
| **No hay forma de medir** | No hay GA4/Pixel/Plausible, UTM, «¿cómo nos conociste?» ni ligas de WhatsApp con referencia | Sin esto no hay embudo que optimizar: es la fase 0 |

---

## 3. Buyer personas

Son pesos **estimados** dentro de la audiencia comprometida (inferencia triangulada, no medición). Toda la comunicación se dirige a mayores de 25 por COFEPRIS; la edad real no se midió.

| | Persona | Peso | Motivación | Dolor u objeción | Dónde y cuándo | Entra al embudo por | CTA que le funciona |
|---|---|---|---|---|---|---|---|
| **P1** | El plan del finde con la banda | ~30% | Plan resuelto en grupo | Información incompleta, servicio lento, estacionamiento | Reels, stories y Canal de WhatsApp; decide jue–vie de 15 a 20 h | Descubrir (evento o aliado) | Ver agenda → Apartar lugar (WhatsApp con referencia) |
| **P2** | La Parvada creativa (diseño, ilustración, DJ, foto) | ~20% | Escena local, lugares con personalidad | Lugar vacío, trato frío | Reels y collabs, jue–sáb de noche | Descubrir (coautoría) | Convocatoria «¡Cuéntalo en el Cisne!», expo o noche de vinilos (anunciada con datos) |
| **P3** | Foodie pachuqueño / no es de cerveza | ~18% | Comer bien y probar | Carta corta, opciones vegetarianas, precio | Carruseles, Google Maps, foodies locales; domingo 14–19 h | Descubrir por Google o por un creador | Ver menú y maridaje · Cómo llegar |
| **P4** | El lupulero de barrio (geek cervecero) | ~14% | Estilos nuevos, hablar con quien la hace | Frescura, precio contra calidad, sin latas | IG, Canal «barril nuevo», mar–jue | Considerar → Lealtad | Pasaporte por estilos, vuelo de 4 oz, growler, aviso de barril de su estilo |
| **P5** | El socio de la escena (negocios y creadores) | ~12% | Alcance compartido, eventos, venta | — | DM, WhatsApp | Carril B2B | Propuesta de collab mensual, tap takeover, barril en consignación |
| **P6** | Perrhijos y familia de domingo | ~6% | Lugar pet friendly, plan tranquilo | Horario, estacionamiento | Stories, Facebook, domingo temprano | Considerar | Perrhijos del Cisne, comida para todos (nunca menores en contenido con cerveza) |

**Segmentos de la base de socios** (operativos, calculados con datos del Pasaporte):
- **Por recencia y frecuencia de visitas:**
  - Nuevo: 1 visita, menos de 30 días.
  - En camino: 2–3 visitas.
  - Habitual: 4–9 visitas.
  - Campeón: 10 o más y activo.
  - En riesgo: habitual sin visita en 45 días.
  - Dormido: más de 90 días sin visita.
- **Preferencias:** estilo favorito (de los pedidos ligados al socio y de una pregunta opcional), come o solo bebe, viene a eventos, trae mascota, día y franja habitual.
- **Consentimientos por finalidad:** novedades de barril, eventos, recordatorios de cortesía, cumpleaños. Cada mensaje automático exige el consentimiento correspondiente.

---

## 4. El embudo

| Etapa | Objetivo | Personas | Canales y formatos | Secciones de la parrilla | CTA → destino | Automatización | KPI |
|---|---|---|---|---|---|---|---|
| **1. Descubrir** | Que Pachuca sepa que existe y por qué es distinto | P1, P2, P3 | Reels y TikTok (búsqueda local), coautorías, Trial Reels, perfil de GBP, YouTube Shorts | Agenda Cisne (collab), ¡Cuéntalo en el Cisne!, Pachuca tiene lo suyo, Edición limitada, Efemérides | «Ver agenda» → `/ir`, «Cómo llegar» | Comentario con palabra clave → DM con enlace (A10) | Alcance de no seguidores, vistas de GBP, visitas a `/ir` |
| **2. Considerar** | Resolver dudas y antojar | P3, P4, P6 | Carruseles, GBP (publicaciones y fotos), Threads, Canal de WhatsApp | Barril de la semana, Maridaje del finde, El plato que manda, #CervezaParaTodos, Reseña en voz alta, Perrhijos | «Ver menú y maridaje» → `/menu/`; «Cómo llegar»; «Apartar lugar» → WhatsApp con referencia | Respuestas a reseñas de GBP con borrador de IA (A11) | CTR a `/menu/` y a rutas; consultas de WhatsApp con referencia |
| **3. 1ª visita** | Convertir la visita anónima en socio | Todas | Menú QR en mesa, Wi-Fi para socios, mesero | (en el lugar) | «Abrir mi Pasaporte» (registro con origen) | Bienvenida (A1) | Registros por visita; % que llega con origen |
| **4. 2ª visita** | Que regrese en 30 días o menos | P1, P3, P6 | WhatsApp por API, email | Agenda del finde, Maridaje | Enlace al evento o al menú | Gracias post-visita + NPS (A4); recordatorio a los 21 días con micro-recompensa sin alcohol (A2) | % con 2ª visita ≤30 días (meta >22%) |
| **5. Lealtad** | Llegar a 4 o más visitas y mantenerse activo | P4, P1 | WhatsApp, Pasaporte (PWA), stories | Lunes de producción, Barril de la semana, Ranking | «Tu Pasaporte» | Visitas acumuladas (A3), barril de tu estilo (A7), cortesía por vencer (A8), reactivación por inactividad (A6) | % activo a 90 días; visitas por socio al mes |
| **6. Embajador** | Reseñas, contenido de clientes y referidos | Campeones | Google, IG | Reseña en voz alta, Ranking, Quién te sirve | «Cuéntalo en Google» (ya existe), «Trae a alguien» (referido) | NPS ≥9 → reseña (existe); NPS ≤6 → alerta al dueño (A5) | Reseñas al mes, % respondidas, ★, NPS |
| **B2B. Aliados** | Una collab al mes | P5 | DM, WhatsApp, email | Agenda Cisne, Edición limitada | «Propón una collab» → `/aliados` | Seguimiento de aliados en el Hub (catálogo Aliado) | Collabs al mes; alcance prestado; visitas atribuidas al código del aliado |

**Mezcla objetivo de la parrilla por etapa** (por semana): 35% Descubrir, 30% Considerar, 20% 2ª visita y Lealtad, 15% Embajador. Se mide en la vista «Embudo» del Hub (§8).

---

## 5. Omnicanal: todos los canales a la página, y de ahí al CTA

```
 IG · TikTok · FB · Threads · YT Shorts · GBP · Canal WA · QR impreso · aliados
            │  (cada enlace con UTM; cada QR con su código)
            ▼
   /ir  (link-in-bio propio: 5 botones, se edita desde el CMS)
            │
   ┌────────┼──────────────┬───────────────┬───────────────┐
   ▼        ▼              ▼               ▼               ▼
/eventos/<evento>  /menu/ (maridaje)   Cómo llegar     /menu/#pasaporte   WhatsApp ?text=…(ref)
 Apartar lugar      Mi pedido → mesero  (Maps + UTM)    registro + origen   (apartar, grupos, collab)
            │                             │                │
            └──────────── visita ─────────┴──── check-in del Pasaporte (dato propio) ──► automatizaciones
```

**Reglas:**
- **Página propia, no Linktree.** El dominio, el SEO y los datos quedan en el negocio. Se crea `/ir` con los 5 CTA, editable en el CMS.
- **UTM obligatorio** en todo enlace: `utm_source=<red>&utm_medium=<bio|story|reel|post|qr|gbp|wa>&utm_campaign=<campaña>&utm_content=<clave de la pieza>`. El Hub lo arma solo a partir de la clave de la pieza.
- **QR distintos por destino:** por mesa (lleva el número de mesa, que hoy se escribe a mano), por campaña (carteles y posavasos) y por aliado.
- **WhatsApp con referencia:** `wa.me/52771…?text=Quiero%20apartar%20para%20<evento>%20(ref:IG-REEL-<clave>)`. La referencia permite atribuir aunque el chat sea manual.
- **Página de evento** (plantilla nueva del CMS):
  - Fecha, hora, aliado, qué incluye y qué no, estacionamiento, mascotas.
  - Cupo honesto y cuenta regresiva ligada a un límite real.
  - Un solo CTA: «Apartar lugar».
  - Sin imperativos de consumo.
- **CTA según COFEPRIS:** «Ver agenda», «Ver menú», «Cómo llegar», «Apartar lugar», «Abrir mi Pasaporte». Nada de «ven por tu chela».

**CTA por canal:**

| Canal | CTA principal | Destino |
|---|---|---|
| IG (bio, stories, reels) | Ver agenda · Ver menú | `/ir` con UTM; sticker de enlace en stories |
| TikTok | Enlace en bio (reactivar) | `/ir` |
| Facebook | Cómo llegar · Ver agenda | `/ir` y álbum del evento |
| Threads | Conversación → Ver agenda | `/ir` |
| YouTube Shorts | Enlace relacionado | `/ir` |
| GBP | Botón Menú · Rutas · Llamar | `/menu/?utm_source=google&utm_medium=gbp` |
| Canal de WhatsApp | Ver agenda · Barril de la semana | Página del evento o `/menu/` |
| QR de mesa | Menú, Pasaporte, Wi-Fi para socios | `/menu/?mesa=N` |

---

## 6. Automatizaciones

**Stack (~5–15 USD al mes más el costo por mensaje):**
- **n8n Community** en el VPS como orquestador.
- **WhatsApp Cloud API** (número verificado; plantillas de servicio y marketing).
- **Brevo Free** para email.
- **API oficial de Instagram** para responder comentarios por DM (o ManyChat Pro, unos 29–39 USD al mes, si no se quiere mantener código).
- **API de reseñas de Google Business Profile.**
- **Analítica sin cookies** (Plausible o Umami en el VPS), más GA4 si se quiere la integración con GBP.

El backend del Pasaporte suma una tabla de eventos de salida y un webhook firmado hacia n8n. **No se usa la app WhatsApp Business para promociones de cerveza**, porque su política lo prohíbe.

| # | Flujo | Disparador | Canal | Consentimiento | Mensaje (resumen, sin imperativos) | Medición |
|---|---|---|---|---|---|---|
| A1 | Bienvenida | Registro en el Pasaporte | WhatsApp (servicio) / email | Necesario (servicio) | Tu Pasaporte, cómo funcionan los sellos, Wi-Fi | % que hace el 1er check-in |
| A2 | 2ª visita | Día 21 sin 2ª visita | WhatsApp (marketing) | Eventos y novedades | Agenda de la semana + **micro-recompensa sin alcohol en la visita 2** (botana o sticker) | % con 2ª visita ≤30 días |
| A3 | Hito | Te falta 1 visita para la cortesía | WhatsApp (servicio) | Recordatorios | «Te falta 1 sello» (informativo) | Visitas en 14 días |
| A4 | Gracias + NPS | 2 h después del check-in | WhatsApp / la PWA (ya existe en el menú) | Necesario | Gracias + NPS; 9–10 → invitación a Google (ya existe para todos) | Respuestas, clics a reseña |
| A5 | Detractor | NPS ≤6 | **Alerta al dueño** (WhatsApp, Telegram o email) | — | Contactar en menos de 24 h; tarea en el panel | Detractores resueltos |
| A6 | Reactivación | 45 / 90 días sin visita | WhatsApp (marketing) | Novedades | Qué hay de nuevo: barril, platillo, evento | % reactivado |
| A7 | Barril de tu estilo | Barril nuevo publicado en el CMS cuyo estilo coincide con la preferencia del socio | WhatsApp (marketing) | Novedades de barril | «Entró un barril <estilo>: <nombre>, <ABV>, notas…» + leyenda | Visitas en 7 días |
| A8 | Cortesía por vencer | Faltan 5 días para que venza | WhatsApp (servicio) | Recordatorios | «Tu cortesía vence el <fecha>» (sin incitar a consumir) | Canjes |
| A9 | Recordatorio de evento | Apartó lugar | WhatsApp (servicio) | Eventos | Fecha, hora, cómo llegar, qué incluye | Asistencia |
| A10 | Comentario → DM | Palabra clave en comentario de IG («AGENDA», «MENÚ») | DM de IG (1 respuesta privada, ventana de 7 días) | — (lo inicia el usuario) | Enlace a `/ir` con UTM | CTR, visitas |
| A11 | Reseñas de Google | Reseña nueva | Borrador de IA → aprobación humana → API | — | Respuesta personal, nunca genérica | % respondidas, tiempo de respuesta |
| A12 | Reporte semanal | Lunes 9:00 | Email o WhatsApp al dueño | — | KPIs del embudo, segmentos, laboratorio de contenido | — |

**Orden de construcción** (por impacto medido y costo):
1. A11 + A5 + A4 (ya casi existen).
2. A1 + A2 + A3.
3. A10 + A9 (página de evento del Aniversario).
4. A6 + A7 + A8.
5. Cumpleaños, solo si se agrega ese dato.

**Plan B mientras se aprueba la API de WhatsApp** (verificación de Meta): una lista diaria en el panel con los socios a contactar por segmento. El equipo los atiende 1 a 1 con mensajes de servicio, **sin promociones de cerveza desde la app**.

---

## 7. Segmentación aplicada a la parrilla

Se agregan al Hub tres **atributos personalizados de pieza**:
- `persona`: lista múltiple P1–P6.
- `etapa`: Descubrir, Considerar, 1ª visita, 2ª visita, Lealtad, Embajador o B2B.
- `cta`: Ver agenda, Apartar lugar, Ver menú, Cómo llegar, Pasaporte o Collab.

Además, `utm_content` se genera solo. Con eso la matriz del Hub muestra persona × etapa × canal × formato, y alerta si una etapa o persona queda sin cubrir.

**Mapeo inicial de las 16 secciones:**

| Sección | Persona principal | Etapa | Canal y formato líder | CTA |
|---|---|---|---|---|
| Barril de la semana | P4 | Considerar → Lealtad | Carrusel IG, Canal WA | Ver menú |
| ¡Cuéntalo en el Cisne! | P2, P1 | Descubrir | Reel IG, TikTok, Shorts | Ver agenda (convocatoria) |
| Lunes de producción | P4 | Lealtad | Reel, TikTok | Pasaporte |
| Si te gusta… tu barril es… | P1, P3 | Considerar | Slideshow TikTok, carrusel | Ver menú |
| Maridaje del finde | P3 | Considerar | Carrusel, GBP (comida) | Ver menú / Cómo llegar |
| El plato que manda | P3 | Descubrir → Considerar | Reel, GBP | Cómo llegar |
| A puerta abierta | P3, P2 | Descubrir | Reel | Ver menú |
| #CervezaParaTodos | P3, P6 | Considerar | Carrusel, GBP | Ver menú |
| Reseña en voz alta | Todas | Considerar / Embajador | Imagen IG, Threads | Cómo llegar |
| Ranking del Pasaporte | Campeones | Lealtad / Embajador | Imagen IG, stories | Pasaporte |
| Perrhijos del Cisne | P6 | Considerar | Foto, stories, FB | Cómo llegar |
| Quién te sirve | P1, P3 | Considerar (contra el dolor del servicio) | Reel | Ver agenda |
| Agenda Cisne | P1, P2, P5 | Descubrir → 1ª visita | Imagen o carrusel con coautor, Canal WA | Apartar lugar |
| Efemérides | P1 | Descubrir | Carrusel | Ver agenda |
| Pachuca tiene lo suyo | P1, P2 | Descubrir | Reel, TikTok | Ver agenda |
| Edición limitada | P4, P5 | Descubrir → Lealtad | Reel, Canal WA, aviso A7 | Pasaporte |

**Aliados prioritarios para coautoría** (cuentas de negocio o creador públicas, del análisis de audiencia):
1. **Ya probados:** Möwe Biergarten, Coffee Park (ya vende Karnaval), @amordeveranostd, El Garnashians y La Jabonera.
2. **Cerveceras de Hidalgo** para tap takeovers: Trap Haus, Un Hidalgo, La Vizcaína, Briah.
3. **Comida local:** El Garito de San Ja, Bakery San Ja, La Borraja.
4. **Escena musical** (solo eventos anunciados con datos): Musicofilia, Autómata.
5. **Prensa** de CDMX solo para el Aniversario.

---

## 8. Cambios técnicos (backlog)

| Componente | Cambio | Para qué |
|---|---|---|
| Pasaporte (`club_server.py`) | Guardar `origen`, `utm_*`, `ref` y «¿cómo nos conociste?» al registrarse y al hacer check-in | Atribución |
| Pasaporte | Consentimientos **por finalidad**, cada uno con fecha y versión del aviso; baja con «BAJA»; confirmación 18+ | LFPDPPP y WhatsApp |
| Pasaporte | Opcionales: estilo favorito, mes y día de cumpleaños, email | Segmentación (A7, cumpleaños, Brevo) |
| Pasaporte | Tabla `eventos_salida` y webhook firmado hacia n8n | Automatizaciones |
| Pasaporte | Segmentos calculados (por frecuencia y antigüedad de visita) y filtros en `/admin/` | CRM |
| `/v2` pedido y mesero | Ligar la cuenta al socio (`socio_id`) cuando hay sesión; QR de mesa con `?mesa=N` | Gasto y preferencias por socio |
| Sitio y CMS | Página `/ir`, plantilla `/eventos/<slug>` con «Apartar lugar», enlaces de WhatsApp con referencia, `/aliados` | Hub omnicanal |
| Sitio | Analítica sin cookies + eventos de clic (WhatsApp, rutas, menú, registro, instalar app); aviso de cookies si se usa GA4 o Pixel | Medición |
| Content Hub | Atributos `persona`, `etapa` y `cta`; generador de UTM; vista «Embudo» (cobertura) | Segmentación de la parrilla |
| VPS | n8n, WhatsApp Cloud API, Brevo, alerta de detractores, borradores de respuesta a reseñas | Automatización |
| Meta (después) | Conversions API con eventos de visita (`physical_store`), audiencias de clientes y lookalikes a 25+ | Pauta medible (requiere permiso COFEPRIS) |

---

## 9. Medición

| Etapa | KPI | Línea base | Meta del piloto (19 de oct – 29 de nov) |
|---|---|---|---|
| Descubrir | Alcance a no seguidores; vistas de GBP | Requiere Insights (B2/B3) | Medir la base |
| Considerar | Clics a `/ir` y `/menu/` por canal; rutas y llamadas de GBP | 0 (sin medición) | Medición activa desde la semana 1 |
| 1ª visita | Registros con origen conocido | 0% | ≥70% |
| 2ª visita | % con 2ª visita ≤30 días (cohorte mensual) | Calcular con `visitas` | >22% (referencia de la industria) → 30% |
| Lealtad | % activo a 90 días; % que llega a 4 visitas | Calcular | +5 puntos |
| Embajador | Reseñas nuevas por semana; % respondidas; ★ | 0% respondidas | 100% respondidas en <24 h; ≥3 por semana |
| ⭐ | **Visitas atribuidas por canal y pieza** | 0 | Primer reporte por canal |

**Reporte:** cohortes por mes del 1er check-in, embudo por canal (UTM → registro → 2ª visita) y efecto de cada automatización contra un grupo de control pequeño (10% de los socios sin mensaje).

---

## 10. Legal y cumplimiento

- **Aviso de privacidad (reescribir antes de automatizar):**
  - Finalidades secundarias separadas, cada una con su casilla sin marcar: novedades por WhatsApp o email, recordatorios, cumpleaños, perfilado por hábitos de visita y consumo, medición de campañas.
  - Medio para negarse sin perder el servicio.
  - Meta/WhatsApp y Brevo como encargados.
  - Analítica y cookies.
  - Baja en el mismo canal.
  - Registro de la versión aceptada.
  - La nueva autoridad (Secretaría Anticorrupción y Buen Gobierno).
- **WhatsApp:**
  - Solo la API oficial para mensajes sobre cerveza.
  - Consentimiento explícito por categoría.
  - Confirmación de 18+.
  - Nada de catálogo ni venta de alcohol en el chat.
- **COFEPRIS:** en plantillas de WhatsApp, email, DMs y páginas de evento aplican las mismas reglas que en la parrilla:
  - Leyenda «EVITE EL EXCESO.».
  - Texto informativo, sin imperativos.
  - Sin «barra libre».
  - Cortesías comunicadas sin incitar a consumir más.
  - Pauta solo con permiso de publicidad y segmentación de 25+.
- **Datos de terceros:** la audiencia de la Jabonera se usó solo en forma **agregada** para diseñar personas. **No se contacta ni se sigue a esas cuentas, ni se suben a audiencias publicitarias.** Los crudos están en `scraping/raw/` (fuera de git) y conviene borrarlos al cerrar el piloto.
- **Consulta legal ya aprobada:** sumar estos puntos: mensajes automatizados, perfilado y si la publicidad propia en redes requiere permiso.

---

## 11. Hoja de ruta (alineada al piloto de contenido)

| Fase | Fechas | Entregables |
|---|---|---|
| **F0 · Medir y arreglar fugas** | 9 al 18 de oct | Responder las 69 reseñas; `/ir` con UTM; enlaces de WhatsApp con referencia; «¿cómo nos conociste?» y origen en el Pasaporte; analítica sin cookies; aviso de privacidad con finalidades separadas; atributos `persona`, `etapa` y `cta` en la parrilla |
| **F1 · Recompra** | 19 de oct al 8 de nov | Webhook y n8n; alerta de detractores (A5); A4 ampliado; A1–A3 por email (Brevo) mientras se verifica WhatsApp; micro-recompensa de la visita 2; respuesta por DM a comentarios con «AGENDA» (A10); página de evento de Halloween |
| **F2 · Lealtad y evento ancla** | 9 al 29 de nov | WhatsApp Cloud API con plantillas aprobadas; A6–A9; página y «Apartar lugar» del Aniversario III con aliados; borradores de respuesta a reseñas (A11); reporte semanal (A12) |
| **F3 · Escalar** | Dic | Segmentos en `/admin/`; ligar pedidos al socio; Conversions API y audiencias (si se tramita el permiso de pauta); revisión de personas con datos propios |

---

## 12. Decisiones pendientes

1. **Micro-recompensa de la 2ª visita:** ¿botana, sticker o merch? Tiene que ser sin alcohol.
2. **WhatsApp:** ¿se tramita la API oficial con un número nuevo o se migra el actual? Migrarlo saca el número de la app.
3. **Email:** ¿se pide email opcional en el Pasaporte para usar Brevo?
4. **Respuesta por DM a comentarios:** API propia (sin costo, hay que mantenerla) o ManyChat Pro (~29–39 USD al mes).
5. **Analítica:** solo Plausible o Umami (sin cookies), o también GA4 + Meta Pixel (requieren aviso de cookies).
6. **Página `/ir` y páginas de evento** dentro del CMS. Va de la mano con la integración del Hub, en pausa hasta que se suba la rama del CMS.

## 13. Fuentes

- Resy y Toast, Regulars Report 2026: https://blog.resy.com/newsroom/the-regulars-report-2026-resy-toast/
- Bloom Intelligence, benchmarks de email y retención: https://bloomintelligence.com/blog/restaurant-email-marketing-benchmarks/
- Paytronix, brecha de retención temprana: https://e-commerce.news/story/paytronix-loyalty-report-spotlights-early-retention-gap
- Proserpio y Zervas, efecto de responder reseñas (HBR): https://hbr.org/2018/02/study-replying-to-customer-reviews-results-in-better-ratings
- BrightLocal, encuesta de reseñas locales 2026: https://www.brightlocal.com/research/local-consumer-review-survey/
- Política de WhatsApp Business: https://whatsappbusiness.com/es-la/policy/
- Precios de WhatsApp Business Platform: https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing
- Google Business Profile, respuesta a reseñas (`updateReply`): https://developers.google.com/my-business/reference/rest/v4/accounts.locations.reviews/updateReply
- COFEPRIS, Guía de publicidad de bebidas alcohólicas: https://www.gob.mx/cms/uploads/attachment/file/936691/Gu_a_Publicidad_de_Bebidas_Alcoh_licas._CAS_y_COS___002_.pdf__4_.pdf
- LFPDPPP 2025 (texto vigente): https://www.diputados.gob.mx/LeyesBiblio/pdf/LFPDPPP.pdf

**Pendiente de verificar:**
- Tarifas de WhatsApp en México desde octubre de 2026.
- Si la publicidad propia en redes requiere permiso de COFEPRIS.
- Plazos de respuesta a derechos ARCO.
- Cambio en las etiquetas de mensajes de Meta del 27 de abril de 2026.
