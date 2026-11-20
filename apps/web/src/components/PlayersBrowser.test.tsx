import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PlayersBrowser from "./PlayersBrowser";

const URL_ = "http://localhost:8787";

const player = (id: number, name: string, meta: number, source: "stats" | "face", price: number | null) => ({
  resource_id: id,
  name,
  rating: 88,
  positions: ["ST", "CF"],
  league_name: "Premier League",
  nation_name: "England",
  club_name: "Arsenal",
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
    fireEvent.click(await screen.findByRole("button", { name: "Tabla" }));
    expect(await screen.findByText("Alfa")).toBeInTheDocument();
    expect(screen.getByText("91.2")).toBeInTheDocument();
    expect(screen.getByText("88.4~")).toBeInTheDocument(); // estimado con la cara
    expect(screen.getByText("50.000")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument(); // sin precio
    expect(screen.getByText("2 jugadores")).toBeInTheDocument();
    expect(screen.getAllByText("Arsenal · Premier League · England")).toHaveLength(2);
  });

  it("muestra por defecto las cartas en cuadrícula con precio y meta", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        json({ ...page([player(1, "Alfa", 91.2, "stats", 50000)]), items: [{ ...player(1, "Alfa", 91.2, "stats", 50000), image_path: "2027/card/1.webp" }] }),
      ),
    );
    render(<PlayersBrowser apiUrl={URL_} />);
    const img = await screen.findByAltText("Carta de Alfa");
    expect(img.getAttribute("src")).toContain("2027/card/1.webp");
    expect(screen.getByText("50.000")).toBeInTheDocument();
    expect(screen.getByText("91.2")).toBeInTheDocument();
  });

  it("aplica los filtros al buscar y vuelve a la página 1", async () => {
    const fetchMock = vi.fn().mockImplementation(async (url: string) =>
      String(url).includes("/catalog?kind=league")
        ? json([{ id: 13, name: "Premier League" }])
        : json(page([player(1, "Alfa", 91, "stats", 1000)])),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<PlayersBrowser apiUrl={URL_} />);
    fireEvent.click(await screen.findByRole("button", { name: "Tabla" }));
    await screen.findByText("Alfa");
    await screen.findByRole("option", { name: "Premier League" });

    fireEvent.change(screen.getByLabelText("Nombre"), { target: { value: "alfa" } });
    fireEvent.change(screen.getByLabelText("Posición"), { target: { value: "ST" } });
    fireEvent.change(screen.getByLabelText("Precio máximo"), { target: { value: "20000" } });
    fireEvent.change(screen.getByLabelText("Liga"), { target: { value: "13" } });
    fireEvent.click(screen.getByRole("button", { name: "Buscar" }));

    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(1));
    const last = new URL(fetchMock.mock.calls.at(-1)![0]);
    expect(last.pathname).toBe("/players");
    expect(last.searchParams.get("q")).toBe("alfa");
    expect(last.searchParams.get("position")).toBe("ST");
    expect(last.searchParams.get("max_price")).toBe("20000");
    expect(last.searchParams.get("page")).toBe("1");
    expect(last.searchParams.get("league_id")).toBe("13");
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


describe("PlayersBrowser: detalle de carta", () => {
  it("abre el detalle al pulsar el nombre y lo cierra al volver a pulsar", async () => {
    const detail = {
      resource_id: 1,
      name: "Alfa",
      height: 183,
      accelerate_type: "EXPLOSIVE",
      skill_moves: 5,
      weak_foot: 4,
      play_style_names: ["Technical"],
      play_style_plus_names: ["Quick Step"],
      league_name: "Premier League",
      nation_name: "England",
      club_name: "Arsenal",
      face_stats: { pace: 92, shooting: 88, passing: 70, dribbling: 90, defending: 40, physicality: 75 },
      stats: { finishing: 94, acceleration: 93 },
      roles: [{ role: "adv_forward", position: "ST", meta: 91.2, source: "stats" }],
      price: 50000,
    };
    const fetchMock = vi.fn().mockImplementation(async (url: string) =>
      String(url).includes("/players/1")
        ? json(detail)
        : json(page([player(1, "Alfa", 91.2, "stats", 50000)])),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<PlayersBrowser apiUrl={URL_} />);
    fireEvent.click(await screen.findByRole("button", { name: "Tabla" }));
    const name = await screen.findByRole("button", { name: "Alfa" });

    fireEvent.click(name);
    expect(await screen.findByText("Meta por rol")).toBeInTheDocument();
    expect(screen.getByText("Delantero")).toBeInTheDocument();
    expect(screen.getByText("Quick Step+")).toBeInTheDocument();
    expect(screen.getByText("Technical")).toBeInTheDocument();
    expect(screen.getByText("finishing")).toBeInTheDocument();
    expect(screen.getByText(/183 cm/)).toBeInTheDocument();

    fireEvent.click(name);
    await waitFor(() => expect(screen.queryByText("Meta por rol")).toBeNull());
  });
});
