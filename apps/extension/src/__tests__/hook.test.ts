import { describe, expect, it, vi } from "vitest";
import { installHook, type HookTarget } from "../hook";

const BASE = "https://utas.mob.v5.prd.futc-ext.gcp.ea.com/ut/game/fc27";
const flushPromises = () => new Promise((r) => setTimeout(r, 0));

function setup(res: Response | Promise<Response>, raw = false) {
  const post = vi.fn();
  const original = vi.fn(async () => res);
  const target: HookTarget = { fetch: original as unknown as typeof fetch, postMessage: post };
  installHook(target, () => raw);
  return { post, original, target };
}

describe("installHook (fetch)", () => {
  it("devuelve la respuesta intacta y publica el cuerpo sin query", async () => {
    const res = new Response(JSON.stringify({ itemData: [1] }), { status: 200 });
    const { post, target } = setup(res);
    const out = await target.fetch!(`${BASE}/club?sid=SECRETO`, { headers: { "X-UT-SID": "SECRETO" } });
    expect(out).toBe(res);
    await flushPromises();
    expect(post).toHaveBeenCalledWith({ source: "fcsl", url: `${BASE}/club?…`, body: { itemData: [1] } }, "*");
    expect(JSON.stringify(post.mock.calls)).not.toContain("SECRETO");
    expect(await out.json()).toEqual({ itemData: [1] });
  });

  it("ignora URLs no listadas, salvo /ut/game/ en modo muestras", async () => {
    const mk = () => new Response("{}", { status: 200 });
    const a = setup(mk());
    await a.target.fetch!(`${BASE}/user/credits`);
    await flushPromises();
    expect(a.post).not.toHaveBeenCalled();
    const b = setup(mk(), true);
    await b.target.fetch!(`${BASE}/user/credits`);
    await flushPromises();
    expect(b.post).toHaveBeenCalledTimes(1);
    const c = setup(mk(), true);
    await c.target.fetch!("https://www.ea.com/otra");
    await flushPromises();
    expect(c.post).not.toHaveBeenCalled();
  });

  it("no lanza con cuerpo no JSON ni con respuestas no 200, y propaga el rechazo original", async () => {
    const a = setup(new Response("<html>", { status: 200 }));
    await a.target.fetch!(`${BASE}/club`);
    const b = setup(new Response("{}", { status: 500 }));
    await b.target.fetch!(`${BASE}/club`);
    await flushPromises();
    expect(a.post).not.toHaveBeenCalled();
    expect(b.post).not.toHaveBeenCalled();
    const c = setup(Promise.reject(new Error("red")));
    await expect(c.target.fetch!(`${BASE}/club`)).rejects.toThrow("red");
  });
});
