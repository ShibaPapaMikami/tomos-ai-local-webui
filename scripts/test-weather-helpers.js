const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");

function createStorage(seed = {}) {
  const data = new Map(Object.entries(seed));
  return {
    getItem: (key) => data.get(key) || null,
    setItem: (key, value) => data.set(key, String(value)),
    removeItem: (key) => data.delete(key),
  };
}

const context = { window: { localStorage: createStorage() }, console };
vm.createContext(context);
vm.runInContext(fs.readFileSync("web/weather.js", "utf8"), context, { filename: "web/weather.js" });

const {
  loadSavedWeatherLocation,
  normalizeWeatherLocation,
  saveWeatherLocation,
  weatherCoordinatesForRequest,
  weatherLocationFromText,
} = context.window.GEMMA_WEATHER;

assert.equal(weatherLocationFromText("今日の天気は？"), "");
assert.equal(weatherLocationFromText("新潟の天気は？"), "新潟");

assert.equal(normalizeWeatherLocation({ latitude: 91, longitude: 139 }), null);
assert.deepEqual(
  JSON.parse(JSON.stringify(normalizeWeatherLocation({ latitude: "35.1", longitude: "139.2", accuracy: "25", updatedAt: "now" }))),
  { latitude: 35.1, longitude: 139.2, accuracy: 25, updatedAt: "now" },
);

const storage = createStorage();
const saved = saveWeatherLocation({ latitude: 35.1, longitude: 139.2, accuracy: 25, updatedAt: "now" }, storage);
assert.equal(saved.latitude, 35.1);
assert.equal(loadSavedWeatherLocation(storage).longitude, 139.2);

assert.equal(
  weatherCoordinatesForRequest({
    text: "新潟の天気は？",
    savedLocation: saved,
  }),
  null,
);

assert.equal(
  weatherCoordinatesForRequest({
    text: "今日の天気は？",
    savedLocation: saved,
  }).latitude,
  35.1,
);

console.log("weather helper tests passed");
