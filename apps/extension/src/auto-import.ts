/**
 * Importación automática (como EasySBC): con la sesión ya iniciada, pide a la propia web app de EA
 * que lea el club y el Almacén SBC usando sus servicios internos. Las respuestas las captura el hook
 * pasivo (`hook.ts`) y siguen el camino normal hacia el API.
 *
 * Límites: solo lecturas (Club.search, Item.searchStorageItems), ≥ 1 s entre peticiones, tope de
 * páginas y parada ante el primer error. Nunca mercado, pujas, movimientos ni ventas.
 */

export interface ServiceResult {
  success: boolean;
  status?: number;
  response?: { retrievedAll?: boolean; items?: unknown[] };
}

interface Observer {
  unobserve?(owner: object): void;
}

export interface FutObservable {
  observe(owner: object, cb: (obs: Observer, result: ServiceResult) => void): void;
}

export interface FutServices {
  Club?: { search?: (criteria: unknown) => FutObservable };
  Item?: { searchStorageItems?: (criteria: unknown) => FutObservable };
}

export type CriteriaClass = new () => object;

export interface AutoImportResult {
  ok: boolean;
  clubPages: number;
  storage: boolean;
  error?: string;
  /** Ids de todo el club; solo si se leyó completo (retrievedAll). */
  clubItemIds?: number[];
}

export const PAGE_SIZE = 90;
export const MAX_PAGES = 50;
export const DELAY_MS = 1000;

/**
 * Nombres de los sobres (id → nombre) que la propia web app ya trae en su tabla de traducciones
 * (`FUT_STORE_PACK_<id>_NAME`). Solo lee memoria local: no hace ninguna petición a EA.
 */
export function readPackNames(services: unknown): Record<string, string> {
  try {
    const dict = (services as { Localization?: { repository?: { _collection?: unknown } } } | null)
      ?.Localization?.repository?._collection;
    if (!dict || typeof dict !== "object") return {};
    const out: Record<string, string> = {};
    for (const [key, value] of Object.entries(dict as Record<string, unknown>)) {
      const m = /^FUT_STORE_PACK_(\d+)_NAME$/.exec(key);
      if (m && typeof value === "string" && value.trim()) out[m[1]] = value.trim();
    }
    return out;
  } catch {
    return {};
  }
}

/** Busca en `window` la clase de criterio de búsqueda de la web app (la reconoce por sus métodos). */
export function findCriteriaClass(win: Window): CriteriaClass | null {
  for (const name of Object.getOwnPropertyNames(win)) {
    try {
      const v = (win as unknown as Record<string, unknown>)[name];
      const proto = typeof v === "function" ? (v as { prototype?: unknown }).prototype : null;
      if (
        proto &&
        typeof (proto as Record<string, unknown>).hasValidDefId === "function" &&
        typeof (proto as Record<string, unknown>).resetDefId === "function"
      ) {
        return v as CriteriaClass;
      }
    } catch {
      /* propiedades con getter que lanzan */
    }
  }
  return null;
}

function call(obs: FutObservable): Promise<ServiceResult> {
  return new Promise((resolve) => {
    const owner = {};
    obs.observe(owner, (o, result) => {
      try {
        o?.unobserve?.(owner);
      } catch {
        /* ignorar */
      }
      resolve(result ?? { success: false });
    });
  });
}

function criteria(Criteria: CriteriaClass, offset: number, count: number): Record<string, unknown> {
  const c = new Criteria() as Record<string, unknown>;
  c.type = "player";
  c.sort = "desc";
  c.sortBy = "ovr";
  c.count = count;
  c.offset = offset;
  c.preferredPositionOnly = false;
  c.ovrMin = 45;
  c.ovrMax = 99;
  try {
    Object.defineProperty(c, "cacheable", { value: false });
  } catch {
    /* ignorar */
  }
  return c;
}

export async function runAutoImport(opts: {
  services: FutServices;
  Criteria: CriteriaClass;
  sleep: (ms: number) => Promise<void>;
  maxPages?: number;
  delayMs?: number;
}): Promise<AutoImportResult> {
  const { services, Criteria, sleep } = opts;
  const maxPages = opts.maxPages ?? MAX_PAGES;
  const delayMs = Math.max(opts.delayMs ?? DELAY_MS, DELAY_MS);
  const search = services.Club?.search;
  if (typeof search !== "function")
    return { ok: false, clubPages: 0, storage: false, error: "La web app de EA no expone services.Club.search" };

  let clubPages = 0;
  let complete = false;
  const ids = new Set<number>();
  for (let page = 0; page < maxPages; page++) {
    const r = await call(search.call(services.Club, criteria(Criteria, page * PAGE_SIZE, PAGE_SIZE)));
    if (!r.success)
      return { ok: false, clubPages, storage: false, error: `EA respondió ${String(r.status)} al leer el club` };
    clubPages++;
    for (const it of r.response?.items ?? []) {
      const id = (it as { id?: unknown } | null)?.id;
      if (typeof id === "number" && Number.isFinite(id)) ids.add(id);
    }
    await sleep(delayMs);
    if (r.response?.retrievedAll) {
      complete = true;
      break;
    }
  }
  // Solo con el club entero (y algún id) se puede limpiar lo que ya no está.
  const club = complete && ids.size > 0 ? { clubItemIds: [...ids] } : {};

  const storageSearch = services.Item?.searchStorageItems;
  if (typeof storageSearch !== "function") return { ok: true, clubPages, storage: false, ...club };
  const s = await call(storageSearch.call(services.Item, criteria(Criteria, 0, 1000)));
  await sleep(delayMs);
  if (!s.success)
    return {
      ok: false,
      clubPages,
      storage: false,
      error: `EA respondió ${String(s.status)} al leer el Almacén SBC`,
    };
  return { ok: true, clubPages, storage: true, ...club };
}
