import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync(new URL("../../backend/app/static/theme.js", import.meta.url), "utf8");

function createEnvironment({ stored, dark = false, enabled = false } = {}) {
  const values = new Map();
  if (stored !== undefined) values.set("mybeacon-theme", stored);
  const mediaListeners = new Set();
  const windowListeners = new Map();
  const root = {
    dataset: {},
    style: {},
    hasAttribute(name) { return enabled && name === "data-theme-enabled"; },
  };
  const media = {
    matches: dark,
    addEventListener(type, fn) { if (type === "change") mediaListeners.add(fn); },
    removeEventListener(type, fn) { if (type === "change") mediaListeners.delete(fn); },
    addListener(fn) { mediaListeners.add(fn); },
    removeListener(fn) { mediaListeners.delete(fn); },
  };
  const localStorage = {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, value); },
  };
  const windowObject = {
    localStorage,
    matchMedia() { return media; },
    dispatchEvent(event) { for (const fn of windowListeners.get(event.type) || []) fn(event); },
    addEventListener(type, fn) { if (!windowListeners.has(type)) windowListeners.set(type, new Set()); windowListeners.get(type).add(fn); },
    removeEventListener(type, fn) { windowListeners.get(type)?.delete(fn); },
  };
  class CustomEvent {
    constructor(type, options) { this.type = type; this.detail = options.detail; }
  }
  const context = { window: windowObject, document: { documentElement: root }, CustomEvent };
  vm.runInNewContext(source, context);
  return {
    api: windowObject.MyBeaconTheme,
    root,
    values,
    media,
    mediaListeners,
    setSystemDark(value) {
      media.matches = value;
      for (const listener of [...mediaListeners]) listener({ matches: value });
    },
  };
}

{
  const env = createEnvironment();
  assert.equal(env.api.getPreference(), "system");
  env.api.start();
  assert.equal(env.root.dataset.themePreference, "system");
  assert.equal(env.root.dataset.theme, "light");
}
{
  const env = createEnvironment({ stored: "dark" });
  env.api.start();
  assert.equal(env.root.dataset.theme, "dark");
}
{
  const env = createEnvironment({ stored: "light", dark: true });
  env.api.start();
  assert.equal(env.root.dataset.theme, "light");
}
{
  const env = createEnvironment({ stored: "system", dark: true });
  env.api.start();
  assert.equal(env.root.dataset.theme, "dark");
}
{
  const env = createEnvironment({ stored: "invalid", dark: true });
  assert.equal(env.api.getPreference(), "system");
  env.api.start();
  assert.equal(env.root.dataset.theme, "dark");
}
{
  const env = createEnvironment();
  env.api.setPreference("dark");
  assert.equal(env.root.dataset.theme, "dark");
  assert.equal(env.values.get("mybeacon-theme"), "dark");
  env.api.setPreference("light");
  assert.equal(env.root.dataset.theme, "light");
  assert.equal(env.values.get("mybeacon-theme"), "light");
}
{
  const env = createEnvironment({ stored: "system" });
  env.api.start();
  assert.equal(env.mediaListeners.size, 1);
  env.setSystemDark(true);
  assert.equal(env.root.dataset.theme, "dark");
  env.api.setPreference("light");
  assert.equal(env.mediaListeners.size, 0);
  env.setSystemDark(false);
  assert.equal(env.root.dataset.theme, "light");
}
{
  const env = createEnvironment({ stored: "dark", enabled: true });
  assert.equal(env.root.dataset.theme, "dark");
}
assert.equal(createEnvironment().api.key, "mybeacon-theme");
console.log("theme helper tests passed");
