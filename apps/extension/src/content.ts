import type { Config } from "./types";

const sendConfig = (config: Partial<Config> | undefined): void => {
  try {
    window.postMessage(
      { source: "fcsl-config", rawMode: config?.rawMode === true, autoImport: config?.autoImport !== false },
      "*",
    );
  } catch {
    /* ignorar */
  }
};

try {
  window.addEventListener("message", (event) => {
    try {
      if (event.source !== window) return;
      const data = event.data as { source?: unknown } | null;
      if (!data || (data.source !== "fcsl" && data.source !== "fcsl-status")) return;
      void chrome.runtime.sendMessage(data).catch(() => {});
    } catch {
      /* ignorar */
    }
  });
  const readConfig = (): void => {
    chrome.storage.local
      .get("config")
      .then(({ config }) => sendConfig(config as Partial<Config> | undefined))
      .catch(() => {});
  };
  readConfig();
  window.addEventListener("DOMContentLoaded", readConfig);
  chrome.storage.onChanged.addListener((changes) => {
    if (changes.config) sendConfig(changes.config.newValue as Partial<Config> | undefined);
  });
} catch {
  /* nunca romper la web app */
}
