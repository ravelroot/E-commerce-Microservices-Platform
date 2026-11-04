(function () {
  var KEY = "argo:theme";
  var PALETTE_KEY = "argo:palette";
  var PALETTES = [
    { id: "argo", colors: ["#F6F7F7", "#C6CACC", "#1F5C4C", "#15181B"] },
    { id: "crivo", colors: ["#E6DDCE", "#A3B4BE", "#F6E4A6", "#5D1C16"] },
    { id: "bento", colors: ["#F5F4F4", "#BAB7B6", "#4D4B4B", "#000000"] },
    { id: "sonda", colors: ["#F3F1EC", "#7FA7B8", "#17212B", "#A8235A"] },
    { id: "nexo", colors: ["#E8E8E8", "#D9D1CE", "#AB9D9D", "#000000"] },
  ];
  var media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  var listeners = [];

  function read() {
    try {
      var value = localStorage.getItem(KEY);
      return value === "dark" || value === "system" ? value : "light";
    } catch (e) {
      return "light";
    }
  }

  function readPalette() {
    try {
      var value = localStorage.getItem(PALETTE_KEY);
      for (var i = 0; i < PALETTES.length; i++) if (PALETTES[i].id === value) return value;
    } catch (e) {}
    return PALETTES[0].id;
  }

  function resolved(choice) {
    if (choice === "system") return media && media.matches ? "dark" : "light";
    return choice;
  }

  function apply() {
    var choice = read();
    var theme = resolved(choice);
    var palette = readPalette();
    var root = document.documentElement;
    root.dataset.theme = theme;
    if (palette === PALETTES[0].id) delete root.dataset.palette;
    else root.dataset.palette = palette;
    var meta = document.querySelector('meta[name="theme-color"]');
    var paper = getComputedStyle(root).getPropertyValue("--paper").trim();
    if (meta) meta.setAttribute("content", paper || (theme === "dark" ? "#0f1113" : "#f6f7f7"));
    listeners.forEach(function (fn) {
      fn(choice, theme);
    });
  }

  window.argoTheme = {
    get: read,
    current: function () {
      return resolved(read());
    },
    set: function (choice) {
      try {
        localStorage.setItem(KEY, choice);
      } catch (e) {}
      apply();
    },
    toggle: function () {
      this.set(resolved(read()) === "dark" ? "light" : "dark");
    },
    palettes: PALETTES,
    palette: readPalette,
    setPalette: function (id) {
      try {
        localStorage.setItem(PALETTE_KEY, id);
      } catch (e) {}
      apply();
    },
    nextPalette: function () {
      var current = readPalette();
      var index = 0;
      for (var i = 0; i < PALETTES.length; i++) if (PALETTES[i].id === current) index = i;
      this.setPalette(PALETTES[(index + 1) % PALETTES.length].id);
    },
    onChange: function (fn) {
      listeners.push(fn);
    },
  };

  if (media && media.addEventListener) media.addEventListener("change", apply);
  apply();
})();
