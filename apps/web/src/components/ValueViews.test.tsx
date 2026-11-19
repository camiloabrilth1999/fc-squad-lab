import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ValueViews from "./ValueViews";

const URL_ = "http://localhost:8787";

const bargain = (id: number, name: string, meta: number, price: number, score: number) => ({
  resource_id: id,
  name,
  rating: 84,
  positions: ["ST"],
  rarity_name: "Rare",
  role: "adv_forward",
  meta,
  meta_source: "face" as const,
  tier: "A+",
  price,
  score,
});
const fodder = [
  { rating: 85, cheapest: 2300, cards: [{ resource_id: 1, name: "Barato Uno", positions: ["CB"], price: 2300 }] },
  { rating: 86, cheapest: 4600, cards: [{ resource_id: 2, name: "Barato Dos", positions: ["CM"], price: 4600 }] },
];
const json = (body: unknown) => ({ ok: true, status: 200, json: async () => body });

afterEach(() => vi.unstubAllGlobals());

describe("ValueViews", () => {
  it("muestra los chollos con meta, precio y valor", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(json({ items: [bargain(1, "Alfa", 90.2, 1500, 0.75)] })),
    );
    render(<ValueViews apiUrl={URL_} />);
    expect(await screen.findByText("Alfa")).toBeInTheDocument();
    expect(screen.getByText(/90\.2~/)).toBeInTheDocument();
    expect(screen.getByText("1.500")).toBeInTheDocument();
    expect(screen.getByText("+75")).toBeInTheDocument();
  });

  it("aplica los filtros al buscar chollos", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ items: [bargain(1, "Alfa", 90, 1500, 0.5)] }));
    vi.stubGlobal("fetch", fetchMock);
    render(<ValueViews apiUrl={URL_} />);
    await screen.findByText("Alfa");
    fireEvent.change(screen.getByLabelText("Posición"), { target: { value: "ST" } });
    fireEvent.change(screen.getByLabelText("Precio máximo"), { target: { value: "20000" } });
    fireEvent.click(screen.getByRole("button", { name: "Buscar chollos" }));
    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(1));
    const last = new URL(fetchMock.mock.calls.at(-1)![0]);
    expect(last.pathname).toBe("/value/bargains");
    expect(last.searchParams.get("position")).toBe("ST");
    expect(last.searchParams.get("max_price")).toBe("20000");
  });

  it("avisa cuando no hay chollos", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ items: [] })));
    render(<ValueViews apiUrl={URL_} />);
    expect(await screen.findByText("Ningún chollo con esos filtros.")).toBeInTheDocument();
  });

  it("la pestaña de fodder lista lo más barato por media", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (url: string) =>
        String(url).includes("/value/fodder") ? json(fodder) : json({ items: [] }),
      ),
    );
    render(<ValueViews apiUrl={URL_} />);
    fireEvent.click(screen.getByRole("tab", { name: "Fodder para SBC" }));
    expect(await screen.findByText("2.300", { selector: "td" })).toBeInTheDocument();
    expect(screen.getByText("4.600", { selector: "td" })).toBeInTheDocument();
    expect(screen.getByText(/Barato Uno \(2\.300\)/)).toBeInTheDocument();
  });

  it("muestra error si la API falla", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }),
    );
    render(<ValueViews apiUrl={URL_} />);
    expect(await screen.findByText("No se pudieron cargar los chollos.")).toBeInTheDocument();
  });
});
