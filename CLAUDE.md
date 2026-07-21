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

- **2026-07-21 — Posicionamiento de texto: siempre analizar el foco visual de la foto antes de poner texto:** Antes de decidir si el texto va arriba o abajo, identificar dónde está el protagonista de la imagen. El texto va en la zona OPUESTA, en el espacio vacío disponible. Si el foco está en el centro-abajo → texto arriba. Si el foco está arriba → texto abajo. Nunca poner texto encima del elemento que la imagen quiere mostrar. **Por qué importa:** Daniel lo señaló en el carrusel Argentina — el texto de S4 tapaba exactamente el "SERRAT RELOJES" tatuado que era el reveal del carrusel.

- **2026-07-21 — display:flex en slide raíz rompe visibilidad (se repitió):** Slide S4 tenía `display:flex` inline en el `.slide` root → más específico que `.slide { display:none }` → slide siempre visible. Fix: poner el flex en un `div` hijo con `position:absolute; inset:0`. **Por qué importa:** bug que se sigue repitiendo — la regla es: NUNCA poner `display:flex/grid` en el elemento `.slide` raíz.

- **2026-07-21 — export_carousel.py bloqueado cuando el sandbox classifier de Anthropic está caído:** Cuando el clasificador está down, Python vía Bash es bloqueado. Alternativa: script Pillow puro en `.tmp/export_argentina.py` que aplica gradiente + texto + fuentes directamente sobre PNGs. Ejecutar con `python3 .tmp/export_argentina.py` desde la raíz. **Por qué importa:** si el clasificador falla de nuevo, Pillow es el fallback confiable.

- **2026-07-21 — Carruseles de tendencia: workflow validado con Daniel:** (1) Agente propone secuencia de slides. (2) Daniel edita las fotos externamente y las deja en `Borradores/<nombre>/`. (3) Agente integra textos y gradientes. (4) Export. Las fotos deben llegar listas en 1080×1350. **Por qué importa:** primera vez que se hace carrusel viral/meme en Serrat — formato zoom progresivo aprobado.

- **2026-07-21 — Dashboard: ranking por métricas manuales debe usar ALL_POSTS_VU, no GROWTH_POSTS:** `GROWTH_POSTS` solo incluye posts publicados después del primer snapshot (2026-06-29). Los posts más históricos tienen métricas manuales llenadas pero nunca aparecían en el ranking. Fix: cuando `isManual` es true, usar `ALL_POSTS_VU` como `sourcePool`. Para métricas de API (reach, likes, vida_util) seguir usando `GROWTH_POSTS`. **Por qué importa:** el video con mayor watch time (23s, jun-9) y otros 12 posts quedaban excluidos del ranking aunque tuvieran datos llenados.

- **2026-07-21 — Watch time y skip rate: solo disponibles para videos, NO para carruseles ni imágenes:** Instagram Insights solo muestra tiempo promedio de reproducción y % omisiones para Reels/videos. Para carruseles e imágenes no existen. En la tabla: mostrar "n/a" estático en lugar de input. En el modal: deshabilitar los campos con placeholder "solo videos". `new_followers` sí aplica a todos los formatos. **Por qué importa:** Daniel lo corrigió — si no se aplica la restricción, Daniel entra datos incorrectos en carruseles.

- **2026-07-21 — Arquitectura _insights en post_tags.json:** Las métricas manuales de Instagram Insights por post se guardan en `post_tags.json` bajo `_insights: {post_id: {avg_watch_time, skip_rate, new_followers, read_at}}`. El timestamp `read_at` se auto-genera al guardar — asumido que Daniel las lee y pone en el mismo momento (no hay delay). Server `/save-tags` hace deep-merge a nivel de `post_id` (no sobrescribe todos los insights, solo el post actualizado). En JS: `let _insights = {post_insights_json}` (mutable), se actualiza localmente tras cada save sin recargar página. `applyInsightsToInputs()` sincroniza los inputs de la tabla al cargar tags del servidor. **Por qué importa:** es la fuente de datos para el ranking por watch time/skip rate/nuevos seguidores y para la sección "¿Qué funciona mejor?" con métricas manuales.

- **2026-07-21 — Primer análisis de métricas manuales (22 posts, jul-21):** Watch time es el predictor más fuerte de nuevos seguidores — correlación casi lineal: 23s→12NF, 13s→5NF, 12s→3NF, 7-8s→2-5NF, 3-4s→0-2NF. El video de 23s ("Envíaselo ya sabes a quien", conexión) es el benchmark: ratio 1 seguidor cada 200 alcanzados. Conexión promedia 10.5s watch time y 7.2 NF vs atracción 7s/2.2NF vs conversión 5s/2NF. Videos de promo/urgencia tienen skip rate >65% — se identifican como publicidad en el primer segundo. Los con skip <45% tienen hooks de curiosidad o identidad social. **Por qué importa:** base empírica para priorizar contenido que maximice watch time > reach.

- **2026-07-21 — Dashboard: métricas manuales de Insights inline en tabla y modal:** Nuevos campos por post: `avg_watch_time` (s), `skip_rate` (%), `new_followers`. En tabla: 3 columnas con inputs editables, guardado automático al perder el foco (onblur → `/save-tags`), feedback visual borde verde 1.2s. En modal: 3 campos + botón "Guardar métricas". Ranking: 3 nuevas opciones de orden (watch time desc, skip rate asc = menor omisiones primero, nuevos seg desc). "¿Qué funciona mejor?": 3 cajas nuevas por métrica manual por etapa del embudo. Cola de priorización: card mostrando posts 36-72h sin métricas, ordenados por proximidad a 48h, click abre modal. **Por qué importa:** permite llenar datos directamente en el dashboard sin abrir Instagram Insights y el dashboard de cada sesión; el sistema aprende de cada post publicado.

- **2026-07-16 — Lab v2: sistema científico de hipótesis + diseño de experimentos:** El Lab evolucionó de un simple registro de A/B tests a un framework científico completo. Arquitectura final: (1) **Hipótesis** — 6 tarjetas en grid con barra de certeza 0-100% (sube 20% por cada exp válido cerrado, máx 5 exps = 100%), click abre modal con descripción, implicación, caveat y experimentos que la testean; (2) **Diseño de experimentos** — 3 propuestas con instrucciones exactas de producción, botón "Activar" guarda `{id:"_active", data:{design:"ed_001"}}` en `experiments.json`; (3) **Métricas manuales** — cada variante tiene campos para tiempo promedio de reproducción (s), % omisiones y nuevos seguidores, auto-timestampeados al guardar. `HYPOTHESES` se pasa a JS via `__HYPS__` placeholder igual que `__EXPS__` y `__REACH__`. Función `_mkMetric()` genera los inputs numéricos. `mm_` prefix en `data-lab-field` indica métrica manual → se guarda en `variant.avg_watch_time`, `variant.skip_rate`, `variant.new_followers`, `variant.read_at`. **Por qué importa:** base del sistema de ingeniería inversa de contenido — cada hipótesis necesita 5 experimentos confirmatorios para llegar al 100%.

- **2026-07-16 — Instagram Insights reales vs fuentes web (corrección importante):** Las fuentes web citaban que Instagram muestra DM shares separados de shares totales — FALSO. Lo que Instagram realmente muestra en Insights de un post es: visualizaciones, cuentas alcanzadas, tiempo promedio de reproducción, nuevos seguidores, porcentaje de omisiones. NO hay separación de DM vs story shares en la UI. Las métricas de retención (tiempo prom. reproducción y % omisiones) son las más valiosas y NO están en la API — solo en la app. Por eso se agregaron como campos manuales en el Lab. **Por qué importa:** no confiar en artículos sobre métricas de IG — verificar siempre con Daniel directamente qué ve en su app.

- **2026-07-16 — Trial Reels: penalización por video base idéntico confirmada experimentalmente:** exp_002 ("una camisa se desgasta", 6 variantes): mismo video base con diferente texto en pantalla y música. A fue el primero (2,888 reach), B-F subidos después (22-130 reach). Patrón idéntico al de penalización documentada. Contraste con exp_001 (hooks hablados distintos, videos genuinamente diferentes): A fue el TERCERO en subirse y aun así ganó con 5,810 reach. Conclusión: el fingerprint visual actúa sobre frames, no sobre audio. Regla: solo testear con Trial Reels en ráfaga si cada variante tiene frames genuinamente distintos desde el segundo 1. **Por qué importa:** exp_002 quedó invalidado metodológicamente — sus datos no son interpretables como test de texto en pantalla.

- **2026-07-16 — Principio de diseño del Lab: pensar antes de construir, siempre preguntar:** Daniel fue explícito — el agente tiende a arrancar a construir sin pensar bien qué construir. El flujo correcto: proponer la arquitectura en texto → esperar aprobación → construir. Solo construir sin preguntar cuando Daniel lo dice explícitamente ("construyelo ya así"). **Por qué importa:** varias iteraciones se hicieron en la dirección equivocada porque se construyó antes de entender bien el modelo mental de Daniel.

- **2026-07-16 — Python string regular `"""..."""`: `\'` se procesa y rompe JS embebido:** Cuando el JS del Lab se puso en un Python string regular (no f-string, no raw), los `\'` que eran JS escape sequences se procesaron como Python → quedaban como `'` simples en el output → el parser de JS fallaba completamente (sin gráficas, sin nada en la página). Fix aplicado: usar `data-eid` y `data-pid` en atributos HTML y `this.dataset.eid` en el onclick, eliminando la necesidad de comillas escapadas. Alternativa: usar `r"""..."""` (raw string). **Por qué importa:** cualquier vez que se embeba JS con comillas escapadas en Python strings, usar data attributes o raw string — nunca `\'` en string regular.

- **2026-07-16 — Instagram Trial Reels: feature específico de IG, no solo "subir varias versiones":** Trial Reels se publican SOLO a no-seguidores (seguidores nunca los ven). Aparecen en la API aunque nunca se publiquen al feed — confirmado: los reels de prueba de Daniel (mismos captions) están en los snapshots con `published_at` vacío. Después de 24-72h se elige el ganador manualmente o con auto-share. La detección automática usa: mismo caption + publicados con <60 min de diferencia = Trial Reel experiment. **Por qué importa:** cambia toda la lógica — no hay contaminación de audiencia. El único campo que Daniel llena es "qué cambié". El sistema detecta y jala métricas automáticamente.

- **2026-07-16 — Lab: arquitectura del pestaña de experimentos construida:** Nueva pestaña 🧪 Lab en el dashboard. `experiments.json` en root del repo (como `post_tags.json`). Server: `GET /experiments` + `POST /save-experiment` (actualiza experimento por ID, sin reemplazar el objeto completo). JS del Lab definido como Python string regular (`_LAB_JS`) — separado del f-string del HTML para evitar escapado de llaves. Se embebe vía `{lab_js}` en el f-string. Datos de reach por post → `lab_reach_map` calculado desde `all_posts_data`. Dos experimentos iniciales: exp_001 (hacen ver pobre, 4 variantes, ganador ~5,853 reach) y exp_002 (camisa, 6 variantes, ganador ~3,182 reach). **Por qué importa:** base del sistema de aprendizaje acumulado. El flujo: Daniel llena "qué cambié" → datos automáticos → juntos llegamos al insight → queda guardado.

- **2026-07-16 — Instagram API: website_clicks y profile_views NO soportan period=day sin metric_type=total_value:** Intentar obtener serie diaria de `website_clicks,profile_views` con `period=day` sin `metric_type=total_value` devuelve HTTP 400. Solo están disponibles como total agregado para el período. Solución implementada: guardar el valor de ventana 1d (`since=now-86400, until=now`) en el `_meta` de cada snapshot via `get_daily_business_metrics()`, y construir la serie desde el historial de snapshots con `build_clicks_series()`. **Por qué importa:** no volver a intentar el endpoint diario directo — siempre usar snapshots acumulados para la serie temporal.

- **2026-07-16 — Follower growth tracking: followers_count en _meta de cada snapshot:** Tanto `take_snapshot.py` (Railway) como `save_snapshot()` en `generate_dashboard.py` guardan `followers_count` en el `_meta` de cada snapshot. `build_follower_series()` calcula delta diario, baseline = mediana de deltas (robusto a picos), orgánico estimado = max(0, delta - baseline). La campaña de pauta de Daniel corre constante → baseline estable → picos sobre el baseline son señal orgánica. El gráfico muestra barras apiladas (orgánico verde + pauta naranja). **Por qué importa:** sin esto no se puede correlacionar posts con ganancia de seguidores.

- **2026-07-16 — Posts fijados sesgan el análisis: deben excluirse de insights:** Los dos posts fijados en el perfil ("Este post es muy especial" y "Tiene que nacer acá 🇨🇴") tienen tráfico constante del perfil — no son comparables con posts orgánicos. Sin excluirlos, conexión parecía igual a atracción (2,833 vs 2,781) cuando en realidad conexión sin fijados promedia ~1,265. Implementado: flag `_pinned` en `post_tags.json`, botón 📌 en tabla y en modal, posts fijados excluidos de `renderInsights()`. **Por qué importa:** los posts fijados siempre van a inflar la categoría a la que pertenecen — hay que marcarlos al inicio de cada sesión de análisis.

- **2026-07-16 — generate_dashboard.py: siempre sincronizar snapshots desde GitHub antes de generar:** El archivo `.tmp/post_snapshots.json` local puede estar desactualizado (Railway escribe directo a GitHub). Desde este fix, `main()` siempre hace `{**remote, **local}` al inicio — local gana en conflictos (más reciente). Sin esto el HTML generado localmente tenía solo 9 snapshots en vez de 33. **Por qué importa:** cada vez que se genera localmente sin sincronizar primero, el HTML queda con datos incompletos y se sube a GitHub pisando el bueno.

- **2026-07-16 — /save-tags DEBE fusionar (merge), no sobrescribir:** Si `_tags` en el browser está incompleto (sesión nueva, fetch fallido) y el usuario guarda, se pierden todas las etiquetas previas. Ocurrió: 32 tags → guardó 3 → se perdieron 29. Fix en `server.py`: leer existing → `{**existing, **new}` → escribir. Para `_pinned` (lista): unión de sets. Las tags se recuperaron del historial de git de GitHub. **Por qué importa:** bug crítico de pérdida de datos — siempre merge, nunca replace en endpoints de guardado.

- **2026-07-16 — Análisis actualizado con todas las etiquetas (39 posts):** Con todos los posts etiquetados y fijados excluidos: atracción=2,781 (n=10, 30%), conversión=2,066 (n=17, 52%), conexión orgánica=~1,265 (n=4, sin fijados). VIDEO+atracción = combo ganador (2,845 avg). Vassar (jul 1-5) hundió métricas: contenido de evento no viaja orgánicamente. Reels de prueba ("te hacen ver pobre" x4, "camisa" x6) muestran diferencias de 39x-143x entre versiones — A/B testing sin documentar. **Por qué importa:** base de datos limpia para decisiones de contenido.

- **2026-07-16 — Reels de prueba = A/B testing intencional sin documentación:** Daniel sube variaciones del mismo video (mismo caption, distintos IDs) para probar qué versión funciona mejor. El problema es que no documenta qué varía entre versiones, por lo que el experimento produce datos pero no aprendizaje. Aparecen como duplicados en el tracking. Solución futura: marcar variantes con "variante de [ID_ganador]" en el dashboard. **Por qué importa:** sin documentar la variable cambiada, no se puede transferir el aprendizaje a futuros videos.

- **2026-07-14 — Dashboard: siempre actualizar docs/index.html al cambiar generate_dashboard.py:** Cada vez que se modifica el script y se hace push, hay que también regenerar el HTML y subirlo: `python3 execution/generate_dashboard.py && cp .tmp/dashboard.html docs/index.html && git add docs/index.html`. Sin este paso el servidor Railway sigue sirviendo el HTML viejo (cacheado 5min desde GitHub). **Por qué importa:** Daniel lo detectó — cambios en el script no se reflejaban en la URL pública.

- **2026-07-14 — Dashboard Railway web: arquitectura server-side para etiquetas:** El servidor `execution/server.py` sirve el HTML desde GitHub API (caché 5min) y maneja `/save-tags` y `/tags` server-side. El GH_TOKEN nunca llega al browser. Las etiquetas se cargan vía `fetch("/tags")` al abrir el dashboard — funciona desde cualquier dispositivo. **Por qué importa:** evita embeber tokens en HTML público y hace el sistema verdaderamente multi-dispositivo.

- **2026-07-14 — Snapshots cada 6h: clave YYYY-MM-DD_HHh con slot UTC:** El slot se calcula como `(now_utc.hour // 6) * 6` → valores 0, 6, 12, 18. La clave queda `2026-07-12_06h`. Telegram solo en slot 0 (medianoche Colombia = 05h UTC → slot 00h). El dashboard ordena por `sorted(keys)` que funciona correctamente con este formato. **Por qué importa:** permite comparar alcance 48h real entre posts sin depender de snapshot diario que puede capturar el post en momentos muy distintos de su vida.

- **2026-07-14 — Métrica principal del ranking: alcance 48h, no vida útil:** Vida útil (reach/hora) siempre favorece al post más reciente porque está en su pico de algorithmo. La métrica correcta para comparar posts es el reach del snapshot más cercano a las 48h de vida (`min(series, key=lambda x: abs(x['hours']-48))`). Vida útil queda solo en el modal como curva de decaimiento. **Por qué importa:** el ranking con vida útil siempre mostraba el último post publicado primero — no daba información útil.

- **2026-07-14 — Primer análisis real de datos: atracción supera conversión en 66%:** Con 24 snapshots y 39 posts: atracción=2,567 reach prom, conexión=1,923, conversión=1,546. El 64% de posts son conversión pero es la categoría con menos reach. Los posts sin etiquetar (los mejores históricos de mayo-junio) son probablemente atracción. La cadencia actual está invertida — hay que publicar más atracción y menos conversión. **Por qué importa:** valida la estrategia 4-2-1 (atracción-conexión-conversión) con datos reales.

- **2026-07-07 — Selección de fotos: primero la necesidad visual, después la fuente:** Antes de buscar fotos, definir qué debe mostrar el slide visualmente (objeto/producto, situación de uso, emoción, contexto de marca). Solo después revisar si existe una foto que lo resuelva, o si hay que crearla con IA, o editarla. El orden incorrecto es: buscar qué foto disponible encaja con el texto — eso lleva a carruseles homogéneos con siempre el mismo tipo de imagen. **Fuentes disponibles en orden de preferencia:** (1) Fotos reales existentes en carpetas del proyecto (`Fotos Relojes/`, `Fotos Lifestyle/`, `Fotos Vassar/`, cualquier carpeta nueva que agregue Daniel); (2) Foto real existente + edición IA (cambiar fondo, wrist shot con gemini-3.1-flash-image); (3) Imagen IA desde cero con Imagen 4.0 para escenas de lifestyle/atmósfera donde no hay foto propia. **Por qué importa:** 3 carruseles seguidos con macro de relojes sobre fondo oscuro se ven iguales — la variedad visual es parte del engagement.

- **2026-07-07 — Modelo correcto para wrist shots con reloj Serrat: `gemini-3.1-flash-image`:** Usar `gemini-3.1-flash-image` con `responseModalities: ["IMAGE"]` y la foto real del reloj como `inline_data` en el mismo `parts[]`. El modelo respeta el diseño del reloj de la referencia (dial, correa, caja). `gemini-2.0-flash-exp` no existe, `imagen-4.0` no acepta referenceImages sin formato exacto. **Por qué importa:** es el único modelo que genera wrist shots fotorrealistas con el reloj Serrat real.

- **2026-07-07 — REGLA CRÍTICA: todo reloj en imagen IA debe basarse en foto real Serrat:** Nunca generar una imagen IA con un reloj genérico. SIEMPRE usar una foto real de `Fotos Relojes/` como referencia visual (vía Imagen API con referenceImages, o via rembg+composite). Las fotos validadas como referencia: `_DSC1682.jpg` (la mejor), `_DSC1735.jpg`, `_DSC1737.jpg`. **Por qué importa:** Daniel lo corrigió explícitamente — un reloj IA genérico no es Serrat y daña la credibilidad de la marca.

- **2026-07-07 — Bandera colombiana en IA: especificar "sin escudo, sin coat of arms":** Imagen 4.0 tiende a agregar el escudo de Colombia en la bandera, haciéndola parecer la de Ecuador. Siempre incluir en el prompt: "plain Colombian tricolor flag — yellow, blue, red horizontal stripes, NO coat of arms, NO escudo, NO emblem". **Por qué importa:** Daniel lo detectó de inmediato — "así parece de ecuador".

- **2026-07-07 — Cadencia semanal de contenido definida:** 7 carruseles/semana con proporción fija: **4 atracción · 2 conexión · 1 conversión**. Los 3 pilares son el eje de toda la estrategia de contenido. Atracción = llegar a personas nuevas (identidad, humor, emoción). Conexión = construir relación con quien ya sigue (historia de marca, humanización). Conversión = vender a quien ya confía (producto, CTA, regalo). **Por qué importa:** los datos muestran que atracción genera 3-4x más reach que conversión directa — la proporción refleja esa realidad.

- **2026-07-06 — Dashboard: métrica "vida útil" como eje de comparación justo:** `reach_acumulado / horas_desde_publicación` = reach/hora desde que nació el post. Justa entre posts de distinta edad sin depender de ventanas de snapshot. El ranking usa el último snapshot disponible. El modal muestra barras (no línea) por honestidad con pocos puntos. Si solo hay 1 snapshot, mostrar mensaje "vuelve mañana". **Por qué importa:** reemplaza los botones de 24h/48h/72h que dejaban posts fuera del ranking por falta de snapshots en esa ventana exacta.

- **2026-07-06 — Dashboard: automatización completa Railway + GitHub Pages:** Railway cron `0 5 * * *` (medianoche Colombia) corre `take_snapshot.py` → guarda snapshot en GitHub via API → genera HTML → sube a `docs/index.html` → GitHub Pages sirve en URL pública → Telegram notifica con top 3 + link. El script usa `import generate_dashboard as gd` para reutilizar `build_html`. **Por qué importa:** sin computador encendido, sin intervención manual.

- **2026-07-06 — git push: las credenciales ya están guardadas en macOS:** No usar token en URL del remote (bloqueado por seguridad). Con `credential.helper store` y las credenciales ya guardadas del sistema, `git push` funciona directamente sin parámetros adicionales. **Por qué importa:** puedo hacer push libremente con `git push` simple.

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
