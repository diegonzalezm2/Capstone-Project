/* global Chart */
(function () {
  const CFG = {
    urlSummary: "/dashboard/api/summary/",
    urlMonthly: "/dashboard/api/monthly/",
    urlTopGuards: "/dashboard/api/top_guardias/?days=30&limit=10",
    // CSV por gráfico
    csv14d: "/dashboard/export/csv/14d/",
    csvHourToday: "/dashboard/export/csv/hour_today/",
    csvLocToday: "/dashboard/export/csv/location_today/",
    csvTopWeek: "/dashboard/export/csv/top_visitors_week/",
    csvMonthly: "/dashboard/export/csv/monthly/",
    csvTopGuards: "/dashboard/export/csv/top_guards/?days=30&limit=10",
  };

  // Nodos KPIs
  const elKpiToday = document.getElementById("kpi-today");
  const elKpiInside = document.getElementById("kpi-inside");

  // Canvas
  const ctx14d = document.getElementById("chart-14d");
  const ctxHour = document.getElementById("chart-hour");
  const ctxLoc = document.getElementById("chart-location");
  const ctxTop = document.getElementById("chart-top");
  const ctxMonth = document.getElementById("chart-month");
  const ctxTopGuards = document.getElementById("chart-topguards");

  function safeSetText(node, val) { if (node) node.textContent = val; }

  function lineChart(ctx, labels, values, title) {
    if (!ctx) return null;
    return new Chart(ctx, {
      type: "line",
      data: { labels, datasets: [{ label: title, data: values, tension: 0.3, fill: false }] },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { grid: { display: false } }, y: { beginAtZero: true, ticks: { precision: 0 } } }
      }
    });
  }

  function barChart(ctx, labels, values, title) {
    if (!ctx) return null;
    return new Chart(ctx, {
      type: "bar",
      data: { labels, datasets: [{ label: title, data: values }] },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { grid: { display: false } }, y: { beginAtZero: true, ticks: { precision: 0 } } }
      }
    });
  }

  async function loadSummary() {
    const res = await fetch(CFG.urlSummary, { headers: { "X-Requested-With": "fetch" } });
    const data = await res.json();
    if (!data.ok) throw new Error(data.message || "Respuesta inválida");

    safeSetText(elKpiToday, data.kpis.today);
    safeSetText(elKpiInside, data.kpis.inside_now);

    lineChart(ctx14d, data.series_14d.labels, data.series_14d.values, "Entradas por día (14)");
    lineChart(ctxHour, data.by_hour.labels, data.by_hour.values, "Entradas por hora");
    barChart(ctxLoc, data.by_location_today.labels, data.by_location_today.values, "Entradas por ubicación (hoy)");
    barChart(ctxTop, data.top_visitors_week.labels, data.top_visitors_week.values, "Top visitantes (7 días)");
  }

  async function loadMonthly() {
    if (!ctxMonth) return;
    const res = await fetch(CFG.urlMonthly, { headers: { "X-Requested-With": "fetch" } });
    const data = await res.json();
    if (!data.ok) throw new Error(data.message || "Respuesta inválida");
    lineChart(ctxMonth, data.labels, data.values, "Entradas por mes");
  }

  async function loadTopGuards() {
    if (!ctxTopGuards) return;
    const res = await fetch(CFG.urlTopGuards, { headers: { "X-Requested-With": "fetch" } });
    const data = await res.json();
    if (!data.ok) throw new Error(data.message || "Respuesta inválida");
    barChart(ctxTopGuards, data.labels, data.values, "Top guardias (30 días)");
  }

  // Botones CSV por gráfico (simple GET = descarga)
  function bindCsvButtons() {
    const go = (url) => { window.location.href = url; };

    document.getElementById("btn-csv-14d")?.addEventListener("click", () => go(CFG.csv14d));
    document.getElementById("btn-csv-hour")?.addEventListener("click", () => go(CFG.csvHourToday));
    document.getElementById("btn-csv-loc")?.addEventListener("click", () => go(CFG.csvLocToday));
    document.getElementById("btn-csv-top")?.addEventListener("click", () => go(CFG.csvTopWeek));
    document.getElementById("btn-csv-month")?.addEventListener("click", () => go(CFG.csvMonthly));
    document.getElementById("btn-csv-guards")?.addEventListener("click", () => go(CFG.csvTopGuards));
  }

  document.addEventListener("DOMContentLoaded", () => {
    Promise.all([loadSummary(), loadMonthly(), loadTopGuards()])
      .then(bindCsvButtons)
      .catch((err) => {
        console.error(err);
        alert("No se pudieron cargar los datos del tablero.");
      });
  });
})();
