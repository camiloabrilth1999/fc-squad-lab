import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import EvolutionsBrowser, { formatRemaining } from "./EvolutionsBrowser";

const URL_ = "http://localhost:8787";

const evo = (id: number, name: string, extra: Record<string, unknown> = {}) => ({
  id,
  name,
  description: `Descripción de ${name}`,
  status: "NOT_STARTED",
  category_id: 0,
  category: "Evoluciones",
  timed: false,
  ends_at: null,
  gk_only: false,
  outfield_only: true,
  multi_choice: false,
  total_rewards: 5,
  cost: [{ currency: "COINS", amount: 10000 }],
  top_rewards: [
    { stat: 11, name: "Valoración general", count: 3, max_value: 83 },
    { stat: 22, name: "Velocidad", count: 10, max_value: 86 },
  ],
  upgrades: [],
  levels: [
    { level: 0, state: "NOT_STARTED", objectives: [], awards: [] },
    {
      level: 1,
      state: "NOT_STARTED",
      objectives: [{ id: 7, name: "Juega 3 partidos", description: "*" }],
      awards: [{ stat: 22, name: "Velocidad", count: 10, max_value: 86 }],
    },
  ],
  requirements: ["GRL máximo: 80", "Posición: MCO O MC"],
  ...extra,
});
const cats = [
  { id: 0, name: "Evoluciones", total: 9, imported: 2 },
  { id: 30, name: "Campus", total: 4, imported: 0 },
];
const json = (body: unknown) => ({ ok: true, status: 200, json: async () => body });
const router = (list: unknown) =>
  vi.fn().mockImplementation(async (url: string) =>
    String(url).includes("/evolutions/categories") ? json(cats) : json(list),
  );

afterEach(() => vi.unstubAllGlobals());

describe("formatRemaining", () => {
  const now = Date.parse("2026-11-19T12:00:00Z");
  it("formatea minutos, horas y días", () => {
    expect(formatRemaining("2026-11-19T12:30:00Z", now)).toBe("30 min");
    expect(formatRemaining("2026-11-19T17:00:00Z", now)).toBe("5 h");
    expect(formatRemaining("2026-11-22T12:00:00Z", now)).toBe("3 días");
    expect(formatRemaining("2026-11-19T11:00:00Z", now)).toBe("caducada");
    expect(formatRemaining(null, now)).toBeNull();
  });
});

describe("EvolutionsBrowser", () => {
  it("lista evoluciones con mejoras por nombre, coste y las que faltan por ver", async () => {
    vi.stubGlobal("fetch", router({ items: [evo(1, "Bajo los focos")], total: 1 }));
    render(<EvolutionsBrowser apiUrl={URL_} />);
    expect(await screen.findByText("Bajo los focos")).toBeInTheDocument();
    expect(screen.getByText("Valoración general")).toBeInTheDocument();
    expect(screen.getByText("+3")).toBeInTheDocument();
    expect(screen.getByText("Coste: 10.000 monedas")).toBeInTheDocument();
    expect(screen.getByText("+3 más")).toBeInTheDocument(); // 5 premios, 2 mostrados
    expect(screen.getByText(/solo jugadores de campo/)).toBeInTheDocument();
  });

  it("muestra el coste en monedas y FC Points con el formato real de EA", async () => {
    const cost = [
      { funds: 10000, finalFunds: 0, name: "COINS" },
      { funds: 100, finalFunds: 0, name: "POINTS" },
    ];
    vi.stubGlobal("fetch", router({ items: [evo(1, "Bajo los focos", { cost })], total: 1 }));
    render(<EvolutionsBrowser apiUrl={URL_} />);
    expect(await screen.findByText("Coste: 10.000 monedas + 100 FC Points")).toBeInTheDocument();
  });

  it("muestra las categorías con lo importado y filtra al elegir una", async () => {
    const fetchMock = router({ items: [evo(1, "A")], total: 1 });
    vi.stubGlobal("fetch", fetchMock);
    render(<EvolutionsBrowser apiUrl={URL_} />);
    const campus = await screen.findByRole("button", { name: /Campus/ });
    expect(campus).toHaveTextContent("0/4");
    fireEvent.click(campus);
    await waitFor(() => {
      const last = new URL(fetchMock.mock.calls.at(-1)![0]);
      expect(last.pathname).toBe("/evolutions");
      expect(last.searchParams.get("category_id")).toBe("30");
    });
  });

  it("busca por texto", async () => {
    const fetchMock = router({ items: [evo(1, "A")], total: 1 });
    vi.stubGlobal("fetch", fetchMock);
    render(<EvolutionsBrowser apiUrl={URL_} />);
    await screen.findByText("A");
    fireEvent.change(screen.getByLabelText("Buscar evolución"), { target: { value: "focos" } });
    fireEvent.click(screen.getByRole("button", { name: "Buscar" }));
    await waitFor(() =>
      expect(new URL(fetchMock.mock.calls.at(-1)![0]).searchParams.get("q")).toBe("focos"),
    );
  });

  it("despliega los niveles con sus objetivos", async () => {
    vi.stubGlobal("fetch", router({ items: [evo(1, "Bajo los focos")], total: 1 }));
    render(<EvolutionsBrowser apiUrl={URL_} />);
    fireEvent.click(await screen.findByRole("button", { name: "Ver 1 niveles" }));
    expect(screen.getByText("Nivel 1")).toBeInTheDocument();
    expect(screen.getByText("Juega 3 partidos")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Ocultar niveles" }));
    expect(screen.queryByText("Nivel 1")).toBeNull();
  });

  it("explica cómo importar cuando no hay nada", async () => {
    vi.stubGlobal("fetch", router({ items: [], total: 0 }));
    render(<EvolutionsBrowser apiUrl={URL_} />);
    expect(await screen.findByText(/Aún no hay evoluciones aquí/)).toBeInTheDocument();
  });

  it("muestra error si la API falla", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }),
    );
    render(<EvolutionsBrowser apiUrl={URL_} />);
    expect(await screen.findByText("No se pudieron cargar las evoluciones.")).toBeInTheDocument();
  });
});


describe("EvolutionsBrowser: requisitos y mis cartas", () => {
  const candidates = {
    items: [
      {
        item_id: 1,
        resource_id: 1,
        name: "Paulina Bartz",
        rating: 68,
        positions: ["CM", "CDM"],
        eligible: true,
        unknown: [],
        meta_before: 64.0,
        meta_after: 74.2,
        meta_gain: 10.2,
      },
      {
        item_id: 2,
        resource_id: 2,
        name: "Sin cara",
        rating: 70,
        positions: ["CAM"],
        eligible: null,
        unknown: ["Ritmo máximo: 86"],
        meta_before: null,
        meta_after: null,
        meta_gain: null,
      },
    ],
    eligible_count: 1,
    unknown_count: 1,
    total_checked: 193,
  };
  const withCandidates = () =>
    vi.fn().mockImplementation(async (url: string) => {
      if (String(url).includes("/candidates")) return json(candidates);
      if (String(url).includes("/evolutions/categories")) return json(cats);
      return json({ items: [evo(2850, "Bajo los focos")], total: 1 });
    });

  it("muestra los requisitos de cada evolución", async () => {
    vi.stubGlobal("fetch", withCandidates());
    render(<EvolutionsBrowser apiUrl={URL_} />);
    expect(await screen.findByText(/GRL máximo: 80 · Posición: MCO O MC/)).toBeInTheDocument();
  });

  it("lista tus cartas aptas con el meta antes y después", async () => {
    const fetchMock = withCandidates();
    vi.stubGlobal("fetch", fetchMock);
    render(<EvolutionsBrowser apiUrl={URL_} />);
    fireEvent.click(await screen.findByRole("button", { name: "Mis cartas aptas" }));
    expect(await screen.findByText("Paulina Bartz")).toBeInTheDocument();
    expect(screen.getByText(/64\.0 → 74\.2/)).toBeInTheDocument();
    expect(screen.getByText("(+10.2)")).toBeInTheDocument();
    expect(screen.getByText(/1 aptas · 1 sin poder comprobar de 193 cartas/)).toBeInTheDocument();
    expect(screen.getByText("sin stats")).toBeInTheDocument();
    const call = fetchMock.mock.calls.find((c) => String(c[0]).includes("/candidates"))!;
    expect(String(call[0])).toContain("/evolutions/2850/candidates");
    fireEvent.click(screen.getByRole("button", { name: "Ocultar mis cartas" }));
    expect(screen.queryByText("Paulina Bartz")).toBeNull();
  });
});
