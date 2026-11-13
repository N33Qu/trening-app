(function () {
  "use strict";
  var root = document.documentElement;

  function setTheme(theme) {
    root.setAttribute("data-theme", theme);
    try { localStorage.setItem("theme", theme); } catch (e) { /* storage disabled */ }
    document.dispatchEvent(new CustomEvent("themechange", { detail: theme }));
  }

  document.addEventListener("DOMContentLoaded", function () {
    var toggle = document.querySelector("[data-theme-toggle]");
    if (toggle) {
      toggle.addEventListener("click", function () {
        setTheme(root.getAttribute("data-theme") === "dark" ? "light" : "dark");
      });
    }

    if (window.matchMedia) {
      var mq = window.matchMedia("(prefers-color-scheme: dark)");
      var onChange = function (ev) {
        var stored = null;
        try { stored = localStorage.getItem("theme"); } catch (e) { /* ignore */ }
        if (!stored) {
          root.setAttribute("data-theme", ev.matches ? "dark" : "light");
          document.dispatchEvent(new CustomEvent("themechange"));
        }
      };
      if (mq.addEventListener) { mq.addEventListener("change", onChange); }
    }

    var navToggle = document.querySelector("[data-nav-toggle]");
    if (navToggle) {
      navToggle.addEventListener("click", function () {
        var nav = navToggle.closest(".nav");
        var open = nav.classList.toggle("open");
        navToggle.setAttribute("aria-expanded", open ? "true" : "false");
      });
    }

    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
      form.addEventListener("submit", function (ev) {
        if (!window.confirm(form.getAttribute("data-confirm"))) { ev.preventDefault(); }
      });
    });

    initWorkoutForm();
  });

  function initWorkoutForm() {
    var container = document.querySelector("[data-entries]");
    if (!container) { return; }
    var cardio = [];
    try { cardio = JSON.parse(container.getAttribute("data-cardio") || "[]"); } catch (e) { cardio = []; }

    function classify(row) {
      var select = row.querySelector("select");
      var id = parseInt(select.value, 10);
      row.classList.toggle("is-cardio", cardio.indexOf(id) !== -1);
      row.classList.toggle("is-strength", id > 0 && cardio.indexOf(id) === -1);
    }

    function renumber() {
      container.querySelectorAll(".entry-row").forEach(function (row, idx) {
        row.querySelectorAll("[name], [id], label[for]").forEach(function (el) {
          ["name", "id", "for"].forEach(function (attr) {
            var v = el.getAttribute(attr);
            if (v) { el.setAttribute(attr, v.replace(/entries-\d+-/, "entries-" + idx + "-")); }
          });
        });
      });
    }

    function bind(row) {
      row.querySelector("select").addEventListener("change", function () { classify(row); });
      var rm = row.querySelector("[data-remove-row]");
      if (rm) {
        rm.addEventListener("click", function () {
          var rows = container.querySelectorAll(".entry-row");
          if (rows.length > 1) { row.remove(); renumber(); }
          else { row.querySelectorAll("input").forEach(function (i) { i.value = ""; }); row.querySelector("select").value = "0"; classify(row); }
        });
      }
      classify(row);
    }

    container.querySelectorAll(".entry-row").forEach(bind);

    var add = document.querySelector("[data-add-row]");
    if (add) {
      add.addEventListener("click", function () {
        var rows = container.querySelectorAll(".entry-row");
        if (rows.length >= 30) { return; }
        var clone = rows[rows.length - 1].cloneNode(true);
        clone.querySelectorAll("input").forEach(function (i) { i.value = ""; });
        clone.querySelectorAll(".errors").forEach(function (e) { e.remove(); });
        clone.querySelectorAll(".has-error").forEach(function (e) { e.classList.remove("has-error"); });
        clone.querySelector("select").value = "0";
        container.appendChild(clone);
        renumber();
        bind(clone);
        clone.querySelector("select").focus();
      });
    }
  }
})();
