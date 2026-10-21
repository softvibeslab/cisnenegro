# Pasaporte Cisne — Plan de gamificación

> Objetivo: que el Pasaporte deje de ser solo "cuenta visitas" y premie lo que más le sirve a Cisne Negro: **volver más seguido, venir en días flojos, traer gente, generar contenido y decir la verdad en el NPS**.
> Propuesta del 2026-10-06, pendiente de que el cliente apruebe valores y premios.

---

## 1. Principios (no negociables)

1. **Nunca premiar reseñas de Google.** Google prohíbe las reseñas incentivadas y también pedirlas solo a los clientes contentos. Se premia la *calificación interna* (NPS), y el enlace a Google se ofrece a todos sin premio, como ya funciona.
2. **Premiar el NPS sin importar el score.** Si un 3 vale lo mismo que un 10, la gente contesta con honestidad y el NPS sigue sirviendo para medir.
3. **Nunca premiar volumen de alcohol.** Se premian visitas, acciones y comunidad, nunca "tómate 5 y gana". Hay un tope por día y el registro exige ser **mayor de 18 años** (falta agregar esa casilla: ver G1).
4. **Lo que se puede falsear lo valida el equipo:** las publicaciones en redes y los retos se aprueban desde el panel.
5. **Reglas simples de explicar en la barra.** Si el bartender no puede explicarlo en 10 segundos, sobra.

## 2. Moneda: de sellos a **Plumas** 🪶

Hoy, 1 visita = 1 sello. Proponemos que el Pasaporte acumule **plumas**:

| Acción | Plumas | Validación | Tope |
|---|---|---|---|
| Visita con código del día | **1** | Código del día | 1 por día |
| Responder el NPS de la visita | **0.5** | Automática | 1 por visita |
| Publicación en IG/TikTok que menciona a @cisnenegro.mx con #CuéntaloEnElCisne | **0.5** | El cliente pega el enlace y el equipo aprueba en el panel | 1 por visita |
| **Combo "Cuéntalo"** = publicación + NPS en la misma visita | **la visita vale 2** (1 + 0.5 + 0.5) | La suma de las dos anteriores | — |
| Visita en día flojo (mar o mié; configurable) | **+0.5** | Automática por fecha | 1 por día |
| Traer a un amigo que se registra y hace su 1ª visita | **+1 para cada uno** | Código de referido + check-in del amigo | 3 por mes |
| Racha: 3 semanas seguidas con visita | **+1** | Automática | 1 por racha |

Este es el ejemplo que pediste: **publicación + calificación = 2 visitas**. Una visita normal vale 1 pluma; si además contesta el NPS y publica, vale 2.

Las cortesías siguen igual pero cuentan plumas: **5 plumas → 4 oz** y **10 plumas → 12 oz**, y el ciclo se reinicia. Así, quien hace el combo llega al doble de rápido.

**Tope global:** 3 plumas por día por socio, para que nadie "farmee" plumas.

## 3. Mecánicas de colección

| Mecánica | Cómo funciona | Premio |
|---|---|---|
| **Reto "Vacía el barril"** (por temporada) | El bartender marca en el panel cada estilo de barril que el socio prueba. El Vuelo del Cisne cuenta como 4 | Insignia de temporada + 1 pluma |
| **Insignias de evento** | El check-in en un evento (Noche de Velas, Arte & Chela, Oktoberfest, aniversario) da una pluma de color coleccionable | Colección visible en el Pasaporte |
| **Bautiza una cerveza** | Los socios de nivel "Cisne Negro" o superior proponen nombres para el siguiente barril; el equipo elige al ganador | Su nombre en la ficha del barril («Bautizada por Ana R.») + insignia legendaria |
| **Lunes de Producción VIP** | 2 veces al año, el top 10 del ranking o el nivel "Cisne Real" ve una cocción en el día cerrado | Experiencia, sin descuento: refuerza la historia de la marca |

## 4. Niveles (plumas acumuladas de por vida)

| Nivel | Plumas | Beneficio |
|---|---|---|
| Polluelo | 0–4 | Bienvenida y su primera cortesía a las 5 plumas |
| Cisne | 5–14 | Puede mostrar su insignia y entra al Club del Barril (aviso de barril nuevo por WhatsApp) |
| Cisne Negro | 15–29 | Propone nombres en "Bautiza una cerveza" y tiene preventa de eventos |
| Cisne Real | 30+ | Vaso grabado con su nombre y Lunes de Producción VIP |

## 5. Ranking

- **El ranking ya está construido** (semanal, mensual y total, con alias «Ana R.» y opción de ocultarse). En G1 pasa a contar **plumas** en lugar de visitas.
- **Premio mensual al top 3:** playera, tarro o growler, nunca un "barril libre". Se anuncia en Instagram (contenido de comunidad, que es el que mejor funciona según el análisis).
- Empates: gana quien llegó primero a ese número.

## 6. Implementación por fases

### G1 — Plumas y combo "Cuéntalo" (1 semana)
- **Backend:**
  - Tabla `movimientos` (socio, tipo, plumas, visita, referencia/enlace, estado pendiente/aprobado/rechazado, aprobado_por, fecha).
  - Las cortesías y el ranking cuentan `sum(plumas)` aprobadas. Migración: cada visita existente se convierte en 1 pluma.
  - Reglas en una tabla de configuración: valores, días flojos y topes.
- **Menú:**
  - Contador de plumas (con medias plumas) y botón "Compartí mi visita": pega el enlace de IG o TikTok y queda pendiente.
  - Explicación del combo después del NPS.
  - Casilla obligatoria "Soy mayor de 18 años" en el registro.
- **Panel:** bandeja "Publicaciones por aprobar" (enlace, socio, aprobar/rechazar) y edición de las reglas.
- **KPIs nuevos:** plumas emitidas por tipo, % de visitas con combo y publicaciones aprobadas al mes.

### G2 — Racha, referidos y días flojos (1 semana)
- Código de referido por socio (`/menu/?ref=ANA7`), atribución en el registro y premio en la 1ª visita del amigo.
- Rachas semanales calculadas al hacer check-in, con aviso en el Pasaporte: "¡3 semanas seguidas! +1 🪶".
- Bonificación en días flojos configurable desde el panel.

### G3 — Colección y niveles (2 semanas)
- Insignias (catálogo en el panel), retos de temporada con marcado por el bartender, niveles con su barra de progreso y la galería de insignias en el Pasaporte.
- "Bautiza una cerveza": formulario para el nivel Cisne Negro y moderación en el panel.

### G4 — Club del Barril (WhatsApp)
- Aviso de barril nuevo a quien aceptó WhatsApp (el opt-in ya se captura). Requiere WhatsApp Business API o un envío asistido desde el panel. Fuera del alcance de G1–G3.

## 7. Cómo sabremos si funciona (meta a 90 días del lanzamiento)

| KPI | Cómo se mide | Meta |
|---|---|---|
| Visitas por socio activo al mes | Panel → Estadísticas | +30% contra el mes 1 |
| Retención (socios con 2+ visitas) | Panel → Estadísticas | ≥ 45% |
| Tasa de respuesta del NPS | NPS / visitas | ≥ 60% |
| Publicaciones de clientes al mes (UGC) | Publicaciones aprobadas | 30+ |
| Visitas en días flojos | Visitas por día de la semana | +25% en mar y mié |
| Socios traídos por referido | Altas con código de referido | 15% de las altas |
| Clics a Google tras el NPS | Panel → Estadísticas | ≥ 25% de los NPS |

## 8. Decisiones que necesitamos del cliente

1. ¿Aprueban los valores de la tabla (sobre todo la media pluma por NPS y por publicación)?
2. ¿Qué días son realmente flojos? Mar y mié es una hipótesis; Google no publica horas pico para esta ficha.
3. ¿Qué premios para el top 3 mensual y para el nivel Cisne Real?
4. ¿El bartender puede marcar los estilos probados (reto "Vacía el barril") o lo dejamos solo con el Vuelo?
5. Confirmar el texto legal de la casilla 18+ y las bases de la promoción (vigencia y restricciones) para publicarlas junto al aviso de privacidad.
