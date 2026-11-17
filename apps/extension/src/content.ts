import type { PageMessage } from "./types";

const sendConfig = (rawMode: boolean): void => {
  try {
    window.postMessage({ source: "fcsl-config", rawMode }, "*");
  } catch {
    /* ignorar */
  }
};

try {
  window.addEventListener("message", (event) => {
    try {
      if (event.source !== window) return;
      const data = event.data as PageMessage | null;
      if (!data || data.source !== "fcsl") return;
      void chrome.runtime.sendMessage(data).catch(() => {});
    } catch {
      /* ignorar */
    }
  });
  const readRaw = (): void => {
    chrome.storage.local
      .get("config")
      .then(({ config }) => sendConfig((config as { rawMode?: boolean } | undefined)?.rawMode === true))
      .catch(() => {});
  };
  readRaw();
  window.addEventListener("DOMContentLoaded", readRaw);
  chrome.storage.onChanged.addListener((changes) => {
    if (changes.config) sendConfig((changes.config.newValue as { rawMode?: boolean } | undefined)?.rawMode === true);
  });
} catch {
  /* nunca romper la web app */
}
