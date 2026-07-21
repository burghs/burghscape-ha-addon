(function () {
  "use strict";
  var KEY = "mybeacon-theme";
  var VALID = ["dark", "light", "system"];
  var media = null;
  var mediaHandler = null;

  function valid(value) { return VALID.indexOf(value) !== -1; }
  function read() {
    try {
      var value = window.localStorage.getItem(KEY);
      return valid(value) ? value : "system";
    } catch (_) { return "system"; }
  }
  function systemTheme() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function resolve(preference) { return preference === "system" ? systemTheme() : preference; }
  function apply(preference) {
    var safe = valid(preference) ? preference : "system";
    var resolved = resolve(safe);
    var root = document.documentElement;
    root.dataset.theme = resolved;
    root.dataset.themePreference = safe;
    root.style.colorScheme = resolved;
    window.dispatchEvent(new CustomEvent("mybeacon-theme-change", { detail: { preference: safe, theme: resolved } }));
    return resolved;
  }
  function detachSystemListener() {
    if (media && mediaHandler) {
      if (media.removeEventListener) media.removeEventListener("change", mediaHandler);
      else if (media.removeListener) media.removeListener(mediaHandler);
    }
    media = null;
    mediaHandler = null;
  }
  function attachSystemListener() {
    detachSystemListener();
    if (!window.matchMedia) return;
    media = window.matchMedia("(prefers-color-scheme: dark)");
    mediaHandler = function () {
      if (read() === "system") apply("system");
    };
    if (media.addEventListener) media.addEventListener("change", mediaHandler);
    else if (media.addListener) media.addListener(mediaHandler);
  }
  function start() {
    var preference = read();
    apply(preference);
    if (preference === "system") attachSystemListener();
    else detachSystemListener();
    return preference;
  }
  function setPreference(preference) {
    var safe = valid(preference) ? preference : "system";
    try { window.localStorage.setItem(KEY, safe); } catch (_) {}
    apply(safe);
    if (safe === "system") attachSystemListener();
    else detachSystemListener();
    return safe;
  }
  function stop() { detachSystemListener(); }
  function clear() {
    stop();
    var root = document.documentElement;
    delete root.dataset.theme;
    delete root.dataset.themePreference;
    root.style.colorScheme = "";
  }
  window.MyBeaconTheme = {
    key: KEY,
    values: VALID.slice(),
    isValid: valid,
    getPreference: read,
    resolve: resolve,
    apply: apply,
    start: start,
    setPreference: setPreference,
    stop: stop,
    clear: clear
  };
  if (document.documentElement.hasAttribute("data-theme-enabled")) start();
})();
