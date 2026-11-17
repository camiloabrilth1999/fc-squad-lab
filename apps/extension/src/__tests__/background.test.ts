import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as bg from "../background";

const BASE = "https://utas.mob.v5.prd.futc-ext.gcp.ea.com/ut/game/fc27";
const item = (id: number) => ({ id, resourceId: id, assetId: id, rating: 80, itemType: "player" });

let store: Record<string, unknown>;
let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  store = { config: { apiUrl: "http://localhost:8787/", token: "tok", rawMode: false } };
  vi.stubGlobal("chrome", {
    storage: {
      local: {
        get: vi.fn(async (k: string) => ({ [k]: store[k] })),
        set: vi.fn(async (o: Record<string, unknown>) => void Object.assign(store, o)),
      },
    },
  });
  fetchMock = vi.fn(async () => ({ ok: true, status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  bg._reset();
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("background", () => {
  it("agrupa y envía en lotes de máx. 500 ítems con el token", async () => {
    bg.handleMessage({ source: "fcsl", url: `${BASE}/club?sid=abc`, body: { itemData: Array.from({ length: 1200 }, (_, i) => item(i + 1)) } });
    await bg.flush();
    expect(fetchMock).toHaveBeenCalledTimes(3);
    const sizes = fetchMock.mock.calls.map(([, init]) => JSON.parse(init.body).items.length);
    expect(sizes).toEqual([500, 500, 200]);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8787/import/club");
    expect(init.method).toBe("POST");
    expect(init.headers["X-FCSL-Token"]).toBe("tok");
    expect(JSON.parse(init.body).location).toBe("club");
    expect((store.stats as { totalItems: number }).totalItems).toBe(1200);
    expect((store.stats as { lastSentAt: string }).lastSentAt).toBeTruthy();
  });

  it("solo manda los duplicados de cada lote", async () => {
    bg.handleMessage({
      source: "fcsl",
      url: `${BASE}/club`,
      body: { itemData: Array.from({ length: 501 }, (_, i) => item(i + 1)), duplicateItemIdList: [{ itemId: 1 }, { itemId: 501 }] },
    });
    await bg.flush();
    const bodies = fetchMock.mock.calls.map(([, i]) => JSON.parse(i.body));
    expect(bodies[0].duplicate_item_ids).toEqual([1]);
    expect(bodies[1].duplicate_item_ids).toEqual([501]);
  });

  it("agrupa observaciones de mercado en lotes de 500", async () => {
    const auctionInfo = Array.from({ length: 501 }, (_, i) => ({ buyNowPrice: 100 + i, itemData: { resourceId: 7 } }));
    bg.handleMessage({ source: "fcsl", url: `${BASE}/transfermarket`, body: { auctionInfo } });
    await bg.flush();
    expect(fetchMock.mock.calls.map(([u]) => u)).toEqual(["http://localhost:8787/import/market", "http://localhost:8787/import/market"]);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).observations).toHaveLength(500);
  });

  it("envía tras 2 s de agrupación", async () => {
    vi.useFakeTimers();
    bg.handleMessage({ source: "fcsl", url: `${BASE}/watchlist`, body: { auctionInfo: [{ itemData: item(9) }] } });
    await vi.advanceTimersByTimeAsync(1900);
    expect(fetchMock).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("cuenta errores y guarda lastError", async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 401 });
    bg.handleMessage({ source: "fcsl", url: `${BASE}/club`, body: { itemData: [item(1)] } });
    await bg.flush();
    const s = store.stats as { errors: number; lastError: string };
    expect(s.errors).toBe(1);
    expect(s.lastError).toContain("401");
    fetchMock.mockRejectedValue(new Error("caído"));
    bg.handleMessage({ source: "fcsl", url: `${BASE}/club`, body: { itemData: [item(1)] } });
    await bg.flush();
    expect((store.stats as { errors: number }).errors).toBe(2);
    expect((store.stats as { lastError: string }).lastError).toContain("caído");
  });

  it("sin token no envía y registra el error", async () => {
    store.config = { apiUrl: "http://localhost:8787", token: "", rawMode: false };
    bg.handleMessage({ source: "fcsl", url: `${BASE}/club`, body: { itemData: [item(1)] } });
    await bg.flush();
    expect(fetchMock).not.toHaveBeenCalled();
    expect((store.stats as { lastError: string }).lastError).toMatch(/token/i);
  });

  it("modo muestras: /import/raw con la query reemplazada, solo /ut/game/", async () => {
    store.config = { apiUrl: "http://localhost:8787", token: "tok", rawMode: true };
    bg.handleMessage({ source: "fcsl", url: `${BASE}/user/credits?sid=SECRETO`, body: { credits: 5 } });
    bg.handleMessage({ source: "fcsl", url: "https://www.ea.com/otra?x=1", body: { a: 1 } });
    await bg.flush();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8787/import/raw");
    expect(JSON.parse(init.body)).toEqual({ url: `${BASE}/user/credits?…`, body: { credits: 5 } });
    expect(init.body).not.toContain("SECRETO");
  });

  it("sin modo muestras no envía raw y descarta mensajes ajenos", async () => {
    bg.handleMessage({ source: "fcsl", url: `${BASE}/user/credits`, body: { credits: 5 } });
    bg.handleMessage({ source: "otro", url: `${BASE}/club`, body: { itemData: [item(1)] } } as never);
    bg.handleMessage(null as never);
    await bg.flush();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
