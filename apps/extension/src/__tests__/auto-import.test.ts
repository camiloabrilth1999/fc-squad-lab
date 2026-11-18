import { describe, expect, it, vi } from "vitest";
import { findCriteriaClass, runAutoImport, type FutServices, type ServiceResult } from "../auto-import";

class FakeCriteria {
  type = "";
  count = 0;
  offset = 0;
  hasValidDefId(): boolean {
    return false;
  }
  resetDefId(): void {}
}

/** Devuelve un "observable" al estilo de la web app de EA que responde con `result`. */
const observable = (result: ServiceResult) => ({
  observe: (owner: object, cb: (obs: { unobserve(o: object): void }, res: ServiceResult) => void) => {
    const obs = { unobserve: vi.fn() };
    queueMicrotask(() => cb(obs, result));
  },
});

function fakeServices(clubPages: ServiceResult[], storage: ServiceResult = { success: true }) {
  const club = vi.fn((c: unknown) =>
    observable(clubPages[Math.floor((c as FakeCriteria).offset / 90)] ?? { success: false, status: 500 }),
  );
  const store = vi.fn(() => observable(storage));
  const services: FutServices = { Club: { search: club }, Item: { searchStorageItems: store } };
  return { services, club, store };
}

const noSleep = () => Promise.resolve();

describe("findCriteriaClass", () => {
  it("encuentra la clase de criterio de búsqueda por sus métodos", () => {
    const win = { foo: 1, Bar: class {}, Crit: FakeCriteria } as unknown as Window;
    expect(findCriteriaClass(win)).toBe(FakeCriteria);
  });
  it("null si no existe", () => {
    expect(findCriteriaClass({ a: class {} } as unknown as Window)).toBeNull();
  });
});

describe("runAutoImport", () => {
  it("pagina el club de 90 en 90 hasta retrievedAll y luego lee el Almacén SBC", async () => {
    const { services, club, store } = fakeServices([
      { success: true, response: { retrievedAll: false } },
      { success: true, response: { retrievedAll: false } },
      { success: true, response: { retrievedAll: true } },
    ]);
    const sleep = vi.fn((_ms: number) => Promise.resolve());
    const r = await runAutoImport({ services, Criteria: FakeCriteria, sleep });
    expect(r).toEqual({ ok: true, clubPages: 3, storage: true });
    const crits = club.mock.calls.map(([c]) => c as FakeCriteria);
    expect(crits.map((c) => c.offset)).toEqual([0, 90, 180]);
    expect(crits.every((c) => c.type === "player" && c.count === 90)).toBe(true);
    expect(store).toHaveBeenCalledTimes(1);
    // pausa entre cada petición (≥ 1 s por defecto)
    expect(sleep).toHaveBeenCalledTimes(4); // 3 páginas + almacén
    expect(sleep.mock.calls.every(([ms]) => ms >= 1000)).toBe(true);
  });

  it("para ante un error de EA y no sigue pidiendo", async () => {
    const { services, club, store } = fakeServices([{ success: true, response: {} }, { success: false, status: 429 }]);
    const r = await runAutoImport({ services, Criteria: FakeCriteria, sleep: noSleep });
    expect(r).toEqual({ ok: false, clubPages: 1, storage: false, error: "EA respondió 429 al leer el club" });
    expect(club).toHaveBeenCalledTimes(2);
    expect(store).not.toHaveBeenCalled();
  });

  it("tiene un tope de páginas", async () => {
    const { services, club } = fakeServices(Array.from({ length: 100 }, () => ({ success: true, response: {} })));
    const r = await runAutoImport({ services, Criteria: FakeCriteria, sleep: noSleep, maxPages: 5 });
    expect(club).toHaveBeenCalledTimes(5);
    expect(r.ok).toBe(true);
    expect(r.clubPages).toBe(5);
  });

  it("devuelve los ids del club solo si lo leyó entero", async () => {
    const page = (ids: number[], retrievedAll: boolean): ServiceResult => ({
      success: true,
      response: { retrievedAll, items: ids.map((id) => ({ id })) },
    });
    const full = fakeServices([page([1, 2], false), page([3, 2], true)]);
    const r = await runAutoImport({ services: full.services, Criteria: FakeCriteria, sleep: noSleep });
    expect(r.clubItemIds).toEqual([1, 2, 3]);
    const capped = fakeServices([page([1], false), page([2], false), page([3], true)]);
    const r2 = await runAutoImport({ services: capped.services, Criteria: FakeCriteria, sleep: noSleep, maxPages: 2 });
    expect(r2.ok).toBe(true);
    expect(r2.clubItemIds).toBeUndefined();
  });

  it("falla limpio si la web app no expone los servicios", async () => {
    const r = await runAutoImport({ services: {}, Criteria: FakeCriteria, sleep: noSleep });
    expect(r).toEqual({ ok: false, clubPages: 0, storage: false, error: "La web app de EA no expone services.Club.search" });
  });

  it("solo usa lecturas: nunca toca mercado ni otros servicios", async () => {
    const { services } = fakeServices([{ success: true, response: { retrievedAll: true } }]);
    const forbidden = vi.fn();
    const all = { ...services, TransferMarket: { search: forbidden, bid: forbidden }, Item: { ...services.Item, move: forbidden, list: forbidden } };
    await runAutoImport({ services: all, Criteria: FakeCriteria, sleep: noSleep });
    expect(forbidden).not.toHaveBeenCalled();
  });
});
