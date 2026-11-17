import { findCriteriaClass, runAutoImport, type AutoImportResult, type FutServices } from "./auto-import";
import { installHook } from "./hook";

/** Tras iniciar sesión, espera a que la web app se asiente antes de leer el club. */
const SETTLE_MS = 5000;
/** Espera máxima a que la web app exponga sus servicios. */
const READY_TIMEOUT_MS = 60_000;
/** No repetir la importación automática si se recarga la web app al poco. */
const COOLDOWN_MS = 15 * 60_000;
const COOLDOWN_KEY = "fcsl:autoImportAt";

let rawMode = false;
let autoImport = true;
let configSeen = false;
let loggedIn = false;
let started = false;

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

function report(result: AutoImportResult): void {
  try {
    window.postMessage({ source: "fcsl-status", kind: "auto-import", at: new Date().toISOString(), ...result }, "*");
  } catch {
    /* ignorar */
  }
}

function inCooldown(): boolean {
  try {
    const last = Number(sessionStorage.getItem(COOLDOWN_KEY));
    return Number.isFinite(last) && Date.now() - last < COOLDOWN_MS;
  } catch {
    return false;
  }
}

async function start(): Promise<void> {
  try {
    sessionStorage.setItem(COOLDOWN_KEY, String(Date.now()));
  } catch {
    /* ignorar */
  }
  await sleep(SETTLE_MS);
  const deadline = Date.now() + READY_TIMEOUT_MS;
  for (;;) {
    const services = (window as unknown as { services?: FutServices }).services;
    const Criteria = findCriteriaClass(window);
    if (services?.Club?.search && Criteria) {
      report(await runAutoImport({ services, Criteria, sleep }));
      return;
    }
    if (Date.now() > deadline) {
      report({ ok: false, clubPages: 0, storage: false, error: "La web app de EA no expuso sus servicios a tiempo" });
      return;
    }
    await sleep(2000);
  }
}

function maybeStart(): void {
  if (started || !configSeen || !autoImport || !loggedIn || inCooldown()) return;
  started = true;
  start().catch((e) =>
    report({ ok: false, clubPages: 0, storage: false, error: e instanceof Error ? e.message : String(e) }),
  );
}

try {
  window.addEventListener("message", (event) => {
    try {
      if (event.source !== window) return;
      const d = event.data as { source?: string; rawMode?: unknown; autoImport?: unknown } | null;
      if (d?.source !== "fcsl-config") return;
      rawMode = d.rawMode === true;
      autoImport = d.autoImport !== false;
      configSeen = true;
      maybeStart();
    } catch {
      /* ignorar */
    }
  });
  installHook(
    window,
    () => rawMode,
    (url) => {
      // usermassinfo llega justo después del login: señal de que hay sesión.
      if (!loggedIn && url.includes("/ut/game/") && url.includes("/usermassinfo")) {
        loggedIn = true;
        maybeStart();
      }
    },
  );
} catch {
  /* nunca romper la web app */
}
