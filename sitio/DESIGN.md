# Cisne Negro — Sistema visual "Neón y tinta"

Aplica a todo lo publicado en `cisnenegro.softvibes.art`: la landing (`/`), el menú (`/menu/`), el análisis (`/analisis/`) y el hub (`/proyecto/`).

## Origen
- **Mascota:** cisne negro estilo tatuaje/linograbado, con pico naranja, un rayo en el cuello y un tarro de cerveza (`assets/img/marca/cisne-mascota.jpg`, fondo blanco).
- **Letrero de neón** "CISNE NEGRO" en el taproom: tipografía de palo seco con luz ámbar cálida sobre concreto oscuro (`assets/img/lugar/neon.jpg`).
- **Pluma negra** del sitio actual (`assets/img/marca/pluma.png`, fondo transparente).
- **Tono:** de barrio, sin pretensiones, con humor ("¡Cuéntalo en el Cisne!", "¿A poco sí pa'?").

## Tokens

```css
:root{
  --tinta:#0E0D0B;      /* fondo principal: negro cálido del bar */
  --carbon:#191714;     /* superficies/cards */
  --borde:#2B2823;      /* líneas y divisores */
  --hueso:#F3EDE2;      /* texto principal y secciones "papel" */
  --gris:#A39B8E;       /* texto secundario */
  --neon:#F2C97D;       /* ámbar del letrero: titulares destacados, glow */
  --pico:#FF5A1F;       /* naranja del pico: ÚNICO acento (CTA, badges, precios) */
  --lupulo:#B7C46A;     /* solo para etiquetas de estilo "lupulada" en el menú */
}
```

- Contraste: hueso sobre tinta (≈16:1) y pico sobre tinta para CTA con texto tinta encima (botón naranja con texto oscuro).
- Glow de neón **solo** en el titular del hero: `text-shadow: 0 0 18px rgba(242,201,125,.45)`.
- Secciones "papel" (hueso de fondo, tinta de texto) para alternar ritmo y presentar la mascota sobre su fondo blanco natural, como si fuera una calcomanía.

## Tipografía (Google Fonts)
- **Titulares:** `Big Shoulders Display` 800/900, MAYÚSCULAS, tracking 0.02em (industrial, de cartel cervecero).
- **Cuerpo:** `Manrope` 400/600/700.
- **Datos técnicos** (ABV, IBU, precios, horarios): `JetBrains Mono` 500.

## Componentes
- **Botón primario:** fondo `--pico`, texto `--tinta`, radio de 999px, peso 800.
- **Botón secundario:** borde 1.5px `--hueso`, transparente.
- **Ficha de barril:** card `--carbon` con borde `--borde`, nombre en Big Shoulders, línea mono `RED IPA · 7.0% ABV`, chip de perfil (lupulada/oscura/ácida/ligera), precio en `--pico`.
- **Sello/sticker:** la mascota dentro de un círculo hueso con borde de 3px tinta, ligeramente rotado (-6°).
- **Iconografía:** trazos simples; la pluma como separador o marca de agua al 6% de opacidad.

## Reglas
- Móvil primero (el 90% llega por el QR o Instagram).
- Fotos reales del lugar y de los platillos; nada de stock.
- No inventar datos: teléfono (771) 244-2025, WhatsApp `https://wa.me/message/M766JUHYWQYYC1`, horario Mar–Jue 16–22 · Vie–Sáb 16–23:30 · Dom 14–19 · **Lun cerrado (día de producción)**.
- `<meta name="robots" content="noindex,nofollow">` en todo: es una vista previa en el dominio de Softvibes y el dominio canónico del cliente es cisnenegro.mx.
- Imágenes con `loading="lazy"` (excepto el hero), `width` y `height` explícitos, y texto alternativo en español.
