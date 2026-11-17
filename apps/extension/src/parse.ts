import type { Endpoint, EaItem, ImportClubBody, MarketObservation } from "./types";

const ENDPOINTS: Record<string, Endpoint> = {
  club: "club",
  storagepile: "storage",
  tradepile: "tradepile",
  watchlist: "watchlist",
  transfermarket: "market",
};
const ENDPOINT_RE = /\/ut\/game\/[^/]+\/(club|storagepile|tradepile|watchlist|transfermarket)\/?$/;

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
  if (!endpoint || endpoint === "market" || !isRecord(body)) return null;
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
