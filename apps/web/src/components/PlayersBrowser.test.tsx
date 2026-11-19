import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PlayersBrowser from "./PlayersBrowser";

const URL_ = "http://localhost:8787";

const player = (id: number, name: string, meta: number, source: "stats" | "face", price: number | null) => ({
  resource_id: id,
  name,
  rating: 88,
  positions: ["ST", "CF"],
  rarity_name: "Rare",
  meta,
  role: "adv_forward",
  meta_source: source,
  tier: "S",
  price,
});

const page = (items: ReturnType<typeof player>[], total = items.length, pageNo = 1) => ({
  items,
  total,
  page: pageNo,
  page_size: 50,
});
const json = (body: unknown) => ({ ok: true, status: 200, json: async () => body });

afterEach(() => vi.unstubAllGlobals());

describe("PlayersBrowser", () => {
  it("lista jugadores con meta, tier y precio, marcando el meta estimado", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        json(page([player(1, "Alfa", 91.2, "stats", 50000), player(2, "Beta", 88.4, "face", null)])),
      ),
    );
    render(<PlayersBrowser apiUrl={URL_} />);
    expect(await screen.findByText("Alfa")).toBeInTheDocument();
    expect(screen.getByText("91.2")).toBeInTheDocument();
    expect(screen.getByText("88.4~")).toBeInTheDocument(); // estimado con la cara
    expect(screen.getByText("50.000")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument(); // sin precio
    expect(screen.getByText("2 jugadores")).toBeInTheDocument();
  });

  it("aplica los filtros al buscar y vuelve a la página 1", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(page([player(1, "Alfa", 91, "stats", 1000)])));
    vi.stubGlobal("fetch", fetchMock);
    render(<PlayersBrowser apiUrl={URL_} />);
    await screen.findByText("Alfa");

    fireEvent.change(screen.getByLabelText("Nombre"), { target: { value: "alfa" } });
    fireEvent.change(screen.getByLabelText("Posición"), { target: { value: "ST" } });
    fireEvent.change(screen.getByLabelText("Precio máximo"), { target: { value: "20000" } });
    fireEvent.click(screen.getByRole("button", { name: "Buscar" }));

    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(1));
    const last = new URL(fetchMock.mock.calls.at(-1)![0]);
    expect(last.pathname).toBe("/players");
    expect(last.searchParams.get("q")).toBe("alfa");
    expect(last.searchParams.get("position")).toBe("ST");
    expect(last.searchParams.get("max_price")).toBe("20000");
    expect(last.searchParams.get("page")).toBe("1");
  });

  it("pagina con Siguiente y Anterior", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(json(page([player(1, "Alfa", 91, "stats", 1000)], 120)));
    vi.stubGlobal("fetch", fetchMock);
    render(<PlayersBrowser apiUrl={URL_} />);
    await screen.findByText("Alfa");
    expect(screen.getByText("Página 1 de 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    await waitFor(() =>
      expect(new URL(fetchMock.mock.calls.at(-1)![0]).searchParams.get("page")).toBe("2"),
    );
  });

  it("muestra error si la API falla", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }),
    );
    render(<PlayersBrowser apiUrl={URL_} />);
    expect(await screen.findByText("No se pudo cargar la lista de jugadores.")).toBeInTheDocument();
  });
});
