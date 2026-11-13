(function () {
  "use strict";
  if (typeof Chart === "undefined") { return; }
  var dataEl = document.getElementById("chart-data");
  if (!dataEl) { return; }
  var data = JSON.parse(dataEl.textContent || "{}");
  var i18nEl = document.getElementById("chart-i18n");
  var t = i18nEl ? JSON.parse(i18nEl.textContent || "{}") : {};
  var shortDate = null;
  if (t.lang && t.lang !== "pl" && window.Intl) {
    shortDate = new Intl.DateTimeFormat(t.lang, { month: "short", day: "numeric", timeZone: "UTC" });
  }
  var instances = [];

  function css(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function alpha(hex, a) {
    var h = hex.replace("#", "");
    if (h.length === 3) { h = h.split("").map(function (c) { return c + c; }).join(""); }
    var n = parseInt(h, 16);
    return "rgba(" + ((n >> 16) & 255) + "," + ((n >> 8) & 255) + "," + (n & 255) + "," + a + ")";
  }

  function fmtDate(iso) {
    var p = iso.split("-");
    if (p.length !== 3) { return iso; }
    if (shortDate) { return shortDate.format(new Date(Date.UTC(+p[0], +p[1] - 1, +p[2]))); }
    return p[2] + "." + p[1];
  }

  function lineDataset(label, values, color, fill) {
    return {
      label: label, data: values, borderColor: color, backgroundColor: fill ? alpha(color, 0.15) : color,
      fill: !!fill, tension: 0.3, pointRadius: 3, pointHoverRadius: 6, borderWidth: 2.5, spanGaps: true
    };
  }

  function baseOptions(unit) {
    var text = css("--text-muted");
    var grid = css("--border");
    return {
      responsive: true, maintainAspectRatio: false, animation: { duration: 400 },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: text, boxWidth: 12, usePointStyle: true } },
        tooltip: { callbacks: { label: function (ctx) { return ctx.dataset.label + ": " + ctx.parsed.y + (unit ? " " + unit : ""); } } }
      },
      scales: {
        x: { ticks: { color: text, maxRotation: 0, autoSkip: true }, grid: { color: grid, display: false } },
        y: { ticks: { color: text }, grid: { color: grid }, beginAtZero: false }
      }
    };
  }

  var builders = {
    perWeek: function () {
      var d = data.perWeek; if (!d) { return null; }
      var opts = baseOptions("");
      opts.scales.y.beginAtZero = true;
      opts.scales.y.ticks.stepSize = 1;
      opts.plugins.legend.display = false;
      return { type: "bar", data: { labels: d.labels.map(fmtDate), datasets: [{ label: t.workouts || "Treningi", data: d.values, backgroundColor: css("--accent"), borderRadius: 6, maxBarThickness: 36 }] }, options: opts };
    },
    bodyWeight: function () {
      var d = data.bodyWeight; if (!d || !d.values.length) { return null; }
      var opts = baseOptions("kg");
      opts.plugins.legend.display = false;
      return { type: "line", data: { labels: d.labels.map(fmtDate), datasets: [lineDataset(t.bodyWeight || "Masa ciała", d.values, css("--info"), true)] }, options: opts };
    },
    progress: function () {
      var d = data.progress; if (!d || !d.labels.length) { return null; }
      var labels = d.labels.map(fmtDate);
      if (data.cardio) {
        return { type: "line", data: { labels: labels, datasets: [lineDataset(t.distance || "Dystans (km)", d.distance, css("--accent"), true)] }, options: baseOptions("km") };
      }
      return { type: "line", data: { labels: labels, datasets: [lineDataset(t.maxWeight || "Maks. ciężar (kg)", d.max_weight, css("--accent"), true)] }, options: baseOptions("kg") };
    },
    e1rm: function () {
      var d = data.progress; if (!d || !d.labels.length) { return null; }
      var labels = d.labels.map(fmtDate);
      if (data.cardio) {
        return { type: "line", data: { labels: labels, datasets: [lineDataset(t.duration || "Czas (min)", d.duration, css("--info"), false)] }, options: baseOptions("min") };
      }
      return { type: "line", data: { labels: labels, datasets: [lineDataset(t.e1rm || "Szacowany 1RM (kg)", d.e1rm, css("--success"), false)] }, options: baseOptions("kg") };
    },
    volume: function () {
      var d = data.progress; if (!d || !d.labels.length || data.cardio) { return null; }
      var opts = baseOptions("kg");
      opts.scales.y.beginAtZero = true;
      opts.plugins.legend.display = false;
      return { type: "bar", data: { labels: d.labels.map(fmtDate), datasets: [{ label: t.volume || "Objętość", data: d.volume, backgroundColor: alpha(css("--accent"), 0.7), borderRadius: 5, maxBarThickness: 28 }] }, options: opts };
    }
  };

  function render() {
    instances.forEach(function (c) { c.destroy(); });
    instances = [];
    document.querySelectorAll("canvas[data-chart]").forEach(function (canvas) {
      var build = builders[canvas.getAttribute("data-chart")];
      var cfg = build && build();
      if (cfg) { instances.push(new Chart(canvas, cfg)); }
    });
  }

  Chart.defaults.font.family = css("--font") || "system-ui";
  render();
  document.addEventListener("themechange", render);
})();
