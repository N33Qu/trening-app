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
      document.addEventListener("keydown", function (ev) {
        var nav = navToggle.closest(".nav");
        if (ev.key === "Escape" && nav.classList.contains("open")) {
          nav.classList.remove("open");
          navToggle.setAttribute("aria-expanded", "false");
          navToggle.focus();
        }
      });
    }

    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
      form.addEventListener("submit", function (ev) {
        if (!window.confirm(form.getAttribute("data-confirm"))) { ev.preventDefault(); }
      });
    });

    document.querySelectorAll("select[data-autosubmit]").forEach(function (select) {
      select.addEventListener("change", function () { select.form.submit(); });
    });

    document.querySelectorAll("select[data-exercise-picker]").forEach(enhancePicker);
    initWorkoutForm();
  });

  // Searchable exercise picker (combobox). Progressive enhancement: the native
  // <select> stays in the form and receives the chosen value; without JS it is used directly.
  var pickerData = null;
  var pickerQueue = [];
  var pickerSeq = 0;
  var LIMIT = 60;

  function fold(text) {
    return (text || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/ł/g, "l");
  }

  function pickerText() {
    try { return JSON.parse(document.body.getAttribute("data-picker-i18n") || "{}"); } catch (e) { return {}; }
  }

  function loadPickerData(cb) {
    if (pickerData) { cb(pickerData); return; }
    pickerQueue.push(cb);
    if (pickerQueue.length > 1) { return; }
    var url = document.body.getAttribute("data-picker-url");
    if (!url || !window.fetch) { return; }
    fetch(url, { credentials: "same-origin", headers: { "Accept": "application/json" } })
      .then(function (r) { if (!r.ok) { throw new Error(r.status); } return r.json(); })
      .then(function (items) {
        items.forEach(function (it) { it.fname = fold(it.name); it.key = it.fname + " " + fold(it.alt || ""); });
        pickerData = items;
        pickerQueue.splice(0).forEach(function (fn) { fn(items); });
      })
      .catch(function () { pickerQueue = []; });
  }

  function enhancePicker(select) {
    if (!select || select.getAttribute("data-picker-ready") || !document.body.getAttribute("data-picker-url")) { return; }
    loadPickerData(function (items) { buildPicker(select, items); });
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) { n.className = cls; }
    if (text) { n.textContent = text; }
    return n;
  }

  function buildPicker(select, items) {
    if (select.getAttribute("data-picker-ready")) { return; }
    select.setAttribute("data-picker-ready", "1");
    var t = pickerText();
    var allowed = {};
    Array.prototype.forEach.call(select.options, function (o) { allowed[o.value] = o.text; });
    var list = items.filter(function (it) { return allowed[String(it.id)] !== undefined; });
    var groups = [];
    list.forEach(function (it) { if (groups.indexOf(it.group) === -1) { groups.push(it.group); } });

    var uid = "picker-" + (++pickerSeq);
    var wrap = el("div", "picker");
    var input = el("input", "picker-input");
    input.type = "text";
    input.id = (select.id || uid) + "-search";
    input.autocomplete = "off";
    input.spellcheck = false;
    input.placeholder = t.placeholder || "";
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-controls", uid + "-list");
    var pop = el("div", "picker-pop");
    pop.hidden = true;
    var chips = el("div", "picker-chips");
    var listbox = el("ul", "picker-list");
    listbox.id = uid + "-list";
    listbox.setAttribute("role", "listbox");
    var note = el("p", "picker-note");
    pop.appendChild(chips); pop.appendChild(listbox); pop.appendChild(note);
    wrap.appendChild(input); wrap.appendChild(pop);
    select.parentNode.insertBefore(wrap, select);
    select.classList.add("picker-native");
    select.setAttribute("tabindex", "-1");
    select.setAttribute("aria-hidden", "true");
    var label = select.id ? document.querySelector('label[for="' + select.id + '"]') : null;
    if (label) { label.setAttribute("for", input.id); input.setAttribute("aria-labelledby", label.id || ""); if (!label.id) { input.removeAttribute("aria-labelledby"); } }

    var group = null;
    var shown = [];
    var active = -1;

    function chip(name, value) {
      var b = el("button", "picker-chip", name);
      b.type = "button";
      b.setAttribute("aria-pressed", value === group ? "true" : "false");
      b.addEventListener("mousedown", function (ev) { ev.preventDefault(); });
      b.addEventListener("click", function () { group = value; renderChips(); render(); input.focus(); });
      return b;
    }
    function renderChips() {
      chips.textContent = "";
      chips.appendChild(chip(t.all || "*", null));
      groups.forEach(function (g) { chips.appendChild(chip(g, g)); });
    }
    function currentName() {
      var o = select.options[select.selectedIndex];
      return o && o.value !== "0" ? o.text : "";
    }
    function render() {
      var words = fold(input.value === currentName() ? "" : input.value).trim().split(/\s+/).filter(Boolean);
      var matches = list.filter(function (it) {
        return (!group || it.group === group) && words.every(function (w) { return it.key.indexOf(w) !== -1; });
      });
      if (words.length) {
        var rank = function (it) {
          var n = it.fname;
          if (n.indexOf(words[0]) === 0) { return 0; }
          return words.every(function (w) { return n.indexOf(w) !== -1; }) ? 1 : 2;
        };
        matches = matches.map(function (it, i) { return [rank(it), i, it]; })
          .sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; })
          .map(function (x) { return x[2]; });
      }
      shown = matches.slice(0, LIMIT);
      listbox.textContent = "";
      shown.forEach(function (it, idx) {
        var li = el("li", "picker-option");
        li.id = uid + "-opt-" + idx;
        li.setAttribute("role", "option");
        li.setAttribute("aria-selected", String(it.id) === select.value ? "true" : "false");
        var th = el("span", "picker-thumb");
        if (it.thumb) { var img = el("img"); img.src = it.thumb; img.alt = ""; img.loading = "lazy"; img.decoding = "async"; th.appendChild(img); }
        li.appendChild(th);
        var txt = el("span", "picker-text");
        txt.appendChild(el("span", "picker-name", it.name));
        txt.appendChild(el("span", "picker-group", it.own ? (t.mine || it.group) : it.group));
        li.appendChild(txt);
        li.addEventListener("mousedown", function (ev) { ev.preventDefault(); });
        li.addEventListener("click", function () { choose(it); });
        listbox.appendChild(li);
      });
      note.textContent = matches.length === 0 ? (t.none || "") : (matches.length > LIMIT ? (t.more || "") : "");
      note.hidden = !note.textContent;
      setActive(shown.length ? 0 : -1);
    }
    function setActive(idx) {
      var opts = listbox.children;
      if (active >= 0 && opts[active]) { opts[active].classList.remove("is-active"); }
      active = idx;
      if (idx >= 0 && opts[idx]) {
        opts[idx].classList.add("is-active");
        input.setAttribute("aria-activedescendant", opts[idx].id);
        var o = opts[idx], top = o.offsetTop, bottom = top + o.offsetHeight;
        if (top < listbox.scrollTop) { listbox.scrollTop = top; }
        else if (bottom > listbox.scrollTop + listbox.clientHeight) { listbox.scrollTop = bottom - listbox.clientHeight; }
      } else { input.removeAttribute("aria-activedescendant"); }
    }
    function open() {
      if (!pop.hidden) { return; }
      pop.hidden = false;
      wrap.classList.add("is-open");
      input.setAttribute("aria-expanded", "true");
      renderChips();
      render();
    }
    function close(restore) {
      pop.hidden = true;
      wrap.classList.remove("is-open");
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      if (restore) { input.value = currentName(); }
    }
    function choose(it) {
      select.value = String(it.id);
      select.dispatchEvent(new Event("change", { bubbles: true }));
      input.value = it.name;
      close(false);
      input.focus();
    }

    input.value = currentName();
    input.addEventListener("focus", function () { input.select(); open(); });
    input.addEventListener("click", open);
    input.addEventListener("input", function () { open(); render(); });
    input.addEventListener("blur", function () { close(true); });
    input.addEventListener("keydown", function (ev) {
      if (ev.key === "ArrowDown") { ev.preventDefault(); if (pop.hidden) { open(); } else { setActive(Math.min(active + 1, shown.length - 1)); } }
      else if (ev.key === "ArrowUp") { ev.preventDefault(); setActive(Math.max(active - 1, 0)); }
      else if (ev.key === "Enter") { if (!pop.hidden && active >= 0 && shown[active]) { ev.preventDefault(); choose(shown[active]); } }
      else if (ev.key === "Escape") { if (!pop.hidden) { ev.preventDefault(); ev.stopPropagation(); close(true); } }
    });
    select.addEventListener("change", function () { if (document.activeElement !== input) { input.value = currentName(); } });
  }

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
      enhancePicker(row.querySelector("select"));
      row.querySelector("select").addEventListener("change", function () { classify(row); });
      var rm = row.querySelector("[data-remove-row]");
      if (rm) {
        rm.addEventListener("click", function () {
          var rows = container.querySelectorAll(".entry-row");
          if (rows.length > 1) { row.remove(); renumber(); }
          else { row.querySelectorAll("input").forEach(function (i) { i.value = ""; }); row.querySelector("select").value = "0"; row.querySelector("select").dispatchEvent(new Event("change")); }
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
        clone.querySelectorAll(".picker").forEach(function (e) { e.remove(); });
        clone.querySelectorAll("select").forEach(function (sel) { sel.removeAttribute("data-picker-ready"); sel.classList.remove("picker-native"); sel.removeAttribute("tabindex"); sel.removeAttribute("aria-hidden"); });
        clone.querySelectorAll("label[for$='-search']").forEach(function (l) { l.setAttribute("for", l.getAttribute("for").replace(/-search$/, "")); });
        clone.querySelector("select").value = "0";
        container.appendChild(clone);
        renumber();
        bind(clone);
        var target = clone.querySelector(".picker-input") || clone.querySelector("select");
        if (target) { target.focus(); }
      });
    }
  }
})();
