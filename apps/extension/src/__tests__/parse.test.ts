import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { classifyUrl, isFutUrl, sanitizeUrl, toClubImport, toEvolutionsImport, toMarketObservations } from "../parse";

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
    expect(classifyUrl(`${BASE}/academy/hub/v2?offset=0&count=20`)).toBe("academy");
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


const HUB = {
  categories: [{ id: 0, description: "Evoluciones", count: 1, priority: 200, slotIds: [2695] }],
  slots: [
    {
      id: 2695,
      contentId: 23409,
      slotName: "Introducción a las Evoluciones",
      slotDescription: "Mejora a un futbolista",
      status: "NOT_STARTED",
      timed: false,
      endTime: 0,
      categoryId: 0,
      isGkExclusive: false,
      isOutfieldExclusive: true,
      isMultiChoice: false,
      resetCount: 0,
      totalRewardsCount: 18,
      currencies: [{ currency: "COINS", amount: 10000 }],
      academyTopRewards: [{ value: 11, count: 34, maxValue: 79, priority: 1 }],
      elgReqs: [{ type: "PLAYER_ATTRIBUTE", eligibilityKey: 1, eligibilitySlot: 1, eligibilityValue: 80 }],
      levels: [
        { level: 0, levelState: "NOT_STARTED", awards: [{ value: 11, count: 34, priority: 1 }] },
        {
          level: 1,
          levelState: "NOT_STARTED",
          objectives: [{ objectiveId: 7, name: "Juega 3 partidos", description: "*", multiplier: 1, priority: 1 }],
          awards: [{ value: 22, count: 40, maxValue: 80, priority: 1 }],
        },
      ],
      randomPlayerPreview: {
        itemData: { resourceId: 80327, rating: 75 },
        academyBonusesPerLevel: { "1": [{ id: 11, totalBonus: 79, initialAttributeValue: 75 }, { id: 22, totalBonus: 80 }] },
      },
    },
  ],
};

describe("toEvolutionsImport", () => {
  it("reduce la respuesta: sin jugador de muestra, con claves snake_case", () => {
    const out = toEvolutionsImport(HUB);
    expect(out).not.toBeNull();
    expect(out!.categories).toEqual([{ id: 0, name: "Evoluciones", slot_ids: [2695] }]);
    const s = out!.slots[0];
    expect(s).toMatchObject({
      id: 2695,
      name: "Introducción a las Evoluciones",
      description: "Mejora a un futbolista",
      status: "NOT_STARTED",
      timed: false,
      category_id: 0,
      outfield_only: true,
      gk_only: false,
      total_rewards: 18,
    });
    expect(s.top_rewards).toEqual([{ stat: 11, count: 34, max_value: 79 }]);
    expect(s.requirements).toEqual([{ type: "PLAYER_ATTRIBUTE", key: 1, slot: 1, value: 80 }]);
    expect(s.levels[1].objectives).toEqual([{ id: 7, name: "Juega 3 partidos", description: "*" }]);
    expect(s.levels[1].awards).toEqual([{ stat: 22, count: 40, max_value: 80 }]);
    expect(s.bonuses).toEqual({ "1": [{ stat: 11, total: 79, initial: 75 }, { stat: 22, total: 80, initial: null }] });
    expect(JSON.stringify(out)).not.toContain("80327"); // el jugador de muestra no sale
  });
  it("devuelve null si no es una respuesta de evoluciones", () => {
    expect(toEvolutionsImport(null)).toBeNull();
    expect(toEvolutionsImport({ itemData: [] })).toBeNull();
    expect(toEvolutionsImport({ slots: "no" })).toBeNull();
  });
  it("ignora slots sin id", () => {
    const out = toEvolutionsImport({ categories: [], slots: [{ slotName: "x" }, ...HUB.slots] });
    expect(out!.slots.map((s) => s.id)).toEqual([2695]);
  });
});
