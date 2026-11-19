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

  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function lineDataset(label, values, color, fill) {
    return {
      label: label, data: values, borderColor: color, backgroundColor: fill ? alpha(color, 0.14) : color,
      fill: !!fill, tension: 0.32, pointRadius: 0, pointHitRadius: 12, pointHoverRadius: 5,
      pointBackgroundColor: color, pointHoverBorderColor: css("--surface"), pointHoverBorderWidth: 2,
      borderWidth: 2.5, spanGaps: true
    };
  }

  function solo(cfg) { cfg.options.plugins.legend.display = false; return cfg; }

  function baseOptions(unit) {
    var text = css("--chart-text");
    var grid = css("--chart-grid");
    var font = css("--font-ui") || "system-ui";
    return {
      responsive: true, maintainAspectRatio: false,
      animation: reduced ? false : { duration: 500, easing: "easeOutQuart" },
      interaction: { mode: "index", intersect: false },
      layout: { padding: { top: 4 } },
      plugins: {
        legend: { labels: { color: text, boxWidth: 10, boxHeight: 10, usePointStyle: true, font: { family: font, size: 12 } } },
        tooltip: {
          backgroundColor: css("--chart-tip-bg"), titleColor: css("--chart-tip-ink"), bodyColor: css("--chart-tip-ink"),
          borderColor: "transparent", padding: 10, cornerRadius: 6, displayColors: false,
          titleFont: { family: font, size: 12, weight: "600" }, bodyFont: { family: font, size: 13, weight: "700" },
          callbacks: { label: function (ctx) { return ctx.dataset.label + ": " + ctx.parsed.y + (unit ? " " + unit : ""); } }
        }
      },
      scales: {
        x: { ticks: { color: text, maxRotation: 0, autoSkip: true, font: { family: font, size: 11 } }, grid: { display: false }, border: { color: grid } },
        y: { ticks: { color: text, font: { family: font, size: 11 }, padding: 6 }, grid: { color: grid }, border: { display: false }, beginAtZero: false }
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
      return { type: "bar", data: { labels: d.labels.map(fmtDate), datasets: [{ label: t.workouts || "Treningi", data: d.values, backgroundColor: d.values.map(function (_, i) { return i === d.values.length - 1 ? css("--chart-hi") : css("--chart-bar"); }), borderRadius: 6, borderSkipped: false, maxBarThickness: 24 }] }, options: opts };
    },
    bodyWeight: function () {
      var d = data.bodyWeight; if (!d || !d.values.length) { return null; }
      var opts = baseOptions("kg");
      opts.plugins.legend.display = false;
      return { type: "line", data: { labels: d.labels.map(fmtDate), datasets: [lineDataset(t.bodyWeight || "Masa ciała", d.values, css("--chart-2"), true)] }, options: opts };
    },
    progress: function () {
      var d = data.progress; if (!d || !d.labels.length) { return null; }
      var labels = d.labels.map(fmtDate);
      if (data.cardio) {
        return solo({ type: "line", data: { labels: labels, datasets: [lineDataset(t.distance || "Dystans (km)", d.distance, css("--chart-1"), true)] }, options: baseOptions("km") });
      }
      return solo({ type: "line", data: { labels: labels, datasets: [lineDataset(t.maxWeight || "Maks. ciężar (kg)", d.max_weight, css("--chart-1"), true)] }, options: baseOptions("kg") });
    },
    e1rm: function () {
      var d = data.progress; if (!d || !d.labels.length) { return null; }
      var labels = d.labels.map(fmtDate);
      if (data.cardio) {
        return solo({ type: "line", data: { labels: labels, datasets: [lineDataset(t.duration || "Czas (min)", d.duration, css("--chart-2"), false)] }, options: baseOptions("min") });
      }
      return solo({ type: "line", data: { labels: labels, datasets: [lineDataset(t.e1rm || "Szacowany 1RM (kg)", d.e1rm, css("--chart-2"), false)] }, options: baseOptions("kg") });
    },
    volume: function () {
      var d = data.progress; if (!d || !d.labels.length || data.cardio) { return null; }
      var opts = baseOptions("kg");
      opts.scales.y.beginAtZero = true;
      opts.plugins.legend.display = false;
      return { type: "bar", data: { labels: d.labels.map(fmtDate), datasets: [{ label: t.volume || "Objętość", data: d.volume, backgroundColor: alpha(css("--chart-2"), 0.8), hoverBackgroundColor: css("--chart-2"), borderRadius: 6, borderSkipped: false, maxBarThickness: 24 }] }, options: opts };
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

  Chart.defaults.font.family = css("--font-ui") || "system-ui";
  Chart.defaults.locale = t.lang === "pl" ? "pl-PL" : (t.lang || "en");
  render();
  document.addEventListener("themechange", render);
})();
