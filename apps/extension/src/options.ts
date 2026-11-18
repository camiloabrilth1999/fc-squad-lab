import { DEFAULT_CONFIG, EMPTY_STATS, type Config, type Stats } from "./types";

const $ = <T extends HTMLElement>(id: string): T => document.getElementById(id) as T;

function setStatus(text: string, error = false): void {
  const el = $("status");
  el.textContent = text;
  el.className = error ? "err" : "";
}

function readForm(): Config {
  return {
    apiUrl: $<HTMLInputElement>("apiUrl").value.trim().replace(/\/+$/, "") || DEFAULT_CONFIG.apiUrl,
    token: $<HTMLInputElement>("token").value.trim(),
    rawMode: $<HTMLInputElement>("rawMode").checked,
    autoImport: $<HTMLInputElement>("autoImport").checked,
  };
}

function renderStats(s: Stats): void {
  const rows: [string, string][] = [
    ["Última importación automática", s.lastAutoImport ?? "—"],
    ["Último envío", s.lastSentAt ?? "—"],
    ["Último error", s.lastError ?? "—"],
    ["Errores", String(s.errors)],
    ["Ítems enviados", String(s.totalItems)],
    ["Observaciones de mercado", String(s.totalObservations)],
    ["Muestras crudas", String(s.totalRaw)],
  ];
  const dl = $("stats");
  dl.replaceChildren();
  for (const [k, v] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = k;
    const dd = document.createElement("dd");
    dd.textContent = v;
    dl.append(dt, dd);
  }
}

/** Si la URL no es localhost, pide el permiso opcional para ese host (requiere gesto del usuario). */
async function ensureHostPermission(apiUrl: string): Promise<boolean> {
  const u = new URL(apiUrl);
  if (u.hostname === "localhost" || u.hostname === "127.0.0.1") return true;
  return chrome.permissions.request({ origins: [`${u.protocol}//${u.hostname}/*`] });
}

async function load(): Promise<void> {
  const { config, stats } = await chrome.storage.local.get(["config", "stats"]);
  const c: Config = { ...DEFAULT_CONFIG, ...(config as Partial<Config> | undefined) };
  $<HTMLInputElement>("apiUrl").value = c.apiUrl;
  $<HTMLInputElement>("token").value = c.token;
  $<HTMLInputElement>("rawMode").checked = c.rawMode;
  $<HTMLInputElement>("autoImport").checked = c.autoImport;
  renderStats({ ...EMPTY_STATS, ...(stats as Partial<Stats> | undefined) });
}

async function save(): Promise<Config | null> {
  const c = readForm();
  try {
    if (!(await ensureHostPermission(c.apiUrl))) {
      setStatus("Permiso denegado para esa URL del API", true);
      return null;
    }
  } catch {
    setStatus("URL del API inválida", true);
    return null;
  }
  await chrome.storage.local.set({ config: c });
  setStatus("Guardado");
  return c;
}

async function test(): Promise<void> {
  const c = await save();
  if (!c) return;
  try {
    const res = await fetch(`${c.apiUrl}/health`);
    setStatus(res.ok ? "Conexión correcta" : `El API respondió HTTP ${res.status}`, !res.ok);
  } catch (e) {
    setStatus(`No se pudo conectar: ${e instanceof Error ? e.message : String(e)}`, true);
  }
}

if (typeof document !== "undefined" && document.getElementById("save")) {
  void load();
  $("save").addEventListener("click", () => void save());
  $("test").addEventListener("click", () => void test());
  chrome.storage.onChanged.addListener((changes) => {
    if (changes.stats) renderStats({ ...EMPTY_STATS, ...(changes.stats.newValue as Partial<Stats> | undefined) });
  });
}
