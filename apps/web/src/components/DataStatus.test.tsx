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
    expect(await screen.findAllByText("Nunca")).toHaveLength(3);
    expect(fetch).toHaveBeenCalledWith(`${URL_}/data/status`, expect.anything());
  });

  it("shows counts, friendly sources and sync errors", async () => {
    mockStatus({
      cards: 12345,
      prices: { "ea-session": 40, "easysbc:market": 7 },
      club_items: 812,
      last_sync: {
        club: { status: "ok", finished_at: "2026-11-17T10:00:00Z", items: 812, error: null },
        prices: { status: "error", finished_at: "2026-11-17T11:00:00Z", items: 0, error: "boom" },
      },
    });
    render(<DataStatus apiUrl={URL_} />);
    expect(await screen.findByText("12.345")).toBeInTheDocument();
    expect(screen.getByText("Mercado (tu sesión)")).toBeInTheDocument();
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
