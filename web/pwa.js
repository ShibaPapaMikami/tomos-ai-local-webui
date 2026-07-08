(() => {
  async function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    if (window.location.protocol !== "http:" && window.location.protocol !== "https:") return;
    try {
      await navigator.serviceWorker.register("/sw.js?v=0.8.207-tomos49");
    } catch (error) {
      console.warn("Service worker registration failed", error);
    }
  }

  window.addEventListener("load", registerServiceWorker);
})();
