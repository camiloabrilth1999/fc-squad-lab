import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import SquadBuilder from "./SquadBuilder";

const URL_ = "http://localhost:8787";

const slot = (
  i: number,
  position: string,
  name: string,
  chemistry = 3,
  meta_source = "stats",
  in_position = true,
) => ({
  slot_index: i,
  position,
  card_id: `club:${i}`,
  resource_id: i,
  name,
  rating: 85,
  meta: 86.4,
  meta_source,
  chemistry,
  in_position,
});

const built = {
  status: "optimal",
  formation: "442",
  slots: [
    slot(0, "GK", "Portero Uno", 3, "rating"),
    slot(1, "CB", "Central Uno"),
    slot(2, "ST", "Delantero Uno", 0, "stats", false),
  ],
  total_meta: 258.8,
  team_rating: 85,
  team_chemistry: 6,
  solve_time_s: 0.01,
  message: null,
};

const json = (body: unknown) => ({ ok: true, status: 200, json: async () => body });

afterEach(() => vi.unstubAllGlobals());

describe("SquadBuilder", () => {
  it("pide el once con formación, química y modo elegidos y lo muestra", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(built));
    vi.stubGlobal("fetch", fetchMock);
    render(<SquadBuilder apiUrl={URL_} />);

    fireEvent.change(screen.getByLabelText("Formación"), { target: { value: "433" } });
    fireEvent.change(screen.getByLabelText("Química mínima"), { target: { value: "20" } });
    fireEvent.change(screen.getByLabelText("Fuera de posición"), { target: { value: "any" } });
    fireEvent.click(screen.getByRole("button", { name: "Armar mi mejor once" }));

    expect(await screen.findByText("Óptimo")).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${URL_}/squad/build`);
    expect(JSON.parse(init.body)).toEqual({
      formation: "433",
      min_chemistry: 20,
      out_of_position: "any",
    });
    expect(screen.getByText("Portero Uno")).toBeInTheDocument();
    expect(screen.getByText("Delantero Uno")).toBeInTheDocument();
    expect(screen.getByText("85")).toBeInTheDocument(); // media del equipo
    expect(screen.getByText("6/33")).toBeInTheDocument();
    expect(screen.getByText(/meta 86\.4\*/)).toBeInTheDocument(); // portero sin stats
  });

  it("por defecto permite posiciones afines y marca al jugador fuera de posición", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(built));
    vi.stubGlobal("fetch", fetchMock);
    render(<SquadBuilder apiUrl={URL_} />);
    fireEvent.click(screen.getByRole("button", { name: "Armar mi mejor once" }));
    await screen.findByText("Óptimo");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).out_of_position).toBe("family");
    expect(screen.getAllByText("fuera de posición")).toHaveLength(1); // solo el delantero
  });

  it("avisa cuando no hay once posible", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          json({ ...built, status: "infeasible", slots: [], message: "Ninguna carta juega de ST" }),
        ),
    );
    render(<SquadBuilder apiUrl={URL_} />);
    fireEvent.click(screen.getByRole("button", { name: "Armar mi mejor once" }));
    expect(await screen.findByText("No hay once posible con tu club")).toBeInTheDocument();
    expect(screen.getByText("Ninguna carta juega de ST")).toBeInTheDocument();
  });

  it("muestra error si la API falla", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }),
    );
    render(<SquadBuilder apiUrl={URL_} />);
    fireEvent.click(screen.getByRole("button", { name: "Armar mi mejor once" }));
    await waitFor(() =>
      expect(screen.getByText("No se pudo armar la plantilla.")).toBeInTheDocument(),
    );
  });
});

describe("SquadBuilder con mercado", () => {
  it("envía pool y presupuesto y muestra lo que hay que comprar", async () => {
    const market = {
      ...built,
      slots: [{ ...slot(1, "CB", "Fichaje Caro"), source: "market", price: 5000 }],
      spent: 5000,
      pending_stats: 3,
    };
    const fetchMock = vi.fn().mockResolvedValue(json(market));
    vi.stubGlobal("fetch", fetchMock);
    render(<SquadBuilder apiUrl={URL_} />);

    fireEvent.change(screen.getByLabelText("Cartas"), { target: { value: "both" } });
    fireEvent.change(screen.getByLabelText("Presupuesto (monedas)"), { target: { value: "50000" } });
    fireEvent.click(screen.getByRole("button", { name: "Armar mi mejor once" }));

    expect(await screen.findByText("Fichaje Caro")).toBeInTheDocument();
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body).toMatchObject({ pool: "both", budget: 50000 });
    expect(screen.getByText(/5\.000 monedas/)).toBeInTheDocument();
    expect(screen.getByText(/comprar 5\.000/)).toBeInTheDocument();
    expect(screen.getByText(/3 candidatos del mercado aún no tienen stats/)).toBeInTheDocument();
  });

  it("con solo mi club no manda presupuesto", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(built));
    vi.stubGlobal("fetch", fetchMock);
    render(<SquadBuilder apiUrl={URL_} />);
    expect(screen.queryByLabelText("Presupuesto (monedas)")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Armar mi mejor once" }));
    await screen.findByText("Óptimo");
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.pool).toBeUndefined();
    expect(body.budget).toBeUndefined();
  });
});
