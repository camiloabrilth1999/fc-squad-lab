import { classifyUrl, isFutUrl, sanitizeUrl, toClubImport, toEvolutionsImport, toMarketObservations } from "./parse";
import {
  DEFAULT_CONFIG,
  EMPTY_STATS,
  type Config,
  type EaItem,
  type EvolutionsImport,
  type Location,
  type MarketObservation,
  type PageMessage,
  type Stats,
  type StatusMessage,
} from "./types";

export const BATCH_MS = 2000;
export const CHUNK = 500;
const MAX_RAW_BYTES = 2 * 1024 * 1024;

interface ClubQueue {
  items: EaItem[];
  dups: Set<number>;
  /** Ids de la última lista completa vista de esta ubicación (para borrar lo que ya no está). */
  keep: number[] | null;
}
const newQueue = (): ClubQueue => ({ items: [], dups: new Set<number>(), keep: null });
let club = new Map<Location, ClubQueue>();
let market: MarketObservation[] = [];
// Evoluciones: cada lectura trae todo, así que solo importa la última.
let evolutions: EvolutionsImport | null = null;
let raw: { url: string; body: unknown }[] = [];
let timer: ReturnType<typeof setTimeout> | null = null;
let flushing: Promise<void> = Promise.resolve();

export function _reset(): void {
  club = new Map();
  market = [];
  evolutions = null;
  raw = [];
  if (timer) clearTimeout(timer);
  timer = null;
  flushing = Promise.resolve();
}

const chunks = <T>(arr: T[]): T[][] => {
  const out: T[][] = [];
  for (let i = 0; i < arr.length; i += CHUNK) out.push(arr.slice(i, i + CHUNK));
  return out;
};

async function getConfig(): Promise<Config> {
  const { config } = await chrome.storage.local.get("config");
  return { ...DEFAULT_CONFIG, ...(config as Partial<Config> | undefined) };
}

async function updateStats(fn: (s: Stats) => void): Promise<void> {
  const { stats } = await chrome.storage.local.get("stats");
  const s: Stats = { ...EMPTY_STATS, ...(stats as Partial<Stats> | undefined) };
  fn(s);
  await chrome.storage.local.set({ stats: s });
}

export function handleMessage(msg: PageMessage): void {
  try {
    if (!msg || msg.source !== "fcsl" || typeof msg.url !== "string") return;
    const kind = classifyUrl(msg.url);
    if (kind === "market") {
      market.push(...toMarketObservations(msg.body, new Date()));
    } else if (kind === "academy") {
      evolutions = toEvolutionsImport(msg.body) ?? evolutions;
    } else if (kind) {
      const parsed = toClubImport(msg.url, msg.body);
      if (parsed) {
        const q = club.get(parsed.location) ?? newQueue();
        q.items.push(...parsed.items);
        parsed.duplicate_item_ids.forEach((d) => q.dups.add(d));
        if (parsed.complete) q.keep = parsed.items.map((i) => i.id);
        club.set(parsed.location, q);
      }
    }
    // El modo muestras se decide al enviar (flush), leyendo la config actual.
    if (isFutUrl(msg.url)) raw.push({ url: sanitizeUrl(msg.url), body: msg.body });
    schedule();
  } catch {
    // nunca romper por un mensaje raro
  }
}

function schedule(): void {
  if (timer) return;
  timer = setTimeout(() => {
    timer = null;
    void flush();
  }, BATCH_MS);
}

export function flush(): Promise<void> {
  flushing = flushing.then(doFlush, doFlush);
  return flushing;
}

async function doFlush(): Promise<void> {
  const pendingClub = club;
  const pendingMarket = market;
  const pendingEvolutions = evolutions;
  const pendingRaw = raw;
  club = new Map();
  market = [];
  evolutions = null;
  raw = [];
  if (!pendingClub.size && !pendingMarket.length && !pendingEvolutions && !pendingRaw.length) return;
  const config = await getConfig();
  const jobs: { path: string; body: unknown; items: number; obs: number; raw: number }[] = [];
  for (const [location, q] of pendingClub) {
    for (const part of chunks(q.items)) {
      const ids = new Set(part.map((i) => i.id));
      jobs.push({
        path: "/import/club",
        body: { location, items: part, duplicate_item_ids: [...q.dups].filter((d) => ids.has(d)) },
        items: part.length,
        obs: 0,
        raw: 0,
      });
    }
    if (q.keep) {
      jobs.push({
        path: "/import/club",
        body: { location, items: [], duplicate_item_ids: [], keep_item_ids: q.keep },
        items: 0,
        obs: 0,
        raw: 0,
      });
    }
  }
  for (const part of chunks(pendingMarket)) {
    jobs.push({ path: "/import/market", body: { observations: part }, items: 0, obs: part.length, raw: 0 });
  }
  if (pendingEvolutions) {
    jobs.push({
      path: "/import/evolutions",
      body: pendingEvolutions,
      items: pendingEvolutions.slots.length,
      obs: 0,
      raw: 0,
    });
  }
  if (config.rawMode) {
    for (const r of pendingRaw) {
      if (JSON.stringify(r).length > MAX_RAW_BYTES) continue;
      jobs.push({ path: "/import/raw", body: r, items: 0, obs: 0, raw: 1 });
    }
  }
  if (!jobs.length) return;
  if (!config.token) {
    await updateStats((s) => {
      s.errors += 1;
      s.lastError = "Falta configurar el token en las opciones de la extensión";
    });
    return;
  }
  const base = config.apiUrl.replace(/\/+$/, "");
  for (const job of jobs) {
    try {
      const res = await fetch(`${base}${job.path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-FCSL-Token": config.token },
        body: JSON.stringify(job.body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status} en ${job.path}`);
      await updateStats((s) => {
        s.lastSentAt = new Date().toISOString();
        s.totalItems += job.items;
        s.totalObservations += job.obs;
        s.totalRaw += job.raw;
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      await updateStats((s) => {
        s.errors += 1;
        s.lastError = msg;
      });
    }
  }
}

/** Resultado de la importación automática (page-hook → content → aquí). */
export async function handleStatus(msg: StatusMessage): Promise<void> {
  try {
    if (!msg || msg.source !== "fcsl-status" || msg.kind !== "auto-import") return;
    const at = typeof msg.at === "string" ? msg.at : new Date().toISOString();
    const summary = msg.ok
      ? `${at} · OK · ${msg.clubPages} páginas de club${msg.storage ? " + Almacén SBC" : ""}`
      : `${at} · ERROR · ${msg.error ?? "desconocido"}`;
    await updateStats((s) => {
      s.lastAutoImport = summary;
      if (!msg.ok) {
        s.errors += 1;
        s.lastError = msg.error ?? "Importación automática fallida";
      }
    });
    // Club leído entero: tras enviar sus páginas, borrar del club lo que ya no está.
    const ids = Array.isArray(msg.clubItemIds) ? msg.clubItemIds.filter((n) => Number.isFinite(n)) : [];
    if (msg.ok && ids.length > 0) {
      const q = club.get("club") ?? newQueue();
      q.keep = ids;
      club.set("club", q);
      await flush();
    }
  } catch {
    // nunca romper por un mensaje raro
  }
}

if (typeof chrome !== "undefined" && chrome.runtime?.onMessage) {
  chrome.runtime.onMessage.addListener((msg: PageMessage | StatusMessage) => {
    if (msg?.source === "fcsl-status") void handleStatus(msg);
    else handleMessage(msg as PageMessage);
  });
}
