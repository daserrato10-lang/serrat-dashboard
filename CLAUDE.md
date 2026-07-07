# Instrucciones para el Agente

> Este archivo está replicado en CLAUDE.md, AGENTS.md y GEMINI.md para que las mismas instrucciones carguen en cualquier entorno de IA.

## Aprendizajes del Agente (Mejora Continua)

> **INSTRUCCIÓN CRÍTICA — LEER PRIMERO:** Esta sección es tu memoria persistente de mejora continua. **Con cada ciclo de ejecución** (al completar una tarea, resolver un error, descubrir un patrón, o ajustar un flujo) **y con cada actualización de cualquier Markdown** (directivas, CLAUDE.md, AGENTS.md, GEMINI.md, READMEs de scripts), **debes agregar aquí un aprendizaje nuevo** si surgió algo no trivial. El objetivo es que este archivo se vuelva más útil y preciso con el tiempo, acumulando conocimiento del proyecto que no se pierde entre sesiones.
>
> **Qué registrar:** restricciones de APIs descubiertas, rate limits reales, patrones que funcionan, errores que se repiten, decisiones de diseño tomadas con el usuario, supuestos que resultaron falsos, atajos útiles, gotchas del entorno.
>
> **Qué NO registrar:** detalles efímeros de una sola tarea, información ya documentada en la directiva correspondiente, cosas triviales derivables del código.
>
> **Formato de cada aprendizaje:**
> ```
> - **YYYY-MM-DD — [Tema corto]:** Descripción del aprendizaje en 1-3 líneas. **Por qué importa:** consecuencia práctica o cómo aplicarlo en el futuro.
> ```
>
> **Higiene:** si un aprendizaje queda obsoleto o se contradice con otro más reciente, actualízalo o elimínalo en vez de acumular ruido. Mantén la lista ordenada por fecha (más recientes arriba). Si superas ~25 entradas, consolida las más antiguas o promuévelas a la directiva que corresponda.

### Registro de aprendizajes

- **2026-07-06 — Snapshots: usar hora Colombia (UTC-5) para etiquetar el día:** El script usaba `datetime.now(timezone.utc)` para determinar la fecha del snapshot — esto etiquetaba snapshots de las 11pm Colombia como el día siguiente. Fix: usar `timezone(timedelta(hours=-5))` para la fecha del día, y mantener UTC solo para el `taken_at` exacto (cálculo de horas). **Por qué importa:** sin esto los snapshots quedan en el día equivocado y los cálculos de horas de vida de cada post son incorrectos.

- **2026-07-06 — Historias Instagram: API solo devuelve las activas (últimas 24h):** No hay endpoint de historias archivadas. Una vez que expiran, sus métricas desaparecen. Métricas disponibles en v21: `reach`, `replies`, `follows`, `navigation` (total). `taps_forward`, `taps_back`, `exits` ya no están disponibles por separado. Medir historias requiere cron automático — con snapshots manuales a horas variables es impráctico. **Por qué importa:** no vale la pena intentar medir historias hasta tener automatización.

- **2026-07-06 — Automatización pendiente: Railway + GitHub para snapshots diarios:** Plan acordado: Railway corre el script en cron diario, el script hace commit del `post_snapshots.json` actualizado al repo de GitHub. Sin esto los snapshots dependen de que Daniel abra el computador. **Por qué importa:** se perdió el snapshot del 3, 4 de julio por no tener el computador encendido.

- **2026-07-01 — Instagram API: usar graph.facebook.com, NO graph.instagram.com:** El endpoint correcto es `https://graph.facebook.com/v21.0/{IG_ID}/media?fields=...&access_token={IG_TOKEN}`. El endpoint `graph.instagram.com` devuelve "Cannot parse access token" aunque el token sea válido. Verificar que la cuenta funciona: `https://graph.facebook.com/v21.0/{IG_ID}?fields=name,followers_count&access_token={IG_TOKEN}`. **Cómo leer el token:** usar `subprocess.run(['curl','-s', url], capture_output=True, text=True)` — NO usar `urllib.request.urlopen()` que falla con tokens largos. Leer .env así: `lines=open('.env').readlines(); env={}; [env.update({l.split('=',1)[0]:l.split('=',1)[1].strip()}) for l in lines if '=' in l]`. **Por qué importa:** cada sesión nueva que intente usar `graph.instagram.com` o `urllib` fallará — este es el único patrón que funciona.

- **2026-07-01 — Captions de Instagram @serratrelojes: estilo real vs Brand Guidelines:** El tono real de los posts es MUY diferente al Brand Guidelines formal. Características: (1) energético y cercano, no sofisticado; (2) emojis frecuentes — los recurrentes son ⌚️🧡🔥🤩😮‍💨; (3) mayúsculas para énfasis ("ES HOY !!", "TODOS"); (4) 3-6 líneas máximo, nunca párrafos largos; (5) preguntas directas al seguidor para engagement; (6) CTA al final: "LINK EN BIO", "escríbenos por DM/WhatsApp"; (7) pocos o ningún hashtag (3-4 máximo); (8) hablan en plural — "Los esperamos", "estamos". **Estructura del caption:** Hook energético (primera línea visible) → contexto/oferta (2-3 líneas) → info práctica si aplica → CTA → emojis de cierre. **Por qué importa:** generar captions en el tono del Brand Guidelines sonaría corporativo y fuera de marca.

- **2026-07-01 — Carruseles Instagram: safe zone inferior para ícono de repost:** El ícono de repost de Instagram ocupa la esquina inferior-izquierda del post, cubriendo hasta ~150px desde el fondo (llega a tapar texto grande como headlines de 64px). Safe zone carruseles: **nada de texto por debajo de `bottom:170px`**. El handle `@serratrelojes` se mueve a `top:20px; right:32px` (esquina superior derecha, fuera de todos los elementos de UI de Instagram). **Por qué importa:** el primer fix de `bottom:56px` fue insuficiente — el repost icon llegaba a tapar hasta "ESTAMOS" en el S1 del carrusel Vassar.

- **2026-07-02 — Dialecto colombiano en copy:** Usar "tú" y nunca "vos". En Colombia no se usa "vos" — es forma rioplatense (Argentina/Uruguay). **Por qué importa:** Daniel lo corrigió explícitamente en el carrusel día 4.

- **2026-07-02 — Focal point vs posición de texto:** Antes de posicionar texto, evaluar dónde está el sujeto en la foto. Sujeto en mitad **superior** → texto en `bottom:170px` + `g-bottom`. Sujeto en mitad **inferior o centro** → texto en `top:32px` + `g-top`. Fotos macro que llenan el frame → `object-position: center 60%` para empujar el sujeto hacia abajo, texto en `top:32px`. **Safe zone carruseles: solo abajo (`bottom:170px`). Arriba no hay restricción** — la UI de Instagram no tapa nada en la parte superior de carruseles. La safe zone de `top:100px` es SOLO para historias. **Por qué importa:** Daniel rechazó el overlap — "queda feo cuando el foco de la foto y el texto se sobreponen."

- **2026-07-01 — Historias Instagram: safe zone obligatoria:** Top 100px y bottom 110px del viewer (405×720px) son zona muerta — Instagram los cubre con UI. Todo texto y elementos visuales deben estar dentro de esa franja. Exportar con `--story` flag. **Por qué importa:** Daniel pidió explícitamente respetar estas zonas para que el texto no se corte al subir a Instagram.

- **2026-07-01 — Fotos de evento iPhone: siempre EXIF orientation=6:** Las fotos tomadas con iPhone en modo portrait llegan como 4032×3024 (HORIZONTAL) con EXIF orientation=6. Usar siempre `ImageOps.exif_transpose()` antes de cualquier procesamiento. Sin esto, las fotos aparecen rotadas 90°. **Por qué importa:** todas las fotos de Vassar tenían este problema.

- **2026-07-01 — Estructura de carpetas del proyecto establecida:** `Carruseles/` para PNGs de carruseles, `Historias/<tema>/` para historias, `Imágenes IA/` para todas las imágenes generadas. Copiar a estas carpetas al finalizar cada pieza. **Por qué importa:** Daniel quiere acceso organizado sin depender de `.tmp/` que puede borrarse.

- **2026-07-01 — Gemini wrist: fotos con cast de color engañan el dial:** Cuando la foto de referencia tiene un dominante de color (agua azul, luz cálida, sombra verde), Gemini toma ese color como el color real del dial. Fix: describir explícitamente el color real ("MATTE BLACK dial", "white dial") e indicar "ignore the color cast from [causa]". **Por qué importa:** DSC1551 tomada bajo agua producía dial azul en vez de negro — sin el fix el reloj queda con colores erróneos.

- **2026-07-01 — Describir materiales explícitamente hace el resultado menos realista:** Cuando la foto de referencia tiene problemas (color cast, poca visibilidad), compensar con descripción textual detallada hace que Gemini trabaje de forma "ilustrativa" en vez de fotográfica — el resultado se ve más IA. Regla: si una referencia requiere más de 1 línea de descripción del reloj, descartar esa referencia. La versatilidad viene de variar el contexto (escena, luz), no de cambiar la referencia. **Por qué importa:** Daniel lo detectó directamente — "se siente más hecha con IA."

- **2026-07-01 — Fotos de referencia para Gemini: solo sirven si el reloj es claramente visible:** DSC1714 produjo baja fidelidad porque el reloj no tiene suficiente detalle visible en esa foto. Regla: antes de usar una foto como referencia, verificar que muestre claramente cara del dial, caja y correa. Fotos validadas como referencia: DSC1682 (la mejor), DSC1760, DSC1551 (con fix de color). DSC1714 descartada. **Por qué importa:** evita generar imágenes con diseño incorrecto del reloj.

- **2026-07-01 — Orientación del reloj en muñeca:** Siempre incluir en el prompt: "watch worn correctly on the left wrist — crown/stem on the right side of the case as seen from the wearer's perspective, dial facing upward toward the wearer's face." Sin esta instrucción, Gemini puede poner el reloj al revés (como en wrist_clean). **Por qué importa:** Daniel rechazó wrist_clean por este error — "estaría viendo la hora al revés."

- **2026-06-30 — Carrusel Instagram: sin botones, sin elementos de UI web:** Los carruseles son piezas estáticas para Instagram — no tienen interactividad. Nunca agregar botones tipo CTA ("Ver colección →"), badges clickeables ni ningún elemento de UI web. Si hay llamado a la acción, va como texto simple. **Por qué importa:** Daniel lo rechazó explícitamente — "esto no va a tener botones, es una pieza para Instagram."

- **2026-06-30 — No usar retratos IA de personas mirando a cámara:** Las fotos de personas generadas con IA se ven artificiales cuando imitan retratos reales (cara de frente, expresión natural). Daniel las rechaza por parecer falsas. **Usar en cambio:** texturas, objetos, manos/muñecas, atmósferas abstractas, o fotos reales. Para personas: solo si es un plano muy abstracto o de espaldas. **Por qué importa:** "se ven muy IA" — rompe la credibilidad de la marca.

- **2026-06-30 — Legibilidad del texto: nunca bajar de 70% de opacidad en texto que debe leerse:** El texto pequeño con `rgba(255,255,255,.4)` o menos sobre fotos resulta ilegible. Regla: texto informativo/copy → mínimo `rgba(255,255,255,.80)`. Solo el handle `@serratrelojes` puede ir a `.30-.35`. Text-shadow obligatorio en todo texto sobre foto. **Por qué importa:** Daniel señaló que las letras pequeñas "no se alcanzan a leer bien."

- **2026-06-30 — REGLA DE ORO tipográfica: una palabra = una línea, sin excepciones:** Nunca usar `<br>` dentro de una palabra ni dejar que el texto haga wrap mid-word. `white-space: nowrap` en todos los headlines. **Fórmula correcta (actualizada 2026-07-01):** `font-size ≤ 400 / (coef × chars)` donde coef = **0.85** para Black/900, **0.65** para Light/300. Usable width = 400px (viewer 480px − padding 32px×2 = 416px, con margen de seguridad de 16px). **Siempre contar TODOS los caracteres incluyendo puntuación y tildes.** Un "." o "," cuenta igual. El coeficiente anterior (0.78) era demasiado optimista — causó overflow sistemático en múltiples carruseles. **Por qué importa:** Daniel lo rechazó múltiples veces — es la regla más violada y más crítica.

- **2026-06-30 — Gemini API key activa, acceso a Imagen 4.0 y Veo 3.1:** Key guardada en `.env` como `GEMINI_API_KEY`. Modelos disponibles: `imagen-4.0-generate-001`, `imagen-4.0-ultra-generate-001`, `imagen-4.0-fast-generate-001`, `veo-3.1-generate-preview`. Endpoint imagen: `POST https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict?key=KEY`. **Por qué importa:** usar Imagen 4.0 (no 3) para generar imágenes lifestyle de Serrat — escenas que no existen en las fotos reales.

- **2026-06-30 — `display:flex` en slide raíz rompe el sistema de visibilidad:** El sistema de carruseles usa `.slide { display:none }` / `.slide.active { display:block }`. Si se agrega `display:flex` directamente al selector de un slide (ej: `#s08 { display:flex }`), el ID es más específico y anula el `display:none` — el slide queda siempre visible encima de todos los demás. **Fix correcto:** usar `position:absolute` en los hijos para layouts complejos (splits, paneles). Nunca poner `display:flex/grid` en el slide raíz.

- **2026-06-30 — Logos/motifs PNG de Serrat tienen fondo blanco/negro sólido, no son transparentes:** Todos los archivos en `LOGO/` y `MOTIF/` tienen fondo sólido (blanco o negro), sin canal alpha. Usarlos como imagen sobre fondos oscuros muestra un rectángulo feo. **Fix correcto:** usar texto con `font-family: 'MADE Outer Sans'` para el handle/wordmark. No intentar filter+blend-mode sobre PNGs con fondo sólido.

- **2026-06-30 — Tamaños de fuente seguros para MADE Outer Sans Black:** La fuente es ancha (~0.78× por carácter mayúscula). Con padding 40px/lado = 520px usable: 7 chars → máx 88px, 5 chars → máx 110px, > 8 chars → < 70px. Usar `white-space: nowrap`. Nunca usar `&shy;` — Daniel rechazó explícitamente las palabras cortadas a mitad.

- **2026-06-30 — Splits con fotos: `object-fit: contain` + fondo negro:** En layouts partidos (Split top/bottom, Franja izq/der), usar `object-fit: contain` con `background: #1B1D1B` para que la foto se vea completa sin recorte. Daniel rechazó fotos recortadas: "tiene que ser una foto del tamaño de donde se ve la foto".

- **2026-06-30 — Carrusel v2: sistema de legibilidad universal para fotos de fondo:** La solución correcta para texto legible sobre cualquier foto es: (1) clases de overlay con gradiente de 5 stops sin cortes abruptos (`.grad-bottom`, `.grad-top`, `.grad-both`, `.grad-left`), (2) text-shadow en 3 capas en todas las tipografías, (3) variable CSS `--grad-strength` ajustable por slide para fotos muy claras. NUNCA usar paneles sólidos con `transparent X%` — crean un corte visible. El archivo de referencia es `.tmp/carousel_v2.html`. **Por qué importa:** Daniel rechazó explícitamente los cortes abruptos — la solución de gradiente suave es la estándar para todos los carruseles futuros.

- **2026-06-30 — Carrusel: estilo validado por Daniel es foto full-bleed + texto flotante:** El primer prototipo (v1) usaba fondos de color sólido — Daniel lo aprobó pero dijo "está demasiado sencillo". Las referencias muestran foto full-bleed como fondo + texto grande encima sin cajas. La v2 con fotos reales fue aprobada ("está bastante bien, me sorprende"). El estilo correcto: foto ocupa 100% del slide, texto flota con gradiente suave detrás. **Por qué importa:** No volver al estilo de fondos sólidos — siempre foto de fondo para Serrat.

- **2026-06-30 — Fotos de Serrat son de calidad profesional, no necesitan IA para producto:** Las 30 fotos en `Fotos Relojes/` son con Sony A6100, calidad de agencia. Para slides de producto usar siempre las fotos reales. IA (Gemini Imagen 3) solo para slides de lifestyle/ambiente donde no hay foto propia. **Por qué importa:** evita generar imágenes IA innecesarias y mantiene autenticidad del producto.

- **2026-06-30 — Dashboard resuelto: HTML autogenerado por Python, no Google Sheets:** La arquitectura final es `execution/generate_dashboard.py` → `.tmp/dashboard.html`. Sin Google, sin MCP de Drive, sin pasos manuales. El script llama Instagram API, toma snapshot diario en `.tmp/post_snapshots.json`, genera HTML con Chart.js interactivo. **Por qué importa:** es la única ruta donde Claude Code hace todo — Google Sheets requería pasos manuales del usuario que él no aceptó.

- **2026-06-30 — Snapshots diarios: lógica de comparación justa entre posts:** El ranking solo muestra posts publicados DESPUÉS del primer snapshot (2026-06-29). Posts anteriores tienen métricas acumuladas históricas no comparables — no sabemos cómo crecieron día a día. El modal sí muestra todos los posts sin filtro. Tolerancia del ranking: ±3 días. **Por qué importa:** Daniel detectó el error de comparar posts de diferente antigüedad — prefiere ranking vacío y honesto a uno con datos engañosos.

- **2026-06-30 — Drive MCP: reconectar en la misma conversación SÍ funciona:** Si el Drive MCP falla con "token expired", el usuario puede ir a claude.ai → Settings → Connectors → Google Drive → Disconnect → Reconnect y en la misma conversación ya funciona. (Corrección del aprendizaje anterior que decía que había que abrir nueva conversación — eso era incorrecto.) **Por qué importa:** no hay que cerrar la conversación, solo reconectar.

- **2026-06-30 — Instagram dashboard: token, IDs y ruta correcta ya resueltos:** System User Token de Business Manager es la ruta correcta (no expira, no requiere app review). Token guardado en `.env` como `IG_TOKEN`. IG Business ID: `17841400598267708`. FB Page ID: `126690630678974`. **Por qué importa:** NO hay que resolver el token en próximas sesiones — ir directo a usar el script.

- **2026-06-30 — Drive MCP expiraba mid-session (obsoleto — ver corrección arriba):** ~~Aunque el usuario reconecte Google Drive en Settings → Conectores, el token MCP de la sesión activa NO se refresca.~~ Esto resultó ser incorrecto — reconectar en la misma sesión sí funciona.

- **2026-06-30 — Ruta correcta para instagram_manage_insights sin app review:** (1) En Meta Developer App, agregar caso de uso "Gestionar contenido de Instagram" — eso hace aparecer el permiso. (2) En Business Manager: crear System User, asignarlo a la app como admin, asignar la cuenta de Instagram al system user. (3) Generar token del system user con los 4 permisos. Token no expira. **Por qué importa:** evita el ciclo de frustración de la sesión anterior con tokens personales que no ven páginas.

- **2026-06-30 — Instagram Graph API v21: nombres de métricas correctos:** `impressions` ya no existe — usar `reach`. Para métricas totales (profile_views, website_clicks, total_interactions, likes, comments, shares, saves) se necesita `metric_type=total_value`. Para follower_demographics usar `period=lifetime` + `breakdown=age,gender` o `city` o `country`. **Por qué importa:** evita errores de API al construir el dashboard.

- **2026-06-29 — Looker Studio no tiene API — no usar para dashboards:** Looker Studio no tiene API pública para crear/editar reportes programáticamente. Proponer Looker Studio termina en darle instrucciones manuales al usuario, lo que viola el principio de que Claude Code ejecuta. Alternativa correcta: Google Sheets + Apps Script. **Por qué importa:** Daniel dijo explícitamente que Claude Code debe hacer el trabajo, no dar instrucciones.

- **2026-06-29 — Meta Developer instagram_manage_insights requiere app review:** El permiso `instagram_manage_insights` no aparece en el Graph API Explorer si no está configurado vía "Casos de uso" en la app, y en producción requiere revisión de Meta. En modo desarrollo funciona solo para el admin de la app. La ruta de Meta Developer App es demasiado compleja para usuarios no técnicos. Buscar ruta alternativa más simple para obtener token. **Por qué importa:** Invertimos mucho tiempo en esta ruta sin éxito.

- **2026-06-29 — Porter Metrics Instagram Insights en Looker Studio SÍ conecta:** El conector "Instagram Insights" de Porter Metrics en Looker Studio (Partner Connector) se conectó exitosamente a @serratrelojes. Tiene todos los datos: Account Metrics, Posts, Stories, Audience demographics. No requiere Meta Developer App. Pero no sirve porque Looker Studio no tiene API.

- **2026-06-29 — Proyecto Serrat Relojes activo:** Este directorio es el sistema de contenido de Instagram para @serratrelojes. El hub central es Notion (page ID: 38f60eba5d61808296f2cb6a72bcd0ea). Ver memory/project_serrat.md para contexto completo de marca, IDs de bases de datos y diagnóstico. **Por qué importa:** cargar este contexto al inicio de cada sesión evita re-preguntar información al usuario.

- **2026-06-29 — API Notion: usar Python, no bash para JSON con caracteres especiales:** Los posts con tildes, comillas o caracteres especiales fallan cuando se construye el JSON en bash con variables de shell. La solución es siempre usar un script Python con json.dumps() para serializar el payload. El script base está en el scratchpad de sesión. **Por qué importa:** evita que posts del calendario se pierdan silenciosamente.

- **2026-06-29 — Notion integrations internas no pueden crear páginas en raíz del workspace:** Error "Provide a parent.page_id" al intentar crear página a nivel workspace. El usuario debe crear la página raíz manualmente y compartirla con la integración. Solo entonces se puede crear contenido hijo. **Por qué importa:** al iniciar un workspace nuevo siempre hay este paso manual.

<!-- Agrega nuevas entradas arriba de esta línea. -->

---

Tú operas dentro de una arquitectura de 3 capas que separa responsabilidades para maximizar la confiabilidad. Los LLMs son probabilísticos, mientras que la mayoría de la lógica de negocio es determinista y requiere consistencia. Este sistema resuelve esa incompatibilidad.

## La Arquitectura de 3 Capas

**Capa 1: Directiva (Qué hacer)**
- Básicamente son SOPs escritos en Markdown, ubicados en `directives/`
- Definen los objetivos, entradas, herramientas/scripts a usar, salidas y casos extremos
- Instrucciones en lenguaje natural, como las que le daría a un empleado de nivel medio

**Capa 2: Orquestación (Toma de decisiones)**
- Esta es tu función. Tu trabajo: enrutamiento inteligente.
- Leer directivas, llamar herramientas de ejecución en el orden correcto, manejar errores, pedir aclaraciones, actualizar directivas con los aprendizajes
- Tú eres el puente entre la intención y la ejecución. Por ejemplo, no intentes hacer scraping de sitios web por tu cuenta—lee `directives/scrape_website.md`, define entradas/salidas y luego ejecuta `execution/scrape_single_site.py`

**Capa 3: Ejecución (Hacer el trabajo)**
- Scripts de Python deterministas en `execution/`
- Variables de entorno, tokens de API, etc. se almacenan en `.env`
- Manejan llamadas a APIs, procesamiento de datos, operaciones de archivos e interacciones con bases de datos
- Confiables, testeables, rápidos. Use scripts en vez de trabajo manual.

**Por qué funciona esto:** si tú haces todo por tu cuenta, los errores se acumulan. Un 90% de precisión por paso = 59% de éxito en 5 pasos. La solución es empujar la complejidad hacia código determinista. Así tú te concentras solo en la toma de decisiones.

## Principios de Operación

**1. Revise primero si existen herramientas**
Antes de escribir un script, revisa `execution/` según tu directiva. Solo crea scripts nuevos si no existe ninguno.

**2. Auto-corrección cuando algo falla**
- Lee el mensaje de error y el stack trace
- Corrige el script y pruébalo de nuevo (a menos que use tokens/créditos de pago—en ese caso consulta primero con el usuario)
- Actualiza la directiva con lo que aprendiste (límites o rate limits de API, tiempos, casos extremos)
- Ejemplo: si llegas al rate limit de una API → investigas la API → encuentras un endpoint batch que soluciona el problema → reescribes el script → pruebas → actualizas la directiva.

**3. Actualice las directivas a medida que aprende**
Las directivas son documentos vivos. Cuando descubras restricciones de API, mejores enfoques, errores comunes o expectativas de tiempo—actualiza la directiva. Pero no crees ni sobreescribas directivas sin preguntar, a menos que se te indique explícitamente. Las directivas son tu conjunto de instrucciones y deben preservarse (y mejorarse con el tiempo, no usarse de manera improvisada y luego descartarse).

## Ciclo de Auto-corrección

Los errores son oportunidades de aprendizaje. Cuando algo falla:
1. Corrija el problema
2. Actualice la herramienta
3. Pruebe la herramienta, asegúrese de que funcione
4. Actualice la directiva con el nuevo flujo
5. El sistema ahora es más robusto

## Organización de Archivos

**Estructura de directorios:**
- `.tmp/` - Todos los archivos intermedios (dossiers, datos scrapeados, exportaciones temporales). Nunca se suben al repositorio, siempre se regeneran.
- `execution/` - Scripts de Python (las herramientas deterministas).
- `directives/` - SOPs en Markdown (el conjunto de instrucciones).
- `.env` - Variables de entorno y claves de API.
- `credentials.json`, `token.json` - Credenciales de OAuth de Google (solo cuando el flujo los requiera; en `.gitignore`).

**Principio clave:** Los archivos intermedios viven en `.tmp/` y pueden borrarse siempre. Cualquier salida del flujo debe ser reproducible ejecutando el flujo de nuevo, nunca editada a mano.

## Resumen

Tú estás entre la intención humana (directivas) y la ejecución determinista (scripts de Python). Lee instrucciones, toma decisiones, llama herramientas, maneja errores y mejora el sistema continuamente.

Se pragmático. Se confiable. Auto-corríjete.
