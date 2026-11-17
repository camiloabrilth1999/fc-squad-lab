import { installHook } from "./hook";

let rawMode = false;
try {
  window.addEventListener("message", (event) => {
    try {
      if (event.source !== window) return;
      const d = event.data as { source?: string; rawMode?: unknown } | null;
      if (d?.source === "fcsl-config") rawMode = d.rawMode === true;
    } catch {
      /* ignorar */
    }
  });
  installHook(window, () => rawMode);
} catch {
  /* nunca romper la web app */
}
