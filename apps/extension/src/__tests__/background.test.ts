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

describe("estado de la importación automática", () => {
  it("guarda el resumen y, si falló, el error", async () => {
    await bg.handleStatus({ source: "fcsl-status", kind: "auto-import", at: "2026-11-17T15:00:00Z", ok: true, clubPages: 2, storage: true });
    expect((store.stats as { lastAutoImport: string }).lastAutoImport).toBe("2026-11-17T15:00:00Z · OK · 2 páginas de club + Almacén SBC");
    await bg.handleStatus({ source: "fcsl-status", kind: "auto-import", at: "2026-11-17T16:00:00Z", ok: false, clubPages: 1, storage: false, error: "EA respondió 429 al leer el club" });
    const s = store.stats as { lastAutoImport: string; lastError: string; errors: number };
    expect(s.lastAutoImport).toBe("2026-11-17T16:00:00Z · ERROR · EA respondió 429 al leer el club");
    expect(s.lastError).toBe("EA respondió 429 al leer el club");
    expect(s.errors).toBe(1);
  });
  it("ignora mensajes raros", async () => {
    await bg.handleStatus({ source: "otro" } as never);
    expect(store.stats).toBeUndefined();
  });
  it("con el club completo envía primero sus páginas y luego keep_item_ids", async () => {
    bg.handleMessage({ source: "fcsl", url: `${BASE}/club`, body: { itemData: [item(1), item(2)] } });
    await bg.handleStatus({
      source: "fcsl-status", kind: "auto-import", at: "x", ok: true, clubPages: 1, storage: true, clubItemIds: [1, 2],
    });
    const bodies = fetchMock.mock.calls.map(([, i]) => JSON.parse(i.body));
    expect(bodies).toHaveLength(2);
    expect(bodies[0].items.map((i: { id: number }) => i.id)).toEqual([1, 2]);
    expect(bodies[1]).toEqual({ location: "club", items: [], duplicate_item_ids: [], keep_item_ids: [1, 2] });
  });
  it("sin ids del club (incompleto o fallido) no limpia nada", async () => {
    await bg.handleStatus({ source: "fcsl-status", kind: "auto-import", at: "x", ok: true, clubPages: 50, storage: true });
    await bg.handleStatus({
      source: "fcsl-status", kind: "auto-import", at: "x", ok: false, clubPages: 1, storage: false, error: "e", clubItemIds: [1],
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("listas completas", () => {
  it("lista de transferencias: envía sus ítems y luego keep con los ids vistos", async () => {
    const auctionInfo = [
      { tradeState: "active", tradeOwner: true, itemData: item(5) },
      { tradeState: "closed", tradeOwner: true, itemData: item(6) }, // vendida
    ];
    bg.handleMessage({ source: "fcsl", url: `${BASE}/tradepile`, body: { auctionInfo } });
    await bg.flush();
    const bodies = fetchMock.mock.calls.map(([, i]) => JSON.parse(i.body));
    expect(bodies.map((b) => b.keep_item_ids)).toEqual([undefined, [5]]);
    expect(bodies[0].items.map((i: { id: number }) => i.id)).toEqual([5]);
  });
  it("almacén vacío: un único envío con keep vacío", async () => {
    bg.handleMessage({ source: "fcsl", url: `${BASE}/storagepile`, body: { itemData: [] } });
    await bg.flush();
    const bodies = fetchMock.mock.calls.map(([, i]) => JSON.parse(i.body));
    expect(bodies).toEqual([{ location: "storage", items: [], duplicate_item_ids: [], keep_item_ids: [] }]);
  });
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
    bg.handleMessage({ source: "fcsl", url: `${BASE}/club`, body: { itemData: [item(9)] } });
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


describe("evoluciones", () => {
  const hub = { categories: [], slots: [{ id: 5, slotName: "E", levels: [] }] };
  it("envía la versión reducida a /import/evolutions", async () => {
    bg.handleMessage({ source: "fcsl", url: `${BASE}/academy/hub/v2`, body: hub });
    await bg.flush();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8787/import/evolutions");
    expect(JSON.parse(init.body).slots.map((s: { id: number }) => s.id)).toEqual([5]);
    expect(init.headers["X-FCSL-Token"]).toBe("tok");
  });
  it("si llegan dos lecturas seguidas, solo manda la última", async () => {
    bg.handleMessage({ source: "fcsl", url: `${BASE}/academy/hub/v2`, body: hub });
    bg.handleMessage({ source: "fcsl", url: `${BASE}/academy/hub/v2`, body: { categories: [], slots: [{ id: 9 }] } });
    await bg.flush();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).slots.map((s: { id: number }) => s.id)).toEqual([9]);
  });
  it("una respuesta rara no envía nada", async () => {
    bg.handleMessage({ source: "fcsl", url: `${BASE}/academy/hub/v2`, body: { nada: true } });
    await bg.flush();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
