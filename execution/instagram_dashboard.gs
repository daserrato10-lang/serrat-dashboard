// ============================================================
// SERRAT RELOJES — Instagram Dashboard
// Google Apps Script
// Pegar en: Extensions > Apps Script > Code.gs
// Ejecutar: actualizarDashboard()
// ============================================================

const IG_TOKEN = "EAAOyT2h7pY4BR8zNsXWeUbjIWbNKcA4vLlXKmbPe05bljMAjbKG3YRlf2P9JP4YXOuL1daZBLtVrZC3EZC6REkD5CcFaDIZBkrTA1YvYNO8qZAnwJz76Ll0LnTwLQaGEBLRRpDQol2lTkJPTFYt3kdYqeffORumiznLftDl7ZBLRHyF0TOLjnIuY3ucPGF0XQO5AZDZD";
const IG_ID   = "17841400598267708";
const BASE    = "https://graph.facebook.com/v21.0";

// ── Utilidades ───────────────────────────────────────────────

function igGet(path, params) {
  params = params || {};
  params.access_token = IG_TOKEN;
  const qs = Object.keys(params).map(k => k + "=" + encodeURIComponent(params[k])).join("&");
  const url = BASE + "/" + path + "?" + qs;
  const res = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  const data = JSON.parse(res.getContentText());
  if (data.error) throw new Error(data.error.message);
  return data;
}

function getOrCreate(ss, name, color) {
  let sh = ss.getSheetByName(name);
  if (!sh) sh = ss.insertSheet(name);
  sh.clear();
  sh.setTabColor(color || null);
  return sh;
}

function header(sh, row, col, values, bg) {
  const range = sh.getRange(row, col, 1, values.length);
  range.setValues([values]);
  range.setBackground(bg || "#1a1a2e");
  range.setFontColor("#ffffff");
  range.setFontWeight("bold");
  range.setFontSize(11);
}

function fmt(sh, row, col, rows, cols, options) {
  const r = sh.getRange(row, col, rows, cols);
  if (options.bg)        r.setBackground(options.bg);
  if (options.bold)      r.setFontWeight("bold");
  if (options.size)      r.setFontSize(options.size);
  if (options.color)     r.setFontColor(options.color);
  if (options.center)    r.setHorizontalAlignment("center");
  if (options.format)    r.setNumberFormat(options.format);
  if (options.wrap)      r.setWrap(true);
  return r;
}

// ── Datos desde la API ───────────────────────────────────────

function getPerfil() {
  return igGet(IG_ID, {
    fields: "username,followers_count,follows_count,media_count,website"
  });
}

function getInsights28d() {
  const since = Math.floor((Date.now() - 28*24*60*60*1000) / 1000);
  const until = Math.floor(Date.now() / 1000);

  // Métricas por día
  const daily = igGet(IG_ID + "/insights", {
    metric: "reach,follower_count",
    period: "day",
    since: since,
    until: until
  });

  // Métricas totales
  const totals = igGet(IG_ID + "/insights", {
    metric: "profile_views,website_clicks,total_interactions,likes,comments,shares,saves",
    metric_type: "total_value",
    period: "day",
    since: since,
    until: until
  });

  const result = {};

  // Extraer reach total y seguidores ganados
  for (const m of daily.data) {
    const vals = m.values || [];
    result[m.name] = vals.reduce((s, v) => s + (typeof v.value === "number" ? v.value : 0), 0);
    if (m.name === "reach") result.reach_daily = vals.map(v => ({ date: v.end_time.slice(0,10), value: v.value }));
    if (m.name === "follower_count") result.followers_daily = vals.map(v => ({ date: v.end_time.slice(0,10), value: v.value }));
  }

  // Extraer totales
  for (const m of totals.data) {
    result[m.name] = (m.total_value || {}).value || 0;
  }

  return result;
}

function getPosts(limit) {
  limit = limit || 20;
  const media = igGet(IG_ID + "/media", {
    fields: "id,caption,media_type,timestamp,like_count,comments_count,permalink",
    limit: limit
  });

  const posts = media.data || [];

  // Obtener reach e impresiones por post
  for (const post of posts) {
    try {
      const ins = igGet(post.id + "/insights", {
        metric: "reach,saved,shares"
      });
      for (const m of (ins.data || [])) {
        post["metric_" + m.name] = (m.values && m.values[0]) ? m.values[0].value : 0;
      }
    } catch(e) {
      post.metric_reach = 0;
      post.metric_saved = 0;
      post.metric_shares = 0;
    }
    Utilities.sleep(100);
  }

  return posts;
}

function getDemografia() {
  const byAge = igGet(IG_ID + "/insights", {
    metric: "follower_demographics",
    metric_type: "total_value",
    period: "lifetime",
    breakdown: "age,gender"
  });

  const byCity = igGet(IG_ID + "/insights", {
    metric: "follower_demographics",
    metric_type: "total_value",
    period: "lifetime",
    breakdown: "city"
  });

  const byCountry = igGet(IG_ID + "/insights", {
    metric: "follower_demographics",
    metric_type: "total_value",
    period: "lifetime",
    breakdown: "country"
  });

  return { byAge, byCity, byCountry };
}

// ── Hojas ────────────────────────────────────────────────────

function escribirResumen(ss, perfil, insights) {
  const sh = getOrCreate(ss, "📊 Resumen", "#1a73e8");
  sh.setColumnWidth(1, 260);
  sh.setColumnWidth(2, 160);
  sh.setColumnWidth(3, 200);
  sh.setColumnWidth(4, 200);

  // Título principal
  sh.getRange("A1:D1").merge().setValue("SERRAT RELOJES — Dashboard Instagram")
    .setBackground("#1a1a2e").setFontColor("#ffffff").setFontSize(16).setFontWeight("bold")
    .setHorizontalAlignment("center");

  sh.getRange("A2:D2").merge()
    .setValue("Actualizado: " + new Date().toLocaleString("es-CO", {timeZone: "America/Bogota"}))
    .setBackground("#2d2d44").setFontColor("#aaaacc").setFontSize(10)
    .setHorizontalAlignment("center");

  // Cuenta
  header(sh, 4, 1, ["CUENTA", "VALOR"], "#16213e");
  const cuentaData = [
    ["👥 Seguidores", perfil.followers_count],
    ["➡️ Siguiendo", perfil.follows_count],
    ["📸 Posts totales", perfil.media_count],
    ["🌐 Sitio web", perfil.website || "—"]
  ];
  sh.getRange(5, 1, cuentaData.length, 2).setValues(cuentaData);
  fmt(sh, 5, 2, 3, 1, { format: "#,##0", bold: true });

  // Últimos 28 días
  const row28 = 5 + cuentaData.length + 2;
  header(sh, row28, 1, ["ÚLTIMOS 28 DÍAS", "VALOR", "MÉTRICA", "VALOR"], "#16213e");

  const col1 = [
    ["📣 Alcance total", insights.reach || 0],
    ["👁️ Visitas de perfil", insights.profile_views || 0],
    ["🔗 Clics al sitio web", insights.website_clicks || 0],
    ["📈 Seguidores ganados", insights.follower_count || 0]
  ];
  const col2 = [
    ["💬 Interacciones totales", insights.total_interactions || 0],
    ["❤️ Likes", insights.likes || 0],
    ["💭 Comentarios", insights.comments || 0],
    ["🔁 Compartidos", insights.shares || 0]
  ];

  for (let i = 0; i < col1.length; i++) {
    sh.getRange(row28 + 1 + i, 1, 1, 2).setValues([[col1[i][0], col1[i][1]]]);
    sh.getRange(row28 + 1 + i, 3, 1, 2).setValues([[col2[i][0], col2[i][1]]]);
  }
  fmt(sh, row28+1, 2, 4, 1, { format: "#,##0", bold: true });
  fmt(sh, row28+1, 4, 4, 1, { format: "#,##0", bold: true });

  // Engagement rate
  const rowEng = row28 + col1.length + 2;
  const engRate = perfil.followers_count > 0
    ? ((insights.total_interactions || 0) / perfil.followers_count * 100).toFixed(2)
    : 0;
  sh.getRange(rowEng, 1, 1, 2).setValues([["📊 Tasa de engagement (28d)", engRate + "%"]]);
  fmt(sh, rowEng, 1, 1, 2, { bold: true, bg: "#e8f5e9" });

  // Guardar marca de tiempo en histórico
  const savedCounts = {
    fecha: new Date().toLocaleDateString("es-CO", {timeZone: "America/Bogota"}),
    seguidores: perfil.followers_count,
    reach: insights.reach || 0,
    perfil_views: insights.profile_views || 0,
    web_clicks: insights.website_clicks || 0,
    interacciones: insights.total_interactions || 0,
    engagement: engRate
  };

  return savedCounts;
}

function escribirPosts(ss, posts) {
  const sh = getOrCreate(ss, "📱 Posts", "#34a853");
  sh.setFrozenRows(1);
  sh.setColumnWidths(1, 8, 130);
  sh.setColumnWidth(2, 350);
  sh.setColumnWidth(1, 120);

  header(sh, 1, 1, ["Fecha", "Caption (primeros 200 chars)", "Tipo", "Likes", "Comentarios", "Alcance", "Guardados", "URL"], "#1a1a2e");

  const rows = posts.map(p => [
    (p.timestamp || "").slice(0, 10),
    (p.caption || "").slice(0, 200).replace(/\n/g, " "),
    p.media_type || "",
    p.like_count || 0,
    p.comments_count || 0,
    p.metric_reach || 0,
    p.metric_saved || 0,
    p.permalink || ""
  ]);

  if (rows.length > 0) {
    sh.getRange(2, 1, rows.length, 8).setValues(rows);
    fmt(sh, 2, 4, rows.length, 4, { format: "#,##0" });
    fmt(sh, 2, 2, rows.length, 1, { wrap: false });

    // Colorear filas alternadas
    for (let i = 0; i < rows.length; i++) {
      if (i % 2 === 0) sh.getRange(i+2, 1, 1, 8).setBackground("#f8f9fa");
    }
  }
}

function escribirAudiencia(ss, demo) {
  const sh = getOrCreate(ss, "👥 Audiencia", "#fbbc04");

  // Edad y género
  header(sh, 1, 1, ["EDAD + GÉNERO", "SEGUIDORES", "", "PAÍS", "SEGUIDORES"], "#1a1a2e");

  let ageData = [];
  try {
    const breakdowns = demo.byAge.data[0].total_value.breakdowns[0].results;
    ageData = breakdowns
      .sort((a, b) => b.value - a.value)
      .map(r => [r.dimension_values.join(" / "), r.value]);
  } catch(e) { ageData = [["Sin datos", ""]]; }

  let countryData = [];
  try {
    const breakdowns = demo.byCountry.data[0].total_value.breakdowns[0].results;
    countryData = breakdowns
      .sort((a, b) => b.value - a.value)
      .slice(0, 15)
      .map(r => [r.dimension_values[0], r.value]);
  } catch(e) { countryData = [["Sin datos", ""]]; }

  const maxRows = Math.max(ageData.length, countryData.length);
  for (let i = 0; i < maxRows; i++) {
    const age = ageData[i] || ["", ""];
    const country = countryData[i] || ["", ""];
    sh.getRange(i+2, 1, 1, 5).setValues([[age[0], age[1], "", country[0], country[1]]]);
  }

  fmt(sh, 2, 2, maxRows, 1, { format: "#,##0" });
  fmt(sh, 2, 5, maxRows, 1, { format: "#,##0" });

  // Ciudades
  let cityData = [];
  try {
    const breakdowns = demo.byCity.data[0].total_value.breakdowns[0].results;
    cityData = breakdowns
      .sort((a, b) => b.value - a.value)
      .slice(0, 15)
      .map(r => [r.dimension_values[0], r.value]);
  } catch(e) { cityData = [["Sin datos", ""]]; }

  const cityRow = maxRows + 3;
  header(sh, cityRow, 1, ["TOP CIUDADES", "SEGUIDORES"], "#16213e");
  if (cityData.length > 0) {
    sh.getRange(cityRow+1, 1, cityData.length, 2).setValues(cityData);
    fmt(sh, cityRow+1, 2, cityData.length, 1, { format: "#,##0" });
  }

  sh.setColumnWidth(1, 200);
  sh.setColumnWidth(2, 120);
  sh.setColumnWidth(4, 200);
  sh.setColumnWidth(5, 120);
}

function escribirHistorico(ss, snapshot) {
  let sh = ss.getSheetByName("📈 Histórico");
  if (!sh) {
    sh = ss.insertSheet("📈 Histórico");
    sh.setTabColor("#ea4335");
    header(sh, 1, 1, ["Fecha", "Seguidores", "Reach 28d", "Visitas Perfil", "Clics Web", "Interacciones", "Engagement %"], "#1a1a2e");
    sh.setFrozenRows(1);
  }

  // Append nueva fila
  const lastRow = Math.max(sh.getLastRow(), 1);
  sh.getRange(lastRow+1, 1, 1, 7).setValues([[
    snapshot.fecha,
    snapshot.seguidores,
    snapshot.reach,
    snapshot.perfil_views,
    snapshot.web_clicks,
    snapshot.interacciones,
    snapshot.engagement
  ]]);
  fmt(sh, lastRow+1, 2, 1, 5, { format: "#,##0" });

  sh.setColumnWidths(1, 7, 140);
}

// ── Main ─────────────────────────────────────────────────────

function actualizarDashboard() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  Logger.log("Obteniendo perfil...");
  const perfil = getPerfil();

  Logger.log("Obteniendo insights 28d...");
  const insights = getInsights28d();

  Logger.log("Obteniendo posts...");
  const posts = getPosts(20);

  Logger.log("Obteniendo demografía...");
  const demo = getDemografia();

  Logger.log("Escribiendo Resumen...");
  const snapshot = escribirResumen(ss, perfil, insights);

  Logger.log("Escribiendo Posts...");
  escribirPosts(ss, posts);

  Logger.log("Escribiendo Audiencia...");
  escribirAudiencia(ss, demo);

  Logger.log("Escribiendo Histórico...");
  escribirHistorico(ss, snapshot);

  Logger.log("✅ Dashboard actualizado: " + new Date());
  SpreadsheetApp.getUi().alert("✅ Dashboard actualizado correctamente.\n\nÚltima actualización: " + new Date().toLocaleString("es-CO"));
}

// ── Trigger automático (ejecutar una sola vez para activar) ──

function configurarTriggerSemanal() {
  // Eliminar triggers existentes
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));

  // Crear trigger: todos los lunes a las 8am hora Colombia
  ScriptApp.newTrigger("actualizarDashboard")
    .timeBased()
    .onWeekDay(ScriptApp.WeekDay.MONDAY)
    .atHour(8)
    .create();

  SpreadsheetApp.getUi().alert("✅ Trigger configurado: el dashboard se actualizará automáticamente cada lunes a las 8am.");
}
