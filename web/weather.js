(() => {
const WEATHER_LOCATION_KEY = "gemma4.weatherLocation";

function isWeatherRequest(text) {
  return /(天気|気温|降水|雨|晴れ|曇り|weather|temperature|forecast)/i.test(text);
}

function weatherLocationFromText(text) {
  const normalized = text.replace(/\s+/g, " ").trim();
  const explicit = normalized.match(/(.+?)(?:の|で|における)(?:今日|現在|今|明日|週間)?(?:の)?(?:天気|気温|降水|weather|forecast)/i);
  if (explicit) {
    const location = explicit[1]
      .replace(/^(今日|現在|今|明日|本日|いま)\s*/i, "")
      .replace(/^(今日の|現在の|今の|明日の)/, "")
      .trim();
    if (location && !/^(今日|現在|今|明日|本日|いま)$/.test(location)) return location;
  }
  const trailing = normalized.match(/(?:天気|気温|降水|weather|forecast).{0,8}(?: in | at | for )([A-Za-z\s.-]+)$/i);
  if (trailing?.[1]) return trailing[1].trim();
  return "";
}

function normalizeWeatherLocation(value) {
  if (!value || typeof value !== "object") return null;
  const latitude = Number(value.latitude);
  const longitude = Number(value.longitude);
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
  if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) return null;
  return {
    latitude,
    longitude,
    accuracy: Number.isFinite(Number(value.accuracy)) ? Number(value.accuracy) : null,
    updatedAt: String(value.updatedAt || ""),
  };
}

function loadSavedWeatherLocation(storage = window.localStorage) {
  try {
    return normalizeWeatherLocation(JSON.parse(storage.getItem(WEATHER_LOCATION_KEY) || "null"));
  } catch {
    return null;
  }
}

function saveWeatherLocation(location, storage = window.localStorage) {
  const normalized = normalizeWeatherLocation(location);
  if (!normalized) {
    storage.removeItem(WEATHER_LOCATION_KEY);
    return null;
  }
  storage.setItem(WEATHER_LOCATION_KEY, JSON.stringify(normalized));
  return normalized;
}

function weatherCoordinatesForRequest({ text, savedLocation }) {
  if (weatherLocationFromText(text)) return null;
  return normalizeWeatherLocation(savedLocation);
}

window.GEMMA_WEATHER = {
  isWeatherRequest,
  loadSavedWeatherLocation,
  normalizeWeatherLocation,
  saveWeatherLocation,
  weatherCoordinatesForRequest,
  weatherLocationFromText,
};
})();
