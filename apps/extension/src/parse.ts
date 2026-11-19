import type {
  Endpoint,
  EaItem,
  EvolutionLevel,
  EvolutionSlot,
  EvolutionsImport,
  ImportClubBody,
  MarketObservation,
} from "./types";

const ENDPOINTS: Record<string, Endpoint> = {
  club: "club",
  storagepile: "storage",
  tradepile: "tradepile",
  watchlist: "watchlist",
  transfermarket: "market",
};
const ENDPOINT_RE = /\/ut\/game\/[^/]+\/(club|storagepile|tradepile|watchlist|transfermarket)\/?$/;

const ACADEMY_RE = /\/ut\/game\/[^/]+\/academy\/hub\/v2\/?$/;

const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);

function parseUrl(url: string): URL | null {
  try {
    return new URL(url, "https://www.ea.com");
  } catch {
    return null;
  }
}

export function isFutUrl(url: string): boolean {
  return parseUrl(url)?.pathname.includes("/ut/game/") ?? false;
}

export function classifyUrl(url: string): Endpoint | null {
  const u = parseUrl(url);
  if (u && ACADEMY_RE.test(u.pathname)) return "academy";
  const m = u ? ENDPOINT_RE.exec(u.pathname) : null;
  return m ? ENDPOINTS[m[1]] : null;
}

/** Quita query y fragmento (pueden llevar tokens) y deja `?…` si había query. */
export function sanitizeUrl(url: string): string {
  const u = parseUrl(url);
  if (!u) return url.split(/[?#]/)[0];
  const base = /^[a-z]+:\/\//i.test(url) ? u.origin : "";
  return `${base}${u.pathname}${u.search ? "?…" : ""}`;
}

const num = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

function pickItem(raw: unknown): EaItem | null {
  if (!isRecord(raw)) return null;
  if (typeof raw.itemType === "string" && raw.itemType.toLowerCase() !== "player") return null;
  if (!num(raw.id) || !num(raw.resourceId) || !num(raw.assetId) || !num(raw.rating)) return null;
  const opt = (k: string): number | null | undefined => {
    const v = raw[k];
    return num(v) ? v : v === null ? null : undefined;
  };
  return {
    id: raw.id,
    resourceId: raw.resourceId,
    assetId: raw.assetId,
    rating: raw.rating,
    untradeable: raw.untradeable === true,
    lastSalePrice: opt("lastSalePrice"),
    marketDataMinPrice: opt("marketDataMinPrice"),
    marketDataMaxPrice: opt("marketDataMaxPrice"),
    owners: opt("owners"),
    loans: opt("loans"),
    itemType: typeof raw.itemType === "string" ? raw.itemType : undefined,
  };
}

/**
 * Una subasta cerrada ya no es tuya si la vendiste (`tradeOwner`) o si no ganaste la puja
 * (`bidState` distinto de "highest"). Activas, caducadas o sin estado siguen siendo tuyas.
 */
function stillOwned(a: Record<string, unknown>): boolean {
  if (a.tradeState !== "closed") return true;
  return a.tradeOwner !== true && a.bidState === "highest";
}

export function toClubImport(url: string, body: unknown): ImportClubBody | null {
  const endpoint = classifyUrl(url);
  if (!endpoint || endpoint === "market" || endpoint === "academy" || !isRecord(body)) return null;
  let rawItems: unknown[] | null = null;
  if (Array.isArray(body.itemData)) rawItems = body.itemData;
  else if (Array.isArray(body.auctionInfo))
    rawItems = body.auctionInfo.map((a) => (isRecord(a) && stillOwned(a) ? a.itemData : null));
  if (!rawItems) return null;
  const items = rawItems.map(pickItem).filter((i): i is EaItem => i !== null);
  // Almacén, lista de transferencias y seguimiento llegan siempre enteros; el club va paginado.
  const complete = COMPLETE_LOCATIONS.has(endpoint);
  if (items.length === 0 && !complete) return null;
  const dups = Array.isArray(body.duplicateItemIdList) ? body.duplicateItemIdList : [];
  const duplicate_item_ids = dups
    .map((d) => (isRecord(d) ? d.itemId : null))
    .filter((v): v is number => num(v));
  return { location: endpoint, items, duplicate_item_ids, complete };
}

const COMPLETE_LOCATIONS: ReadonlySet<Endpoint> = new Set(["storage", "tradepile", "watchlist"]);

export function toMarketObservations(body: unknown, now: Date): MarketObservation[] {
  if (!isRecord(body) || !Array.isArray(body.auctionInfo)) return [];
  const seenAt = now.toISOString();
  const out: MarketObservation[] = [];
  for (const a of body.auctionInfo) {
    if (!isRecord(a) || !isRecord(a.itemData)) continue;
    const { buyNowPrice } = a;
    const { resourceId } = a.itemData;
    if (num(buyNowPrice) && buyNowPrice > 0 && num(resourceId)) {
      out.push({ resourceId, buyNowPrice, seenAt });
    }
  }
  return out;
}


const str = (v: unknown): string | null => (typeof v === "string" ? v : null);
const numOrNull = (v: unknown): number | null => (num(v) ? v : null);

function toLevel(raw: unknown): EvolutionLevel | null {
  if (!isRecord(raw) || !num(raw.level)) return null;
  const objectives = Array.isArray(raw.objectives) ? raw.objectives : [];
  const awards = Array.isArray(raw.awards) ? raw.awards : [];
  return {
    level: raw.level,
    state: str(raw.levelState),
    objectives: objectives.filter(isRecord).map((o) => ({
      id: numOrNull(o.objectiveId),
      name: str(o.name) ?? "",
      description: str(o.description),
    })),
    awards: awards
      .filter((a): a is Record<string, unknown> => isRecord(a) && num(a.value) && num(a.count))
      .map((a) => ({ stat: a.value as number, count: a.count as number, max_value: numOrNull(a.maxValue) })),
  };
}

function toSlot(raw: unknown): EvolutionSlot | null {
  if (!isRecord(raw) || !num(raw.id)) return null;
  const arr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
  const preview = isRecord(raw.randomPlayerPreview) ? raw.randomPlayerPreview : {};
  const perLevel = isRecord(preview.academyBonusesPerLevel) ? preview.academyBonusesPerLevel : {};
  const bonuses: EvolutionSlot["bonuses"] = {};
  for (const [level, list] of Object.entries(perLevel)) {
    bonuses[level] = arr(list)
      .filter((b): b is Record<string, unknown> => isRecord(b) && num(b.id) && num(b.totalBonus))
      .map((b) => ({ stat: b.id as number, total: b.totalBonus as number, initial: numOrNull(b.initialAttributeValue) }));
  }
  return {
    id: raw.id,
    content_id: numOrNull(raw.contentId),
    name: str(raw.slotName),
    description: str(raw.slotDescription),
    status: str(raw.status),
    timed: raw.timed === true,
    end_time: numOrNull(raw.endTime),
    category_id: numOrNull(raw.categoryId),
    gk_only: raw.isGkExclusive === true,
    outfield_only: raw.isOutfieldExclusive === true,
    multi_choice: raw.isMultiChoice === true,
    reset_count: num(raw.resetCount) ? raw.resetCount : 0,
    total_rewards: numOrNull(raw.totalRewardsCount),
    currencies: arr(raw.currencies),
    top_rewards: arr(raw.academyTopRewards)
      .filter((r): r is Record<string, unknown> => isRecord(r) && num(r.value) && num(r.count))
      .map((r) => ({ stat: r.value as number, count: r.count as number, max_value: numOrNull(r.maxValue) })),
    requirements: arr(raw.elgReqs)
      .filter((r): r is Record<string, unknown> => isRecord(r) && num(r.eligibilityKey))
      .map((r) => ({
        type: str(r.type) ?? "",
        key: r.eligibilityKey as number,
        slot: num(r.eligibilitySlot) ? r.eligibilitySlot : 0,
        value: num(r.eligibilityValue) ? r.eligibilityValue : 0,
      })),
    levels: arr(raw.levels).map(toLevel).filter((l): l is EvolutionLevel => l !== null),
    bonuses,
  };
}

/** Respuesta de `academy/hub/v2` → evoluciones reducidas (sin el jugador de muestra). */
export function toEvolutionsImport(body: unknown): EvolutionsImport | null {
  if (!isRecord(body) || !Array.isArray(body.slots)) return null;
  const categories = (Array.isArray(body.categories) ? body.categories : [])
    .filter((c): c is Record<string, unknown> => isRecord(c) && num(c.id))
    .map((c) => ({
      id: c.id as number,
      name: str(c.description) ?? "",
      slot_ids: (Array.isArray(c.slotIds) ? c.slotIds : []).filter(num) as number[],
    }));
  const slots = body.slots.map(toSlot).filter((s): s is EvolutionSlot => s !== null);
  return { categories, slots };
}
