import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import DataStatus from "./DataStatus";

const URL_ = "http://localhost:8787";

function mockStatus(body: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => body }));
}

describe("DataStatus", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows Nunca when there are no syncs", async () => {
    mockStatus({ cards: 0, prices: {}, club_items: 0, last_sync: {} });
    render(<DataStatus apiUrl={URL_} />);
    expect(await screen.findAllByText("Nunca")).toHaveLength(4);
    const sync = screen.getByRole("heading", { name: "Última sincronización" }).nextElementSibling!;
    for (const label of ["Cartas (FUT.GG)", "Precios (EasySBC)", "Club (tu sesión)", "Mercado (tu sesión)"]) {
      expect(sync.textContent).toContain(`${label}: Nunca`);
    }
    expect(fetch).toHaveBeenCalledWith(`${URL_}/data/status`, expect.anything());
  });

  it("shows counts, friendly sources and sync errors", async () => {
    mockStatus({
      cards: 12345,
      prices: { "ea-session": 40, "easysbc:market": 7 },
      club_items: 812,
      // Tipos reales que escribe el backend: cards/prices (CLI) y club/market (/import/*).
      last_sync: {
        cards: { status: "ok", finished_at: "2026-11-17T09:00:00Z", items: 12345, error: null },
        prices: { status: "partial", finished_at: "2026-11-17T11:00:00Z", items: 7, error: "boom" },
        club: { status: "ok", finished_at: "2026-11-17T10:00:00Z", items: 812, error: null },
        market: { status: "ok", finished_at: "2026-11-17T12:00:00Z", items: 40, error: null },
      },
    });
    render(<DataStatus apiUrl={URL_} />);
    expect(await screen.findByText("12.345")).toBeInTheDocument();
    expect(screen.queryByText("Nunca")).not.toBeInTheDocument();
    expect(screen.queryByText(/^cards:/)).not.toBeInTheDocument();
    const sync = screen.getByRole("heading", { name: "Última sincronización" }).nextElementSibling!;
    expect(sync.textContent).toContain("Cartas (FUT.GG):");
    expect(sync.textContent).toContain("Precios (EasySBC):");
    expect(sync.textContent).toContain("(partial)");
    expect(sync.textContent).toContain("Club (tu sesión):");
    expect(sync.textContent).toContain("Mercado (tu sesión):");
    expect(sync.querySelectorAll("li")).toHaveLength(4);
    expect(screen.getByText("EasySBC mercado")).toBeInTheDocument();
    expect(screen.getByText("812", { selector: "dd" })).toBeInTheDocument();
    const err = screen.getByText(/boom/);
    expect(err).toHaveClass("text-red-600");
  });

  it("shows an error when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network")));
    render(<DataStatus apiUrl={URL_} />);
    expect(await screen.findByText("No se pudo cargar el estado de los datos")).toBeInTheDocument();
  });
});
