import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { classifyUrl, isFutUrl, sanitizeUrl, toClubImport, toMarketObservations } from "../parse";

const load = (name: string) =>
  JSON.parse(readFileSync(new URL(`../../../api/tests/data/${name}`, import.meta.url), "utf8"));
const club = load("ea_club.json");
const market = load("ea_transfermarket.json");
const BASE = "https://utas.mob.v5.prd.futc-ext.gcp.ea.com/ut/game/fc27";

describe("classifyUrl", () => {
  it("reconoce los endpoints listados, ignorando query", () => {
    expect(classifyUrl(`${BASE}/club?count=91&start=0`)).toBe("club");
    expect(classifyUrl(`${BASE}/storagepile`)).toBe("storage");
    expect(classifyUrl(`${BASE}/tradepile`)).toBe("tradepile");
    expect(classifyUrl(`${BASE}/watchlist`)).toBe("watchlist");
    expect(classifyUrl(`${BASE}/transfermarket?num=21&type=player`)).toBe("market");
  });
  it("ignora otros endpoints y URLs fuera de /ut/game/", () => {
    expect(classifyUrl(`${BASE}/club/stats/staff`)).toBeNull();
    expect(classifyUrl(`${BASE}/user/credits`)).toBeNull();
    expect(classifyUrl("https://www.ea.com/club")).toBeNull();
    expect(classifyUrl("no es una url")).toBeNull();
  });
});

describe("isFutUrl / sanitizeUrl", () => {
  it("isFutUrl exige /ut/game/", () => {
    expect(isFutUrl(`${BASE}/foo`)).toBe(true);
    expect(isFutUrl("https://www.ea.com/otra")).toBe(false);
  });
  it("sanitizeUrl quita la query y la reemplaza por ?…", () => {
    expect(sanitizeUrl(`${BASE}/club?sid=SECRET&x=1`)).toBe(`${BASE}/club?…`);
    expect(sanitizeUrl(`${BASE}/club`)).toBe(`${BASE}/club`);
    expect(sanitizeUrl(`${BASE}/club#frag`)).toBe(`${BASE}/club`);
  });
});

describe("toClubImport", () => {
  it("club: itemData + duplicados", () => {
    const r = toClubImport(`${BASE}/club?start=0`, club);
    expect(r?.location).toBe("club");
    expect(r?.items.map((i) => i.id)).toEqual([111000001, 111000002, 111000003]);
    expect(r?.duplicate_item_ids).toEqual([111000003]);
    expect(r?.items[0]).toMatchObject({ resourceId: 50000001, assetId: 1001, rating: 88, itemType: "player" });
  });
  it("storage, tradepile y watchlist (auctionInfo[].itemData)", () => {
    expect(toClubImport(`${BASE}/storagepile`, club)?.location).toBe("storage");
    const body = { auctionInfo: market.auctionInfo };
    const t = toClubImport(`${BASE}/tradepile`, body);
    expect(t?.location).toBe("tradepile");
    expect(t?.items).toHaveLength(3);
    expect(toClubImport(`${BASE}/watchlist`, body)?.location).toBe("watchlist");
  });
  it("ignora ítems que no son jugador", () => {
    const body = {
      itemData: [
        { id: 1, resourceId: 2, assetId: 3, rating: 80, itemType: "player" },
        { id: 4, resourceId: 5, assetId: 6, rating: 0, itemType: "stadium" },
      ],
    };
    expect(toClubImport(`${BASE}/club`, body)?.items.map((i) => i.id)).toEqual([1]);
  });
  it("ignora subastas cerradas que ya no son tuyas (vendidas o pujas perdidas)", () => {
    const item = (id: number) => ({ id, resourceId: id, assetId: id, rating: 80, itemType: "player" });
    const auction = (id: number, tradeState: string, tradeOwner: boolean, bidState = "none") => ({
      tradeId: id * 10,
      tradeState,
      tradeOwner,
      bidState,
      itemData: item(id),
    });
    const tradepile = {
      auctionInfo: [
        auction(1, "active", true),
        auction(2, "expired", true), // no vendida: sigue siendo tuya
        auction(3, "closed", true), // vendida
        auction(4, null as unknown as string, true), // sin estado (recién movida): se conserva
      ],
    };
    expect(toClubImport(`${BASE}/tradepile`, tradepile)?.items.map((i) => i.id)).toEqual([1, 2, 4]);
    const watchlist = {
      auctionInfo: [
        auction(5, "active", false, "outbid"),
        auction(6, "closed", false, "highest"), // ganada: es tuya
        auction(7, "closed", false, "outbid"), // perdida
        auction(8, "closed", false, "none"), // perdida
      ],
    };
    expect(toClubImport(`${BASE}/watchlist`, watchlist)?.items.map((i) => i.id)).toEqual([5, 6]);
    // Lista completa sin nada tuyo: se envía vacía para poder limpiar la ubicación.
    expect(toClubImport(`${BASE}/tradepile`, { auctionInfo: [auction(9, "closed", true)] })).toMatchObject({
      items: [],
      complete: true,
    });
  });
  it("marca como completas almacén, lista de transferencias y seguimiento, pero no el club", () => {
    expect(toClubImport(`${BASE}/storagepile`, { itemData: [] })).toEqual({
      location: "storage",
      items: [],
      duplicate_item_ids: [],
      complete: true,
    });
    expect(toClubImport(`${BASE}/watchlist`, { auctionInfo: [] })?.complete).toBe(true);
    expect(toClubImport(`${BASE}/club`, club)?.complete).toBe(false);
  });
  it("null con cuerpos raros o URL no soportada", () => {
    for (const b of [null, {}, "texto", 5, { itemData: "x" }, { itemData: [] }]) {
      expect(toClubImport(`${BASE}/club`, b)).toBeNull();
    }
    expect(toClubImport(`${BASE}/transfermarket`, market)).toBeNull();
    expect(toClubImport(`${BASE}/user/credits`, club)).toBeNull();
  });
});

describe("toMarketObservations", () => {
  const now = new Date("2026-11-17T10:00:00Z");
  it("toma resourceId de itemData y buyNowPrice", () => {
    expect(toMarketObservations(market, now)).toEqual([
      { resourceId: 50000001, buyNowPrice: 13500, seenAt: now.toISOString() },
      { resourceId: 50000001, buyNowPrice: 12000, seenAt: now.toISOString() },
      { resourceId: 50000002, buyNowPrice: 900, seenAt: now.toISOString() },
    ]);
  });
  it("filtra buyNowPrice 0 o ausente y cuerpos raros", () => {
    const body = {
      auctionInfo: [
        { buyNowPrice: 0, itemData: { resourceId: 1 } },
        { itemData: { resourceId: 2 } },
        { buyNowPrice: 500, itemData: { resourceId: 3 } },
        { buyNowPrice: 500 },
      ],
    };
    expect(toMarketObservations(body, now).map((o) => o.resourceId)).toEqual([3]);
    for (const b of [null, {}, "x", { auctionInfo: 3 }]) expect(toMarketObservations(b, now)).toEqual([]);
  });
});
